from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from japan_rental_agent.domain import ComparisonItem, Listing

InputType = Literal["text", "file", "url"]
OutputFormat = Literal["chat", "json", "csv", "pdf"]
ResponseStatus = Literal["success", "need_clarification", "error"]


class RequestContext(BaseModel):
    previous_filters: dict[str, Any] = Field(default_factory=dict)
    selected_listings: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    recent_listings: list[dict[str, Any]] = Field(default_factory=list)


class RequestOptions(BaseModel):
    top_k: int = 5
    output_format: OutputFormat = "chat"


class AgentRequest(BaseModel):
    session_id: str
    message: str
    input_type: InputType = "text"
    context: RequestContext = Field(default_factory=RequestContext)
    options: RequestOptions = Field(default_factory=RequestOptions)


class AgentError(BaseModel):
    code: str
    message: str


class AgentMeta(BaseModel):
    tool_used: list[str] = Field(default_factory=list)
    confidence: float | None = None
    processing_time_ms: int | None = None


class AgentData(BaseModel):
    filters_used: dict[str, Any] = Field(default_factory=dict)
    listings: list[Listing] = Field(default_factory=list)
    comparison: list[ComparisonItem] = Field(default_factory=list)
    file: str | None = None
    missing_fields: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    status: ResponseStatus
    reply: str
    data: AgentData = Field(default_factory=AgentData)
    meta: AgentMeta = Field(default_factory=AgentMeta)
    error: AgentError | None = None
