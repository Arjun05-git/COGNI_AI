from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Iterable

from app.config import settings
from app.logging_utils import configure_logging

configure_logging()

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.tool.models import ToolContext
from vanna.core.user import RequestContext, User, UserResolver
from vanna.integrations.google import GeminiLlmService
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.ollama import OllamaLlmService
from vanna.integrations.openai import OpenAILlmService
from vanna.integrations.sqlite import SqliteRunner
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool


def _build_from_signature(target: Any, candidates: dict[str, Any]) -> Any:
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return target(**candidates)

    accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    if accepts_kwargs:
        return target(**candidates)

    filtered = {name: value for name, value in candidates.items() if name in signature.parameters}
    return target(**filtered)


def _register_tool(registry: ToolRegistry, tool: Any) -> None:
    register_local_tool = getattr(registry, "register_local_tool", None)
    if callable(register_local_tool):
        access_groups = list(getattr(tool, "access_groups", None) or ["admin", "user"])
        register_local_tool(tool, access_groups=access_groups)
        return

    for method_name in ("register_tool", "register", "add_tool"):
        method = getattr(registry, method_name, None)
        if callable(method):
            method(tool)
            return
    raise RuntimeError("Unable to register tools with the current ToolRegistry implementation.")


class DefaultUserResolver(UserResolver):
    def __init__(self) -> None:
        self._default_user = _build_from_signature(
            User,
            {
                "id": "default-user",
                "email": "default-user@example.com",
                "display_name": "Default User",
                "name": "Default User",
            },
        )

    def get_default_user(self) -> User:
        return self._default_user

    async def resolve_user(self, request_context: RequestContext | None = None) -> User:
        return self._default_user

    def resolve(self, request_context: RequestContext | None = None) -> User:
        return self._default_user


@dataclass
class AgentComponents:
    agent: Agent
    llm_service: Any
    memory: Any
    runner: Any
    tool_registry: ToolRegistry
    user_resolver: DefaultUserResolver


def build_request_context() -> RequestContext:
    candidates = {
        "headers": {},
        "query_params": {},
        "cookies": {},
        "client_host": "127.0.0.1",
        "path": "/chat",
        "method": "POST",
    }
    try:
        return _build_from_signature(RequestContext, candidates)
    except TypeError:
        return RequestContext()


def build_tool_context(memory: Any, user: User) -> ToolContext:
    return ToolContext(
        user=user,
        conversation_id="seed-conversation",
        request_id="seed-request",
        agent_memory=memory,
        metadata={"source": "seed_memory.py"},
    )


def _build_agent_config() -> AgentConfig:
    return _build_from_signature(
        AgentConfig,
        {
            "name": "clinic-nl2sql-agent",
            "system_prompt": (
                "You are a helpful assistant that writes safe SQLite SQL for a clinic database. "
                "Generate SQL only when asked."
            ),
            "temperature": 0.1,
            "max_steps": 6,
        },
    )


def _build_llm_service() -> Any:
    provider = settings.llm_provider

    if provider == "gemini":
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is missing. Add it to your .env file before starting the agent.")
        return _build_from_signature(
            GeminiLlmService,
            {
                "api_key": settings.google_api_key,
                "model": settings.gemini_model,
            },
        )

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file before starting the agent.")
        return _build_from_signature(
            OpenAILlmService,
            {
                "api_key": settings.groq_api_key,
                "model": settings.groq_model,
                "base_url": settings.groq_base_url,
            },
        )

    if provider == "ollama":
        return _build_from_signature(
            OllamaLlmService,
            {
                "model": settings.ollama_model,
                "host": settings.ollama_host,
            },
        )

    raise RuntimeError(
        f"Unsupported VANNA_LLM_PROVIDER '{provider}'. Use one of: gemini, groq, ollama."
    )


def _build_runner() -> Any:
    return _build_from_signature(
        SqliteRunner,
        {
            "database": str(settings.database_path),
            "db_path": str(settings.database_path),
            "database_path": str(settings.database_path),
        },
    )


def _build_memory() -> Any:
    return _build_from_signature(
        DemoAgentMemory,
        {
            "max_items": settings.memory_max_items,
        },
    )


def _build_tools(runner: Any, memory: Any) -> Iterable[Any]:
    return [
        _build_from_signature(RunSqlTool, {"sql_runner": runner, "runner": runner}),
        _build_from_signature(VisualizeDataTool, {}),
        _build_from_signature(SaveQuestionToolArgsTool, {"agent_memory": memory, "memory": memory}),
        _build_from_signature(SearchSavedCorrectToolUsesTool, {"agent_memory": memory, "memory": memory}),
    ]


def get_agent_components() -> AgentComponents:
    llm_service = _build_llm_service()
    runner = _build_runner()
    memory = _build_memory()
    user_resolver = DefaultUserResolver()

    tool_registry = ToolRegistry()
    for tool in _build_tools(runner, memory):
        _register_tool(tool_registry, tool)

    agent_config = _build_agent_config()
    agent = _build_from_signature(
        Agent,
        {
            "config": agent_config,
            "agent_config": agent_config,
            "llm_service": llm_service,
            "llm": llm_service,
            "tool_registry": tool_registry,
            "memory": memory,
            "agent_memory": memory,
            "user_resolver": user_resolver,
        },
    )

    return AgentComponents(
        agent=agent,
        llm_service=llm_service,
        memory=memory,
        runner=runner,
        tool_registry=tool_registry,
        user_resolver=user_resolver,
    )
