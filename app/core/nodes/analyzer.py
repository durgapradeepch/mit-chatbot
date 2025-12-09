"""
Analyzer Node for mit-aichat (v4 - Iterative Drill-Down).

Classifies user intent and generates schema-aware tool plans.
Now supports iterative investigation by examining previous tool results
and deciding whether to drill deeper or respond.
"""
import json
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.state import AgentState
from app.services.llm_factory import get_llm
from app.tools.mcp.client import MCPClient


async def analyze_node(state: AgentState) -> Dict[str, Any]:
    """
    Iterative Investigator: Decides next step based on current knowledge.

    On first run: Plans initial search tools.
    On follow-up: Examines previous results and decides to drill deeper or respond.

    Args:
        state: Current agent state with user_query and accumulated tool_results.

    Returns:
        Dictionary with route, query_analysis, tool_plan, and investigation_depth.
    """
    user_query = state["user_query"]
    all_tool_results = state.get("all_tool_results", [])
    tool_results = state.get("tool_results", [])
    investigation_depth = state.get("investigation_depth", 0)

    # Accumulate results from this iteration
    if tool_results:
        all_tool_results = (all_tool_results or []) + tool_results

    # 1. Fetch full tool schemas dynamically from MCP server
    client = MCPClient()
    tools_schema_text = await client.get_tool_prompt()

    # 2. Build context from previous results
    previous_context = ""
    if all_tool_results:
        previous_context = "\n\n## PREVIOUS INVESTIGATION RESULTS:\n"
        for i, result in enumerate(all_tool_results[-5:], 1):  # Last 5 results max
            tool_name = result.get("tool", "unknown")
            tool_result = result.get("result", {})
            # Truncate large results
            result_str = json.dumps(tool_result, default=str)[:2000]
            previous_context += f"\n### Step {i}: {tool_name}\n```json\n{result_str}\n```\n"

    # 3. Build the Iterative Investigation Prompt
    system_prompt = f"""You are an Iterative Investigator for a DevOps Agent.
Your job is to investigate user questions step-by-step, drilling down for details.

{tools_schema_text}
{previous_context}

---

## YOUR DECISION PROCESS

**If this is the FIRST analysis (no previous results):**
- Plan the initial search to find relevant data
- Use broad search tools like `search_incidents`, `search_resources`

**If there ARE previous results:**
1. Review what was found in the previous steps
2. Ask yourself: "Do I have enough information to answer the user's question?"
   - If YES: Set `route: "simple_chat"` to generate the final answer
   - If NO: Plan the NEXT drill-down step

**Drill-Down Examples:**
- Found Incident ID 1529? -> Call `get_incident_by_id` with that ID
- Found Resource with issues? -> Call `search_changelogs` for that resource
- Need to understand dependencies? -> Call `get_graph_nodes`
- Need logs for debugging? -> Call `query_logs` with relevant filters

---

## RULES

1. **One Step at a Time:** Plan only the next logical step, not 5 tools at once.
2. **Use Found IDs:** If you found an ID in previous results, USE IT in your next tool call.
3. **Stop Condition:** If you have enough data to answer, set `route: "simple_chat"`.
4. **Max Depth:** You are at investigation depth {investigation_depth}/5. If at 5, you MUST respond.
5. **Parameter Strictness:** Only use parameters listed in "Allowed Parameters".

---

## OUTPUT FORMAT (JSON ONLY)

{{
    "route": "simple_chat" | "enhanced_analysis",
    "reasoning": "Brief explanation of your decision",
    "intent": "What the user wants",
    "entities": ["extracted", "entities"],
    "tool_plan": [
        {{
            "tool": "exact_tool_name",
            "args": {{ "valid_param": "value" }}
        }}
    ]
}}

- If `route: "simple_chat"`: tool_plan should be []
- If `route: "enhanced_analysis"`: tool_plan should have 1-2 tools for the next step
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User Question: {user_query}"),
    ]

    # 4. Invoke LLM
    llm = get_llm("router")

    try:
        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        analysis = json.loads(content)

        route = analysis.get("route", "simple_chat")
        query_analysis = {
            "intent": analysis.get("intent", ""),
            "entities": analysis.get("entities", []),
            "reasoning": analysis.get("reasoning", ""),
        }
        tool_plan = analysis.get("tool_plan", [])

        # Validate route
        if route not in ("simple_chat", "enhanced_analysis"):
            route = "simple_chat"
            tool_plan = []

        # Force respond if max depth reached
        if investigation_depth >= 5 and route == "enhanced_analysis":
            print(f"[Analyzer] Max investigation depth reached, forcing response")
            route = "simple_chat"
            tool_plan = []

        # Increment depth if continuing investigation
        new_depth = investigation_depth + 1 if route == "enhanced_analysis" else investigation_depth

        return {
            "route": route,
            "query_analysis": query_analysis,
            "tool_plan": tool_plan,
            "all_tool_results": all_tool_results,
            "investigation_depth": new_depth,
        }

    except Exception as e:
        print(f"Analyzer Error: {e}")
        return {
            "route": "simple_chat",
            "query_analysis": {"intent": "unknown", "entities": [], "error": str(e)},
            "tool_plan": [],
            "all_tool_results": all_tool_results,
            "investigation_depth": investigation_depth,
        }
