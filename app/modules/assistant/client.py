from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.modules.assistant.tool_executor import ToolExecutor, ToolTrace
from app.modules.assistant.tool_registry import response_tools, validate_selected_tools

SYSTEM_INSTRUCTIONS = """
Eres el Asistente de negocio de Smart Retail. Trabajas exclusivamente con las
funciones autorizadas que recibe cada solicitud. Resume los datos con precisión,
identifica claramente cuando el resultado es una muestra y evita afirmar que una
muestra representa el universo completo. Usa lenguaje de negocio accesible. No
propongas SQL ni acciones de escritura. Termina con una respuesta útil y breve.
""".strip()


class AssistantUnavailableError(RuntimeError):
    """El asistente o el proveedor LLM no están disponibles."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add_response(self, response: Any) -> None:
        observed = getattr(response, "usage", None)
        if observed is None:
            return
        input_tokens = int(getattr(observed, "input_tokens", 0) or 0)
        output_tokens = int(getattr(observed, "output_tokens", 0) or 0)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += int(
            getattr(observed, "total_tokens", None) or input_tokens + output_tokens
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


class AssistantClient:
    def __init__(
        self,
        settings: Settings,
        executor: ToolExecutor,
        *,
        openai_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self.executor = executor
        self.openai_client = openai_client

    def _openai(self) -> Any:
        if self.openai_client is not None:
            return self.openai_client
        if not self.settings.assistant_real_llm_enabled:
            raise AssistantUnavailableError(
                "El uso real del LLM está deshabilitado por configuración."
            )
        if not self.settings.openai_api_key:
            raise AssistantUnavailableError("OPENAI_API_KEY no está configurada.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AssistantUnavailableError(
                "El cliente oficial de OpenAI no está instalado."
            ) from exc
        return OpenAI(api_key=self.settings.openai_api_key)

    @staticmethod
    def _function_calls(response: Any) -> list[Any]:
        return [
            item
            for item in list(getattr(response, "output", []) or [])
            if getattr(item, "type", None) == "function_call"
        ]

    @staticmethod
    def _sources(traces: list[ToolTrace]) -> list[str]:
        seen: set[tuple[str, str]] = set()
        sources: list[str] = []
        for trace in traces:
            source_text = json.dumps(trace.source, ensure_ascii=False, default=str)
            identity = (trace.endpoint, source_text)
            if identity in seen:
                continue
            seen.add(identity)
            sources.append(f"- {trace.endpoint} — {source_text}")
        return sources

    @staticmethod
    def _append_sources(answer: str, sources: list[str]) -> str:
        clean = answer.strip()
        if not sources or "Fuentes utilizadas:" in clean:
            return clean
        return clean + "\n\nFuentes utilizadas:\n" + "\n".join(sources)

    def local_restriction(self, question: str) -> dict[str, Any]:
        return {
            "status": "SUCCESS",
            "answer": (
                "El Asistente está configurado únicamente para consultar y explicar "
                "resultados existentes. La acción solicitada debe gestionarse fuera "
                "del Asistente."
            ),
            "sources": [],
            "selected_tools": [],
            "tools_used": [],
            "usage": Usage().as_dict(),
            "model": self.settings.openai_model,
            "model_calls": 0,
            "model_called": False,
            "local_restriction": True,
            "response_id": None,
        }

    def ask(self, question: str, *, allowed_tools: list[str]) -> dict[str, Any]:
        enabled_tools = self.settings.assistant_enabled_tool_names
        selected = validate_selected_tools(
            allowed_tools,
            enabled_tools=enabled_tools,
        )
        openai = self._openai()
        input_items: list[Any] = [{"role": "user", "content": question}]
        usage = Usage()
        traces: list[ToolTrace] = []
        missing = list(selected)
        model_calls = 0
        tool_calls = 0
        last_response_id: str | None = None

        while missing:
            if model_calls >= self.settings.assistant_max_model_calls:
                raise RuntimeError("Se alcanzó el máximo de llamadas al modelo.")
            response = openai.responses.create(
                model=self.settings.openai_model,
                instructions=SYSTEM_INSTRUCTIONS,
                input=input_items,
                tools=response_tools(missing, enabled_tools=enabled_tools),
                tool_choice="required",
                parallel_tool_calls=False,
                store=False,
            )
            model_calls += 1
            usage.add_response(response)
            last_response_id = getattr(response, "id", last_response_id)
            input_items.extend(list(getattr(response, "output", []) or []))
            calls = self._function_calls(response)
            if not calls:
                raise RuntimeError("El modelo no solicitó la función requerida.")

            called_names: list[str] = []
            for call in calls:
                tool_calls += 1
                if tool_calls > self.settings.assistant_max_tool_calls:
                    raise RuntimeError("Se alcanzó el máximo de funciones por consulta.")
                name = str(getattr(call, "name", ""))
                if name not in missing:
                    raise RuntimeError(f"El modelo solicitó una función inesperada: {name}.")
                try:
                    arguments = json.loads(getattr(call, "arguments", "{}") or "{}")
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"La función {name} recibió argumentos JSON inválidos."
                    ) from exc
                if not isinstance(arguments, dict):
                    raise RuntimeError(f"La función {name} requiere argumentos JSON.")
                payload, trace = self.executor.execute(name, arguments)
                traces.append(trace)
                called_names.append(name)
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(
                            self.executor.compact_payload(payload),
                            ensure_ascii=False,
                            default=str,
                            separators=(",", ":"),
                        ),
                    }
                )
            missing = [name for name in missing if name not in called_names]

        if model_calls >= self.settings.assistant_max_model_calls:
            raise RuntimeError("No quedan llamadas disponibles para redactar la respuesta.")
        final_response = openai.responses.create(
            model=self.settings.openai_model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=input_items,
            store=False,
        )
        model_calls += 1
        usage.add_response(final_response)
        last_response_id = getattr(final_response, "id", last_response_id)
        answer = str(getattr(final_response, "output_text", "") or "").strip()
        if not answer:
            raise RuntimeError("El modelo devolvió una respuesta vacía.")
        sources = self._sources(traces)
        return {
            "status": "SUCCESS",
            "answer": self._append_sources(answer, sources),
            "sources": sources,
            "selected_tools": selected,
            "tools_used": [trace.as_dict() for trace in traces],
            "usage": usage.as_dict(),
            "model": self.settings.openai_model,
            "model_calls": model_calls,
            "model_called": True,
            "local_restriction": False,
            "response_id": last_response_id,
        }
