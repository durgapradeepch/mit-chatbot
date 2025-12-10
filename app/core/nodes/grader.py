"""
Grader Node for mit-aichat (Corrective RAG).

Evaluates the quality of tool results to determine if they
are sufficient to answer the user's query or if a rewrite is needed.

IMPORTANT: Uses "partial success" logic - if ANY tool returns valid data,
the overall quality is GOOD. Only mark as BAD if ALL tools failed.
"""

import json
from typing import Any, Dict

from app.core.state import AgentState


# Heuristic patterns that indicate poor/empty results
BAD_RESULT_PATTERNS = [
    "0 results",
    "count: 0",
    "count\":0",
    "count\": 0",
    "no data found",
    "No data found",
    "no results found",
    "No results found",
]


def _extract_actual_data(result: Any) -> Any:
    """
    Extract the actual data from potentially nested API response.

    Manifest API returns: {"success": true, "result": {...actual data...}}
    We need to look inside "result" for the real data.
    """
    if isinstance(result, dict):
        # Check for nested "result" key (Manifest API pattern)
        if "result" in result:
            return result["result"]
        # Check for nested "data" key
        if "data" in result:
            return result["data"]
    return result


def _has_meaningful_data(data: Any) -> bool:
    """
    Check if data contains meaningful content (not empty).

    Returns True if:
    - List with items
    - Dict with non-metadata keys that have values
    - Non-empty string
    - Number
    """
    if data is None:
        return False

    if isinstance(data, list):
        return len(data) > 0

    if isinstance(data, dict):
        # Filter out metadata-only dicts
        data_keys = [k for k in data.keys() if k not in ("meta", "metadata", "pagination", "success")]
        if not data_keys:
            return False
        # Check if any data key has a non-empty value
        for key in data_keys:
            val = data.get(key)
            if val is not None and val != [] and val != {} and val != "":
                return True
        return False

    if isinstance(data, str):
        return len(data.strip()) > 0

    # Numbers, booleans, etc. are meaningful
    return True


def _check_single_result(item: Dict[str, Any]) -> bool:
    """
    Check if a single tool result contains valid data.

    Returns True if the result has meaningful data.
    """
    tool_name = item.get("tool", "unknown")

    # Check for explicit error flags
    if item.get("error"):
        print(f"[Grader Debug] {tool_name}: Has error flag")
        return False

    # Get the raw result
    raw_result = item.get("result", {})

    # Check if raw result indicates explicit failure
    if isinstance(raw_result, dict) and raw_result.get("success") is False:
        print(f"[Grader Debug] {tool_name}: success=False")
        return False

    # Extract actual data (handles nested {"success": true, "result": ...})
    actual_data = _extract_actual_data(raw_result)

    # Quick check: if it's a non-empty list, it's GOOD (skip pattern matching)
    if isinstance(actual_data, list) and len(actual_data) > 0:
        print(f"[Grader Debug] {tool_name}: Non-empty list with {len(actual_data)} items - GOOD")
        return True

    # Convert to string for pattern matching
    result_str = json.dumps(actual_data) if isinstance(actual_data, (dict, list)) else str(actual_data)

    # Check for bad patterns in the actual data
    for pattern in BAD_RESULT_PATTERNS:
        if pattern.lower() in result_str.lower():
            print(f"[Grader Debug] {tool_name}: Bad pattern '{pattern}' found")
            return False

    # Check if there's meaningful data
    has_data = _has_meaningful_data(actual_data)
    print(f"[Grader Debug] {tool_name}: has_meaningful_data={has_data}")
    return has_data


def _check_result_quality(tool_results: list) -> bool:
    """
    Check overall result quality using PARTIAL SUCCESS logic.

    If ANY tool returned valid data, consider it a success.
    Only return False if ALL tools failed or returned empty.

    Args:
        tool_results: List of tool execution results.

    Returns:
        True if at least one result has valid data, False if all failed.
    """
    if not tool_results:
        return False

    # PARTIAL SUCCESS: If ANY tool has good data, overall is good
    for item in tool_results:
        if _check_single_result(item):
            return True

    # All tools failed
    return False


async def grader_node(state: AgentState) -> Dict[str, Any]:
    """
    Grade the quality of tool results.

    Uses PARTIAL SUCCESS logic: If any tool returned valid data,
    the data quality is "good". Only marks as "bad" if all tools
    failed or returned empty results.

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

    # Evaluate result quality with partial success logic
    is_good = _check_result_quality(tool_results)

    # Debug logging
    if not is_good:
        print(f"[Grader] Marked as BAD. Results: {json.dumps(tool_results, default=str)[:500]}")
    else:
        print(f"[Grader] Marked as GOOD. Found valid data in {len(tool_results)} tool(s)")

    return {"data_quality": "good" if is_good else "bad"}
