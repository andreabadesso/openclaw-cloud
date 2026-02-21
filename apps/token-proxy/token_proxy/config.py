from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kimi_api_key: str
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    database_url: str = "postgresql+asyncpg://localhost/openclaw_cloud"
    redis_url: str = "redis://localhost:6379/0"
    internal_api_key: str = ""
    rate_limit_rps: int = 10
    usage_flush_interval_s: float = 5.0
    usage_flush_batch_size: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
