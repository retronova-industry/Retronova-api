from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Annotated

from app.core.database import get_db
from app.core.messages import USER_NOT_FOUND
from app.core.security import verify_firebase_token
from app.models.user import User
from app.models.admin import Admin, AdminRole

security = HTTPBearer()


def get_current_user(
        db: Session = Depends(get_db), # NOSONAR
        credentials: HTTPAuthorizationCredentials = Depends(security) # NOSONAR
) -> User:
    return _get_user_from_token(db, credentials)


def _get_user_from_token(db: Session, credentials: HTTPAuthorizationCredentials) -> User:
    """Helper pour extraire l'utilisateur depuis un token Firebase."""
    token_data = verify_firebase_token(credentials.credentials, "user")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Firebase invalide"
        )

    user = db.query(User).filter(
        User.firebase_uid == token_data["uid"],
        User.is_deleted.is_(False)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND
        )

    return user


def get_current_admin(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Admin:
    """Dependency pour obtenir l'admin actuel (super_admin ou arcade_owner)."""
    token_data = verify_firebase_token(credentials.credentials, "admin")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Firebase admin invalide"
        )

    admin = db.query(Admin).filter(
        Admin.firebase_uid == token_data["uid"],
        Admin.is_deleted == False
    ).first()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte admin non trouvé — contactez un super_admin"
        )

    return admin


def get_current_super_admin(
        admin: Admin = Depends(get_current_admin)
) -> Admin:
    """Dependency réservée aux super_admin."""
    if admin.role != AdminRole.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux super administrateurs"
        )
    return admin


def get_current_arcade_owner(
        admin: Admin = Depends(get_current_admin)
) -> Admin:
    """Dependency pour arcade_owner ET super_admin (accès élargi)."""
    # Les deux rôles ont accès — le filtrage par arcade_id est fait dans chaque endpoint
    return admin

def get_optional_user(
        db: Session = Depends(get_db),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """Dependency pour obtenir l'utilisateur actuel optionnel."""
    if not credentials:
        return None

    token_data = verify_firebase_token(credentials.credentials, "user")
    if not token_data:
        return None

    return db.query(User).filter(
        User.firebase_uid == token_data["uid"],
        User.is_deleted == False
    ).first()
