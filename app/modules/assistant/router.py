from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.dependencies.auth import CurrentUserId
from app.dependencies.database import DatabaseSession
from app.modules.assistant.client import AssistantUnavailableError
from app.modules.assistant.routing import public_questions, resolve_route
from app.modules.assistant.schemas import (
    AssistantHealthResponse,
    AssistantRequest,
    AssistantResponse,
    RouteRequest,
)
from app.modules.assistant.service import AssistantService, ToolUnavailableError
from app.modules.assistant.tool_registry import IMPLEMENTED_TOOL_NAMES

router = APIRouter()
compatibility_router = APIRouter()


@router.get(
    "/health",
    response_model=AssistantHealthResponse,
    status_code=status.HTTP_200_OK,
)
def assistant_health() -> AssistantHealthResponse:
    implemented_enabled = sorted(
        IMPLEMENTED_TOOL_NAMES.intersection(settings.assistant_enabled_tool_names)
    )
    if not settings.assistant_enabled:
        health_status = "disabled"
    elif (
        not settings.assistant_real_llm_enabled
        or not settings.openai_api_key
        or not implemented_enabled
    ):
        health_status = "degraded"
    else:
        health_status = "ok"
    return AssistantHealthResponse(
        status=health_status,
        enabled=settings.assistant_enabled,
        real_llm_enabled=settings.assistant_real_llm_enabled,
        model=settings.openai_model,
        openai_key_available=bool(settings.openai_api_key),
        implemented_tools=sorted(IMPLEMENTED_TOOL_NAMES),
        enabled_tools=implemented_enabled,
        default_forecast_origin=settings.assistant_default_forecast_origin,
    )


@router.get("/questions", status_code=status.HTTP_200_OK)
def assistant_questions(_user_id: CurrentUserId) -> dict[str, Any]:
    enabled = frozenset(settings.assistant_enabled_tool_names)
    rows = public_questions()
    for row in rows:
        planned = row.get("planned_tools", [])
        row["available"] = all(
            name in IMPLEMENTED_TOOL_NAMES and name in enabled for name in planned
        )
    return {
        "status": "SUCCESS",
        "records_returned": len(rows),
        "data": rows,
    }


@router.post("/route", status_code=status.HTTP_200_OK)
def route_question(payload: RouteRequest, _user_id: CurrentUserId) -> dict[str, Any]:
    try:
        decision = resolve_route(payload.question, explicit_tools=None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "status": "SUCCESS",
        "question": payload.question,
        "routing": decision.as_dict(),
    }


def _execute_query(
    payload: AssistantRequest,
    db: DatabaseSession,
    *,
    endpoint: str,
) -> AssistantResponse:
    try:
        return AssistantService(db, settings).execute(payload, endpoint=endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ToolUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AssistantUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/query",
    response_model=AssistantResponse,
    status_code=status.HTTP_200_OK,
)
def assistant_query(
    payload: AssistantRequest,
    _user_id: CurrentUserId,
    db: DatabaseSession,
) -> AssistantResponse:
    return _execute_query(
        payload,
        db,
        endpoint="/api/v1/assistant-light/query",
    )


@compatibility_router.post(
    "/assistant/query",
    response_model=AssistantResponse,
    status_code=status.HTTP_200_OK,
)
def assistant_query_compatibility(
    payload: AssistantRequest,
    _user_id: CurrentUserId,
    db: DatabaseSession,
) -> AssistantResponse:
    return _execute_query(payload, db, endpoint="/api/v1/assistant/query")
