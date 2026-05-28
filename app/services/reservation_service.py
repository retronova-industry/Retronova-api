import random

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.messages import (
    ARCADE_NOT_FOUND,
    INSUFFICIENT_TICKETS,
    RESERVATION_NOT_FOUND
)
from app.models.arcade import Arcade, ArcadeGame
from app.models.game import Game
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User
from app.schemas.reservation import (
    CreateReservationRequest,
    ReservationResponse,
    UpdateReservationStatusRequest
)


def _get_player2_pseudo(db: Session, reservation: Reservation) -> str | None:
    if not reservation.player2_id:
        return None

    player2 = db.query(User).filter(User.id == reservation.player2_id).first()
    if player2:
        return player2.pseudo
    return None


def _get_queue_position(db: Session, reservation: Reservation) -> int | None:
    if reservation.status != ReservationStatus.WAITING:
        return None

    return db.query(Reservation).filter(
        Reservation.arcade_id == reservation.arcade_id,
        Reservation.status == ReservationStatus.WAITING,
        Reservation.created_at <= reservation.created_at,
        Reservation.is_deleted == False
    ).count()


def _build_reservation_response(
    db: Session,
    reservation: Reservation
) -> ReservationResponse:
    return ReservationResponse(
        id=reservation.id,
        unlock_code=reservation.unlock_code,
        status=reservation.status,
        arcade_name=reservation.arcade.nom,
        game_name=reservation.game.nom,
        player_pseudo=reservation.player.pseudo,
        player2_pseudo=_get_player2_pseudo(db, reservation),
        tickets_used=reservation.tickets_used,
        position_in_queue=_get_queue_position(db, reservation)
    )


def create_reservation_service(
    db: Session,
    current_user: User,
    reservation_data: CreateReservationRequest
) -> ReservationResponse:
    """Crée une nouvelle réservation de partie."""

    arcade = db.query(Arcade).filter(
        Arcade.id == reservation_data.arcade_id,
        Arcade.is_deleted == False
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ARCADE_NOT_FOUND
        )

    arcade_game = db.query(ArcadeGame).join(Game).filter(
        ArcadeGame.arcade_id == reservation_data.arcade_id,
        ArcadeGame.game_id == reservation_data.game_id,
        ArcadeGame.is_deleted == False,
        Game.is_deleted == False
    ).first()

    if not arcade_game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jeu non disponible sur cette borne"
        )

    game = arcade_game.game

    player_count = 2 if reservation_data.player2_id else 1
    if player_count < game.min_players or player_count > game.max_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ce jeu nécessite entre {game.min_players} et {game.max_players} joueurs"
        )

    player2 = None
    if reservation_data.player2_id:
        if reservation_data.player2_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous ne pouvez pas jouer contre vous-même"
            )

        player2 = db.query(User).filter(
            User.id == reservation_data.player2_id,
            User.is_deleted == False
        ).first()

        if not player2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Joueur 2 non trouvé"
            )

    if current_user.tickets_balance < game.ticket_cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INSUFFICIENT_TICKETS
        )

    unlock_code = str(random.randint(1, 8))

    reservation = Reservation(
        player_id=current_user.id,
        player2_id=reservation_data.player2_id,
        arcade_id=reservation_data.arcade_id,
        game_id=reservation_data.game_id,
        unlock_code=unlock_code,
        tickets_used=game.ticket_cost
    )

    current_user.tickets_balance -= game.ticket_cost

    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    queue_position = db.query(Reservation).filter(
        Reservation.arcade_id == reservation_data.arcade_id,
        Reservation.status == ReservationStatus.WAITING,
        Reservation.created_at <= reservation.created_at,
        Reservation.is_deleted == False
    ).count()

    return ReservationResponse(
        id=reservation.id,
        unlock_code=unlock_code,
        status=reservation.status,
        arcade_name=arcade.nom,
        game_name=game.nom,
        player_pseudo=current_user.pseudo,
        player2_pseudo=player2.pseudo if player2 else None,
        tickets_used=game.ticket_cost,
        position_in_queue=queue_position
    )


def get_my_reservations_service(
    db: Session,
    current_user: User
) -> list[ReservationResponse]:
    """Récupère les réservations de l'utilisateur actuel."""

    reservations = db.query(Reservation).join(
        Arcade, Reservation.arcade_id == Arcade.id
    ).join(
        Game, Reservation.game_id == Game.id
    ).filter(
        (Reservation.player_id == current_user.id) | (Reservation.player2_id == current_user.id),
        Reservation.is_deleted == False
    ).order_by(Reservation.created_at.desc()).all()

    return [_build_reservation_response(db, reservation) for reservation in reservations]


def get_reservation_service(
    db: Session,
    current_user: User,
    reservation_id: int
) -> ReservationResponse:
    """Récupère les détails d'une réservation spécifique."""

    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        (Reservation.player_id == current_user.id) | (Reservation.player2_id == current_user.id),
        Reservation.is_deleted == False
    ).first()

    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=RESERVATION_NOT_FOUND
        )

    return _build_reservation_response(db, reservation)


def cancel_reservation_service(
    db: Session,
    current_user: User,
    reservation_id: int
) -> dict:
    """Annule une réservation (seulement si en attente)."""

    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.player_id == current_user.id,
        Reservation.is_deleted == False
    ).first()

    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=RESERVATION_NOT_FOUND
        )

    if reservation.status != ReservationStatus.WAITING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les réservations en attente peuvent être annulées"
        )

    reservation.status = ReservationStatus.CANCELLED
    current_user.tickets_balance += reservation.tickets_used

    db.commit()

    return {"message": "Réservation annulée, tickets remboursés"}


def update_reservation_status_service(
    db: Session,
    reservation_id: int,
    status_data: UpdateReservationStatusRequest
) -> dict:
    """Met à jour le statut d'une réservation."""

    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.is_deleted == False
    ).first()

    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=RESERVATION_NOT_FOUND
        )

    valid_transitions = {
        ReservationStatus.WAITING: [ReservationStatus.PLAYING, ReservationStatus.CANCELLED],
        ReservationStatus.PLAYING: [ReservationStatus.COMPLETED, ReservationStatus.CANCELLED],
        ReservationStatus.COMPLETED: [],
        ReservationStatus.CANCELLED: []
    }

    if status_data.status not in valid_transitions.get(reservation.status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transition invalide de {reservation.status.value} vers {status_data.status.value}"
        )

    old_status = reservation.status
    reservation.status = status_data.status
    db.commit()
    db.refresh(reservation)

    return {
        "message": f"Statut mis à jour de {old_status.value} vers {status_data.status.value}",
        "reservation_id": reservation.id,
        "old_status": old_status.value,
        "new_status": reservation.status.value
    }


def get_reservation_status_service(db: Session, reservation_id: int) -> dict:
    """Récupère le statut d'une réservation."""

    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.is_deleted == False
    ).first()

    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=RESERVATION_NOT_FOUND
        )

    return {
        "reservation_id": reservation.id,
        "status": reservation.status.value,
        "player_pseudo": reservation.player.pseudo,
        "game_name": reservation.game.nom,
        "unlock_code": reservation.unlock_code
    }