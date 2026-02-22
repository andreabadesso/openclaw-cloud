import pytest
from pydantic import ValidationError

from openclaw_api.schemas import (
    BoxResponse,
    ProvisionRequest,
    ResizeRequest,
    UpdateBoxRequest,
    UsageResponse,
)


def test_provision_request_valid():
    req = ProvisionRequest(
        telegram_bot_token="tok",
        telegram_user_id=123,
        tier="starter",
        customer_email="a@b.com",
    )
    assert req.tier == "starter"


def test_provision_request_invalid_tier():
    with pytest.raises(ValidationError):
        ProvisionRequest(
            telegram_bot_token="tok",
            telegram_user_id=123,
            tier="enterprise",
            customer_email="a@b.com",
        )


def test_provision_request_defaults():
    req = ProvisionRequest(
        telegram_bot_token="tok",
        telegram_user_id=123,
        tier="pro",
        customer_email="a@b.com",
    )
    assert req.model == "kimi-coding/k2p5"
    assert req.thinking_level == "medium"
    assert req.language == "en"


def test_update_box_request_all_none():
    req = UpdateBoxRequest()
    assert req.model_dump(exclude_none=True) == {}


def test_update_box_request_partial():
    req = UpdateBoxRequest(model="gpt-4o")
    dumped = req.model_dump(exclude_none=True)
    assert dumped == {"model": "gpt-4o"}


def test_resize_request_valid():
    req = ResizeRequest(new_tier="pro")
    assert req.new_tier == "pro"


def test_resize_request_invalid_tier():
    with pytest.raises(ValidationError):
        ResizeRequest(new_tier="enterprise")


def test_resize_request_all_valid_tiers():
    for tier in ["starter", "pro", "team"]:
        req = ResizeRequest(new_tier=tier)
        assert req.new_tier == tier


def test_usage_response():
    resp = UsageResponse(
        tokens_used=100,
        tokens_limit=1000,
        pct_used=10.0,
        period_start="2024-01-01T00:00:00Z",
        period_end="2024-01-31T00:00:00Z",
    )
    assert resp.pct_used == 10.0
