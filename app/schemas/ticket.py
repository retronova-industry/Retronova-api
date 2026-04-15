from pydantic import BaseModel
from typing import Optional

class TicketOfferResponse(BaseModel):
    id: int
    tickets_amount: int
    price_euros: float
    name: str

    class Config:
        from_attributes = True


class PurchaseTicketsRequest(BaseModel):
    offer_id: int


class CreateCheckoutSessionResponse(BaseModel):
    purchase_id: int
    checkout_session_id: str
    checkout_url: str
    status: str


class PurchaseStatusResponse(BaseModel):
    purchase_id: int
    status: str
    tickets_received: int
    amount_paid: float
    stripe_checkout_session_id: Optional[str] = None
    stripe_session_status: Optional[str] = None
    stripe_payment_status: Optional[str] = None
    is_paid: bool