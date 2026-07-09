from functools import lru_cache

from pydantic import Field, PostgresDsn
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
    
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    pinecone_api_key: str | None = Field(default=None, alias="PINECONE_API_KEY")
    langgraph_enabled: bool = Field(default=False, alias="LANGGRAPH_ENABLED")

    db_url: PostgresDsn = Field(
        ...,
        # env="DATABASE_URL",
        # validation_alias="DATABASE_URL",
        alias="DATABASE_URL",
        description=(
            "Neon Postgres async DSN, e.g. "
            "postgresql+asyncpg://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?ssl=true"
        ),
    )
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=300, alias="DB_POOL_RECYCLE")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
