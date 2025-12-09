"""
Analyzer Node for mit-aichat.

The "Router" node that classifies user intent and determines
whether to use simple chat or enhanced analysis with tools.
"""

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings
from app.core.state import AgentState
from app.services.llm_factory import get_llm


ROUTER_SYSTEM_PROMPT = """You are a DevOps routing assistant for an AI Observability platform.

Your job is to classify user queries and determine the appropriate response strategy.

## Classification Rules:

**simple_chat**: Use for:
- General greetings and small talk
- Questions about how to use the platform
- Conceptual explanations (e.g., "What is an incident?")
- Help requests unrelated to specific infrastructure data

**enhanced_analysis**: Use for:
- Queries about specific incidents, alerts, or metrics
- Requests for infrastructure status or health checks
- Log analysis or error investigation
- Performance monitoring queries
- Any request that requires fetching real data from systems

## Available Tools for enhanced_analysis:

- search_incidents: Search for incidents by keyword or status
  args: {"query": string, "status": "open"|"closed"|"all" (optional)}

- get_metrics: Fetch metrics from VictoriaMetrics
  args: {"metric_name": string, "time_range": string (e.g., "1h", "24h")}

- search_logs: Search logs from VictoriaLogs
  args: {"query": string, "severity": "error"|"warn"|"info"|"all" (optional)}

- get_service_status: Get status of a specific service
  args: {"service_name": string}

- query_topology: Query the infrastructure topology from Neo4j
  args: {"entity_type": string, "filters": object (optional)}

## Response Format:

You MUST respond with ONLY valid JSON in this exact format:

{
  "route": "simple_chat" | "enhanced_analysis",
  "intent": "brief description of what the user wants",
  "entities": ["extracted", "key", "entities"],
  "tool_plan": [
    {"tool": "tool_name", "args": {"arg1": "value1"}}
  ]
}

Rules:
- tool_plan should be an empty array [] for simple_chat
- tool_plan should contain 1 or more tools for enhanced_analysis
- Always extract relevant entities (service names, time ranges, keywords)
- Respond with ONLY the JSON object, no additional text or markdown"""


async def analyze_node(state: AgentState) -> Dict[str, Any]:
    """
    Analyze user query and determine routing strategy.

    Classifies the query as simple_chat or enhanced_analysis,
    and generates a tool_plan if tools are needed.

    Args:
        state: Current agent state containing user_query.

    Returns:
        Dictionary with route, query_analysis, and tool_plan to update state.
    """
    user_query = state["user_query"]

    llm = get_llm("router")

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=user_query),
    ]

    try:
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            # Remove markdown code block wrapper
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        parsed = json.loads(response_text)

        route = parsed.get("route", "simple_chat")
        query_analysis = {
            "intent": parsed.get("intent", ""),
            "entities": parsed.get("entities", []),
        }
        tool_plan = parsed.get("tool_plan", [])

        # Validate route value
        if route not in ("simple_chat", "enhanced_analysis"):
            route = "simple_chat"
            tool_plan = []

        return {
            "route": route,
            "query_analysis": query_analysis,
            "tool_plan": tool_plan,
        }

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Default to simple_chat on parse failure to ensure continuity
        print(f"Analyzer parse error: {e}")
        return {
            "route": "simple_chat",
            "query_analysis": {"intent": "unknown", "entities": []},
            "tool_plan": [],
        }
