from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    forecast_origin: date | None = None
    allowed_tools: list[str] | None = Field(default=None, max_length=13)
    user_context: dict[str, Any] | None = None

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("La pregunta no puede estar vacía.")
        return cleaned

    @field_validator("allowed_tools")
    @classmethod
    def clean_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [name.strip() for name in value if name.strip()]
        if not cleaned:
            return None
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("allowed_tools contiene nombres repetidos.")
        return cleaned


class RouteRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("La pregunta no puede estar vacía.")
        return cleaned


class AssistantUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AssistantResponse(BaseModel):
    application: str
    endpoint: str
    request_id: str
    started_utc: str
    completed_utc: str
    status: str
    question: str
    forecast_origin: str | None
    routing: dict[str, Any]
    answer: str
    sources: list[str]
    selected_tools: list[str]
    tools_used: list[dict[str, Any]]
    usage: AssistantUsage
    model: str
    model_calls: int
    model_called: bool
    local_restriction: bool
    response_id: str | None


class AssistantHealthResponse(BaseModel):
    status: str
    enabled: bool
    real_llm_enabled: bool
    model: str
    openai_key_available: bool
    implemented_tools: list[str]
    enabled_tools: list[str]
    default_forecast_origin: date | None
