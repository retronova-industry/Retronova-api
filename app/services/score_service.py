from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased
from app.schemas.score import ScoreResponse
from app.models.arcade import Arcade
from app.models.friend import Friendship, FriendshipStatus
from app.models.score import Score
from app.models.user import User
from app.models.game import Game


class ScoreService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_user(self, user_id: int, label: str) -> User:
        user = self.db.query(User).filter(
            User.id == user_id,
            User.is_deleted.is_(False)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{label} non trouvé"
            )
        return user

    def get_active_entity(self, model, entity_id: int, not_found_msg: str):
        entity = self.db.query(model).filter(
            model.id == entity_id,
            model.is_deleted.is_(False)
        ).first()

        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=not_found_msg
            )
        return entity

    def validate_players(self, score_data):
        player1 = self.get_active_user(score_data.player1_id, "Joueur 1")

        player2 = None
        if score_data.player2_id:
            if score_data.player1_id == score_data.player2_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Les deux joueurs ne peuvent pas être identiques"
                )
            player2 = self.get_active_user(score_data.player2_id, "Joueur 2")

        return player1, player2

    def validate_game_mode(self, game: Game, is_single_player: bool):
        if is_single_player and game.min_players > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ce jeu nécessite au minimum {game.min_players} joueurs"
            )

        if not is_single_player and game.max_players < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce jeu ne supporte pas 2 joueurs"
            )

    def determine_winner(self, score_data, player1, player2, is_single_player):
        if is_single_player:
            return None

        if score_data.score_j1 > score_data.score_j2:
            return player1.pseudo

        if score_data.score_j2 > score_data.score_j1:
            return player2.pseudo

        return "Égalité"

    def _base_query(self):
        player1_alias = aliased(User)
        player2_alias = aliased(User)

        return (
            self.db.query(Score, player1_alias, player2_alias, Game, Arcade)
            .join(player1_alias, Score.player1_id == player1_alias.id)
            .outerjoin(player2_alias, Score.player2_id == player2_alias.id)
            .join(Game, Score.game_id == Game.id)
            .join(Arcade, Score.arcade_id == Arcade.id)
            .filter(Score.is_deleted.is_(False))
        )

    def _apply_filters(self, query, game_id, arcade_id, single_player_only):
        if game_id:
            query = query.filter(Score.game_id == game_id)

        if arcade_id:
            query = query.filter(Score.arcade_id == arcade_id)

        if single_player_only:
            query = query.filter(Score.player2_id.is_(None))

        return query

    def _get_friend_ids(self, current_user):
        friendships = self.db.query(Friendship).filter(
            and_(
                or_(
                    Friendship.requester_id == current_user.id,
                    Friendship.requested_id == current_user.id
                ),
                Friendship.status == FriendshipStatus.ACCEPTED,
                Friendship.is_deleted.is_(False)
            )
        ).all()

        return [
            f.requested_id if f.requester_id == current_user.id else f.requester_id
            for f in friendships
        ]

    def _apply_friend_filter(self, query, current_user, friend_ids):
        return query.filter(
            or_(
                Score.player1_id.in_(friend_ids),
                Score.player2_id.in_(friend_ids),
                and_(
                    Score.player1_id == current_user.id,
                    Score.player2_id.in_(friend_ids)
                ),
                and_(
                    Score.player2_id == current_user.id,
                    Score.player1_id.in_(friend_ids)
                )
            )
        )

    def _to_response(self, score, player1, player2, game, arcade):
        is_single = score.player2_id is None

        winner = None
        if not is_single:
            if score.score_j1 > score.score_j2:
                winner = player1.pseudo
            elif score.score_j2 > score.score_j1:
                winner = player2.pseudo
            else:
                winner = "Égalité"

        return ScoreResponse(
            id=score.id,
            player1_pseudo=player1.pseudo,
            player2_pseudo=player2.pseudo if player2 else None,
            game_name=game.nom,
            arcade_name=arcade.nom,
            score_j1=score.score_j1,
            score_j2=score.score_j2,
            winner_pseudo=winner,
            is_single_player=is_single,
            created_at=score.created_at.isoformat()
        )