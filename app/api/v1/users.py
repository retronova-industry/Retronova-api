from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Annotated, List, Optional
from datetime import datetime, timezone
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserUpdate, UserResponse, UserSearchResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Récupère le profil de l'utilisateur connecté."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
        user_update: UserUpdate,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Met à jour le profil de l'utilisateur connecté."""

    # Vérifier l'unicité du pseudo si modifié
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

    # Vérifier l'unicité du téléphone si modifié
    if user_update.numero_telephone and user_update.numero_telephone != current_user.numero_telephone:
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

    # Mettre à jour les champs modifiés
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me")
async def delete_my_account(
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Permet à un utilisateur de supprimer son propre compte (soft delete)."""

    # Vérifier s'il y a des réservations en cours
    from app.models.reservation import Reservation, ReservationStatus
    active_reservations = db.query(Reservation).filter(
        (Reservation.player_id == current_user.id) | (Reservation.player2_id == current_user.id),
        Reservation.status.in_([ReservationStatus.WAITING, ReservationStatus.PLAYING]),
        Reservation.is_deleted == False
    ).count()

    if active_reservations > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de supprimer le compte : {active_reservations} réservation(s) active(s). "
                   "Veuillez d'abord annuler vos réservations en cours."
        )
    current_user.is_deleted = True
    current_user.deleted_at = datetime.now(timezone.utc)

    # Soft delete des relations d'amitié
    from app.models.friend import Friendship
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
        "note": "Toutes vos données personnelles ont été marquées comme supprimées. "
                "Vos scores et historiques restent anonymisés dans le système."
    }


@router.get("/search", response_model=List[UserSearchResponse])
async def search_users(
        q: Annotated[str, Query(..., min_length=2, description="Terme de recherche (pseudo, nom, prénom)")],
        limit: Annotated[int, Query(10, le=50)],
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Recherche des utilisateurs par pseudo, nom ou prénom."""

    search_term = f"%{q}%"
    users = db.query(User).filter(
        User.is_deleted == False,
        User.id != current_user.id,  # Exclure l'utilisateur actuel
        (
                User.pseudo.ilike(search_term) |
                User.nom.ilike(search_term) |
                User.prenom.ilike(search_term)
        )
    ).limit(limit).all()

    return users