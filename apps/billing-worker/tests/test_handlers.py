from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from billing_worker.handlers import (
    handle_checkout_session_completed,
    handle_invoice_payment_failed,
    handle_invoice_payment_succeeded,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from tests.conftest import make_db_row, make_empty_result, make_stripe_event


# ---------------------------------------------------------------------------
# checkout.session.completed
# ---------------------------------------------------------------------------

class TestCheckoutSessionCompleted:
    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_creates_subscription_and_enqueues_provision(self, mock_stripe, mock_db, mock_redis):
        mock_stripe.Subscription.retrieve.return_value = {
            "items": {"data": [{"price": {"id": "price_123", "product": "prod_123"}}]},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }
        mock_stripe.Product.retrieve.return_value = MagicMock(
            metadata={"tier": "pro", "tokens_limit": "5000000"}
        )

        event = make_stripe_event("checkout.session.completed", {
            "metadata": {"openclaw_customer_id": "cust-001"},
            "subscription": "sub_123",
            "customer": "cus_stripe_123",
        })

        # First execute: UPDATE customers (no return needed)
        # Second execute: SELECT subscription (not found = new)
        # Third execute: INSERT subscription
        # Fourth execute: INSERT usage_monthly
        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(),              # UPDATE customers
            make_empty_result(),       # SELECT subscription (not found)
            MagicMock(),              # INSERT subscription
            MagicMock(),              # INSERT usage_monthly
        ])

        await handle_checkout_session_completed(event, mock_db, mock_redis)

        # Verify subscription was created
        assert mock_db.execute.call_count == 4
        mock_db.commit.assert_called_once()

        # Verify provision job enqueued
        mock_redis.rpush.assert_called_once()
        call_args = mock_redis.rpush.call_args
        assert call_args[0][0] == "operator:jobs"
        import json
        job = json.loads(call_args[0][1])
        assert job["type"] == "provision"
        assert job["customer_id"] == "cust-001"
        assert job["payload"]["tier"] == "pro"

    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_skips_duplicate_subscription(self, mock_stripe, mock_db, mock_redis):
        mock_stripe.Subscription.retrieve.return_value = {
            "items": {"data": [{"price": {"id": "price_123", "product": "prod_123"}}]},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }
        mock_stripe.Product.retrieve.return_value = MagicMock(
            metadata={"tier": "starter", "tokens_limit": "1000000"}
        )

        event = make_stripe_event("checkout.session.completed", {
            "metadata": {"openclaw_customer_id": "cust-001"},
            "subscription": "sub_123",
            "customer": "cus_stripe_123",
        })

        # Subscription already exists
        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(),                                 # UPDATE customers
            make_db_row("existing-sub-id"),               # SELECT subscription (found)
        ])

        await handle_checkout_session_completed(event, mock_db, mock_redis)

        # Should NOT insert subscription or enqueue job
        assert mock_db.execute.call_count == 2
        mock_redis.rpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_customer_id_in_metadata(self, mock_db, mock_redis):
        event = make_stripe_event("checkout.session.completed", {
            "metadata": {},
            "subscription": "sub_123",
            "customer": "cus_stripe_123",
        })

        await handle_checkout_session_completed(event, mock_db, mock_redis)

        mock_db.execute.assert_not_called()
        mock_redis.rpush.assert_not_called()


# ---------------------------------------------------------------------------
# invoice.payment_succeeded
# ---------------------------------------------------------------------------

