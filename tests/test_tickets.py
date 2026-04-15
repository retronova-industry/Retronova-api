import pytest


class TestTickets:
    """Tests pour les endpoints de tickets."""

    def test_get_ticket_offers(self, client, sample_ticket_offer):
        """Test de récupération des offres de tickets."""
        response = client.get("/api/v1/tickets/offers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        # Vérifier que notre offre de test est présente
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
        """Test d'achat de tickets réussi."""
        initial_balance = sample_user.tickets_balance

        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        response = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["tickets_received"] == sample_ticket_offer.tickets_amount
        assert data["amount_paid"] == sample_ticket_offer.price_euros
        assert data["new_balance"] == initial_balance + sample_ticket_offer.tickets_amount

        # Vérifier que le solde a bien été mis à jour en base
        db.refresh(sample_user)
        assert sample_user.tickets_balance == initial_balance + sample_ticket_offer.tickets_amount

    def test_purchase_tickets_invalid_offer(self, client, auth_headers_user):
        """Test d'achat avec offre inexistante."""
        purchase_data = {
            "offer_id": 99999  # ID inexistant
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

    def test_get_purchase_history_with_purchases(self, client, auth_headers_user, sample_user, sample_ticket_offer, db):
        """Test de récupération de l'historique avec achats."""
        from app.models import TicketPurchase

        # On capture l'ID utilisateur immédiatement
        user_id = sample_user.id

        purchase = TicketPurchase(
            user_id=user_id,
            offer_id=sample_ticket_offer.id,
            tickets_received=sample_ticket_offer.tickets_amount,
            amount_paid=sample_ticket_offer.price_euros,
            stripe_payment_id="test_payment_123"
        )
        db.add(purchase)
        db.commit()

        response = client.get("/api/v1/tickets/history", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == user_id  # On utilise l'id capturé

    def test_purchase_creates_history_entry(self, client, auth_headers_user, sample_user, sample_ticket_offer, db):
        """Test que l'achat crée bien une entrée dans l'historique."""
        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        # Effectuer l'achat
        response = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)
        assert response.status_code == 200

        # Vérifier l'historique
        response = client.get("/api/v1/tickets/history", headers=auth_headers_user)
        assert response.status_code == 200

        history = response.json()
        assert len(history) == 1
        assert history[0]["tickets_received"] == sample_ticket_offer.tickets_amount

    def test_tickets_endpoints_unauthorized(self, client, sample_ticket_offer):
        """Test d'accès non autorisé aux endpoints nécessitant l'authentification."""
        protected_endpoints = [
            ("POST", "/api/v1/tickets/purchase", {"offer_id": sample_ticket_offer.id}),
            ("GET", "/api/v1/tickets/balance", None),
            ("GET", "/api/v1/tickets/history", None)
        ]

        for method, endpoint, json_data in protected_endpoints:
            if method == "POST":
                response = client.post(endpoint, json=json_data)
            else:
                response = client.get(endpoint)

            assert response.status_code == 403

    def test_multiple_purchases_accumulate_balance(self, client, auth_headers_user, sample_user, sample_ticket_offer,
                                                   db):
        """Test que plusieurs achats cumulent bien le solde."""
        initial_balance = sample_user.tickets_balance

        purchase_data = {
            "offer_id": sample_ticket_offer.id
        }

        # Premier achat
        response1 = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)
        assert response1.status_code == 200
        expected_balance_1 = initial_balance + sample_ticket_offer.tickets_amount
        assert response1.json()["new_balance"] == expected_balance_1

        # Deuxième achat
        response2 = client.post("/api/v1/tickets/purchase", json=purchase_data, headers=auth_headers_user)
        assert response2.status_code == 200
        expected_balance_2 = expected_balance_1 + sample_ticket_offer.tickets_amount
        assert response2.json()["new_balance"] == expected_balance_2

        # Vérifier le solde final
        db.refresh(sample_user)
        assert sample_user.tickets_balance == expected_balance_2