"""
Rewriter Node for mit-aichat (Corrective RAG).
"""
import json
from typing import Any, Dict
from langchain_core.messages import HumanMessage
from app.core.state import AgentState
from app.services.llm_factory import get_llm

# --- UPDATED PROMPT FOR "SMART SPLITTING" ---
REWRITER_SYSTEM_PROMPT = """You are a query rewriter for a DevOps Observability agent.
The previous search returned 0 results. Your job is to fix the query.

STRATEGY 1: SPLIT HYPHENATED NAMES (High Priority)
If the user searched for a long, specific service name like "acme-cart-service-prod" and it failed:
- The exact name might be wrong.
- SPLIT it into broader terms.
- Example: "acme-cart-service" -> "cart" OR "acme cart"

STRATEGY 2: REMOVE SPECIFIC IDs
If the user searched for "incident-12345" and it failed:
- The ID might be wrong.
- Search for the *type* of issue instead.
- Example: "incident-12345" -> "latest incidents"

STRATEGY 3: FIX TYPOS
- Example: "sevrity" -> "severity"

Return ONLY the rewritten query text. Do not add quotes or explanations."""


async def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    Rewrite the user's query to improve tool results.
    """
    user_query = state.get("user_query", "")
    tool_results = state.get("tool_results", [])
    retry_count = state.get("retry_count", 0)

    # Safety valve: stop after 3 tries
    if retry_count >= 3:
        return {
            "retry_count": retry_count,
            "data_quality": "good",  # Force acceptance to stop loop
        }

    # Build context on what failed
    failed_context = []
    for item in tool_results:
        tool_name = item.get("tool", "unknown")
        # We only need to know it failed
        failed_context.append(f"- Tool '{tool_name}' returned empty/error")

    failed_summary = "\n".join(failed_context)

    # Ask LLM to fix it
    rewrite_input = f"""Original query: "{user_query}"
Failures: {failed_summary}

Rewrite this query to be broader and more likely to succeed."""

    llm = get_llm("router")  # Use fast model
    messages = [
        {"role": "system", "content": REWRITER_SYSTEM_PROMPT},
        {"role": "user", "content": rewrite_input},
    ]

    response = await llm.ainvoke(messages)
    rewritten_query = response.content.strip().strip('"')

    return {
        "user_query": rewritten_query,
        "retry_count": retry_count + 1,
        # This message tells the user (and the agent history) what happened
        "messages": [HumanMessage(content=f"Search failed. Retrying with broader term: '{rewritten_query}'")],
        # Clear previous results so the analyzer runs fresh
        "tool_plan": None,
        "tool_results": None,
        "query_analysis": None,
    }