class TestInvoicePaymentSucceeded:
    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_resets_token_counter(self, mock_stripe, mock_db, mock_redis):
        mock_stripe.Subscription.retrieve.return_value = {
            "current_period_start": 1703000000,
            "current_period_end": 1705592000,
        }

        event = make_stripe_event("invoice.payment_succeeded", {
            "id": "inv_123",
            "subscription": "sub_123",
            "billing_reason": "subscription_cycle",
            "attempt_count": 1,
        })

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001", "pro", 5_000_000),  # SELECT subscription
            MagicMock(),                                              # UPDATE subscription period
            MagicMock(),                                              # INSERT usage_monthly
            make_db_row("active"),                                    # SELECT status
        ])

        await handle_invoice_payment_succeeded(event, mock_db, mock_redis)

        assert mock_db.commit.call_count == 1
        # Not suspended, so no reactivate job
        mock_redis.rpush.assert_not_called()

    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_reactivates_suspended_subscription(self, mock_stripe, mock_db, mock_redis):
        mock_stripe.Subscription.retrieve.return_value = {
            "current_period_start": 1703000000,
            "current_period_end": 1705592000,
        }

        event = make_stripe_event("invoice.payment_succeeded", {
            "id": "inv_123",
            "subscription": "sub_123",
            "billing_reason": "subscription_cycle",
            "attempt_count": 1,
        })

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001", "pro", 5_000_000),  # SELECT subscription
            MagicMock(),                                              # UPDATE subscription period
            MagicMock(),                                              # INSERT usage_monthly
            make_db_row("suspended"),                                  # SELECT status
            MagicMock(),                                              # UPDATE status to active
            make_db_row("box-001"),                                   # SELECT box
        ])

        await handle_invoice_payment_succeeded(event, mock_db, mock_redis)

        import json
        mock_redis.rpush.assert_called_once()
        job = json.loads(mock_redis.rpush.call_args[0][1])
        assert job["type"] == "reactivate"
        assert job["customer_id"] == "cust-001"

    @pytest.mark.asyncio
    async def test_skips_initial_subscription_invoice(self, mock_db, mock_redis):
        event = make_stripe_event("invoice.payment_succeeded", {
            "id": "inv_123",
            "subscription": "sub_123",
            "billing_reason": "subscription_create",
            "attempt_count": 1,
        })

        await handle_invoice_payment_succeeded(event, mock_db, mock_redis)

        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_invoice_without_subscription(self, mock_db, mock_redis):
        event = make_stripe_event("invoice.payment_succeeded", {
            "id": "inv_123",
            "subscription": None,
            "billing_reason": "manual",
            "attempt_count": 1,
        })

        await handle_invoice_payment_succeeded(event, mock_db, mock_redis)

        mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# invoice.payment_failed
# ---------------------------------------------------------------------------

class TestInvoicePaymentFailed:
    @pytest.mark.asyncio
    async def test_suspends_after_three_failures(self, mock_db, mock_redis):
        event = make_stripe_event("invoice.payment_failed", {
            "id": "inv_123",
            "subscription": "sub_123",
            "attempt_count": 3,
        })

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001"),  # SELECT subscription
            MagicMock(),                            # UPDATE status to suspended
            make_db_row("box-001"),                 # SELECT box
        ])

        await handle_invoice_payment_failed(event, mock_db, mock_redis)

        import json
        mock_redis.rpush.assert_called_once()
        job = json.loads(mock_redis.rpush.call_args[0][1])
        assert job["type"] == "suspend"
        assert job["customer_id"] == "cust-001"

    @pytest.mark.asyncio
    async def test_logs_warning_before_three_failures(self, mock_db, mock_redis):
        event = make_stripe_event("invoice.payment_failed", {
            "id": "inv_123",
            "subscription": "sub_123",
            "attempt_count": 2,
        })

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001"),  # SELECT subscription
        ])

        await handle_invoice_payment_failed(event, mock_db, mock_redis)

        # No suspend job enqueued
        mock_redis.rpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_invoice_without_subscription(self, mock_db, mock_redis):
        event = make_stripe_event("invoice.payment_failed", {
            "id": "inv_123",
            "subscription": None,
            "attempt_count": 5,
        })

        await handle_invoice_payment_failed(event, mock_db, mock_redis)

        mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# customer.subscription.updated
# ---------------------------------------------------------------------------

