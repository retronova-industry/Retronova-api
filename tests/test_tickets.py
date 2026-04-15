import pytest
from unittest.mock import MagicMock, patch


class TestTickets:
    """Tests pour les endpoints de tickets."""

    def test_get_ticket_offers(self, client, sample_ticket_offer):
        """Test de récupération des offres de tickets."""
        response = client.get("/api/v1/tickets/offers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        offer_found = False
        for offer in data:
            if offer["id"] == sample_ticket_offer.id:
                assert offer["tickets_amount"] == sample_ticket_offer.tickets_amount
                assert offer["price_euros"] == sample_ticket_offer.price_euros
                assert offer["name"] == sample_ticket_offer.name
                offer_found = True
                break

        assert offer_found, "L'offre de test n'a pas été trouvée"

    def test_purchase_tickets_success(self, client, auth_headers_user, sample_user, sample_ticket_offer, db):
        """Test de création de session Stripe réussie."""
        initial_balance = sample_user.tickets_balance

        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        fake_session = MagicMock()
        fake_session.id = "cs_test_123"
        fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"

        with patch("app.api.v1.tickets.stripe.checkout.Session.create", return_value=fake_session):
            response = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()

        assert "purchase_id" in data
        assert data["checkout_session_id"] == "cs_test_123"
        assert data["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_123"
        assert data["status"] == "pending"

        db.refresh(sample_user)
        assert sample_user.tickets_balance == initial_balance

    def test_purchase_tickets_invalid_offer(self, client, auth_headers_user):
        """Test d'achat avec offre inexistante."""
        purchase_data = {
            "offer_id": 99999
        }

        response = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)

        assert response.status_code == 404
        assert "Offre de tickets non trouvée" in response.json()["detail"]

    def test_get_ticket_balance(self, client, auth_headers_user, sample_user):
        """Test de récupération du solde de tickets."""
        response = client.get("/api/v1/tickets/balance", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["balance"] == sample_user.tickets_balance

    def test_get_purchase_history_empty(self, client, auth_headers_user):
        """Test de récupération de l'historique vide."""
        response = client.get("/api/v1/tickets/history", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_purchase_status_pending(self, client, auth_headers_user, sample_ticket_offer):
        """Test de récupération du statut d'un achat en attente."""
        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        fake_create_session = MagicMock()
        fake_create_session.id = "cs_test_456"
        fake_create_session.url = "https://checkout.stripe.com/c/pay/cs_test_456"

        with patch("app.api.v1.tickets.stripe.checkout.Session.create", return_value=fake_create_session):
            purchase_response = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)

        assert purchase_response.status_code == 200
        purchase_id = purchase_response.json()["purchase_id"]

        fake_retrieve_session = MagicMock()
        fake_retrieve_session.status = "open"
        fake_retrieve_session.payment_status = "unpaid"

        with patch("app.api.v1.tickets.stripe.checkout.Session.retrieve", return_value=fake_retrieve_session):
            status_response = client.get(
                f"/api/v1/tickets/purchase/{purchase_id}/status",
                headers=auth_headers_user
            )

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["purchase_id"] == purchase_id
        assert data["status"] == "pending"
        assert data["tickets_received"] == sample_ticket_offer.tickets_amount
        assert data["amount_paid"] == sample_ticket_offer.price_euros
        assert data["stripe_checkout_session_id"] == "cs_test_456"
        assert data["stripe_session_status"] == "open"
        assert data["stripe_payment_status"] == "unpaid"
        assert data["is_paid"] is False

    def test_get_purchase_history_with_purchases(self, client, auth_headers_user, sample_user, sample_ticket_offer, db):
        """Test de récupération de l'historique avec achats."""
        from app.models import TicketPurchase

        user_id = sample_user.id

        purchase = TicketPurchase(
            user_id=user_id,
            offer_id=sample_ticket_offer.id,
            tickets_received=sample_ticket_offer.tickets_amount,
            amount_paid=sample_ticket_offer.price_euros,
            stripe_payment_id="test_payment_123",
            stripe_checkout_session_id="cs_test_history",
            status="pending",
        )
        db.add(purchase)
        db.commit()

        response = client.get("/api/v1/tickets/history", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == user_id
        assert data[0]["tickets_received"] == sample_ticket_offer.tickets_amount
        assert data[0]["status"] == "pending"

    def test_purchase_creates_history_entry(self, client, auth_headers_user, sample_user, sample_ticket_offer, db):
        """Test que la création d'achat crée bien une entrée d'historique pending."""
        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        fake_session = MagicMock()
        fake_session.id = "cs_test_history_create"
        fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_history_create"

        with patch("app.api.v1.tickets.stripe.checkout.Session.create", return_value=fake_session):
            response = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)

        assert response.status_code == 200

        history_response = client.get("/api/v1/tickets/history", headers=auth_headers_user)
        assert history_response.status_code == 200

        history = history_response.json()
        assert len(history) == 1
        assert history[0]["tickets_received"] == sample_ticket_offer.tickets_amount
        assert history[0]["amount_paid"] == sample_ticket_offer.price_euros
        assert history[0]["status"] == "pending"

    def test_tickets_endpoints_unauthorized(self, client, sample_ticket_offer):
        """Test d'accès non autorisé aux endpoints nécessitant l'authentification."""
        protected_endpoints = [
            ("POST", "/api/v1/tickets/purchase", {"offer_id": sample_ticket_offer.id}),
            ("GET", "/api/v1/tickets/balance", None),
            ("GET", "/api/v1/tickets/history", None),
        ]

        for method, endpoint, json_data in protected_endpoints:
            if method == "POST":
                response = client.post(endpoint, json=json_data)
            else:
                response = client.get(endpoint)

            assert response.status_code == 403

    def test_multiple_purchases_create_multiple_pending_entries(
        self,
        client,
        auth_headers_user,
        sample_user,
        sample_ticket_offer,
        db,
    ):
        """Test que plusieurs achats créent plusieurs entrées pending sans crédit immédiat."""
        initial_balance = sample_user.tickets_balance

        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        fake_session_1 = MagicMock()
        fake_session_1.id = "cs_test_multi_1"
        fake_session_1.url = "https://checkout.stripe.com/c/pay/cs_test_multi_1"

        fake_session_2 = MagicMock()
        fake_session_2.id = "cs_test_multi_2"
        fake_session_2.url = "https://checkout.stripe.com/c/pay/cs_test_multi_2"

        with patch(
            "app.api.v1.tickets.stripe.checkout.Session.create",
            side_effect=[fake_session_1, fake_session_2],
        ):
            response1 = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)
            response2 = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["status"] == "pending"
        assert data2["status"] == "pending"
        assert data1["checkout_session_id"] == "cs_test_multi_1"
        assert data2["checkout_session_id"] == "cs_test_multi_2"

        db.refresh(sample_user)
        assert sample_user.tickets_balance == initial_balance

        history_response = client.get("/api/v1/tickets/history", headers=auth_headers_user)
        assert history_response.status_code == 200
        history = history_response.json()

        assert len(history) == 2
        assert all(item["status"] == "pending" for item in history)