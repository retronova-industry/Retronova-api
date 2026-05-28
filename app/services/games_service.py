from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.messages import GAME_NOT_FOUND
from app.models.game import Game


class GameService:
    def __init__(self, db: Session):
        self.db = db

    def get_games(self):
        return self.db.query(Game).filter(
            Game.is_deleted == False
        ).all()

    def get_game(self, game_id: int):
        game = self.db.query(Game).filter(
            Game.id == game_id,
            Game.is_deleted == False
        ).first()

        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=GAME_NOT_FOUND
            )

        return game