class TestSubscriptionUpdated:
    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_enqueues_resize_on_tier_change(self, mock_stripe, mock_db, mock_redis):
        mock_stripe.Product.retrieve.return_value = MagicMock(
            metadata={"tier": "team", "tokens_limit": "20000000"}
        )

        # Subscription object with dict-style access for items
        sub_obj = {
            "id": "sub_123",
            "items": {"data": [{"price": {"id": "price_team", "product": "prod_team"}}]},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }
        event = make_stripe_event("customer.subscription.updated", sub_obj)

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001", "pro"),  # SELECT subscription
            MagicMock(),                                    # UPDATE subscription
            MagicMock(),                                    # UPDATE usage_monthly
            make_db_row("box-001"),                         # SELECT box
        ])

        await handle_subscription_updated(event, mock_db, mock_redis)

        import json
        mock_redis.rpush.assert_called_once()
        job = json.loads(mock_redis.rpush.call_args[0][1])
        assert job["type"] == "resize"
        assert job["payload"]["new_tier"] == "team"
        assert job["payload"]["old_tier"] == "pro"

    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_no_resize_when_same_tier(self, mock_stripe, mock_db, mock_redis):
        mock_stripe.Product.retrieve.return_value = MagicMock(
            metadata={"tier": "pro", "tokens_limit": "5000000"}
        )

        sub_obj = {
            "id": "sub_123",
            "items": {"data": [{"price": {"id": "price_pro", "product": "prod_pro"}}]},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }
        event = make_stripe_event("customer.subscription.updated", sub_obj)

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001", "pro"),  # SELECT subscription
            MagicMock(),                                    # UPDATE periods
        ])

        await handle_subscription_updated(event, mock_db, mock_redis)

        mock_redis.rpush.assert_not_called()

    @pytest.mark.asyncio
    @patch("billing_worker.handlers.stripe")
    async def test_missing_subscription_in_db(self, mock_stripe, mock_db, mock_redis):
        sub_obj = {
            "id": "sub_nonexistent",
            "items": {"data": [{"price": {"id": "price_pro", "product": "prod_pro"}}]},
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
        }
        event = make_stripe_event("customer.subscription.updated", sub_obj)

        mock_db.execute = AsyncMock(return_value=make_empty_result())

        await handle_subscription_updated(event, mock_db, mock_redis)

        mock_redis.rpush.assert_not_called()


# ---------------------------------------------------------------------------
# customer.subscription.deleted
# ---------------------------------------------------------------------------

class TestSubscriptionDeleted:
    @pytest.mark.asyncio
    async def test_enqueues_destroy_job(self, mock_db, mock_redis):
        event = make_stripe_event("customer.subscription.deleted", {
            "id": "sub_123",
        })

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001"),  # SELECT subscription
            MagicMock(),                            # UPDATE status to cancelled
            make_db_row("box-001"),                 # SELECT box
        ])

        await handle_subscription_deleted(event, mock_db, mock_redis)

        import json
        mock_redis.rpush.assert_called_once()
        job = json.loads(mock_redis.rpush.call_args[0][1])
        assert job["type"] == "destroy"
        assert job["customer_id"] == "cust-001"
        assert job["box_id"] == "box-001"

    @pytest.mark.asyncio
    async def test_handles_missing_subscription(self, mock_db, mock_redis):
        event = make_stripe_event("customer.subscription.deleted", {
            "id": "sub_nonexistent",
        })

        mock_db.execute = AsyncMock(return_value=make_empty_result())

        await handle_subscription_deleted(event, mock_db, mock_redis)

        mock_redis.rpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_no_active_box(self, mock_db, mock_redis):
        event = make_stripe_event("customer.subscription.deleted", {
            "id": "sub_123",
        })

        mock_db.execute = AsyncMock(side_effect=[
            make_db_row("sub-id-1", "cust-001"),  # SELECT subscription
            MagicMock(),                            # UPDATE status
            make_empty_result(),                     # SELECT box (none found)
        ])

        await handle_subscription_deleted(event, mock_db, mock_redis)

        import json
        mock_redis.rpush.assert_called_once()
        job = json.loads(mock_redis.rpush.call_args[0][1])
        assert job["type"] == "destroy"
        # box_id should not be in message when None
        assert "box_id" not in job
