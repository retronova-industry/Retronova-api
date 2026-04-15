from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel


class Arcade(BaseModel):
    __tablename__ = "arcades"

    nom = Column(String, nullable=False)
    description = Column(String)
    arcade_image = Column(String, nullable=True)
    api_key = Column(String, unique=True, nullable=False)
    localisation = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Relations
    arcade_games = relationship("ArcadeGame", back_populates="arcade")
    reservations = relationship("Reservation", back_populates="arcade")
    scores = relationship("Score", back_populates="arcade")


class ArcadeGame(BaseModel):
    """Table d'association entre Arcade et Game avec slot."""
    __tablename__ = "arcade_games"

    arcade_id = Column(Integer, ForeignKey("arcades.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    slot_number = Column(Integer, nullable=False)  # 1 ou 2

    # Relations
    arcade = relationship("Arcade", back_populates="arcade_games")
    game = relationship("Game", back_populates="arcade_games")