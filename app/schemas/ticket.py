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