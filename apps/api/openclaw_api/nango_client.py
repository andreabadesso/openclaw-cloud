import httpx

from openclaw_api.config import settings


class NangoClient:
    def __init__(self, server_url: str, secret_key: str):
        self.base_url = server_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {secret_key}"}

    async def create_connect_session(self, end_user_id: str, provider: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/connect/sessions",
                headers=self.headers,
                json={
                    "end_user": {"id": end_user_id},
                    "allowed_integrations": [provider],
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def list_connections(self, search: str | None = None) -> list[dict]:
        params = {}
        if search:
            params["search"] = search
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/connection",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("connections", data) if isinstance(data, dict) else data

    async def get_connection(self, provider: str, connection_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/connection/{connection_id}",
                headers=self.headers,
                params={"provider_config_key": provider},
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_connection(self, connection_id: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.base_url}/connection/{connection_id}",
                headers=self.headers,
            )
            resp.raise_for_status()

    async def proxy_request(
        self, method: str, path: str, provider: str, connection_id: str, **kwargs
    ) -> httpx.Response:
        proxy_headers = {
            **self.headers,
            "Provider-Config-Key": provider,
            "Connection-Id": connection_id,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{self.base_url}/proxy{path}",
                headers=proxy_headers,
                **kwargs,
            )
            resp.raise_for_status()
            return resp


def get_nango_client() -> NangoClient:
    return NangoClient(settings.nango_server_url, settings.nango_secret_key)
