from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import stripe

from app.core.config import settings
from app.models.ticket import TicketOffer, TicketPurchase
from app.models.user import User
from app.schemas.ticket import (
    CheckoutSessionResponse,
    PaymentConfigResponse,
    PurchaseResponse,
    PurchaseStatusResponse,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


def get_ticket_offers_service(db: Session) -> list[TicketOffer]:
    offers = db.query(TicketOffer).filter(
        TicketOffer.is_deleted == False
    ).all()
    return offers


def purchase_tickets_service(
    db: Session,
    current_user: User,
    offer_id: int
) -> CheckoutSessionResponse | PurchaseResponse:
    offer = db.query(TicketOffer).filter(
        TicketOffer.id == offer_id,
        TicketOffer.is_deleted == False
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre de tickets non trouv\u00e9e"
        )

    if not _has_stripe_secret_key():
        return _purchase_tickets_mock(db, current_user, offer)

    purchase = TicketPurchase(
        user_id=current_user.id,
        offer_id=offer.id,
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        payment_status="pending",
    )
    db.add(purchase)
    db.flush()

    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        client_reference_id=str(purchase.id),
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

    purchase.stripe_session_id = session.id
    db.commit()
    db.refresh(purchase)

    return CheckoutSessionResponse(
        transaction_id=purchase.id,
        stripe_session_id=session.id,
        checkout_url=session.url,
    )


def _purchase_tickets_mock(
    db: Session,
    current_user: User,
    offer: TicketOffer,
) -> PurchaseResponse:
    purchase = TicketPurchase(
        user_id=current_user.id,
        offer_id=offer.id,
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        stripe_payment_id=f"mock_payment_{current_user.id}_{offer.id}",
        payment_status="paid",
    )
    db.add(purchase)

    current_user.tickets_balance += offer.tickets_amount
    db.commit()

    return PurchaseResponse(
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        new_balance=current_user.tickets_balance,
    )


def get_payment_config_service() -> PaymentConfigResponse:
    return PaymentConfigResponse(
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY or "",
        currency="eur",
        checkout_mode="redirect",
    )


def _has_stripe_secret_key() -> bool:
    return bool(
        settings.STRIPE_SECRET_KEY
        and settings.STRIPE_SECRET_KEY.strip().startswith("sk_")
    )


def get_ticket_balance_service(current_user: User) -> dict:
    return {"balance": current_user.tickets_balance}


def get_purchase_status_service(
    db: Session,
    current_user: User,
    transaction_id: int
) -> PurchaseStatusResponse:
    purchase = _get_user_purchase(db, current_user, transaction_id)

    if purchase.payment_status == "pending" and purchase.stripe_session_id:
        _sync_purchase_from_stripe(db, purchase)
        db.refresh(current_user)

    return _build_purchase_status_response(purchase, current_user)


def get_purchase_history_service(db: Session, current_user: User) -> list[TicketPurchase]:
    purchases = db.query(TicketPurchase).filter(
        TicketPurchase.user_id == current_user.id,
        TicketPurchase.is_deleted == False
    ).order_by(TicketPurchase.created_at.desc()).all()

    return purchases


def handle_stripe_webhook_service(
    db: Session,
    payload: bytes,
    stripe_signature: str | None,
) -> dict:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook Stripe non configure"
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload Stripe invalide"
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signature Stripe invalide"
        )

    event_type = event["type"]
    session = event["data"]["object"]

    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        purchase = _find_purchase_from_session(db, session)
        if purchase:
            _mark_purchase_paid(db, purchase, _stripe_value(session, "payment_intent"))
    elif event_type in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        purchase = _find_purchase_from_session(db, session)
        if purchase and purchase.payment_status == "pending":
            purchase.payment_status = "failed"
            db.commit()

    return {"received": True}


def _get_user_purchase(
    db: Session,
    current_user: User,
    transaction_id: int
) -> TicketPurchase:
    purchase = db.query(TicketPurchase).filter(
        TicketPurchase.id == transaction_id,
        TicketPurchase.user_id == current_user.id,
        TicketPurchase.is_deleted == False
    ).first()

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction non trouvee"
        )

    return purchase


def _sync_purchase_from_stripe(db: Session, purchase: TicketPurchase) -> None:
    if not settings.STRIPE_SECRET_KEY:
        return

    session = stripe.checkout.Session.retrieve(purchase.stripe_session_id)

    if session.payment_status == "paid":
        _mark_purchase_paid(db, purchase, session.payment_intent)
    elif session.status in ("expired", "canceled"):
        purchase.payment_status = "failed"
        db.commit()


def _find_purchase_from_session(db: Session, session) -> TicketPurchase | None:
    metadata = _stripe_value(session, "metadata") or {}
    purchase_id = _stripe_value(metadata, "purchase_id")
    query = db.query(TicketPurchase).filter(TicketPurchase.is_deleted == False)

    if purchase_id:
        purchase = query.filter(TicketPurchase.id == int(purchase_id)).first()
        if purchase:
            return purchase

    session_id = _stripe_value(session, "id")
    if session_id:
        return query.filter(TicketPurchase.stripe_session_id == session_id).first()

    return None


def _stripe_value(source, key: str):
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    try:
        return source[key]
    except (KeyError, TypeError):
        return getattr(source, key, None)


def _mark_purchase_paid(
    db: Session,
    purchase: TicketPurchase,
    stripe_payment_id: str | None,
) -> None:
    if purchase.payment_status == "paid":
        return

    user = db.query(User).filter(User.id == purchase.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur de la transaction introuvable"
        )

    user.tickets_balance += purchase.tickets_received
    purchase.payment_status = "paid"
    if stripe_payment_id:
        purchase.stripe_payment_id = stripe_payment_id
    db.commit()


def _build_purchase_status_response(
    purchase: TicketPurchase,
    current_user: User,
) -> PurchaseStatusResponse:
    return PurchaseStatusResponse(
        transaction_id=purchase.id,
        status=purchase.payment_status,
        current_balance=current_user.tickets_balance,
        tickets_received=purchase.tickets_received,
        amount_paid=purchase.amount_paid,
    )
