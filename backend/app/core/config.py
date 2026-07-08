from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="wysdom-backend", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/wysdom",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    pinecone_api_key: str | None = Field(default=None, alias="PINECONE_API_KEY")
    langgraph_enabled: bool = Field(default=False, alias="LANGGRAPH_ENABLED")

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
