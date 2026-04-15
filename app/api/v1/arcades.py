# Correction du fichier app/api/v1/arcades.py
# Ajout des IDs des joueurs dans la réponse de la file d'attente

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.arcade import Arcade, ArcadeGame
from app.models.game import Game
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.api.deps import verify_arcade_key, get_current_user
from pydantic import BaseModel

router = APIRouter()


class GameOnArcadeResponse(BaseModel):
    id: int
    nom: str
    description: str
    game_image: Optional[str] = None
    min_players: int
    max_players: int
    ticket_cost: int
    slot_number: int

    class Config:
        from_attributes = True


class ArcadeResponse(BaseModel):
    id: int
    nom: str
    description: str
    arcade_image: Optional[str] = None
    localisation: str
    latitude: float
    longitude: float
    games: List[GameOnArcadeResponse]

    class Config:
        from_attributes = True


class QueueItemResponse(BaseModel):
    id: int
    player_id: int  # AJOUT: ID du joueur principal
    player_pseudo: str
    player2_id: Optional[int] = None  # AJOUT: ID du joueur 2
    player2_pseudo: Optional[str]
    game_id: int  # AJOUT: ID du jeu
    game_name: str
    unlock_code: str
    position: int

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ArcadeResponse])
async def get_arcades(
        db: Session = Depends(get_db)
):
    """Récupère la liste de toutes les bornes d'arcade."""

    arcades = db.query(Arcade).filter(
        Arcade.is_deleted == False
    ).all()

    # Enrichir avec les jeux
    result = []
    for arcade in arcades:
        arcade_games = db.query(ArcadeGame, Game).join(
            Game, ArcadeGame.game_id == Game.id
        ).filter(
            ArcadeGame.arcade_id == arcade.id,
            ArcadeGame.is_deleted == False,
            Game.is_deleted == False
        ).all()

        games = []
        for arcade_game, game in arcade_games:
            game_data = GameOnArcadeResponse(
                id=game.id,
                nom=game.nom,
                description=game.description,
                game_image=game.game_image,
                min_players=game.min_players,
                max_players=game.max_players,
                ticket_cost=game.ticket_cost,
                slot_number=arcade_game.slot_number
            )
            games.append(game_data)

        arcade_data = ArcadeResponse(
            id=arcade.id,
            nom=arcade.nom,
            description=arcade.description,
            arcade_image=arcade.arcade_image,
            localisation=arcade.localisation,
            latitude=arcade.latitude,
            longitude=arcade.longitude,
            games=games
        )
        result.append(arcade_data)

    return result


@router.get("/{arcade_id}", response_model=ArcadeResponse)
async def get_arcade(
        arcade_id: int,
        db: Session = Depends(get_db)
):
    """Récupère les détails d'une borne d'arcade spécifique."""

    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.is_deleted == False
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borne d'arcade non trouvée"
        )

    # Récupérer les jeux de cette borne
    arcade_games = db.query(ArcadeGame, Game).join(
        Game, ArcadeGame.game_id == Game.id
    ).filter(
        ArcadeGame.arcade_id == arcade.id,
        ArcadeGame.is_deleted == False,
        Game.is_deleted == False
    ).all()

    games = []
    for arcade_game, game in arcade_games:
        game_data = GameOnArcadeResponse(
            id=game.id,
            nom=game.nom,
            description=game.description,
            game_image=game.game_image,
            min_players=game.min_players,
            max_players=game.max_players,
            ticket_cost=game.ticket_cost,
            slot_number=arcade_game.slot_number
        )
        games.append(game_data)

    return ArcadeResponse(
        id=arcade.id,
        nom=arcade.nom,
        description=arcade.description,
        arcade_image=arcade.arcade_image,
        localisation=arcade.localisation,
        latitude=arcade.latitude,
        longitude=arcade.longitude,
        games=games
    )


@router.get("/{arcade_id}/queue", response_model=List[QueueItemResponse])
async def get_arcade_queue(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_arcade_key)
):
    """Récupère la file d'attente d'une borne (authentification par clé API)."""

    # Vérifier que la borne existe
    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.is_deleted == False
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borne d'arcade non trouvée"
        )

    # Récupérer la file d'attente (FIFO) avec toutes les informations nécessaires
    reservations = db.query(Reservation).join(
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
        # Récupérer le joueur 2 si présent
        player2_id = None
        player2_pseudo = None
        if reservation.player2_id:
            player2 = db.query(User).filter(User.id == reservation.player2_id).first()
            if player2:
                player2_id = player2.id
                player2_pseudo = player2.pseudo

        queue_item = QueueItemResponse(
            id=reservation.id,
            player_id=reservation.player_id,  # ID du joueur principal
            player_pseudo=reservation.player.pseudo,
            player2_id=player2_id,  # ID du joueur 2 (optionnel)
            player2_pseudo=player2_pseudo,
            game_id=reservation.game_id,  # ID du jeu
            game_name=reservation.game.nom,
            unlock_code=reservation.unlock_code,
            position=i + 1
        )
        queue.append(queue_item)

    return queue


@router.get("/{arcade_id}/config")
async def get_arcade_config(
        arcade_id: int,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_arcade_key)
):
    """Récupère la configuration d'une borne (pour la borne elle-même)."""

    arcade = db.query(Arcade).filter(
        Arcade.id == arcade_id,
        Arcade.is_deleted == False
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borne d'arcade non trouvée"
        )

    # Récupérer les jeux installés
    arcade_games = db.query(ArcadeGame, Game).join(
        Game, ArcadeGame.game_id == Game.id
    ).filter(
        ArcadeGame.arcade_id == arcade.id,
        ArcadeGame.is_deleted == False,
        Game.is_deleted == False
    ).order_by(ArcadeGame.slot_number).all()

    games_config = []
    for arcade_game, game in arcade_games:
        games_config.append({
            "slot": arcade_game.slot_number,
            "game_id": game.id,
            "game_name": game.nom,
            "min_players": game.min_players,
            "max_players": game.max_players
        })

    return {
        "arcade_id": arcade.id,
        "arcade_name": arcade.nom,
        "games": games_config
    }