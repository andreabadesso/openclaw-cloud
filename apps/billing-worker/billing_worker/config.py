from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+asyncpg://localhost/openclaw_cloud")
    redis_url: str = Field(default="redis://localhost:6379/0")
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")
    port: int = Field(default=8082)

    model_config = {"env_prefix": "", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
