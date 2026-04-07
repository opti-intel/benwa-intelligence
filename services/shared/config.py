"""Shared configuration using pydantic-settings, read from environment variables."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings

_DEFAULT_DB_URL = "postgresql+asyncpg://benwa:changeme@postgres:5432/benwa_intelligence"


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # Postgres
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "benwa_intelligence"
    database_url: str = _DEFAULT_DB_URL

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_db_url(cls, v: str) -> str:
        """Ensure DATABASE_URL uses the asyncpg driver scheme required by SQLAlchemy async."""
        if not v:
            return _DEFAULT_DB_URL
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
