from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FORMA_", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://forma:forma@localhost:5432/forma"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://forma:forma@localhost:5672/"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    jwt_secret: str = Field(
        default="development-only-secret-must-be-32-bytes-long",
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = "HS256"
    google_calendar_client_id: str = ""
    google_calendar_redirect_uri: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
