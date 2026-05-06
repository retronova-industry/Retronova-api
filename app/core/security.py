from fastapi import Depends, HTTPException, Header, status
import firebase_admin
from firebase_admin import credentials, auth
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.arcade import Arcade
from .config import settings
from typing import Annotated, Optional
import logging
import os

logger = logging.getLogger(__name__)

# Firebase Apps
firebase_user_app = None
firebase_admin_app = None


def init_firebase():
    """Initialise les applications Firebase."""
    global firebase_user_app, firebase_admin_app

    try:
        # Vérifier que les fichiers existent
        if not os.path.exists(settings.FIREBASE_USER_CREDENTIALS_PATH):
            raise FileNotFoundError(
                f"Fichier Firebase utilisateurs non trouvé : {settings.FIREBASE_USER_CREDENTIALS_PATH}")

        if not os.path.exists(settings.FIREBASE_ADMIN_CREDENTIALS_PATH):
            raise FileNotFoundError(f"Fichier Firebase admin non trouvé : {settings.FIREBASE_ADMIN_CREDENTIALS_PATH}")
        
        if os.getenv("CI") == "true" or not (os.path.exists(settings.FIREBASE_USER_CREDENTIALS_PATH) and os.path.exists(settings.FIREBASE_ADMIN_CREDENTIALS_PATH)):
            print("Firebase disabled in CI")
            return

        # App pour les utilisateurs finaux
        user_cred = credentials.Certificate(settings.FIREBASE_USER_CREDENTIALS_PATH)
        firebase_user_app = firebase_admin.initialize_app(
            user_cred,
            name="user_app"
        )

        # App pour les administrateurs
        admin_cred = credentials.Certificate(settings.FIREBASE_ADMIN_CREDENTIALS_PATH)
        firebase_admin_app = firebase_admin.initialize_app(
            admin_cred,
            name="admin_app"
        )

        logger.info("Firebase applications initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise


def verify_firebase_token(token: str, app_type: str = "user") -> Optional[dict]:
    """
    Vérifie un token Firebase et retourne les informations utilisateur.

    Args:
        token: Token Firebase
        app_type: "user" ou "admin"

    Returns:
        Dict contenant les infos utilisateur ou None si invalide
    """
    try:
        app = firebase_user_app if app_type == "user" else firebase_admin_app
        decoded_token = auth.verify_id_token(token, app=app)
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False)
        }
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


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