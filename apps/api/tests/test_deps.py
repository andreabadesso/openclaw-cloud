import pytest
from fastapi import HTTPException

from openclaw_api.deps import get_current_customer_id


@pytest.mark.anyio
async def test_get_current_customer_id_valid():
    result = await get_current_customer_id(x_customer_id="cust-123")
    assert result == "cust-123"


@pytest.mark.anyio
async def test_get_current_customer_id_missing():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_customer_id(x_customer_id=None)
    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_customer_id_empty():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_customer_id(x_customer_id="")
    assert exc_info.value.status_code == 401
