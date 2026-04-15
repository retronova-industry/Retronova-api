from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register_user(
        user_data: UserCreate,
        db: Annotated[Session, Depends(get_db)]
):
    """Enregistre un nouvel utilisateur après vérification Firebase."""

    # Vérifier si l'utilisateur existe déjà
    existing_user = db.query(User).filter(
        User.firebase_uid == user_data.firebase_uid
    ).first()

    if existing_user:
        if existing_user.is_deleted:
            # Réactiver un utilisateur supprimé
            existing_user.is_deleted = False
            existing_user.deleted_at = None
            # Mettre à jour les données
            for field, value in user_data.dict(exclude={"firebase_uid"}).items():
                setattr(existing_user, field, value)
            db.commit()
            db.refresh(existing_user)
            return existing_user
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Utilisateur déjà enregistré"
            )

    # Vérifier l'unicité du pseudo et téléphone
    if db.query(User).filter(User.pseudo == user_data.pseudo, User.is_deleted == False).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce pseudo est déjà utilisé"
        )

    if db.query(User).filter(User.numero_telephone == user_data.numero_telephone, User.is_deleted == False).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce numéro de téléphone est déjà utilisé"
        )

    # Créer le nouvel utilisateur
    user = User(**user_data.dict())
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: Annotated[User, Depends(get_current_user)]
):
    """Retourne les informations de l'utilisateur connecté."""
    return current_user