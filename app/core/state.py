"""
State definitions for the LangGraph agent.

Defines the TypedDict that flows through all nodes in the graph.
This is the single source of truth for data passed between nodes.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    State container passed between all nodes in the LangGraph.

    Attributes:
        messages: Chat history accumulator. Uses operator.add for automatic
                  message list concatenation across nodes.
        user_query: The raw input query from the user.
        route: Classification result from analyzer. Either "simple_chat"
               or "enhanced_analysis".
        query_analysis: Structured intent extracted from the query.
                        Contains parsed entities, time ranges, etc.
        tool_plan: List of tools to execute with their parameters.
                   Populated by the planner for enhanced queries.
        tool_results: Raw data returned from MCP server tool executions.
        final_response: The generated response text to return to the user.
    """

    messages: Annotated[List[BaseMessage], operator.add]
    user_query: str
    route: str
    query_analysis: Optional[Dict[str, Any]]
    tool_plan: Optional[List[Dict[str, Any]]]
    tool_results: Optional[List[Dict[str, Any]]]
    final_response: str
