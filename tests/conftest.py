import pytest
import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import tempfile
from unittest.mock import patch, MagicMock
import datetime

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Maintenant on peut importer les modules de l'app
from app.main import app
from app.core.database import get_db, Base
from app.models import User, Game, Arcade, TicketOffer, PromoCode

# Base de données de test en mémoire
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override de la dependency get_db pour les tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Créer les tables de test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Client de test FastAPI."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    """Session de base de données de test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_firebase():
    with patch("app.api.deps.verify_firebase_token") as mock_verify:
        mock_verify.return_value = {
            "uid": "unauthorized_user",
            "email": "unauth@example.com",
            "email_verified": True
        }
        yield mock_verify



@pytest.fixture
def sample_user(db):
    """Utilisateur de test."""
    user = User(
        firebase_uid="test_uid_123",
        email="test@example.com",
        nom="Test",
        prenom="User",
        pseudo="testuser",
        date_naissance=datetime.date(1990, 1, 1),
        numero_telephone="0123456789",
        tickets_balance=10
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_admin_user(db):
    """Administrateur de test."""
    admin = User(
        firebase_uid="admin_uid_123",
        email="admin@example.com",
        nom="Admin",
        prenom="User",
        pseudo="adminuser",
        date_naissance=datetime.date(1990, 1, 1),
        numero_telephone="0987654321",
        tickets_balance=0
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def sample_game(db):
    """Jeu de test."""
    game = Game(
        nom="Test Game",
        description="Un jeu de test",
        min_players=1,
        max_players=2,
        ticket_cost=1
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


@pytest.fixture
def sample_arcade(db):
    """Borne d'arcade de test."""
    arcade = Arcade(
        nom="Test Arcade",
        description="Une borne de test",
        api_key="test_arcade_key_123",
        localisation="Test Location",
        latitude=43.6047,
        longitude=1.4442
    )
    db.add(arcade)
    db.commit()
    db.refresh(arcade)
    return arcade


@pytest.fixture
def sample_ticket_offer(db):
    """Offre de tickets de test."""
    offer = TicketOffer(
        tickets_amount=5,
        price_euros=10.0,
        name="5 Tickets Test"
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


@pytest.fixture
def sample_promo_code(db):
    """Code promo de test."""
    promo = PromoCode(
        code="TESTPROMO",
        tickets_reward=5,
        is_single_use_global=False,
        is_single_use_per_user=True,
        usage_limit=None,
        current_uses=0
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


@pytest.fixture
def auth_headers_user(mock_firebase, sample_user):
    mock_firebase.return_value = {
        "uid": sample_user.firebase_uid,
        "email": sample_user.email,
        "email_verified": True,
    }
    return {"Authorization": "Bearer faketoken"}



@pytest.fixture
def auth_headers_admin(mock_firebase, sample_admin_user):
    """Headers d'authentification pour admin."""
    mock_firebase.return_value = {
        "uid": sample_admin_user.firebase_uid,
        "email": sample_admin_user.email,
        "email_verified": True
    }
    return {"Authorization": "Bearer fake_admin_token"}


@pytest.fixture
def arcade_api_headers():
    """Headers API pour les bornes d'arcade."""
    return {"X-API-Key": "arcade-super-secret-api-key-change-this-in-production"}
