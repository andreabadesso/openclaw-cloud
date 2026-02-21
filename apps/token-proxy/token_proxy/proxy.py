from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse

from token_proxy.config import settings

logger = logging.getLogger(__name__)


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    request_id: str = ""


@dataclass
class ProxyResult:
    response: httpx.Response | StreamingResponse
    usage: UsageInfo = field(default_factory=UsageInfo)


async def forward_request(
    request: Request,
    client: httpx.AsyncClient,
) -> ProxyResult:
    """Forward a chat completion request to the upstream Kimi API."""
    body = await request.body()
    body_json = json.loads(body)
    is_streaming = body_json.get("stream", False)

    upstream_url = f"{settings.kimi_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.kimi_api_key}",
        "Content-Type": "application/json",
    }

    if is_streaming:
        return await _forward_streaming(client, upstream_url, headers, body)
    else:
        return await _forward_non_streaming(client, upstream_url, headers, body)


async def _forward_non_streaming(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: bytes,
) -> ProxyResult:
    resp = await client.post(url, content=body, headers=headers, timeout=120.0)

    usage = UsageInfo()
    if resp.status_code == 200:
        try:
            data = resp.json()
            u = data.get("usage", {})
            usage.prompt_tokens = u.get("prompt_tokens", 0)
            usage.completion_tokens = u.get("completion_tokens", 0)
            usage.total_tokens = u.get("total_tokens", 0)
            usage.model = data.get("model", "")
            usage.request_id = data.get("id", "")
        except Exception:
            logger.exception("Failed to parse upstream response for usage")

    proxy_response = httpx.Response(
        status_code=resp.status_code,
        headers=dict(resp.headers),
        content=resp.content,
    )
    return ProxyResult(response=proxy_response, usage=usage)


async def _forward_streaming(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: bytes,
) -> ProxyResult:
    usage = UsageInfo()

    async def stream_generator() -> AsyncIterator[bytes]:
        async with client.stream("POST", url, content=body, headers=headers, timeout=120.0) as resp:
            async for line in resp.aiter_lines():
                # Yield the SSE line back to the caller
                yield f"{line}\n\n".encode()

                # Try to extract usage from the last chunk
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        u = chunk.get("usage")
                        if u:
                            usage.prompt_tokens = u.get("prompt_tokens", 0)
                            usage.completion_tokens = u.get("completion_tokens", 0)
                            usage.total_tokens = u.get("total_tokens", 0)
                        if chunk.get("model"):
                            usage.model = chunk["model"]
                        if chunk.get("id"):
                            usage.request_id = chunk["id"]
                    except (json.JSONDecodeError, KeyError):
                        pass

    result = ProxyResult(
        response=StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        ),
        usage=usage,
    )
    return result
