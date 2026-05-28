from pydantic import BaseModel


class TicketOfferResponse(BaseModel):
    id: int
    tickets_amount: int
    price_euros: float
    name: str

    class Config:
        from_attributes = True


class PurchaseTicketsRequest(BaseModel):
    offer_id: int


class PurchaseResponse(BaseModel):
    tickets_received: int
    amount_paid: float
    new_balance: int


class PaymentConfigResponse(BaseModel):
    publishable_key: str
    currency: str = "eur"
    checkout_mode: str = "redirect"


class CheckoutSessionResponse(BaseModel):
    transaction_id: int
    stripe_session_id: str
    checkout_url: str


class PurchaseStatusResponse(BaseModel):
    transaction_id: int
    status: str
    current_balance: int
    tickets_received: int
    amount_paid: float
