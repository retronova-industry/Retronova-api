from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional, Annotated
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.database import get_db
from app.core.messages import ARCADE_NOT_FOUND, GAME_NOT_FOUND
from app.models.user import User
from app.models.score import Score
from app.models.game import Game
from app.models.arcade import Arcade
from app.services.score_service import ScoreService
from app.schemas.score import CreateScoreRequest, MyStatsResponse, ScoreResponse
from app.api.deps import get_current_user, verify_arcade_key

router = APIRouter()


@router.post("/", response_model=ScoreResponse)
async def create_score(
    score_data: CreateScoreRequest,
    db: Annotated[Session, Depends(get_db)],
    authenticated_arcade: Annotated[Arcade, Depends(verify_arcade_key)]
):
    """Enregistre un nouveau score."""

    score_service = ScoreService(db)

    player1, player2 = score_service.validate_players(score_data)

    game = score_service.get_active_entity(Game, score_data.game_id, GAME_NOT_FOUND)
    arcade = score_service.get_active_entity(Arcade, score_data.arcade_id, ARCADE_NOT_FOUND)

    if authenticated_arcade.id != score_data.arcade_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette clé API ne correspond pas à cette borne"
        )

    is_single_player = score_data.player2_id is None
    score_service.validate_game_mode(game, is_single_player)

    score = Score(**score_data.model_dump())

    db.add(score)
    db.commit()
    db.refresh(score)

    winner_pseudo = score_service.determine_winner(
        score_data, player1, player2, is_single_player
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
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    game_id: Annotated[Optional[int], Query(description="Filtrer par jeu")] = None,
    arcade_id: Annotated[Optional[int], Query(description="Filtrer par borne")] = None,
    friends_only: Annotated[bool, Query(description="Afficher seulement les scores avec mes amis")] = False,
    single_player_only: Annotated[bool, Query(description="Afficher seulement les scores solo")] = False,
    limit: Annotated[int, Query(le=100)] = 50,
):
    """Récupère la liste des scores avec filtres optionnels."""

    score_service = ScoreService(db)

    query = score_service._base_query()
    query = score_service._apply_filters(query, game_id, arcade_id, single_player_only)

    if friends_only:
        friend_ids = score_service._get_friend_ids(current_user)
        if not friend_ids:
            return []
        query = score_service._apply_friend_filter(query, current_user, friend_ids)

    rows = query.order_by(Score.created_at.desc()).limit(limit).all()

    return [
        score_service._to_response(score, p1, p2, game, arcade)
        for score, p1, p2, game, arcade in rows
    ]

@router.get("/my-stats", response_model=MyStatsResponse)
async def get_my_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère les statistiques personnelles de l'utilisateur."""
    score_service = ScoreService(db)
    return score_service.get_my_stats(current_user)