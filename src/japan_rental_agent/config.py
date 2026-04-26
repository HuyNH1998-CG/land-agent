from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_chat_model: str = Field(default="gemini-3-flash", alias="LLM_CHAT_MODEL")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_embedding_model: str | None = Field(default=None, alias="LLM_EMBEDDING_MODEL")
    llm_reasoning_effort: str | None = "low"
    default_top_k: int = 5
    agent_max_retries: int = 1
    data_dir: Path = Path("data")
    export_dir: Path = Path("data/exports")
    chroma_dir: Path = Path("data/chroma")
    floor_plan_dir: Path = Path("data/floor_plans")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )
