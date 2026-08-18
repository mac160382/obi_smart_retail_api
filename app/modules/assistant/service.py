from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.assistant.client import AssistantClient, AssistantUnavailableError
from app.modules.assistant.repository import AssistantQueryRepository
from app.modules.assistant.routing import contextual_question, resolve_route
from app.modules.assistant.schemas import AssistantRequest, AssistantResponse
from app.modules.assistant.tool_executor import ToolExecutor
from app.modules.assistant.tool_registry import IMPLEMENTED_TOOL_NAMES


class ToolUnavailableError(RuntimeError):
    """La pregunta requiere una herramienta todavía no habilitada."""


class AssistantService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        *,
        openai_client: Any | None = None,
    ) -> None:
        self.settings = settings
        repository = AssistantQueryRepository(db, settings)
        executor = ToolExecutor(repository, settings)
        self.client = AssistantClient(
            settings,
            executor,
            openai_client=openai_client,
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()

    def execute(
        self,
        request: AssistantRequest,
        *,
        endpoint: str = "/api/v1/assistant-light/query",
    ) -> AssistantResponse:
        if not self.settings.assistant_enabled:
            raise AssistantUnavailableError("El Asistente está deshabilitado por configuración.")
        request_id = "assistant-light-" + uuid4().hex
        started = self._utc_now()
        decision = resolve_route(request.question, request.allowed_tools)
        if decision.tools is None:
            result = self.client.local_restriction(request.question)
        else:
            enabled = frozenset(self.settings.assistant_enabled_tool_names)
            unavailable = [
                name
                for name in decision.tools
                if name not in IMPLEMENTED_TOOL_NAMES or name not in enabled
            ]
            if unavailable:
                raise ToolUnavailableError(
                    "La consulta requiere funcionalidades pendientes de migración: "
                    + ", ".join(unavailable)
                    + "."
                )
            prompt = contextual_question(
                request.question,
                forecast_origin=(
                    request.forecast_origin.isoformat()
                    if request.forecast_origin is not None
                    else None
                ),
                decision=decision,
                user_context=request.user_context,
            )
            result = self.client.ask(prompt, allowed_tools=list(decision.tools))

        return AssistantResponse(
            application=self.settings.app_name,
            endpoint=endpoint,
            request_id=request_id,
            started_utc=started,
            completed_utc=self._utc_now(),
            status=str(result.get("status", "SUCCESS")),
            question=request.question,
            forecast_origin=(
                request.forecast_origin.isoformat() if request.forecast_origin is not None else None
            ),
            routing=decision.as_dict(),
            answer=str(result.get("answer", "")),
            sources=list(result.get("sources", [])),
            selected_tools=list(result.get("selected_tools", [])),
            tools_used=list(result.get("tools_used", [])),
            usage=result.get("usage", {}),
            model=str(result.get("model", self.settings.openai_model)),
            model_calls=int(result.get("model_calls", 0)),
            model_called=bool(result.get("model_called", False)),
            local_restriction=bool(result.get("local_restriction", False)),
            response_id=result.get("response_id"),
        )
