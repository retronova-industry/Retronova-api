from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Annotated, List

from app.core.database import get_db
from app.schemas.game import GameResponse
from app.services.games_service import GameService

router = APIRouter()


@router.get("/", response_model=List[GameResponse])
async def get_games(
    db: Annotated[Session, Depends(get_db)]
):
    service = GameService(db)
    return service.get_games()


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: int,
    db: Annotated[Session, Depends(get_db)]
):
    service = GameService(db)
    return service.get_game(game_id)