from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ticket import TicketOffer, TicketPurchase
from app.models.user import User
from app.schemas.ticket import PurchaseResponse


def get_ticket_offers_service(db: Session) -> list[TicketOffer]:
    offers = db.query(TicketOffer).filter(
        TicketOffer.is_deleted == False
    ).all()
    return offers


def purchase_tickets_service(
    db: Session,
    current_user: User,
    offer_id: int
) -> PurchaseResponse:
    offer = db.query(TicketOffer).filter(
        TicketOffer.id == offer_id,
        TicketOffer.is_deleted == False
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre de tickets non trouvée"
        )

    purchase = TicketPurchase(
        user_id=current_user.id,
        offer_id=offer.id,
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        stripe_payment_id=f"mock_payment_{current_user.id}_{offer.id}"
    )
    db.add(purchase)

    current_user.tickets_balance += offer.tickets_amount

    db.commit()

    return PurchaseResponse(
        tickets_received=offer.tickets_amount,
        amount_paid=offer.price_euros,
        new_balance=current_user.tickets_balance
    )


def get_ticket_balance_service(current_user: User) -> dict:
    return {"balance": current_user.tickets_balance}


def get_purchase_history_service(db: Session, current_user: User) -> list[TicketPurchase]:
    purchases = db.query(TicketPurchase).filter(
        TicketPurchase.user_id == current_user.id,
        TicketPurchase.is_deleted == False
    ).order_by(TicketPurchase.created_at.desc()).all()

    return purchases