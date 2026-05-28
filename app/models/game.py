from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel


class Game(BaseModel):
    __tablename__ = "games"

    nom = Column(String, nullable=False)
    description = Column(String)
    game_image = Column(String, nullable=True)
    min_players = Column(Integer, default=1, nullable=False)
    max_players = Column(Integer, default=2, nullable=False)
    ticket_cost = Column(Integer, default=1, nullable=False)

    # Relations
    arcade_games = relationship("ArcadeGame", back_populates="game")
    reservations = relationship("Reservation", back_populates="game")
    scores = relationship("Score", back_populates="game")