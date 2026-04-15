from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated
from app.core.database import get_db
from app.models.user import User
from app.models.ticket import TicketOffer, TicketPurchase
from app.api.deps import get_current_user

from app.schemas.ticket import CreateCheckoutSessionResponse, PurchaseResponse, PurchaseTicketsRequest, TicketOfferResponse

router = APIRouter()

@router.get("/offers", response_model=List[TicketOfferResponse])
async def get_ticket_offers(
        db: Annotated[Session, Depends(get_db)]
):
    """Récupère les offres de tickets disponibles."""

    offers = db.query(TicketOffer).filter(
        TicketOffer.is_deleted == False
    ).all()

    return offers


@router.post("/purchase", response_model=CreateCheckoutSessionResponse)
async def purchase_tickets(
        purchase_data: PurchaseTicketsRequest,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Simule l'achat de tickets (mock Stripe)."""

    # Récupérer l'offre
    offer = db.query(TicketOffer).filter(
        TicketOffer.id == purchase_data.offer_id,
        TicketOffer.is_deleted == False
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre de tickets non trouvée"
        )

    # Simuler le paiement Stripe (toujours réussi pour le mock)
    # Dans la vraie version, on intégrerait Stripe ici

    # Enregistrer l'achat
    purchase = TicketPurchase(
        user_id=current_user.id,
        offer_id=offer.id,
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        stripe_payment_id=f"mock_payment_{current_user.id}_{offer.id}"
    )
    db.add(purchase)

    # Créditer les tickets à l'utilisateur
    current_user.tickets_balance += offer.tickets_amount

    db.commit()

    return PurchaseResponse(
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        new_balance=current_user.tickets_balance
    )


@router.get("/balance")
async def get_ticket_balance(
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère le solde de tickets de l'utilisateur."""

    return {"balance": current_user.tickets_balance}


@router.get("/history")
async def get_purchase_history(
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère l'historique d'achats de tickets."""

    purchases = db.query(TicketPurchase).filter(
        TicketPurchase.user_id == current_user.id,
        TicketPurchase.is_deleted == False
    ).order_by(TicketPurchase.created_at.desc()).all()

    return purchases