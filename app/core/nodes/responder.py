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
    Generate the final response based on route and available data.

    Constructs appropriate prompts based on simple_chat vs enhanced_analysis,
    and synthesizes a response using the responder LLM.

    Args:
        state: Current agent state containing route, tool_results, and user_query.

    Returns:
        Dictionary with final_response and messages to update state.
    """
    user_query = state["user_query"]
    route = state.get("route", "simple_chat")
    tool_results = state.get("tool_results", [])
    messages_history = state.get("messages", [])

    # Construct system prompt based on route
    if route == "enhanced_analysis" and tool_results:
        # Format tool results for the prompt
        formatted_results = json.dumps(tool_results, indent=2, default=str)
        system_prompt = ENHANCED_ANALYSIS_PROMPT.format(tool_results=formatted_results)
    else:
        system_prompt = SIMPLE_CHAT_PROMPT

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

    return {
        "final_response": response.content,
        "messages": [HumanMessage(content=user_query), ai_message],
    }
