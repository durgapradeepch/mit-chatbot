"""
Edge definitions for the LangGraph agent.

Contains conditional routing logic that determines
the flow between nodes based on state.
"""

from typing import Literal

from app.core.state import AgentState


def route_decision(state: AgentState) -> Literal["execute", "respond"]:
    """
    Determine the next node based on the analyzer's routing decision.

    Args:
        state: Current agent state containing the route classification.

    Returns:
        "execute" if enhanced_analysis is needed (triggers Executor node).
        "respond" for simple_chat (skips tools, goes directly to Responder).
    """
    route = state.get("route", "simple_chat")

    if route == "enhanced_analysis":
        return "execute"

    return "respond"
