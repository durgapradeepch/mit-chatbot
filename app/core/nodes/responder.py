"""
Responder Node for mit-aichat.

The "Writer" node that synthesizes the final response
based on route type and available tool results.
"""

import json
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.state import AgentState
from app.services.llm_factory import get_llm


SIMPLE_CHAT_PROMPT = """You are a helpful DevOps assistant for an AI Observability platform.

You assist users with general questions about:
- How to use the platform
- DevOps concepts and best practices
- Troubleshooting guidance
- General technical questions

Be concise, friendly, and professional. If you don't know something, say so."""


ENHANCED_ANALYSIS_PROMPT = """You are a DevOps analyst for an AI Observability platform.

You have been provided with real data from infrastructure monitoring tools.
Your job is to analyze this data and provide actionable insights to the user.

## Tool Results Data:
{tool_results}

## Instructions:
1. Answer the user's question using ONLY the data provided above
2. If the data shows errors or issues, highlight them clearly
3. Provide specific metrics, timestamps, and values when available
4. Suggest next steps or actions if appropriate
5. If the data is insufficient to answer, explain what's missing

Be precise and data-driven. Do not make up information not present in the tool results."""


async def respond_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate the final response based on available data.

    IMPORTANT: If we have tool results (regardless of route), use the
    ENHANCED_ANALYSIS_PROMPT to provide a data-driven response.
    Only use SIMPLE_CHAT for pure conversational queries with no tool data.

    Args:
        state: Current agent state containing route, tool_results, and user_query.

    Returns:
        Dictionary with final_response and messages to update state.
    """
    user_query = state["user_query"]
    route = state.get("route", "simple_chat")
    tool_results = state.get("tool_results") or []
    all_tool_results = state.get("all_tool_results") or []
    messages_history = state.get("messages", [])

    # Determine which results to use (prefer accumulated results)
    results_to_use = all_tool_results if all_tool_results else tool_results

    # KEY FIX: Use enhanced prompt if we have ANY tool results,
    # regardless of what the route says. The route just tells us
    # if the analyzer thinks we're "done" investigating.
    if results_to_use:
        formatted_results = json.dumps(results_to_use, indent=2, default=str)
        system_prompt = ENHANCED_ANALYSIS_PROMPT.format(tool_results=formatted_results)
        print(f"[Responder] Using ENHANCED prompt with {len(results_to_use)} tool results")
    else:
        system_prompt = SIMPLE_CHAT_PROMPT
        print(f"[Responder] Using SIMPLE prompt (no tool data)")

    # Build message list
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
    ]

    llm = get_llm("responder")

    # Invoke LLM (streaming=True is set in factory, enables stream events)
    response = await llm.ainvoke(messages)

    # Create AI message for history
    ai_message = AIMessage(content=response.content)

    # Return all required fields with proper defaults (never None for lists)
    return {
        "final_response": response.content,
        "messages": [HumanMessage(content=user_query), ai_message],
        # Ensure tool_results and all_tool_results are always lists (not None)
        "tool_results": tool_results if tool_results else [],
        "all_tool_results": all_tool_results if all_tool_results else [],
    }
