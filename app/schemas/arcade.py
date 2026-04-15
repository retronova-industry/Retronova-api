from pydantic import BaseModel
from typing import List, Optional


class GameOnArcadeResponse(BaseModel):
    id: int
    nom: str
    description: str
    min_players: int
    max_players: int
    ticket_cost: int
    slot_number: int

    class Config:
        from_attributes = True


class ArcadeResponse(BaseModel):
    id: int
    nom: str
    description: str
    localisation: str
    latitude: float
    longitude: float
    games: List[GameOnArcadeResponse]

    class Config:
        from_attributes = True


class QueueItemResponse(BaseModel):
    id: int
    player_id: int
    player_pseudo: str
    player2_id: Optional[int] = None
    player2_pseudo: Optional[str] = None
    game_id: int
    game_name: str
    unlock_code: str
    position: int

    class Config:
        from_attributes = True