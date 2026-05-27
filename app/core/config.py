from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Arcade API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Firebase - Chemins vers les fichiers JSON
    FIREBASE_USER_CREDENTIALS_PATH: str
    FIREBASE_ADMIN_CREDENTIALS_PATH: str

    # Arcade API Key
    ARCADE_API_KEY: str

    # Email (Resend)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@retronova.fr"
    BACKOFFICE_URL: str = "http://localhost:4200"

    # Bootstrap super_admin (optionnel — utilisé une seule fois au premier démarrage)
    BOOTSTRAP_SUPER_ADMIN_UID: Optional[str] = None
    BOOTSTRAP_SUPER_ADMIN_EMAIL: Optional[str] = None

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()