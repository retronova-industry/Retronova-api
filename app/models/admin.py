import enum
from sqlalchemy import Column, String, Enum
from sqlalchemy.orm import relationship
from .base import BaseModel


class AdminRole(str, enum.Enum):
    super_admin = "super_admin"
    arcade_owner = "arcade_owner"


class Admin(BaseModel):
    __tablename__ = "admins"

    firebase_uid = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(Enum(AdminRole), nullable=False, default=AdminRole.arcade_owner)

    arcades = relationship("Arcade", back_populates="owner_admin", foreign_keys="Arcade.owner_admin_id")
