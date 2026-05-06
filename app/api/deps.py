from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Annotated

from app.core.database import get_db
from app.core.messages import USER_NOT_FOUND
from app.core.security import verify_firebase_token
from app.models.user import User
from app.models.arcade import Arcade

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
) -> dict:
    """Dependency pour obtenir l'admin actuel via Firebase Admin."""
    token_data = verify_firebase_token(credentials.credentials, "admin")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Firebase admin invalide"
        )

    return token_data


def verify_arcade_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Session = Depends(get_db)
) -> Arcade:
    """Vérifie la clé API d'une borne et retourne la borne associée."""

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API borne invalide"
        )

    arcade = db.query(Arcade).filter(
        Arcade.api_key == x_api_key,
        Arcade.is_deleted.is_(False)
    ).first()

    if not arcade:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API borne invalide"
        )

    return arcade


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
        User.is_deleted.is_(False)
    ).first()