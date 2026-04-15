import pytest
from sqlalchemy import text
from datetime import datetime
from app.main import app
from app.api.v1.users import get_current_user
from app.models import User


class TestAdmin:
    """Tests pour les endpoints d'administration."""

    def test_create_arcade_success(self, client, auth_headers_admin):
        """Test de création de borne d'arcade réussie."""
        arcade_data = {
            "nom": "Nouvelle Borne",
            "description": "Une nouvelle borne de test",
            "localisation": "Test Location",
            "latitude": 43.6047,
            "longitude": 1.4442
        }

        response = client.post("/api/v1/admin/arcades/", json=arcade_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert "Borne créée" in data["message"]
        assert "arcade_id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("arcade_key_")

    def test_create_game_success(self, client, auth_headers_admin):
        """Test de création de jeu réussie."""
        game_data = {
            "nom": "Nouveau Jeu",
            "description": "Un nouveau jeu de test",
            "min_players": 1,
            "max_players": 4,
            "ticket_cost": 2
        }

        response = client.post("/api/v1/admin/games/", json=game_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert "Jeu créé" in data["message"]
        assert "game_id" in data

    def test_assign_game_to_arcade_success(self, client, auth_headers_admin, sample_arcade, sample_game):
        """Test d'assignation de jeu à une borne réussie."""
        assignment_data = {
            "arcade_id": sample_arcade.id,
            "game_id": sample_game.id,
            "slot_number": 1
        }

        response = client.put("/api/v1/admin/arcades/{}/games".format(sample_arcade.id),
                              json=assignment_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert "assigné" in data["message"]

    def test_assign_game_to_arcade_invalid_slot(self, client, auth_headers_admin, sample_arcade, sample_game):
        """Test d'assignation avec slot invalide."""
        assignment_data = {
            "arcade_id": sample_arcade.id,
            "game_id": sample_game.id,
            "slot_number": 5  # Slot invalide
        }

        response = client.put("/api/v1/admin/arcades/{}/games".format(sample_arcade.id),
                              json=assignment_data, headers=auth_headers_admin)

        assert response.status_code == 400
        assert "slot doit être 1 ou 2" in response.json()["detail"]

    def test_assign_game_arcade_not_found(self, client, auth_headers_admin, sample_game):
        """Test d'assignation avec borne inexistante."""
        assignment_data = {
            "arcade_id": 99999,
            "game_id": sample_game.id,
            "slot_number": 1
        }

        response = client.put("/api/v1/admin/arcades/99999/games",
                              json=assignment_data, headers=auth_headers_admin)

        assert response.status_code == 404
        assert "Borne non trouvée" in response.json()["detail"]

    def test_assign_game_not_found(self, client, auth_headers_admin, sample_arcade):
        """Test d'assignation avec jeu inexistant."""
        assignment_data = {
            "arcade_id": sample_arcade.id,
            "game_id": 99999,
            "slot_number": 1
        }

        response = client.put("/api/v1/admin/arcades/{}/games".format(sample_arcade.id),
                              json=assignment_data, headers=auth_headers_admin)

        assert response.status_code == 404
        assert "Jeu non trouvé" in response.json()["detail"]

    def test_create_promo_code_success(self, client, auth_headers_admin):
        """Test de création de code promo réussie."""
        promo_data = {
            "code": "ADMIN20",
            "tickets_reward": 20,
            "is_single_use_global": False,
            "is_single_use_per_user": True,
            "usage_limit": 100
        }

        response = client.post("/api/v1/admin/promo-codes/", json=promo_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert "Code promo créé" in data["message"]
        assert "promo_code_id" in data

    def test_create_promo_code_duplicate(self, client, auth_headers_admin, sample_promo_code):
        """Test de création de code promo avec code existant."""
        promo_data = {
            "code": sample_promo_code.code,  # Code déjà existant
            "tickets_reward": 10,
            "is_single_use_global": False,
            "is_single_use_per_user": True
        }

        response = client.post("/api/v1/admin/promo-codes/", json=promo_data, headers=auth_headers_admin)

        assert response.status_code == 400
        assert "code promo existe déjà" in response.json()["detail"]

    def test_list_promo_codes(self, client, auth_headers_admin, sample_promo_code):
        """Test de listage des codes promo."""
        response = client.get("/api/v1/admin/promo-codes/", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Vérifier que notre code de test est présent
        codes = [promo["code"] for promo in data]
        assert sample_promo_code.code in codes

    def test_update_user_tickets_add(self, client, auth_headers_admin, sample_user, db):
        """Test d'ajout de tickets à un utilisateur."""
        initial_balance = sample_user.tickets_balance

        update_data = {
            "user_id": sample_user.id,
            "tickets_to_add": 50
        }

        response = client.put("/api/v1/admin/users/tickets", json=update_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert data["old_balance"] == initial_balance
        assert data["new_balance"] == initial_balance + 50
        assert data["tickets_added"] == 50

        # Vérifier en base
        db.refresh(sample_user)
        assert sample_user.tickets_balance == initial_balance + 50

    def test_update_user_tickets_remove(self, client, auth_headers_admin, sample_user, db):
        """Test de retrait de tickets à un utilisateur."""
        # S'assurer que l'utilisateur a des tickets
        sample_user.tickets_balance = 100
        db.commit()

        update_data = {
            "user_id": sample_user.id,
            "tickets_to_add": -30
        }

        response = client.put("/api/v1/admin/users/tickets", json=update_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert data["old_balance"] == 100
        assert data["new_balance"] == 70
        assert data["tickets_added"] == -30

    def test_update_user_tickets_prevent_negative(self, client, auth_headers_admin, sample_user, db):
        """Test que le solde ne peut pas devenir négatif."""
        sample_user.tickets_balance = 10
        db.commit()

        update_data = {
            "user_id": sample_user.id,
            "tickets_to_add": -50  # Plus que le solde actuel
        }

        response = client.put("/api/v1/admin/users/tickets", json=update_data, headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert data["new_balance"] == 0  # Pas négatif

    def test_update_user_tickets_user_not_found(self, client, auth_headers_admin):
        """Test de mise à jour de tickets pour utilisateur inexistant."""
        update_data = {
            "user_id": 99999,
            "tickets_to_add": 10
        }

        response = client.put("/api/v1/admin/users/tickets", json=update_data, headers=auth_headers_admin)

        assert response.status_code == 404
        assert "Utilisateur non trouvé" in response.json()["detail"]

    def test_list_deleted_users_empty(self, client, auth_headers_admin):
        """Test de listage des utilisateurs supprimés vides."""
        response = client.get("/api/v1/admin/users/deleted", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_list_deleted_users_with_data(self, client, auth_headers_admin, sample_user, db):
        """Test de listage des utilisateurs supprimés avec données."""
        # Supprimer l'utilisateur (soft delete)
        sample_user.is_deleted = True
        user_id = sample_user.id
        if 'sqlite' in str(db.bind.dialect.name):
            now_func = "CURRENT_TIMESTAMP"
            now_str = db.execute(text(f"SELECT {now_func}")).scalar()
            sample_user.deleted_at = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
        else:
            sample_user.deleted_at = db.execute(text("SELECT NOW()")).scalar()
        db.commit()

        response = client.get("/api/v1/admin/users/deleted", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == user_id
        assert data[0]["is_deleted"] == True

    def test_restore_user_success(self, client, auth_headers_admin, sample_user, db):
        """Test de restauration d'utilisateur réussie."""
        # Supprimer l'utilisateur d'abord
        sample_user.is_deleted = True
        if 'sqlite' in str(db.bind.dialect.name):
            now_func = "CURRENT_TIMESTAMP"
            now_str = db.execute(text(f"SELECT {now_func}")).scalar()
            sample_user.deleted_at = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
        else:
            sample_user.deleted_at = db.execute(text("SELECT NOW()")).scalar()
        db.commit()


        response = client.put(f"/api/v1/admin/users/{sample_user.id}/restore", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()
        assert "restauré" in data["message"]

        # Vérifier en base
        db.refresh(sample_user)
        assert sample_user.is_deleted == False
        assert sample_user.deleted_at is None

    def test_restore_user_not_found(self, client, auth_headers_admin):
        """Test de restauration d'utilisateur inexistant."""
        response = client.put("/api/v1/admin/users/99999/restore", headers=auth_headers_admin)

        assert response.status_code == 404
        assert "Utilisateur non trouvé" in response.json()["detail"]
#
    def test_restore_user_not_deleted(self, client, auth_headers_admin, sample_user):
        """Test de restauration d'utilisateur non supprimé."""
        response = client.put(f"/api/v1/admin/users/{sample_user.id}/restore", headers=auth_headers_admin)

        assert response.status_code == 400
        assert "n'est pas supprimé" in response.json()["detail"]

    def test_get_admin_stats(self, client, auth_headers_admin, sample_user, sample_arcade, sample_game,
                             sample_promo_code):
        """Test de récupération des statistiques admin."""
        response = client.get("/api/v1/admin/stats", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()

        assert "active_users" in data
        assert "total_arcades" in data
        assert "total_games" in data
        assert "active_promo_codes" in data
        assert "total_tickets_in_circulation" in data
        assert "ticket_revenue" in data
        assert "top_games" in data
        assert "arcade_occupancy" in data
        assert "reservations_evolution" in data
        assert "timestamp" in data

        # Vérifications des valeurs
        assert data["active_users"] >= 1  # Au moins notre utilisateur de test
        assert data["total_arcades"] >= 1
        assert data["total_games"] >= 1
        assert data["active_promo_codes"] >= 1
        assert data["total_tickets_in_circulation"] >= 0
        assert "current_month" in data["ticket_revenue"]
        assert "previous_month" in data["ticket_revenue"]
        assert "currency" in data["ticket_revenue"]
        assert isinstance(data["top_games"], list)
        assert "occupancy_rate" in data["arcade_occupancy"]
        assert isinstance(data["arcade_occupancy"].get("arcades", []), list)
        assert isinstance(data["reservations_evolution"], list)

    # def test_admin_endpoints_unauthorized_user(self, client, auth_headers_user, sample_arcade, sample_game):
    #     """Test d'accès aux endpoints admin avec utilisateur normal."""
    #     endpoints_to_test = [
    #         ("POST", "/api/v1/admin/arcades/",
    #          {"nom": "Test", "description": "Test", "localisation": "Test", "latitude": 0, "longitude": 0}),
    #         ("POST", "/api/v1/admin/games/", {"nom": "Test", "description": "Test"}),
    #         ("POST", "/api/v1/admin/promo-codes/", {"code": "TEST", "tickets_reward": 5}),
    #         ("PUT", "/api/v1/admin/users/tickets", {"user_id": 1, "tickets_to_add": 10}),
    #         ("GET", "/api/v1/admin/users/deleted", None),
    #         ("PUT", "/api/v1/admin/users/1/restore", None),
    #         ("GET", "/api/v1/admin/stats", None),
    #         ("GET", "/api/v1/admin/promo-codes/", None)
    #     ]
    #
    #     for method, endpoint, json_data in endpoints_to_test:
    #         if method == "POST":
    #             response = client.post(endpoint, json=json_data, headers=auth_headers_user)
    #         elif method == "PUT":
    #             response = client.put(endpoint, json=json_data, headers=auth_headers_user)
    #         else:
    #             response = client.get(endpoint, headers=auth_headers_user)
    #
    #         # Devrait être refusé car utilisateur normal, pas admin
    #         assert response.status_code == 401

    def test_assign_game_replaces_existing(self, client, auth_headers_admin, sample_arcade, sample_game, db):
        """Test que l'assignation remplace le jeu existant sur un slot."""
        from app.models import Game, ArcadeGame

        # Créer un deuxième jeu
        game2 = Game(
            nom="Game 2",
            description="Deuxième jeu",
            min_players=1,
            max_players=2,
            ticket_cost=1
        )
        db.add(game2)
        db.commit()
        db.refresh(game2)

        # Assigner le premier jeu au slot 1
        assignment1 = {
            "arcade_id": sample_arcade.id,
            "game_id": sample_game.id,
            "slot_number": 1
        }

        response1 = client.put(f"/api/v1/admin/arcades/{sample_arcade.id}/games",
                               json=assignment1, headers=auth_headers_admin)
        assert response1.status_code == 200

        # Assigner le deuxième jeu au même slot (devrait remplacer)
        assignment2 = {
            "arcade_id": sample_arcade.id,
            "game_id": game2.id,
            "slot_number": 1
        }

        response2 = client.put(f"/api/v1/admin/arcades/{sample_arcade.id}/games",
                               json=assignment2, headers=auth_headers_admin)
        assert response2.status_code == 200

        # Vérifier qu'il n'y a qu'un seul jeu sur le slot 1
        arcade_games = db.query(ArcadeGame).filter(
            ArcadeGame.arcade_id == sample_arcade.id,
            ArcadeGame.slot_number == 1
        ).all()

        assert len(arcade_games) == 1
        assert arcade_games[0].game_id == game2.id

    # def test_promo_code_case_handling(self, client, auth_headers_admin):
    #     """Test que les codes promo sont automatiquement en majuscules."""
    #     promo_data = {
    #         "code": "lowercase",  # En minuscules
    #         "tickets_reward": 5,
    #         "is_single_use_per_user": True
    #     }
    #
    #     response = client.post("/api/v1/admin/promo-codes/", json=promo_data, headers=auth_headers_admin)
    #
    #     assert response.status_code == 200
    #
    #     # Vérifier que le code a été stocké en majuscules
    #     from app.models import PromoCode
    #     promo = db.query(PromoCode).filter(PromoCode.code == "LOWERCASE").first()
    #     assert promo is not None

    def test_admin_stats_consistency(self, client, auth_headers_admin, db):
        """Test de cohérence des statistiques admin."""
        from app.models import User, Arcade, Game, PromoCode

        # Compter manuellement les éléments
        active_users_count = db.query(User).filter(User.is_deleted == False).count()
        arcades_count = db.query(Arcade).filter(Arcade.is_deleted == False).count()
        games_count = db.query(Game).filter(Game.is_deleted == False).count()
        promo_codes_count = db.query(PromoCode).filter(PromoCode.is_deleted == False).count()

        response = client.get("/api/v1/admin/stats", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json()

        # Vérifier la cohérence
        assert data["active_users"] == active_users_count
        assert data["total_arcades"] == arcades_count
        assert data["total_games"] == games_count
        assert data["active_promo_codes"] == promo_codes_count
        assert data["arcade_occupancy"]["total_arcades"] == arcades_count