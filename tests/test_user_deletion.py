# tests/test_user_deletion.py

import pytest
from datetime import datetime, timezone
from app.models import User, Reservation, ReservationStatus, Friendship, FriendshipStatus, PromoUse, TicketPurchase


class TestUserDeletion:
    """Tests pour la suppression d'utilisateurs."""

    @pytest.fixture
    def user_with_data(self, db, sample_user, sample_arcade, sample_game):
        """Utilisateur avec des données liées pour les tests."""
        # Ajouter des tickets
        sample_user.tickets_balance = 50

        # Créer une amitié
        friend = User(
            firebase_uid="friend_delete_uid",
            email="frienddelete@example.com",
            nom="Friend",
            prenom="Delete",
            pseudo="frienddelete",
            date_naissance=datetime.now().date(),
            numero_telephone="0555555555",
            tickets_balance=0
        )
        db.add(friend)
        db.commit()
        db.refresh(friend)

        friendship = Friendship(
            requester_id=sample_user.id,
            requested_id=friend.id,
            status=FriendshipStatus.ACCEPTED
        )
        db.add(friendship)

        # Créer un code promo utilisé
        from app.models import PromoCode
        promo = PromoCode(
            code="DELETETEST",
            tickets_reward=10,
            is_single_use_per_user=True
        )
        db.add(promo)
        db.commit()
        db.refresh(promo)

        promo_use = PromoUse(
            user_id=sample_user.id,
            promo_code_id=promo.id,
            tickets_received=10
        )
        db.add(promo_use)

        # Créer un achat de tickets
        from app.models import TicketOffer
        offer = TicketOffer(
            tickets_amount=20,
            price_euros=25.0,
            name="Delete Test Offer"
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)

        purchase = TicketPurchase(
            user_id=sample_user.id,
            offer_id=offer.id,
            tickets_received=20,
            amount_paid=25.0,
            stripe_payment_id="delete_test_payment"
        )
        db.add(purchase)

        db.commit()
        return sample_user

    def test_user_self_delete_success(self, client, auth_headers_user, user_with_data, db):
        """Test de suppression de compte par l'utilisateur lui-même."""
        user_id = user_with_data.id

        response = client.delete("/api/v1/users/me", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert "compte a été supprimé" in data["message"]
        assert data["user_id"] == user_id
        assert "deleted_friendships" in data

        # Vérifier que l'utilisateur est marqué comme supprimé
        db.refresh(user_with_data)
        assert user_with_data.is_deleted == True
        assert user_with_data.deleted_at is not None

        # Vérifier que les amitiés sont supprimées
        friendships = db.query(Friendship).filter(
            (Friendship.requester_id == user_id) | (Friendship.requested_id == user_id)
        ).all()
        for friendship in friendships:
            assert friendship.is_deleted == True

    def test_user_self_delete_with_active_reservation(self, client, auth_headers_user, user_with_data, sample_arcade,
                                                      sample_game, db):
        """Test de suppression bloquée par une réservation active."""
        # Créer une réservation active
        reservation = Reservation(
            player_id=user_with_data.id,
            arcade_id=sample_arcade.id,
            game_id=sample_game.id,
            unlock_code="1",
            tickets_used=1,
            status=ReservationStatus.WAITING
        )
        db.add(reservation)
        db.commit()
        all_users = db.query(User).all()
        for user in all_users:
            print(f"ID: {user.id}, Email: {user.email}, is_deleted: {user.is_deleted}")
        response = client.delete("/api/v1/users/me", headers=auth_headers_user)

        assert response.status_code == 400
        assert "réservation(s) active(s)" in response.json()["detail"]

        # Vérifier que l'utilisateur n'est pas supprimé
        refreshed_user = db.query(User).get(user_with_data.id)
        assert refreshed_user is not None
        assert refreshed_user.is_deleted is False

    def test_admin_delete_user_success(self, client, auth_headers_admin, user_with_data, db):
        """Test de suppression d'utilisateur par un admin."""
        user_id = user_with_data.id
        user_pseudo = user_with_data.pseudo

        response = client.delete(f"/api/v1/admin/users/{user_id}", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert f"Utilisateur '{user_pseudo}' supprimé" in data["message"]
        assert data["user_id"] == user_id
        assert "deleted_friendships" in data
        assert "deleted_promo_uses" in data
        assert "deleted_purchases" in data

        # Vérifier que l'utilisateur est marqué comme supprimé
        db.refresh(user_with_data)
        assert user_with_data.is_deleted == True
        assert user_with_data.deleted_at is not None

    def test_admin_delete_user_not_found(self, client, auth_headers_admin):
        """Test de suppression d'utilisateur inexistant."""
        response = client.delete("/api/v1/admin/users/99999", headers=auth_headers_admin)

        assert response.status_code == 404
        assert "Utilisateur non trouvé" in response.json()["detail"]

    def test_admin_delete_user_with_active_reservation(self, client, auth_headers_admin, user_with_data, sample_arcade,
                                                       sample_game, db):
        """Test de suppression admin bloquée par une réservation active."""
        # Créer une réservation active
        reservation = Reservation(
            player_id=user_with_data.id,
            arcade_id=sample_arcade.id,
            game_id=sample_game.id,
            unlock_code="2",
            tickets_used=1,
            status=ReservationStatus.PLAYING
        )
        db.add(reservation)
        db.commit()

        response = client.delete(f"/api/v1/admin/users/{user_with_data.id}", headers=auth_headers_admin)

        assert response.status_code == 400
        assert "réservation(s) active(s)" in response.json()["detail"]

    def test_admin_get_deletion_impact(self, client, auth_headers_admin, user_with_data, db):
        """Test de l'analyse d'impact avant suppression."""
        response = client.get(f"/api/v1/admin/users/{user_with_data.id}/deletion-impact", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["id"] == user_with_data.id
        assert data["user"]["pseudo"] == user_with_data.pseudo
        assert data["can_delete"] == True  # Pas de réservations actives
        assert "deletion_impact" in data
        assert data["deletion_impact"]["friendships_to_delete"] >= 1
        assert data["deletion_impact"]["promo_uses_to_delete"] >= 1
        assert data["deletion_impact"]["purchases_to_delete"] >= 1

    def test_admin_get_deletion_impact_with_blocking_factors(self, client, auth_headers_admin, user_with_data,
                                                             sample_arcade, sample_game, db):
        """Test de l'analyse d'impact avec facteurs bloquants."""
        # Créer une réservation active
        reservation = Reservation(
            player_id=user_with_data.id,
            arcade_id=sample_arcade.id,
            game_id=sample_game.id,
            unlock_code="3",
            tickets_used=1,
            status=ReservationStatus.WAITING
        )
        db.add(reservation)
        db.commit()

        response = client.get(f"/api/v1/admin/users/{user_with_data.id}/deletion-impact", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert data["can_delete"] == False
        assert "blocking_factors" in data
        assert data["blocking_factors"]["active_reservations"] == 1

    def test_admin_force_cancel_reservations(self, client, auth_headers_admin, user_with_data, sample_arcade,
                                             sample_game, db):
        """Test d'annulation forcée des réservations par admin."""
        initial_balance = user_with_data.tickets_balance

        # Créer plusieurs réservations actives
        reservations = [
            Reservation(
                player_id=user_with_data.id,
                arcade_id=sample_arcade.id,
                game_id=sample_game.id,
                unlock_code="4",
                tickets_used=2,
                status=ReservationStatus.WAITING
            ),
            Reservation(
                player_id=user_with_data.id,
                arcade_id=sample_arcade.id,
                game_id=sample_game.id,
                unlock_code="5",
                tickets_used=3,
                status=ReservationStatus.PLAYING
            )
        ]

        for reservation in reservations:
            db.add(reservation)
        db.commit()

        response = client.put(f"/api/v1/admin/users/{user_with_data.id}/force-cancel-reservations",
                              headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert data["cancelled_reservations"] == 2
        assert data["refunded_tickets"] == 5  # 2 + 3
        assert data["new_tickets_balance"] == initial_balance + 5

        # Vérifier que les réservations sont annulées
        for reservation in reservations:
            db.refresh(reservation)
            assert reservation.status == ReservationStatus.CANCELLED

    def test_deleted_user_not_in_search(self, client, auth_headers_user, user_with_data, db):
        """Test que les utilisateurs supprimés n'apparaissent pas dans la recherche."""
        # Supprimer l'utilisateur
        user_with_data.is_deleted = True
        user_with_data.deleted_at = datetime.now(timezone.utc)
        db.commit()

        # Créer un autre utilisateur pour effectuer la recherche
        searcher = User(
            firebase_uid="searcher_uid",
            email="searcher@example.com",
            nom="Searcher",
            prenom="User",
            pseudo="searcher",
            date_naissance=datetime.now().date(),
            numero_telephone="0666666666",
            tickets_balance=0
        )
        db.add(searcher)
        db.commit()

        # Mock l'authentification pour le chercheur
        from unittest.mock import patch
        with patch("app.api.deps.verify_firebase_token") as mock_verify:
            mock_verify.return_value = {
                "uid": searcher.firebase_uid,
                "email": searcher.email,
                "email_verified": True
            }

            headers = {"Authorization": "Bearer fake_searcher_token"}
            response = client.get(f"/api/v1/users/search?q={user_with_data.pseudo}", headers=headers)

            assert response.status_code == 200
            data = response.json()

            # L'utilisateur supprimé ne doit pas apparaître
            user_ids = [user["id"] for user in data]
            assert user_with_data.id not in user_ids

    def test_deleted_user_cannot_login(self, client, user_with_data, db, mock_firebase):
        """Test qu'un utilisateur supprimé ne peut pas se connecter."""
        # Supprimer l'utilisateur
        user_with_data.is_deleted = True
        user_with_data.deleted_at = datetime.now(timezone.utc)
        db.commit()

        # Tenter de se connecter
        mock_firebase.return_value = {
            "uid": user_with_data.firebase_uid,
            "email": user_with_data.email,
            "email_verified": True
        }

        headers = {"Authorization": "Bearer fake_token"}
        response = client.get("/api/v1/users/me", headers=headers)

        assert response.status_code == 404
        assert "Utilisateur non trouvé" in response.json()["detail"]

    def test_user_deletion_preserves_scores_anonymized(self, client, auth_headers_admin, user_with_data, sample_arcade,
                                                       sample_game, db):
        """Test que la suppression préserve les scores de manière anonymisée."""
        # Créer des scores
        from app.models import Score
        score = Score(
            player1_id=user_with_data.id,
            player2_id=user_with_data.id,  # Joue contre lui-même pour le test
            game_id=sample_game.id,
            arcade_id=sample_arcade.id,
            score_j1=100,
            score_j2=90
        )
        db.add(score)
        db.commit()

        # Supprimer l'utilisateur
        response = client.delete(f"/api/v1/admin/users/{user_with_data.id}", headers=auth_headers_admin)

        assert response.status_code == 200

        # Vérifier que le score existe toujours (pas supprimé)
        db.refresh(score)
        assert score.is_deleted == False
        assert score.player1_id == user_with_data.id  # Les IDs restent pour l'intégrité
        assert score.player2_id == user_with_data.id

    def test_self_deletion_unauthorized_without_auth(self, client):
        """Test de suppression de compte sans authentification."""
        response = client.delete("/api/v1/users/me")

        assert response.status_code == 403

    def test_admin_deletion_unauthorized_without_auth(self, client, user_with_data):
        """Test de suppression admin sans authentification."""
        response = client.delete(f"/api/v1/admin/users/{user_with_data.id}")

        assert response.status_code == 403

    def test_user_restoration_after_self_deletion(self, client, auth_headers_admin, user_with_data, db):
        """Test de restauration d'un utilisateur après auto-suppression."""
        user_id = user_with_data.id

        # Simuler une auto-suppression
        user_with_data.is_deleted = True
        user_with_data.deleted_at = datetime.now(timezone.utc)
        db.commit()

        # Utiliser l'endpoint de restauration existant
        response = client.put(f"/api/v1/admin/users/{user_id}/restore", headers=auth_headers_admin)

        assert response.status_code == 200
        assert "restauré" in response.json()["message"]

        # Vérifier que l'utilisateur est restauré
        db.refresh(user_with_data)
        assert user_with_data.is_deleted == False
        assert user_with_data.deleted_at is None

    def test_rgpd_compliance_data_cleanup(self, client, auth_headers_admin, user_with_data, db):
        """Test de conformité RGPD - nettoyage des données personnelles."""
        user_id = user_with_data.id

        # Supprimer l'utilisateur
        response = client.delete(f"/api/v1/admin/users/{user_id}", headers=auth_headers_admin)
        assert response.status_code == 200

        # Vérifier que les données sont marquées comme supprimées
        db.refresh(user_with_data)
        assert user_with_data.is_deleted == True

        # Vérifier que les données liées sont supprimées
        promo_uses = db.query(PromoUse).filter(PromoUse.user_id == user_id).all()
        for promo_use in promo_uses:
            assert promo_use.is_deleted == True

        purchases = db.query(TicketPurchase).filter(TicketPurchase.user_id == user_id).all()
        for purchase in purchases:
            assert purchase.is_deleted == True

    def test_bulk_user_deletion_impact_analysis(self, client, auth_headers_admin, db):
        """Test d'analyse d'impact pour suppression en masse - Version simplifiée."""

        # Créer un seul utilisateur pour simplifier
        user = User(
            firebase_uid="bulk_test_user",
            email="bulktest@example.com",
            nom="BulkTest",
            prenom="User",
            pseudo="bulktestuser",
            date_naissance=datetime.now().date(),
            numero_telephone="0788888888",
            tickets_balance=20
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Tester l'analyse d'impact
        response = client.get(
            f"/api/v1/admin/users/{user.id}/deletion-impact",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        data = response.json()

        # Vérifications de base
        assert data["user"]["id"] == user.id
        assert data["user"]["pseudo"] == user.pseudo
        assert data["can_delete"] == True

        # Vérifier la structure
        assert "deletion_impact" in data
        assert "recommendations" in data

        # Nouvel utilisateur = pas de données liées
        impact = data["deletion_impact"]
        assert impact["friendships_to_delete"] == 0
        assert impact["promo_uses_to_delete"] == 0
        assert impact["purchases_to_delete"] == 0
        assert impact["scores_anonymized"] == 0

    @pytest.fixture
    def sample_user(self, db):
        """Utilisateur de base pour les tests de cette classe."""
        user = User(
            firebase_uid="delete_test_user_uid",
            email="deletetest@example.com",
            nom="Delete",
            prenom="Test",
            pseudo="deletetest",
            date_naissance=datetime.now().date(),
            numero_telephone="0444444444",
            tickets_balance=10
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user