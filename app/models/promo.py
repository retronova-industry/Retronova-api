from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel
from datetime import datetime, timezone
from math import ceil


class PromoCode(BaseModel):
    __tablename__ = "promo_codes"

    code = Column(String, unique=True, nullable=False)
    tickets_reward = Column(Integer, nullable=False)
    is_single_use_global = Column(Boolean, default=False)
    is_single_use_per_user = Column(Boolean, default=True)
    usage_limit = Column(Integer, nullable=True)  # Limite globale optionnelle
    current_uses = Column(Integer, default=0)

    # Nouvelles colonnes pour la gestion des dates
    valid_from = Column(DateTime(timezone=True), nullable=True)  # Date de début de validité
    valid_until = Column(DateTime(timezone=True), nullable=True)  # Date d'expiration
    is_active = Column(Boolean, default=True, nullable=False)  # Activation manuelle
    arcade_id = Column(Integer, ForeignKey("arcades.id", ondelete="SET NULL"), nullable=True)

    # Relations
    promo_uses = relationship("PromoUse", back_populates="promo_code")
    arcade = relationship("Arcade", foreign_keys=[arcade_id])

    def is_valid_now(self) -> bool:
        """Vérifie si le code promo est valide à l'instant présent."""
        if not self.is_active or self.is_deleted:
            return False

        now = datetime.now(timezone.utc)

        valid_until = (
            self.valid_until.replace(tzinfo=timezone.utc)
            if self.valid_until and self.valid_until.tzinfo is None
            else self.valid_until
        )
        valid_from = (
            self.valid_from.replace(tzinfo=timezone.utc)
            if self.valid_from and self.valid_from.tzinfo is None
            else self.valid_from
        )

        if valid_from and now < valid_from:
            return False
        if valid_until and now > valid_until:
            return False

        return True

    def is_expired(self) -> bool:
        """Vérifie si le code promo a expiré."""
        if self.valid_until:
            # Si valid_until est naive, la rendre UTC
            if self.valid_until.tzinfo is None:
                valid_until_aware = self.valid_until.replace(tzinfo=timezone.utc)
            else:
                valid_until_aware = self.valid_until

            return datetime.now(timezone.utc) > valid_until_aware
        return False

    def days_until_expiry(self) -> int:
        """Retourne le nombre de jours avant expiration (ou -1 si pas d'expiration)."""
        if not self.valid_until:
            return -1

        now = datetime.now(timezone.utc)
        valid_until = self.valid_until

        # Forcer valid_until à être timezone-aware en UTC si ce n’est pas déjà le cas
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)

        if now >= valid_until:
            return 0

        delta = valid_until - now
        return ceil(delta.total_seconds() / 86400)


class PromoUse(BaseModel):
    __tablename__ = "promo_uses"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    tickets_received = Column(Integer, nullable=False)

    # Relations
    user = relationship("User", back_populates="promo_uses")
    promo_code = relationship("PromoCode", back_populates="promo_uses")