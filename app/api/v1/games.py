from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, List, Optional
from app.core.database import get_db
from app.models.game import Game
from app.schemas.game import GameResponse
from app.core.messages import GAME_NOT_FOUND

router = APIRouter()


@router.get("/", response_model=List[GameResponse])
async def get_games(
    db: Annotated[Session, Depends(get_db)]
):
    """Récupère la liste de tous les jeux disponibles."""

    games = db.query(Game).filter(
        Game.is_deleted == False
    ).all()

    return games


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
        game_id: int,
        db: Annotated[Session, Depends(get_db)]
):
    """Récupère les détails d'un jeu spécifique."""

    game = db.query(Game).filter(
        Game.id == game_id,
        Game.is_deleted == False
    ).first()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GAME_NOT_FOUND
        )

    return game