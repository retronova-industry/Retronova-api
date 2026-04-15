from sqlalchemy import Column, Integer, ForeignKey, Float, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class TicketOffer(BaseModel):
    __tablename__ = "ticket_offers"

    tickets_amount = Column(Integer, nullable=False)
    price_euros = Column(Float, nullable=False)
    name = Column(String, nullable=False)


class TicketPurchase(BaseModel):
    __tablename__ = "ticket_purchases"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    offer_id = Column(Integer, ForeignKey("ticket_offers.id"), nullable=False)
    tickets_received = Column(Integer, nullable=False)
    amount_paid = Column(Float, nullable=False)
    stripe_payment_id = Column(String, nullable=True)  # Pour plus tard

    # Relations
    user = relationship("User", back_populates="ticket_purchases")
    offer = relationship("TicketOffer")
