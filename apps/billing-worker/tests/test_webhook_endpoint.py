import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch("billing_worker.main.settings") as mock_settings:
        mock_settings.stripe_secret_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test_123"
        mock_settings.database_url = "postgresql+asyncpg://localhost/test"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.port = 8082

        from billing_worker.main import app
        yield TestClient(app)


class TestHealthEndpoint:
    def test_healthz_returns_ok(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestStripeWebhookEndpoint:
    @patch("billing_worker.main._session_factory")
    @patch("billing_worker.main._redis")
    @patch("billing_worker.main.stripe")
    def test_valid_webhook_dispatches_handler(self, mock_stripe, mock_redis_global, mock_sf, client):
        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"
        mock_event.id = "evt_123"
        mock_stripe.Webhook.construct_event.return_value = mock_event

        mock_db = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = mock_session_ctx

        with patch("billing_worker.main.EVENT_HANDLERS") as mock_handlers:
            mock_handler = AsyncMock()
            mock_handlers.get.return_value = mock_handler

            resp = client.post(
                "/webhooks/stripe",
                content=b'{"test": true}',
                headers={"stripe-signature": "t=123,v1=abc"},
            )

            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
            mock_stripe.Webhook.construct_event.assert_called_once()

    @patch("billing_worker.main.stripe")
    def test_invalid_signature_returns_400(self, mock_stripe, client):
        mock_stripe.Webhook.construct_event.side_effect = mock_stripe.error.SignatureVerificationError(
            "Invalid signature", "sig"
        )
        mock_stripe.error.SignatureVerificationError = type(
            "SignatureVerificationError", (Exception,), {}
        )
        mock_stripe.Webhook.construct_event.side_effect = mock_stripe.error.SignatureVerificationError(
            "bad sig"
        )

        resp = client.post(
            "/webhooks/stripe",
            content=b'{"test": true}',
            headers={"stripe-signature": "t=123,v1=bad"},
        )

        assert resp.status_code == 400

    @patch("billing_worker.main.stripe")
    def test_invalid_payload_returns_400(self, mock_stripe, client):
        mock_stripe.Webhook.construct_event.side_effect = ValueError("bad json")

        resp = client.post(
            "/webhooks/stripe",
            content=b'not json',
            headers={"stripe-signature": "t=123,v1=abc"},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid payload"

    @patch("billing_worker.main._session_factory")
    @patch("billing_worker.main._redis")
    @patch("billing_worker.main.stripe")
    def test_unhandled_event_type_returns_ignored(self, mock_stripe, mock_redis_global, mock_sf, client):
        mock_event = MagicMock()
        mock_event.type = "some.unknown.event"
        mock_event.id = "evt_456"
        mock_stripe.Webhook.construct_event.return_value = mock_event

        resp = client.post(
            "/webhooks/stripe",
            content=b'{"test": true}',
            headers={"stripe-signature": "t=123,v1=abc"},
        )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ignored"}

    def test_missing_signature_header_returns_422(self, client):
        resp = client.post(
            "/webhooks/stripe",
            content=b'{"test": true}',
        )

        assert resp.status_code == 422

    @patch("billing_worker.main._session_factory")
    @patch("billing_worker.main._redis")
    @patch("billing_worker.main.stripe")
    def test_handler_exception_returns_500(self, mock_stripe, mock_redis_global, mock_sf, client):
        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"
        mock_event.id = "evt_789"
        mock_stripe.Webhook.construct_event.return_value = mock_event

        mock_db = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = mock_session_ctx

        with patch("billing_worker.main.EVENT_HANDLERS") as mock_handlers:
            mock_handler = AsyncMock(side_effect=RuntimeError("db exploded"))
            mock_handlers.get.return_value = mock_handler

            resp = client.post(
                "/webhooks/stripe",
                content=b'{"test": true}',
                headers={"stripe-signature": "t=123,v1=abc"},
            )

            assert resp.status_code == 500
