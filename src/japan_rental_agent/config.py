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
    app_dev_mode: bool = Field(default=False, alias="APP_DEV_MODE")
    search_provider: str = Field(default="web", alias="SEARCH_PROVIDER")
    web_search_region: str = Field(default="jp-jp", alias="WEB_SEARCH_REGION")
    web_search_max_results: int = Field(default=20, alias="WEB_SEARCH_MAX_RESULTS")
    public_context_enabled: bool = Field(default=True, alias="PUBLIC_CONTEXT_ENABLED")
    estat_app_id: str | None = Field(default=None, alias="ESTAT_APP_ID")
    mlit_api_key: str | None = Field(default=None, alias="MLIT_API_KEY")
    mlit_api_base_url: str = Field(
        default="https://www.reinfolib.mlit.go.jp/ex-api/external",
        alias="MLIT_API_BASE_URL",
    )
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
