from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserUpdate


def get_my_profile_service(current_user: User) -> User:
    """Récupère le profil de l'utilisateur connecté."""
    return current_user


def update_my_profile_service(
    db: Session,
    current_user: User,
    user_update: UserUpdate
) -> User:
    """Met à jour le profil de l'utilisateur connecté."""

    if user_update.pseudo and user_update.pseudo != current_user.pseudo:
        existing_user = db.query(User).filter(
            User.pseudo == user_update.pseudo,
            User.id != current_user.id,
            User.is_deleted == False
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce pseudo est déjà utilisé"
            )

    if (
        user_update.numero_telephone
        and user_update.numero_telephone != current_user.numero_telephone
    ):
        existing_user = db.query(User).filter(
            User.numero_telephone == user_update.numero_telephone,
            User.id != current_user.id,
            User.is_deleted == False
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce numéro de téléphone est déjà utilisé"
            )

    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


def delete_my_account_service(db: Session, current_user: User) -> dict:
    """Permet à un utilisateur de supprimer son propre compte (soft delete)."""

    from app.models.reservation import Reservation, ReservationStatus
    from app.models.friend import Friendship

    active_reservations = db.query(Reservation).filter(
        (Reservation.player_id == current_user.id) | (Reservation.player2_id == current_user.id),
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).count()

    if active_reservations > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Impossible de supprimer le compte : {active_reservations} réservation(s) active(s). "
                "Veuillez d'abord annuler vos réservations en cours."
            )
        )

    current_user.is_deleted = True
    current_user.deleted_at = datetime.now(timezone.utc)

    friendships = db.query(Friendship).filter(
        (Friendship.requester_id == current_user.id) | (Friendship.requested_id == current_user.id),
        Friendship.is_deleted == False
    ).all()

    for friendship in friendships:
        friendship.is_deleted = True
        friendship.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "message": "Votre compte a été supprimé avec succès",
        "user_id": current_user.id,
        "deleted_friendships": len(friendships),
        "note": (
            "Toutes vos données personnelles ont été marquées comme supprimées. "
            "Vos scores et historiques restent anonymisés dans le système."
        )
    }


def search_users_service(
    db: Session,
    current_user: User,
    q: str,
    limit: int
) -> list[User]:
    """Recherche des utilisateurs par pseudo, nom ou prénom."""

    search_term = f"%{q}%"
    users = db.query(User).filter(
        User.is_deleted == False,
        User.id != current_user.id,
        (
            User.pseudo.ilike(search_term) |
            User.nom.ilike(search_term) |
            User.prenom.ilike(search_term)
        )
    ).limit(limit).all()

    return users