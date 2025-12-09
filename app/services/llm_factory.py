"""
LLM Factory for mit-aichat.

Provides a centralized factory function to instantiate LLM clients
with mode-specific configurations (router, planner, responder).
"""

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def get_llm(mode: str) -> ChatOpenAI:
    """
    Factory function to create LLM instances based on operational mode.

    Args:
        mode: The operational mode. Must be one of:
              - "router": For intent classification (deterministic)
              - "planner": For tool planning (deterministic)
              - "responder": For response generation (creative, streaming)

    Returns:
        ChatOpenAI: Configured LLM client instance.

    Raises:
        ValueError: If an invalid mode is provided.
    """
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY.get_secret_value()

    if mode == "router":
        return ChatOpenAI(
            model=settings.ROUTER_MODEL,
            temperature=0,
            api_key=api_key,
        )

    if mode == "planner":
        return ChatOpenAI(
            model=settings.PLANNER_MODEL,
            temperature=0,
            api_key=api_key,
        )

    if mode == "responder":
        return ChatOpenAI(
            model=settings.RESPONDER_MODEL,
            temperature=0.7,
            api_key=api_key,
            streaming=True,
        )

    raise ValueError(
        f"Invalid LLM mode: '{mode}'. Must be one of: 'router', 'planner', 'responder'"
    )
