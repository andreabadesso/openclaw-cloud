from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TEST_CUSTOMER_ID


@pytest.mark.anyio
async def test_portal_session(client, seed_customer, db):
    from openclaw_api.models import Customer
    from sqlalchemy import select

    result = await db.execute(select(Customer).where(Customer.id == TEST_CUSTOMER_ID))
    customer = result.scalar_one()
    customer.stripe_customer_id = "cus_test123"
    await db.commit()

    mock_session = MagicMock()
    mock_session.url = "https://billing.stripe.com/session/test"

    with patch("openclaw_api.routes.billing.stripe") as mock_stripe:
        mock_stripe.billing_portal.Session.create.return_value = mock_session
        resp = await client.post("/billing/portal-session")

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://billing.stripe.com/session/test"


@pytest.mark.anyio
async def test_portal_session_no_stripe_id(client, seed_customer):
    resp = await client.post("/billing/portal-session")
    assert resp.status_code == 400
    assert "no billing account" in resp.json()["detail"]


@pytest.mark.anyio
async def test_portal_session_customer_not_found(client):
    resp = await client.post("/billing/portal-session")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_stripe_webhook_valid(client):
    mock_event = {"type": "invoice.paid", "id": "evt_123"}

    with patch("openclaw_api.routes.billing.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = mock_event
        resp = await client.post(
            "/billing/webhooks/stripe",
            content=b'{"type": "invoice.paid"}',
            headers={"stripe-signature": "sig_test"},
        )

    assert resp.status_code == 200
    assert resp.json()["type"] == "invoice.paid"


@pytest.mark.anyio
async def test_stripe_webhook_invalid_payload(client):
    with patch("openclaw_api.routes.billing.stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.side_effect = ValueError("bad")
        resp = await client.post(
            "/billing/webhooks/stripe",
            content=b"not json",
            headers={"stripe-signature": "sig_test"},
        )

    assert resp.status_code == 400
    assert "Invalid payload" in resp.json()["detail"]


@pytest.mark.anyio
async def test_stripe_webhook_invalid_signature(client):
    with patch("openclaw_api.routes.billing.stripe") as mock_stripe:
        mock_stripe.error.SignatureVerificationError = type("SigError", (Exception,), {})
        mock_stripe.Webhook.construct_event.side_effect = mock_stripe.error.SignatureVerificationError("bad sig")
        resp = await client.post(
            "/billing/webhooks/stripe",
            content=b'{"type": "test"}',
            headers={"stripe-signature": "bad_sig"},
        )

    assert resp.status_code == 400
    assert "Invalid signature" in resp.json()["detail"]
