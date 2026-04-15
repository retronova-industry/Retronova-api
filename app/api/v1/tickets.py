import os
from datetime import datetime, timezone
from typing import Annotated, List

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.messages import TICKET_OFFER_NOT_FOUND
from app.models.ticket import TicketOffer, TicketPurchase
from app.models.user import User
from app.schemas.ticket import (
    CreateCheckoutSessionResponse,
    PurchaseStatusResponse,
    PurchaseTicketsRequest,
    TicketOfferResponse,
)

router = APIRouter()

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _mark_purchase_as_paid_from_session(
    db: Session,
    purchase: TicketPurchase,
    session_data,
) -> None:
    """
    Mark the purchase as paid and credit tickets exactly once.
    Used by webhook and by status polling fallback.
    """
    if purchase.status == "paid":
        return

    user = db.query(User).filter(
        User.id == purchase.user_id,
        User.is_deleted == False,  # noqa: E712
    ).first()

    if not user:
        return

    purchase.status = "paid"
    purchase.paid_at = datetime.now(timezone.utc)

    payment_intent = session_data.get("payment_intent")
    if payment_intent:
        purchase.stripe_payment_intent_id = payment_intent

    user.tickets_balance += purchase.tickets_received
    db.commit()


@router.get("/offers", response_model=List[TicketOfferResponse])
async def get_ticket_offers(
    db: Annotated[Session, Depends(get_db)],
):
    """Return available ticket offers."""
    offers = db.query(TicketOffer).filter(
        TicketOffer.is_deleted == False  # noqa: E712
    ).all()
    return offers


@router.post("/purchase", response_model=CreateCheckoutSessionResponse)
async def purchase_tickets(
    purchase_data: PurchaseTicketsRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create Stripe Checkout session for ticket purchase.
    Tickets are credited only after Stripe confirms payment.
    """
    offer = db.query(TicketOffer).filter(
        TicketOffer.id == purchase_data.offer_id,
        TicketOffer.is_deleted == False,  # noqa: E712
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TICKET_OFFER_NOT_FOUND
        )

    purchase = TicketPurchase(
        user_id=current_user.id,
        offer_id=offer.id,
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        status="pending",
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            success_url="retronova://checkout/success",
            cancel_url="retronova://checkout/cancel",
            metadata={
                "purchase_id": str(purchase.id),
                "user_id": str(current_user.id),
                "offer_id": str(offer.id),
            },
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "eur",
                        "unit_amount": int(round(offer.price_euros * 100)),
                        "product_data": {
                            "name": offer.name,
                            "description": f"{offer.tickets_amount} tickets Retronova",
                        },
                    },
                }
            ],
        )
    except stripe.error.StripeError as exc:
        db.delete(purchase)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erreur Stripe lors de la creation de la session: {str(exc)}",
        ) from exc

    purchase.stripe_checkout_session_id = checkout_session.id
    db.commit()

    return CreateCheckoutSessionResponse(
        purchase_id=purchase.id,
        checkout_session_id=checkout_session.id,
        checkout_url=checkout_session.url,
        status=purchase.status,
    )


@router.get("/purchase/{purchase_id}/status", response_model=PurchaseStatusResponse)
async def get_purchase_status(
    purchase_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return purchase status. Also sync with Stripe as a fallback."""
    purchase = db.query(TicketPurchase).filter(
        TicketPurchase.id == purchase_id,
        TicketPurchase.user_id == current_user.id,
        TicketPurchase.is_deleted == False,  # noqa: E712
    ).first()

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achat non trouve",
        )

    stripe_session_status = None
    stripe_payment_status = None

    if purchase.stripe_checkout_session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(
                purchase.stripe_checkout_session_id
            )
            stripe_session_status = checkout_session.status
            stripe_payment_status = checkout_session.payment_status

            # Fallback if webhook was missed: trust Stripe on status polling.
            if checkout_session.payment_status == "paid":
                _mark_purchase_as_paid_from_session(
                    db=db,
                    purchase=purchase,
                    session_data=checkout_session,
                )
            elif checkout_session.status == "expired" and purchase.status == "pending":
                purchase.status = "expired"
                db.commit()
        except stripe.error.StripeError:
            # Keep DB state if Stripe cannot be reached.
            pass

    return PurchaseStatusResponse(
        purchase_id=purchase.id,
        status=purchase.status,
        tickets_received=purchase.tickets_received,
        amount_paid=purchase.amount_paid,
        stripe_checkout_session_id=purchase.stripe_checkout_session_id,
        stripe_session_status=stripe_session_status,
        stripe_payment_status=stripe_payment_status,
        is_paid=(purchase.status == "paid"),
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Stripe webhook to confirm payment and credit tickets."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="STRIPE_WEBHOOK_SECRET manquante",
        )

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header stripe-signature manquant",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload webhook invalide",
        ) from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature webhook invalide",
        ) from exc

    event_type = event["type"]
    session_data = event["data"]["object"]

    if event_type in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    ):
        purchase = db.query(TicketPurchase).filter(
            TicketPurchase.stripe_checkout_session_id == session_data["id"],
            TicketPurchase.is_deleted == False,  # noqa: E712
        ).first()

        if purchase:
            _mark_purchase_as_paid_from_session(
                db=db,
                purchase=purchase,
                session_data=session_data,
            )

    elif event_type == "checkout.session.expired":
        purchase = db.query(TicketPurchase).filter(
            TicketPurchase.stripe_checkout_session_id == session_data["id"],
            TicketPurchase.is_deleted == False,  # noqa: E712
        ).first()

        if purchase and purchase.status == "pending":
            purchase.status = "expired"
            db.commit()

    return {"received": True}


@router.get("/balance")
async def get_ticket_balance(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return user ticket balance."""
    return {"balance": current_user.tickets_balance}


@router.get("/history")
async def get_purchase_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return ticket purchase history."""
    purchases = db.query(TicketPurchase).filter(
        TicketPurchase.user_id == current_user.id,
        TicketPurchase.is_deleted == False,  # noqa: E712
    ).order_by(
        TicketPurchase.created_at.desc(),
        TicketPurchase.id.desc(),
    ).all()

    return purchases
