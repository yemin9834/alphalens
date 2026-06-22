"""Shared LLM helpers for OpenAI Agents SDK (Bedrock or OpenAI via LiteLLM)."""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

SUPPORTED_LLM_PROVIDERS = ("bedrock", "openai")


def get_llm_provider() -> str:
    """Return normalized LLM provider: bedrock (default) or openai."""
    return os.getenv("LLM_PROVIDER", "bedrock").strip().lower()


def log_agent_mode(agent_name: str, *, llm: bool) -> None:
    """Log whether an agent is running with LLM or deterministic logic."""
    if llm:
        logger.info(
            "[%s] mode=LLM provider=%s model=%s",
            agent_name,
            get_llm_provider(),
            get_bedrock_model_id()
            if get_llm_provider() == "bedrock"
            else get_openai_model_id(),
        )
    else:
        logger.info("[%s] mode=deterministic", agent_name)


def configure_bedrock_env() -> str:
    """Set AWS_REGION_NAME for LiteLLM Bedrock calls."""
    region = os.getenv("BEDROCK_REGION", "us-west-2")
    os.environ["AWS_REGION_NAME"] = region
    return region


def get_bedrock_model_id() -> str:
    return os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")


def get_openai_model_id() -> str:
    return os.getenv("OPENAI_MODEL_ID", "gpt-4.1-mini")


def require_llm_packages() -> None:
    try:
        import agents  # noqa: F401
        import litellm  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "LLM mode requires openai-agents and litellm. "
            "In the agent directory run: uv sync --group llm"
        ) from exc


def get_litellm_model_name() -> str:
    """LiteLLM model string for the configured provider."""
    provider = get_llm_provider()

    if provider == "bedrock":
        configure_bedrock_env()
        return f"bedrock/{get_bedrock_model_id()}"

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai. "
                "Set it in alphalens/.env or switch LLM_PROVIDER=bedrock."
            )
        model_id = get_openai_model_id()
        if model_id.startswith("openai/"):
            return model_id
        return model_id

    raise ValueError(
        f"Unsupported LLM_PROVIDER={provider!r}. "
        f"Use one of: {', '.join(SUPPORTED_LLM_PROVIDERS)}"
    )


def get_litellm_model():
    """Return a LiteLLM-backed model for OpenAI Agents SDK (Bedrock or OpenAI)."""
    require_llm_packages()
    from agents.extensions.models.litellm_model import LitellmModel

    model_name = get_litellm_model_name()
    logger.info("Using LLM provider=%s model=%s", get_llm_provider(), model_name)
    return LitellmModel(model=model_name)


async def run_bedrock_agent(
    *,
    name: str,
    instructions: str,
    task: str,
    tools: Optional[List[Any]] = None,
    mcp_servers: Optional[List[Any]] = None,
    context: Any = None,
    context_type: Optional[Type[Any]] = None,
    max_turns: int = 10,
    output_type: Optional[Type[T]] = None,
) -> Any:
    """
    Run an OpenAI Agents SDK agent via LiteLLM (Bedrock or OpenAI).

    Provider is selected with LLM_PROVIDER (default: bedrock).

    LiteLLM + Bedrock cannot combine tools and structured output on one agent.
    Use mcp_servers for Playwright/Search MCP (discovery agent).
    """
    require_llm_packages()
    from agents import Agent, Runner, trace

    model = get_litellm_model()
    tool_list = tools or []
    mcp_list = mcp_servers or []

    with trace(name):
        if context_type is not None and context is not None:
            agent = Agent[context_type](
                name=name,
                instructions=instructions,
                model=model,
                tools=tool_list,
                mcp_servers=mcp_list,
            )
            result = await Runner.run(
                agent, input=task, context=context, max_turns=max_turns
            )
        elif output_type is not None:
            agent = Agent(
                name=name,
                instructions=instructions,
                model=model,
                output_type=output_type,
            )
            result = await Runner.run(agent, input=task, max_turns=max_turns)
            return result.final_output_as(output_type)
        else:
            agent = Agent(
                name=name,
                instructions=instructions,
                model=model,
                tools=tool_list,
                mcp_servers=mcp_list,
            )
            result = await Runner.run(agent, input=task, max_turns=max_turns)

    return result.final_output
