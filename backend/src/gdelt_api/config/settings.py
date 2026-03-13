"""Application settings using Pydantic Settings."""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    host: str = Field(default="127.0.0.1", alias="DB_HOST")
    port: int = Field(default=3306, alias="DB_PORT")
    user: str = Field(default="root", alias="DB_USER")
    password: str = Field(default="", alias="DB_PASSWORD")
    name: str = Field(default="gdelt_db", alias="DB_NAME")
    
    # Connection pool settings
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")
    
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    @property
    def async_url(self) -> str:
        """Generate async MySQL connection URL."""
        return (
            f"mysql+asyncmy://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )
    
    @property
    def sync_url(self) -> str:
        """Generate sync MySQL connection URL."""
        return (
            f"mysql+mysqlconnector://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class LLMSettings(BaseSettings):
    """LLM API settings."""
    
    api_key: str = Field(default="", alias="API_KEY")
    base_url: str = Field(
        default="https://api.kimi.com/coding/v1", 
        alias="LLM_BASE_URL"
    )
    model: str = Field(default="kimi-k2-0905-preview", alias="LLM_MODEL")
    max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")
    temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    timeout: int = Field(default=60, alias="LLM_TIMEOUT")
    
    model_config = SettingsConfigDict(env_prefix="LLM_")


class MCPSettings(BaseSettings):
    """MCP Server settings."""
    
    server_script_path: str = Field(
        default="mcp_server/server.py",
        alias="MCP_SERVER_SCRIPT"
    )
    timeout: int = Field(default=30, alias="MCP_TIMEOUT")
    
    model_config = SettingsConfigDict(env_prefix="MCP_")


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    env: Literal["development", "testing", "production"] = Field(
        default="development", alias="ENV"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Application
    app_name: str = Field(default="GDELT Narrative API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    api_v1_prefix: str = "/api/v1"
    
    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    reload: bool = Field(default=False, alias="RELOAD")
    workers: int = Field(default=1, alias="WORKERS")
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: list[str] = Field(default=["*"], alias="CORS_ORIGINS")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")
    
    # Sub-configs
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_project_root() -> str:
    """Get project root directory."""
    current_file = os.path.abspath(__file__)
    # backend/src/gdelt_api/config/settings.py
    # -> project root (4 levels up)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file)))))
