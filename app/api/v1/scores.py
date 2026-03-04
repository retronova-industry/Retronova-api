from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Annotated
from app.core.database import get_db
from app.models.user import User
from app.models.score import Score
from app.models.game import Game
from app.models.arcade import Arcade
from app.models.friend import Friendship, FriendshipStatus
from app.services.score_service import ScoreService

from app.api.deps import get_current_user, verify_arcade_key
from pydantic import BaseModel
from sqlalchemy.orm import aliased

router = APIRouter()


class CreateScoreRequest(BaseModel):
    player1_id: int
    player2_id: Optional[int] = None  # Maintenant optionnel
    game_id: int
    arcade_id: int
    score_j1: int
    score_j2: Optional[int] = None  # Optionnel pour jeu solo


class ScoreResponse(BaseModel):
    id: int
    player1_pseudo: str
    player2_pseudo: Optional[str] = None  # Peut être None
    game_name: str
    arcade_name: str
    score_j1: int
    score_j2: Optional[int] = None
    winner_pseudo: Optional[str] = None  # Peut être None pour jeu solo
    created_at: str
    is_single_player: bool  # Nouveau champ

    class Config:
        from_attributes = True


@router.post("/", response_model=ScoreResponse)
async def create_score(
    score_data: CreateScoreRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(verify_arcade_key)]
):
    """Enregistre un nouveau score."""

    player1, player2 = ScoreService.validate_players(score_data, db)

    game = ScoreService.get_active_entity(db, Game, score_data.game_id, "Jeu non trouvé")
    arcade = ScoreService.get_active_entity(db, Arcade, score_data.arcade_id, "Borne d'arcade non trouvée")

    is_single_player = score_data.player2_id is None
    ScoreService.validate_game_mode(db, game, is_single_player)

    score = Score(**score_data.dict())

    db.add(score)
    db.commit()
    db.refresh(score)

    winner_pseudo = ScoreService.determine_winner(
        db, score_data, player1, player2, is_single_player
    )

    return ScoreResponse(
        id=score.id,
        player1_pseudo=player1.pseudo,
        player2_pseudo=player2.pseudo if player2 else None,
        game_name=game.nom,
        arcade_name=arcade.nom,
        score_j1=score.score_j1,
        score_j2=score.score_j2,
        winner_pseudo=winner_pseudo,
        is_single_player=is_single_player,
        created_at=score.created_at.isoformat()
    )


@router.get("/", response_model=List[ScoreResponse])
def get_scores(
        game_id: Annotated[Optional[int], Query(None, description="Filtrer par jeu")] = None,
        arcade_id: Annotated[Optional[int], Query(None, description="Filtrer par borne")] = None,
        friends_only: Annotated[bool, Query(False, description="Afficher seulement les scores avec mes amis")] = False,
        single_player_only: Annotated[bool, Query(False, description="Afficher seulement les scores solo")] = False,
        limit: Annotated[int, Query(50, le=100)] = 50,
        db: Annotated[Session, Depends(get_db)] = None,
        current_user: Annotated[User, Depends(get_current_user)] = None
):
    query = ScoreService._base_query(db)
    query = ScoreService._apply_filters(db, query, game_id, arcade_id, single_player_only)

    if friends_only:
        friend_ids = ScoreService._get_friend_ids(db, current_user)
        if not friend_ids:
            return []
        query = ScoreService._apply_friend_filter(query, current_user, friend_ids)

    rows = query.order_by(Score.created_at.desc()).limit(limit).all()

    return [
        ScoreService._to_response(db, score, p1, p2, game, arcade)
        for score, p1, p2, game, arcade in rows
    ]

@router.get("/my-stats")
async def get_my_stats(
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère les statistiques personnelles de l'utilisateur."""

    # Compter les parties jouées (solo + multi)
    total_games = db.query(Score).filter(
        or_(
            Score.player1_id == current_user.id,
            Score.player2_id == current_user.id
        ),
        Score.is_deleted == False
    ).count()

    # Compter les parties solo
    solo_games = db.query(Score).filter(
        Score.player1_id == current_user.id,
        Score.player2_id.is_(None),
        Score.is_deleted == False
    ).count()

    # Compter les victoires (seulement pour jeux multi)
    wins = db.query(Score).filter(
        or_(
            and_(Score.player1_id == current_user.id, Score.score_j1 > Score.score_j2),
            and_(Score.player2_id == current_user.id, Score.score_j2 > Score.score_j1)
        ),
        Score.player2_id.isnot(None),  # Seulement jeux multi
        Score.is_deleted == False
    ).count()

    # Compter les défaites (seulement pour jeux multi)
    losses = db.query(Score).filter(
        or_(
            and_(Score.player1_id == current_user.id, Score.score_j1 < Score.score_j2),
            and_(Score.player2_id == current_user.id, Score.score_j2 < Score.score_j1)
        ),
        Score.player2_id.isnot(None),  # Seulement jeux multi
        Score.is_deleted == False
    ).count()

    # Compter les égalités (seulement pour jeux multi)
    multi_games = total_games - solo_games
    draws = multi_games - wins - losses

    win_rate = (wins / multi_games * 100) if multi_games > 0 else 0

    return {
        "total_games": total_games,
        "solo_games": solo_games,
        "multiplayer_games": multi_games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(win_rate, 2)
    }