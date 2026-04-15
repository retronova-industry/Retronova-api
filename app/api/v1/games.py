from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.game import Game
from pydantic import BaseModel

router = APIRouter()


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


@router.get("/", response_model=List[GameResponse])
async def get_games(
        db: Session = Depends(get_db)
):
    """Récupère la liste de tous les jeux disponibles."""

    games = db.query(Game).filter(
        Game.is_deleted == False
    ).all()

    return games


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
        game_id: int,
        db: Session = Depends(get_db)
):
    """Récupère les détails d'un jeu spécifique."""

    game = db.query(Game).filter(
        Game.id == game_id,
        Game.is_deleted == False
    ).first()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jeu non trouvé"
        )

    return game