from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = Field(default="redis://localhost:6379/0")
    database_url: str = Field(default="postgresql+asyncpg://localhost/openclaw_cloud")
    token_proxy_url: str = Field(default="http://token-proxy.platform.svc.cluster.local:8080")
    internal_api_key: str = Field(default="")
    openclaw_image: str = Field(default="ghcr.io/andreabadesso/openclaw-cloud/openclaw-gateway:latest")
    job_queue: str = Field(default="operator:jobs")
    health_port: int = Field(default=8081)
    pod_ready_timeout: int = Field(default=60)
    nango_server_url: str = Field(default="http://nango-server.platform.svc.cluster.local:8080")
    nango_secret_key: str = Field(default="")

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
