from pydantic import BaseModel
from typing import Optional


class CreateScoreRequest(BaseModel):
    player1_id: int
    player2_id: Optional[int] = None
    game_id: int
    arcade_id: int
    score_j1: int
    score_j2: Optional[int] = None


class ScoreResponse(BaseModel):
    id: int
    player1_pseudo: str
    player2_pseudo: Optional[str] = None
    game_name: str
    arcade_name: str
    score_j1: int
    score_j2: Optional[int] = None
    winner_pseudo: Optional[str] = None
    created_at: str
    is_single_player: bool

    class Config:
        from_attributes = True