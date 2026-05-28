import pytest
from unittest.mock import patch
import datetime


class TestScores:
    """Tests pour les endpoints de scores."""

    @pytest.fixture
    def player2(self, db):
        """Deuxième joueur pour les tests de scores."""
        from app.models import User
        player = User(
            firebase_uid="player2_score_uid",
            email="player2score@example.com",
            nom="Player2",
            prenom="Score",
            pseudo="player2score",
            date_naissance=datetime.date(1990, 1, 1),
            numero_telephone="0222222222",
            tickets_balance=0
        )
        db.add(player)
        db.commit()
        db.refresh(player)
        return player

    def test_create_score_success(self, client, arcade_api_headers, sample_user, player2, sample_game, sample_arcade):
        """Test de création de score réussie."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": player2.id,
            "game_id": sample_game.id,
            "arcade_id": sample_arcade.id,
            "score_j1": 150,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["player1_pseudo"] == sample_user.pseudo
        assert data["player2_pseudo"] == player2.pseudo
        assert data["game_name"] == sample_game.nom
        assert data["arcade_name"] == sample_arcade.nom
        assert data["score_j1"] == 150
        assert data["score_j2"] == 120
        assert data["winner_pseudo"] == sample_user.pseudo  # J1 gagne

    def test_create_score_draw(self, client, arcade_api_headers, sample_user, player2, sample_game, sample_arcade):
        """Test de création de score avec égalité."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": player2.id,
            "game_id": sample_game.id,
            "arcade_id": sample_arcade.id,
            "score_j1": 100,
            "score_j2": 100
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["winner_pseudo"] == "Égalité"

    def test_create_score_player2_wins(self, client, arcade_api_headers, sample_user, player2, sample_game,
                                       sample_arcade):
        """Test de création de score avec victoire du joueur 2."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": player2.id,
            "game_id": sample_game.id,
            "arcade_id": sample_arcade.id,
            "score_j1": 80,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["winner_pseudo"] == player2.pseudo

    def test_create_score_unauthorized(self, client, sample_user, player2, sample_game, sample_arcade):
        """Test de création de score sans clé API."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": player2.id,
            "game_id": sample_game.id,
            "arcade_id": sample_arcade.id,
            "score_j1": 150,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data)

        assert response.status_code == 401
        assert "Clé API borne invalide" in response.json()["detail"]

    def test_create_score_player_not_found(self, client, arcade_api_headers, sample_game, sample_arcade):
        """Test de création avec joueur inexistant."""
        score_data = {
            "player1_id": 99999,
            "player2_id": 99998,
            "game_id": sample_game.id,
            "arcade_id": sample_arcade.id,
            "score_j1": 150,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 404
        assert "Joueur 1 non trouvé" in response.json()["detail"]

    def test_create_score_same_players(self, client, arcade_api_headers, sample_user, sample_game, sample_arcade):
        """Test de création avec les mêmes joueurs."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": sample_user.id,
            "game_id": sample_game.id,
            "arcade_id": sample_arcade.id,
            "score_j1": 150,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 400
        assert "identiques" in response.json()["detail"]

    def test_create_score_game_not_found(self, client, arcade_api_headers, sample_user, player2, sample_arcade):
        """Test de création avec jeu inexistant."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": player2.id,
            "game_id": 99999,
            "arcade_id": sample_arcade.id,
            "score_j1": 150,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 404
        assert "Jeu non trouvé" in response.json()["detail"]

    def test_create_score_arcade_not_found(self, client, arcade_api_headers, sample_user, player2, sample_game):
        """Test de création avec borne inexistante."""
        score_data = {
            "player1_id": sample_user.id,
            "player2_id": player2.id,
            "game_id": sample_game.id,
            "arcade_id": 99999,
            "score_j1": 150,
            "score_j2": 120
        }

        response = client.post("/api/v1/scores/", json=score_data, headers=arcade_api_headers)

        assert response.status_code == 404
        assert "Borne d'arcade non trouvée" in response.json()["detail"]

    def test_get_scores_empty(self, client, auth_headers_user):
        """Test de récupération des scores vides."""
        response = client.get("/api/v1/scores/", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_scores_with_data(self, client, auth_headers_user, sample_user, player2, sample_game, sample_arcade,
                                  db):
        """Test de récupération des scores avec données."""
        from app.models import Score

        # Créer quelques scores
        scores = [
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=150,
                score_j2=120
            ),
            Score(
                player1_id=player2.id,
                player2_id=sample_user.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=90,
                score_j2=110
            )
        ]

        for score in scores:
            db.add(score)
        db.commit()

        response = client.get("/api/v1/scores/", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_scores_filter_by_game(self, client, auth_headers_user, sample_user, player2, sample_game,
                                       sample_arcade, db):
        """Test de filtrage des scores par jeu."""
        from app.models import Score, Game

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

        # Créer des scores pour les deux jeux
        scores = [
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=150,
                score_j2=120
            ),
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=game2.id,
                arcade_id=sample_arcade.id,
                score_j1=200,
                score_j2=180
            )
        ]

        for score in scores:
            db.add(score)
        db.commit()

        # Filtrer par le premier jeu
        response = client.get(f"/api/v1/scores/?game_id={sample_game.id}", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["game_name"] == sample_game.nom

    def test_get_scores_filter_by_arcade(self, client, auth_headers_user, sample_user, player2, sample_game,
                                         sample_arcade, db):
        """Test de filtrage des scores par borne."""
        from app.models import Score, Arcade

        # Créer une deuxième borne
        arcade2 = Arcade(
            nom="Arcade 2",
            description="Deuxième borne",
            api_key="test_key_2",
            localisation="Location 2",
            latitude=44.0,
            longitude=2.0
        )
        db.add(arcade2)
        db.commit()
        db.refresh(arcade2)

        # Créer des scores pour les deux bornes
        scores = [
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=150,
                score_j2=120
            ),
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=arcade2.id,
                score_j1=200,
                score_j2=180
            )
        ]

        for score in scores:
            db.add(score)
        db.commit()

        # Filtrer par la première borne
        response = client.get(f"/api/v1/scores/?arcade_id={sample_arcade.id}", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["arcade_name"] == sample_arcade.nom

    def test_get_scores_friends_only_empty(self, client, auth_headers_user, sample_user):
        """Test de filtrage par amis quand on n'a pas d'amis."""
        response = client.get("/api/v1/scores/?friends_only=true", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_scores_friends_only_with_friend(self, client, auth_headers_user, sample_user, player2, sample_game,
                                                 sample_arcade, db):
        """Test de filtrage par amis avec un ami."""
        from app.models import Score, Friendship, FriendshipStatus

        # Créer une amitié
        friendship = Friendship(
            requester_id=sample_user.id,
            requested_id=player2.id,
            status=FriendshipStatus.ACCEPTED
        )
        db.add(friendship)

        # Créer un score entre amis
        score = Score(
            player1_id=sample_user.id,
            player2_id=player2.id,
            game_id=sample_game.id,
            arcade_id=sample_arcade.id,
            score_j1=150,
            score_j2=120
        )

        player1_pseudo = sample_user.pseudo
        player2_pseudo = player2.pseudo

        db.add(score)
        db.commit()

        response = client.get("/api/v1/scores/?friends_only=true", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["player1_pseudo"] == player1_pseudo
        assert data[0]["player2_pseudo"] == player2_pseudo

    def test_get_scores_limit(self, client, auth_headers_user, sample_user, player2, sample_game, sample_arcade, db):
        """Test de limitation du nombre de scores."""
        from app.models import Score

        # Créer plusieurs scores
        for i in range(10):
            score = Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=100 + i,
                score_j2=90 + i
            )
            db.add(score)
        db.commit()

        # Limiter à 5 résultats
        response = client.get("/api/v1/scores/?limit=5", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    def test_get_my_stats_no_games(self, client, auth_headers_user):
        """Test des statistiques sans parties jouées."""
        response = client.get("/api/v1/scores/my-stats", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 0
        assert data["wins"] == 0
        assert data["losses"] == 0
        assert data["draws"] == 0
        assert data["win_rate"] == 0

    def test_get_my_stats_with_games(self, client, auth_headers_user, sample_user, player2, sample_game, sample_arcade,
                                     db):
        """Test des statistiques avec parties jouées."""
        from app.models import Score

        # Créer différents types de scores
        scores = [
            # Victoire (en tant que player1)
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=150,
                score_j2=120
            ),
            # Défaite (en tant que player1)
            Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=90,
                score_j2=120
            ),
            # Égalité (en tant que player2)
            Score(
                player1_id=player2.id,
                player2_id=sample_user.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=100,
                score_j2=100
            ),
            # Victoire (en tant que player2)
            Score(
                player1_id=player2.id,
                player2_id=sample_user.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=80,
                score_j2=120
            )
        ]

        for score in scores:
            db.add(score)
        db.commit()

        response = client.get("/api/v1/scores/my-stats", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 4
        assert data["wins"] == 2  # 2 victoires
        assert data["losses"] == 1  # 1 défaite
        assert data["draws"] == 1  # 1 égalité
        assert data["win_rate"] == pytest.approx(50.0)  # 2/4 * 100

    def test_scores_endpoints_unauthorized(self, client, sample_user, player2, sample_game, sample_arcade):
        """Test d'accès non autorisé aux endpoints de scores."""
        protected_endpoints = [
            ("GET", "/api/v1/scores/", None),
            ("GET", "/api/v1/scores/my-stats", None)
        ]

        for method, endpoint, json_data in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 403

    def test_scores_ordered_by_date(self, client, auth_headers_user, sample_user, player2, sample_game, sample_arcade,
                                    db):
        """Test que les scores sont triés par date décroissante."""
        from app.models import Score
        import time

        # Créer plusieurs scores avec des délais
        for i in range(3):
            score = Score(
                player1_id=sample_user.id,
                player2_id=player2.id,
                game_id=sample_game.id,
                arcade_id=sample_arcade.id,
                score_j1=100 + i,
                score_j2=90
            )
            db.add(score)
            db.commit()
            if i < 2:
                time.sleep(0.01)  # Petit délai pour différencier les timestamps

        response = client.get("/api/v1/scores/", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Le plus récent devrait être en premier (score 102)
        assert data[0]["score_j1"] == 100
        assert data[1]["score_j1"] == 101
        assert data[2]["score_j1"] == 102