from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from japan_rental_agent.domain import SearchFilters


class RankingPreferences(BaseModel):
    weight_price: float = Field(default=0.4, ge=0.0, le=1.0)
    weight_location: float = Field(default=0.3, ge=0.0, le=1.0)
    weight_size: float = Field(default=0.2, ge=0.0, le=1.0)
    weight_safety: float = Field(default=0.1, ge=0.0, le=1.0)

    def as_tool_payload(self) -> dict[str, float]:
        return self.model_dump()


class IntentExtractionOutput(BaseModel):
    intent: Literal["search", "compare", "export", "clarification", "unknown"] = "search"
    normalized_query: str
    constraints: SearchFilters = Field(default_factory=SearchFilters)
    missing_fields: list[str] = Field(default_factory=list)
    ranking_preferences: RankingPreferences = Field(default_factory=RankingPreferences)
    output_format: Literal["chat", "json", "csv", "pdf"] | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ClarificationOutput(BaseModel):
    reply: str
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RankingPlanOutput(BaseModel):
    preferences: RankingPreferences = Field(default_factory=RankingPreferences)
    summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ResponseDraft(BaseModel):
    reply: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ErrorDraft(BaseModel):
    reply: str
    code: str = "WORKFLOW_ERROR"
    confidence: float = Field(default=0.3, ge=0.0, le=1.0)

