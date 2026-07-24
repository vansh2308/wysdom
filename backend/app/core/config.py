from functools import lru_cache
from pathlib import Path

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

    # --- Postgres DB  ---
    db_url: PostgresDsn = Field(
        ...,
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



    # --- PDF extraction (marker) ---
    PDF_EXTRACTION_DEVICE: str | None = None  # sets TORCH_DEVICE, e.g. "cuda", "cpu"
    PDF_EXTRACTION_WORKERS: int = 1           # thread pool size
    PDF_EXTRACTION_MAX_CONCURRENCY: int = 1   # concurrent conversions allowed
    PDF_EXTRACTION_TEMP_DIR: Path = Path("/tmp/pdf_extraction")
    PDF_EXTRACTION_MAX_FILE_SIZE_MB: int = 50
    PDF_EXTRACTION_EAGER_LOAD_MODELS: bool = True
    PDF_EXTRACTION_LLM_SERVICE: str | None = None  # e.g. "marker.services.gemini.GoogleGeminiService"


    # --- RETRIEVAL ENGINE ---
    PINECONE_API_KEY: str
    PINECONE_INDEX_HOST: str
    PINECONE_NAMESPACE: str = "default"

    OPENAI_API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 512

    ANTHROPIC_API_KEY: str
    QUERY_PLANNER_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    # CONTEXT_COMPRESSOR_MODEL: str = "claude-sonnet-5"
    CONTEXT_COMPRESSOR_MODEL: str = "google/gemma-4-26b-a4b-it:free"


    AGENT_PLANNER_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    AGENT_CRITIC_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    AGENT_SYNTHESIZER_MODEL: str = "google/gemma-4-26b-a4b-it:free"
    AGENT_MAX_RETRIEVAL_LOOPS: int = 2
    AGENT_RECURSION_LIMIT: int = 25
    


    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_WORKERS: int = 1

    RRF_K: int = 60
    RETRIEVAL_DENSE_TOP_K: int = 30
    RETRIEVAL_KEYWORD_TOP_K: int = 30
    RETRIEVAL_RERANK_TOP_N: int = 40
    RETRIEVAL_FINAL_TOP_K: int = 10

    BM25_INDEX_PERSIST_PATH: Path = Path("/tmp/bm25_index.pkl")


    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
