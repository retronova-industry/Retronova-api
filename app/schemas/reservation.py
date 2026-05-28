from pydantic import BaseModel
from typing import Optional
from app.models.reservation import ReservationStatus


class CreateReservationRequest(BaseModel):
    arcade_id: int
    game_id: int
    player2_id: Optional[int] = None


class ReservationResponse(BaseModel):
    id: int
    unlock_code: str
    status: ReservationStatus
    arcade_name: str
    game_name: str
    player_pseudo: str
    player2_pseudo: Optional[str] = None
    tickets_used: int
    position_in_queue: Optional[int] = None

    class Config:
        from_attributes = True


class UpdateReservationStatusRequest(BaseModel):
    status: ReservationStatus