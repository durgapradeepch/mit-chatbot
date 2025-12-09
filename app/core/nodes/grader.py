"""
Grader Node for mit-aichat (Corrective RAG).

Evaluates the quality of tool results to determine if they
are sufficient to answer the user's query or if a rewrite is needed.
"""

import json
from typing import Any, Dict

from app.core.state import AgentState


# Heuristic patterns that indicate poor/empty results
BAD_RESULT_PATTERNS = [
    "[]",           # Empty array
    "{}",           # Empty object
    '"error"',      # Error in response
    '"Error"',
    "0 results",
    "count: 0",
    "count\":0",
    "count\": 0",
    "no data",
    "No data",
    "not found",
    "Not found",
]


def _check_result_quality(tool_results: list) -> bool:
    """
    Heuristic check for result quality.

    Args:
        tool_results: List of tool execution results.

    Returns:
        True if results appear valid, False if empty/error.
    """
    if not tool_results:
        return False

    # Check each tool result
    for item in tool_results:
        result = item.get("result", {})

        # Convert to string for pattern matching
        result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)

        # Check for bad patterns
        for pattern in BAD_RESULT_PATTERNS:
            if pattern in result_str:
                return False

        # Check for explicit error flags
        if item.get("error") or item.get("success") is False:
            return False

        # Check if result is essentially empty
        if isinstance(result, list) and len(result) == 0:
            return False
        if isinstance(result, dict):
            # Empty dict or dict with only metadata but no actual data
            data_keys = [k for k in result.keys() if k not in ("meta", "metadata", "pagination")]
            if not data_keys:
                return False
            # Check if all data values are empty
            if all(not result.get(k) for k in data_keys):
                return False

    return True


async def grader_node(state: AgentState) -> Dict[str, Any]:
    """
    Grade the quality of tool results.

    Evaluates whether the retrieved data is sufficient to answer
    the user's query. If not, marks data_quality as "bad" to
    trigger query rewriting.

    Args:
        state: Current agent state containing tool_results.

    Returns:
        Dictionary with data_quality ("good" or "bad").
    """
    tool_results = state.get("tool_results", [])
    retry_count = state.get("retry_count", 0)

    # Safety valve: if we've retried too many times, accept whatever we have
    if retry_count >= 3:
        return {"data_quality": "good"}

    # Evaluate result quality
    is_good = _check_result_quality(tool_results)

    return {"data_quality": "good" if is_good else "bad"}
