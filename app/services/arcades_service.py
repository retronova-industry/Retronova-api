from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.messages import ARCADE_NOT_FOUND
from app.models.arcade import Arcade, ArcadeGame
from app.models.game import Game
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.schemas.arcade import ArcadeResponse, GameOnArcadeResponse, QueueItemResponse


class ArcadeService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_arcade(self, arcade_id: int) -> Arcade:
        arcade = self.db.query(Arcade).filter(
            Arcade.id == arcade_id,
            Arcade.is_deleted == False
        ).first()

        if not arcade:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ARCADE_NOT_FOUND
            )

        return arcade

    def get_arcade_games(self, arcade_id: int):
        return self.db.query(ArcadeGame, Game).join(
            Game, ArcadeGame.game_id == Game.id
        ).filter(
            ArcadeGame.arcade_id == arcade_id,
            ArcadeGame.is_deleted == False,
            Game.is_deleted == False
        ).all()

    def build_arcade_response(self, arcade: Arcade) -> ArcadeResponse:
        arcade_games = self.get_arcade_games(arcade.id)

        games = [
            GameOnArcadeResponse(
                id=game.id,
                nom=game.nom,
                description=game.description,
                min_players=game.min_players,
                max_players=game.max_players,
                ticket_cost=game.ticket_cost,
                slot_number=arcade_game.slot_number
            )
            for arcade_game, game in arcade_games
        ]

        return ArcadeResponse(
            id=arcade.id,
            nom=arcade.nom,
            description=arcade.description,
            localisation=arcade.localisation,
            latitude=arcade.latitude,
            longitude=arcade.longitude,
            games=games
        )

    def get_all_arcades(self) -> list[ArcadeResponse]:
        arcades = self.db.query(Arcade).filter(
            Arcade.is_deleted == False
        ).all()

        return [self.build_arcade_response(arcade) for arcade in arcades]

    def get_arcade_details(self, arcade_id: int) -> ArcadeResponse:
        arcade = self.get_active_arcade(arcade_id)
        return self.build_arcade_response(arcade)

    def get_arcade_queue(self, arcade_id: int) -> list[QueueItemResponse]:
        self.get_active_arcade(arcade_id)

        reservations = self.db.query(Reservation).join(
            User, Reservation.player_id == User.id
        ).join(
            Game, Reservation.game_id == Game.id
        ).filter(
            Reservation.arcade_id == arcade_id,
            Reservation.status == ReservationStatus.WAITING,
            Reservation.is_deleted == False
        ).order_by(Reservation.created_at).all()

        queue = []
        for i, reservation in enumerate(reservations):
            player2_id = None
            player2_pseudo = None

            if reservation.player2_id:
                player2 = self.db.query(User).filter(
                    User.id == reservation.player2_id
                ).first()
                if player2:
                    player2_id = player2.id
                    player2_pseudo = player2.pseudo

            queue.append(
                QueueItemResponse(
                    id=reservation.id,
                    player_id=reservation.player_id,
                    player_pseudo=reservation.player.pseudo,
                    player2_id=player2_id,
                    player2_pseudo=player2_pseudo,
                    game_id=reservation.game_id,
                    game_name=reservation.game.nom,
                    unlock_code=reservation.unlock_code,
                    position=i + 1
                )
            )

        return queue

    def get_arcade_config(self, arcade_id: int) -> dict:
        arcade = self.get_active_arcade(arcade_id)

        arcade_games = self.db.query(ArcadeGame, Game).join(
            Game, ArcadeGame.game_id == Game.id
        ).filter(
            ArcadeGame.arcade_id == arcade.id,
            ArcadeGame.is_deleted == False,
            Game.is_deleted == False
        ).order_by(ArcadeGame.slot_number).all()

        games_config = [
            {
                "slot": arcade_game.slot_number,
                "game_id": game.id,
                "game_name": game.nom,
                "min_players": game.min_players,
                "max_players": game.max_players
            }
            for arcade_game, game in arcade_games
        ]

        return {
            "arcade_id": arcade.id,
            "arcade_name": arcade.nom,
            "games": games_config
        }