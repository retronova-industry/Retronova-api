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

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()