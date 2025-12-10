"""
Rewriter Node for mit-aichat (Corrective RAG).

Rewrites failed queries to improve search results while
PRESERVING key identifiers like service names and entity names.
"""
import json
from typing import Any, Dict
from langchain_core.messages import HumanMessage
from app.core.state import AgentState
from app.services.llm_factory import get_llm


REWRITER_SYSTEM_PROMPT = """You are a query rewriter for a DevOps Observability agent.
The previous search returned 0 results. Your job is to fix the query.

CRITICAL RULES:
1. PRESERVE KEY IDENTIFIERS - Never remove service names, product names, or entity names
   - If query has "Acme-cart" -> keep "Acme" and "cart" in some form
   - If query has "payment-service" -> keep "payment" in the rewrite

2. STRATEGY: SIMPLIFY HYPHENATED NAMES
   - "acme-cart-service-prod" -> "acme cart" (split, remove suffixes like -prod, -service)
   - "my-payment-api-v2" -> "payment api" (keep core terms)

3. STRATEGY: REMOVE TECHNICAL SUFFIXES
   - Remove: -service, -api, -prod, -dev, -staging, -v1, -v2
   - Keep: The actual product/service name

4. STRATEGY: TRY PARTIAL MATCH
   - If "acme-cart" failed, try just "cart" but ONLY if "acme cart" also failed
   - Always try the combined form first before going to single words

5. DO NOT:
   - Replace specific terms with generic ones like "application" or "system"
   - Change "acme cart incidents" to just "incidents" (loses context)
   - Make the query so broad it matches unrelated results

EXAMPLES:
- "acme-cart-service incidents" -> "acme cart incidents"
- "payment-api-prod errors" -> "payment api errors"
- "my-service-v2 status" -> "my-service status"

Return ONLY the rewritten query. No quotes, no explanations."""


async def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    Rewrite the user's query to improve tool results.

    Preserves key identifiers while simplifying the query format.
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

    # Build context on what was tried
    tried_context = []
    for item in tool_results:
        tool_name = item.get("tool", "unknown")
        args = item.get("args", {})
        tried_context.append(f"- Tried '{tool_name}' with args: {json.dumps(args)}")

    tried_summary = "\n".join(tried_context) if tried_context else "No tool details available"

    # Ask LLM to fix it while preserving key terms
    rewrite_input = f"""Original query: "{user_query}"

What was tried:
{tried_summary}

Rewrite this query following the rules above. PRESERVE the key service/product names."""

    llm = get_llm("router")  # Use fast model
    messages = [
        {"role": "system", "content": REWRITER_SYSTEM_PROMPT},
        {"role": "user", "content": rewrite_input},
    ]

    response = await llm.ainvoke(messages)
    rewritten_query = response.content.strip().strip('"').strip("'")

    print(f"[Rewriter] Original: '{user_query}' -> Rewritten: '{rewritten_query}'")

    return {
        "user_query": rewritten_query,
        "retry_count": retry_count + 1,
        "messages": [HumanMessage(content=f"Retrying search with: '{rewritten_query}'")],
        # Clear previous results so the analyzer runs fresh
        "tool_plan": None,
        "tool_results": None,
        "query_analysis": None,
    }
