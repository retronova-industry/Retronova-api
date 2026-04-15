from typing import List, Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ticket import (
    PurchaseResponse,
    PurchaseTicketsRequest,
    TicketOfferResponse,
)
from app.services.ticket_service import (
    get_purchase_history_service,
    get_ticket_balance_service,
    get_ticket_offers_service,
    purchase_tickets_service,
)

router = APIRouter()


@router.get("/offers", response_model=List[TicketOfferResponse])
async def get_ticket_offers(
    db: Annotated[Session, Depends(get_db)]
):
    return get_ticket_offers_service(db)


@router.post("/purchase", response_model=PurchaseResponse)
async def purchase_tickets(
    purchase_data: PurchaseTicketsRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return purchase_tickets_service(db, current_user, purchase_data.offer_id)


@router.get("/balance")
async def get_ticket_balance(
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_ticket_balance_service(current_user)


@router.get("/history")
async def get_purchase_history(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    return get_purchase_history_service(db, current_user)