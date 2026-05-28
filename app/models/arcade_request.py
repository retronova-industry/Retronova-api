import enum
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel


class ArcadeRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ArcadeCreationRequest(BaseModel):
    __tablename__ = "arcade_creation_requests"

    requested_by_admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)
    nom = Column(String, nullable=False)
    description = Column(String, nullable=True)
    localisation = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(Enum(ArcadeRequestStatus), nullable=False, default=ArcadeRequestStatus.pending, index=True)
    rejection_reason = Column(String, nullable=True)
    created_arcade_id = Column(Integer, ForeignKey("arcades.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)

    requester = relationship("Admin", foreign_keys=[requested_by_admin_id])
    reviewer = relationship("Admin", foreign_keys=[reviewed_by_admin_id])
    created_arcade = relationship("Arcade", foreign_keys=[created_arcade_id])
