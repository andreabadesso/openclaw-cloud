import pytest
from unittest.mock import MagicMock

from fastapi import HTTPException

from openclaw_api.deps import get_current_customer_id


def _make_request(auth_header=None):
    """Create a mock Request with the given Authorization header."""
    req = MagicMock()
    headers = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    req.headers = headers
    return req


@pytest.mark.anyio
async def test_get_current_customer_id_via_header():
    """In debug mode with X-Customer-Id header, returns the header value."""
    from openclaw_api.config import settings
    original_debug = settings.debug
    settings.debug = True
    try:
        result = await get_current_customer_id(
            request=_make_request(),
            x_customer_id="cust-123",
        )
        assert result == "cust-123"
    finally:
        settings.debug = original_debug


@pytest.mark.anyio
async def test_get_current_customer_id_missing():
    """Without auth and without debug header, returns 401."""
    from openclaw_api.config import settings
    original_debug = settings.debug
    original_dev = settings.dev_mode
    settings.debug = False
    settings.dev_mode = False
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_customer_id(
                request=_make_request(),
                x_customer_id=None,
            )
        assert exc_info.value.status_code == 401
    finally:
        settings.debug = original_debug
        settings.dev_mode = original_dev


@pytest.mark.anyio
async def test_get_current_customer_id_empty():
    """Empty X-Customer-Id with no auth and debug off returns 401."""
    from openclaw_api.config import settings
    original_debug = settings.debug
    original_dev = settings.dev_mode
    settings.debug = False
    settings.dev_mode = False
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_customer_id(
                request=_make_request(),
                x_customer_id="",
            )
        assert exc_info.value.status_code == 401
    finally:
        settings.debug = original_debug
        settings.dev_mode = original_dev
