from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate


def register_user_service(db: Session, user_data: UserCreate) -> User:
    """Enregistre un nouvel utilisateur après vérification Firebase."""

    existing_user = db.query(User).filter(
        User.firebase_uid == user_data.firebase_uid
    ).first()

    if existing_user:
        if existing_user.is_deleted:
            existing_user.is_deleted = False
            existing_user.deleted_at = None

            for field, value in user_data.dict(exclude={"firebase_uid"}).items():
                setattr(existing_user, field, value)

            db.commit()
            db.refresh(existing_user)
            return existing_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur déjà enregistré"
        )

    if db.query(User).filter(
        User.pseudo == user_data.pseudo,
        User.is_deleted == False
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce pseudo est déjà utilisé"
        )

    if db.query(User).filter(
        User.numero_telephone == user_data.numero_telephone,
        User.is_deleted == False
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce numéro de téléphone est déjà utilisé"
        )

    user = User(**user_data.dict())
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_current_user_info_service(current_user: User) -> User:
    """Retourne les informations de l'utilisateur connecté."""
    return current_user