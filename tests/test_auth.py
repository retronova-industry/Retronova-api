import pytest
from unittest.mock import patch


class TestAuth:
    """Tests pour les endpoints d'authentification."""

    def test_register_user_success(self, client, db, mock_firebase):
        """Test d'enregistrement réussi d'un utilisateur."""
        mock_firebase.return_value = {
            "uid": "new_user_123",
            "email": "newuser@example.com",
            "email_verified": True
        }

        user_data = {
            "firebase_uid": "new_user_123",
            "email": "newuser@example.com",
            "nom": "Nouveau",
            "prenom": "Utilisateur",
            "pseudo": "nouveauuser",
            "date_naissance": "1995-05-15",
            "numero_telephone": "0123456789"
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["pseudo"] == user_data["pseudo"]
        assert data["tickets_balance"] == 0

    def test_register_user_duplicate_pseudo(self, client, db, sample_user, mock_firebase):
        """Test d'enregistrement avec pseudo déjà utilisé."""
        mock_firebase.return_value = {
            "uid": "new_user_456",
            "email": "another@example.com",
            "email_verified": True
        }

        user_data = {
            "firebase_uid": "new_user_456",
            "email": "another@example.com",
            "nom": "Another",
            "prenom": "User",
            "pseudo": sample_user.pseudo,  # Pseudo déjà utilisé
            "date_naissance": "1995-05-15",
            "numero_telephone": "0987654321"
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "pseudo est déjà utilisé" in response.json()["detail"]

    def test_register_user_duplicate_phone(self, client, db, sample_user, mock_firebase):
        """Test d'enregistrement avec téléphone déjà utilisé."""
        mock_firebase.return_value = {
            "uid": "new_user_789",
            "email": "phone@example.com",
            "email_verified": True
        }

        user_data = {
            "firebase_uid": "new_user_789",
            "email": "phone@example.com",
            "nom": "Phone",
            "prenom": "User",
            "pseudo": "phoneuser",
            "date_naissance": "1995-05-15",
            "numero_telephone": sample_user.numero_telephone  # Téléphone déjà utilisé
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "numéro de téléphone est déjà utilisé" in response.json()["detail"]

    def test_register_user_already_exists(self, client, db, sample_user, mock_firebase):
        """Test d'enregistrement avec utilisateur déjà existant."""
        mock_firebase.return_value = {
            "uid": sample_user.firebase_uid,
            "email": sample_user.email,
            "email_verified": True
        }

        user_data = {
            "firebase_uid": sample_user.firebase_uid,
            "email": sample_user.email,
            "nom": "Test",
            "prenom": "User",
            "pseudo": "differentpseudo",
            "date_naissance": "1990-01-01",
            "numero_telephone": "0111111111"
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        assert "déjà enregistré" in response.json()["detail"]

    def test_get_current_user_success(self, client, auth_headers_user, sample_user):
        """Test de récupération des infos utilisateur connecté."""
        response = client.get("/api/v1/auth/me", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_user.id
        assert data["email"] == sample_user.email
        assert data["pseudo"] == sample_user.pseudo

    def test_get_current_user_unauthorized(self, client):
        """Test de récupération sans authentification."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 403

    def test_get_current_user_invalid_token(self, client, mock_firebase):
        """Test avec token invalide."""
        mock_firebase.return_value = None

        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 401
        assert "Token Firebase invalide" in response.json()["detail"]