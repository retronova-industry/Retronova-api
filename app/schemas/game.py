from pydantic import BaseModel
from typing import Optional


class GameResponse(BaseModel):
    id: int
    nom: str
    description: str
    game_image: Optional[str] = None
    min_players: int
    max_players: int
    ticket_cost: int

    class Config:
        from_attributes = True