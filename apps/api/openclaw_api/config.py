from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://openclaw:openclaw@localhost:5432/openclaw_cloud"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    web_url: str = "http://localhost:3000"
    debug: bool = False
    nango_server_url: str = "http://nango-server:8080"
    nango_public_url: str = "http://localhost:3003"
    nango_secret_key: str = ""
    nango_public_key: str = ""
    agent_api_secret: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 168

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
