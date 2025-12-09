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


def grader_decision(state: AgentState) -> Literal["analyze", "rewrite"]:
    """
    Determine next step based on grader's quality assessment.

    Part of the Iterative Drill-Down pattern:
    - If data is BAD and retries remain -> rewrite query
    - If data is GOOD -> loop back to analyzer to check if more investigation needed

    The Analyzer will then decide:
    - "I have enough info" -> route: simple_chat -> respond
    - "I need to drill deeper" -> route: enhanced_analysis -> execute

    Args:
        state: Current agent state containing data_quality and retry_count.

    Returns:
        "analyze" if data is good (let analyzer decide next step).
        "rewrite" if data is bad and retries remain.
    """
    data_quality = state.get("data_quality", "good")
    retry_count = state.get("retry_count", 0)
    investigation_depth = state.get("investigation_depth", 0)

    # Safety valve: max 3 rewrites for bad data
    if data_quality == "bad" and retry_count < 3:
        return "rewrite"

    # Safety valve: max 5 investigation depth to prevent infinite loops
    if investigation_depth >= 5:
        return "analyze"  # Will force simple_chat due to depth check in analyzer

    # Data is good -> go back to analyzer to decide if we need more info
    return "analyze"
