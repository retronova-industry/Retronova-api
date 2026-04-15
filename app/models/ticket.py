from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class TicketOffer(Base):
    __tablename__ = "ticket_offers"

    id = Column(Integer, primary_key=True, index=True)
    tickets_amount = Column(Integer, nullable=False)
    price_euros = Column(Float, nullable=False)
    name = Column(String, nullable=False)

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TicketPurchase(Base):
    __tablename__ = "ticket_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    offer_id = Column(Integer, ForeignKey("ticket_offers.id"), nullable=False)

    tickets_received = Column(Integer, nullable=False)
    amount_paid = Column(Float, nullable=False)

    # anciens / nouveaux champs Stripe
    stripe_payment_id = Column(String, nullable=True)
    stripe_checkout_session_id = Column(String, nullable=True)
    stripe_payment_intent_id = Column(String, nullable=True)

    # nouveau statut
    status = Column(String, nullable=False, default="pending")

    paid_at = Column(DateTime(timezone=True), nullable=True)

    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    offer = relationship("TicketOffer")