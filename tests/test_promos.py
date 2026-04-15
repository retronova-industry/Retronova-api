import pytest
import datetime

class TestPromos:
    """Tests pour les endpoints de codes promo."""

    def test_use_promo_code_success(self, client, auth_headers_user, sample_user, sample_promo_code, db):
        """Test d'utilisation de code promo réussie."""
        initial_balance = sample_user.tickets_balance

        promo_data = {
            "code": sample_promo_code.code
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["tickets_received"] == sample_promo_code.tickets_reward
        assert data["new_balance"] == initial_balance + sample_promo_code.tickets_reward
        assert "succès" in data["message"]
        # Vérifier que le solde a été mis à jour
        db.refresh(sample_user)
        assert sample_user.tickets_balance == initial_balance + sample_promo_code.tickets_reward

    def test_use_promo_code_invalid(self, client, auth_headers_user):
        """Test d'utilisation de code promo invalide."""
        promo_data = {
            "code": "INEXISTANT"
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 404
        assert "Code promo invalide" in response.json()["detail"]

    def test_use_promo_code_case_insensitive(self, client, auth_headers_user, sample_user, sample_promo_code, db):
        """Test que les codes promo sont insensibles à la casse."""
        promo_data = {
            "code": sample_promo_code.code.lower()  # En minuscules
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["tickets_received"] == sample_promo_code.tickets_reward

    def test_use_promo_code_already_used_per_user(self, client, auth_headers_user, sample_user, sample_promo_code, db):
        """Test d'utilisation d'un code déjà utilisé par l'utilisateur."""
        # Utiliser le code une première fois
        from app.models import PromoUse
        promo_use = PromoUse(
            user_id=sample_user.id,
            promo_code_id=sample_promo_code.id,
            tickets_received=sample_promo_code.tickets_reward
        )
        db.add(promo_use)
        sample_promo_code.current_uses += 1
        db.commit()

        # Essayer de l'utiliser à nouveau
        promo_data = {
            "code": sample_promo_code.code
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 400
        assert "déjà utilisé ce code promo" in response.json()["detail"]

    def test_use_promo_code_global_single_use(self, client, auth_headers_user, sample_user, db):
        """Test d'utilisation d'un code à usage unique global."""
        from app.models import PromoCode

        # Créer un code à usage unique global déjà utilisé
        global_promo = PromoCode(
            code="GLOBALONCE",
            tickets_reward=10,
            is_single_use_global=True,
            is_single_use_per_user=False,
            current_uses=1  # Déjà utilisé
        )
        db.add(global_promo)
        db.commit()

        promo_data = {
            "code": "GLOBALONCE"
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 400
        assert "déjà été utilisé" in response.json()["detail"]

    def test_use_promo_code_usage_limit_reached(self, client, auth_headers_user, sample_user, db):
        """Test d'utilisation d'un code ayant atteint sa limite."""
        from app.models import PromoCode

        # Créer un code avec limite atteinte
        limited_promo = PromoCode(
            code="LIMITED5",
            tickets_reward=2,
            is_single_use_global=False,
            is_single_use_per_user=False,
            usage_limit=5,
            current_uses=5  # Limite atteinte
        )
        db.add(limited_promo)
        db.commit()

        promo_data = {
            "code": "LIMITED5"
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 400
        assert "limite d'utilisation" in response.json()["detail"]

    def test_use_promo_code_increments_usage(self, client, auth_headers_user, sample_user, sample_promo_code, db):
        """Test que l'utilisation incrémente bien le compteur."""
        initial_uses = sample_promo_code.current_uses

        promo_data = {
            "code": sample_promo_code.code
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 200

        # Vérifier que le compteur a été incrémenté
        db.refresh(sample_promo_code)
        assert sample_promo_code.current_uses == initial_uses + 1

    def test_use_promo_code_creates_history_entry(self, client, auth_headers_user, sample_user, sample_promo_code, db):
        """Test que l'utilisation crée une entrée dans l'historique."""
        promo_data = {
            "code": sample_promo_code.code
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 200

        # Vérifier l'historique
        from app.models import PromoUse
        promo_use = db.query(PromoUse).filter(
            PromoUse.user_id == sample_user.id,
            PromoUse.promo_code_id == sample_promo_code.id
        ).first()

        assert promo_use is not None
        assert promo_use.tickets_received == sample_promo_code.tickets_reward

    def test_get_promo_history_empty(self, client, auth_headers_user):
        """Test de récupération de l'historique vide."""
        response = client.get("/api/v1/promos/history", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_promo_history_with_data(self, client, auth_headers_user, sample_user, sample_promo_code, db):
        """Test de récupération de l'historique avec données."""
        # Créer une entrée d'historique
        from app.models import PromoUse
        promo_use = PromoUse(
            user_id=sample_user.id,
            promo_code_id=sample_promo_code.id,
            tickets_received=sample_promo_code.tickets_reward
        )

        expected_code = sample_promo_code.code
        expected_tickets = sample_promo_code.tickets_reward

        db.add(promo_use)
        db.commit()

        response = client.get("/api/v1/promos/history", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == expected_code
        assert data[0]["tickets_received"] == expected_tickets

    def test_get_promo_history_sorted_by_date(self, client, auth_headers_user, sample_user, db):
        """Test que l'historique est trié par date décroissante."""
        from app.models import PromoCode, PromoUse
        import time

        promo_codes = []
        for i in range(3):
            promo = PromoCode(
                code=f"HISTORY{i}",
                tickets_reward=i + 1,
                is_single_use_per_user=False
            )
            db.add(promo)
            promo_codes.append(promo)
        db.commit()

        for i, promo in enumerate(promo_codes):
            promo_use = PromoUse(
                user_id=sample_user.id,
                promo_code_id=promo.id,
                tickets_received=promo.tickets_reward
            )
            db.add(promo_use)
            db.commit()
            if i < 2:
                time.sleep(0.01)

        response = client.get("/api/v1/promos/history", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        assert data[0]["code"] == "HISTORY2"
        assert data[1]["code"] == "HISTORY1"
        assert data[2]["code"] == "HISTORY0"

    def test_promo_code_with_whitespace(self, client, auth_headers_user, sample_user, db):
        """Test d'utilisation de code promo avec des espaces."""
        from app.models import PromoCode

        promo = PromoCode(
            code="WHITESPACE",
            tickets_reward=3,
            is_single_use_per_user=True
        )
        db.add(promo)
        db.commit()

        # Utiliser le code avec des espaces
        promo_data = {
            "code": "  whitespace  "  # Avec espaces et casse différente
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["tickets_received"] == 3

    def test_multiple_users_same_promo_code(self, client, sample_user, sample_promo_code, db):
        """Test que plusieurs utilisateurs peuvent utiliser le même code."""
        from app.models import User
        from unittest.mock import patch

        # Créer un deuxième utilisateur
        user2 = User(
            firebase_uid="user2_promo_uid",
            email="user2promo@example.com",
            nom="User2",
            prenom="Promo",
            pseudo="user2promo",
            date_naissance=datetime.date(1990, 1, 1),
            numero_telephone="0333333333",
            tickets_balance=0
        )
        db.add(user2)
        db.commit()
        db.refresh(user2)

        # Premier utilisateur utilise le code
        with patch("app.api.deps.verify_firebase_token") as mock_verify:
            mock_verify.return_value = {
                "uid": sample_user.firebase_uid,
                "email": sample_user.email,
                "email_verified": True
            }

            headers1 = {"Authorization": "Bearer fake_user1_token"}
            promo_data = {"code": sample_promo_code.code}

            response1 = client.post("/api/v1/promos/use", json=promo_data, headers=headers1)
            assert response1.status_code == 200

        # Deuxième utilisateur utilise le même code
        with patch("app.api.deps.verify_firebase_token") as mock_verify:
            mock_verify.return_value = {
                "uid": user2.firebase_uid,
                "email": user2.email,
                "email_verified": True
            }

            headers2 = {"Authorization": "Bearer fake_user2_token"}

            response2 = client.post("/api/v1/promos/use", json=promo_data, headers=headers2)
            assert response2.status_code == 200

            # Vérifier que user2 a bien reçu les tickets
            db.refresh(user2)
            assert user2.tickets_balance == sample_promo_code.tickets_reward

    def test_promo_endpoints_unauthorized(self, client, sample_promo_code):
        """Test d'accès non autorisé aux endpoints de codes promo."""
        protected_endpoints = [
            ("POST", "/api/v1/promos/use", {"code": sample_promo_code.code}),
            ("GET", "/api/v1/promos/history", None)
        ]

        for method, endpoint, json_data in protected_endpoints:
            if method == "POST":
                response = client.post(endpoint, json=json_data)
            else:
                response = client.get(endpoint)

            assert response.status_code == 403

    def test_promo_code_deleted_not_usable(self, client, auth_headers_user, db):
        """Test qu'un code promo supprimé n'est pas utilisable."""
        from app.models import PromoCode

        # Créer un code supprimé
        deleted_promo = PromoCode(
            code="DELETED",
            tickets_reward=5,
            is_deleted=True
        )
        db.add(deleted_promo)
        db.commit()

        promo_data = {
            "code": "DELETED"
        }

        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 404
        assert "Code promo invalide" in response.json()["detail"]

    def test_promo_use_full_workflow(self, client, auth_headers_user, sample_user, db):
        """Test du workflow complet d'utilisation de code promo."""
        from app.models import PromoCode

        # Créer un code promo
        promo = PromoCode(
            code="WORKFLOW",
            tickets_reward=7,
            is_single_use_per_user=True,
            usage_limit=10
        )
        db.add(promo)
        db.commit()
        db.refresh(promo)

        initial_balance = sample_user.tickets_balance
        initial_uses = promo.current_uses

        # Utiliser le code
        promo_data = {"code": "WORKFLOW"}
        response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)

        assert response.status_code == 200

        # Vérifier tous les effets
        db.refresh(sample_user)
        db.refresh(promo)

        # Solde mis à jour
        assert sample_user.tickets_balance == initial_balance + 7

        # Compteur d'utilisation incrémenté
        assert promo.current_uses == initial_uses + 1

        # Entrée d'historique créée
        from app.models import PromoUse
        promo_use = db.query(PromoUse).filter(
            PromoUse.user_id == sample_user.id,
            PromoUse.promo_code_id == promo.id
        ).first()
        assert promo_use is not None

        # Historique accessible via API
        history_response = client.get("/api/v1/promos/history", headers=auth_headers_user)
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data) == 1
        assert history_data[0]["code"] == "WORKFLOW"

        # Impossibilité de réutiliser le code
        second_use_response = client.post("/api/v1/promos/use", json=promo_data, headers=auth_headers_user)
        assert second_use_response.status_code == 400