"""
Configuration module for mit-aichat.

Uses pydantic-settings to load and validate all environment variables.
All external URLs, credentials, and model configurations are centralized here.
"""

from functools import lru_cache
from typing import Optional

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All sensitive values use SecretStr to prevent accidental logging.
    All URLs are validated as proper HttpUrl types.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # OpenAI Configuration
    OPENAI_API_KEY: SecretStr

    # MCP Server Configuration
    MCP_SERVER_URL: HttpUrl = "http://localhost:3001"

    # VictoriaMetrics & VictoriaLogs Configuration
    VICTORIA_METRICS_URL: Optional[HttpUrl] = None
    VICTORIA_LOGS_API_URL: Optional[HttpUrl] = None

    # Manifest API Configuration
    MANIFEST_API_URL: HttpUrl
    MANIFEST_API_KEY: SecretStr

    # Application Configuration
    PROJECT_NAME: str = "mit-aichat"

    # LLM Model Configuration
    ROUTER_MODEL: str = "gpt-4o"
    PLANNER_MODEL: str = "gpt-4o"
    RESPONDER_MODEL: str = "gpt-4o"


@lru_cache
def get_settings() -> Settings:
    """
    Factory function to get cached Settings instance.

    Uses lru_cache to ensure settings are loaded only once
    and reused across the application lifecycle.
    """
    return Settings()
