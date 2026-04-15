from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateArcadeRequest(BaseModel):
    nom: str
    description: Optional[str] = ""
    arcade_image: Optional[str] = None
    localisation: str
    latitude: float = 0.0
    longitude: float = 0.0


class CreateGameRequest(BaseModel):
    nom: str
    description: str
    game_image: Optional[str] = None
    min_players: int = 1
    max_players: int = 2
    ticket_cost: int = 1


class CreatePromoCodeRequest(BaseModel):
    code: str
    tickets_reward: int
    is_single_use_global: bool = False
    is_single_use_per_user: bool = True
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True


class UpdatePromoCodeRequest(BaseModel):
    tickets_reward: Optional[int] = None
    is_single_use_global: Optional[bool] = None
    is_single_use_per_user: Optional[bool] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class UpdateUserTicketsRequest(BaseModel):
    user_id: int
    tickets_to_add: int


class ArcadeGameAssignmentRequest(BaseModel):
    arcade_id: int
    game_id: int
    slot_number: int