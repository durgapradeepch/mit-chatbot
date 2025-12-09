"""
Graph orchestration for mit-aichat (v4 - Iterative Drill-Down).

Builds and compiles the LangGraph workflow with:
- Corrective RAG (rewrite bad queries)
- Iterative Investigation (drill down for details)

Flow:
    START -> analyze -> [execute or respond]
                 ^            |
                 |            v
                 +-- grader <-+
                       |
                       v
                    rewriter (if bad data)
"""

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.core.state import AgentState
from app.core.edges import route_decision, grader_decision
from app.core.nodes.analyzer import analyze_node
from app.core.nodes.executor import execute_node
from app.core.nodes.responder import respond_node
from app.core.nodes.grader import grader_node
from app.core.nodes.rewriter import rewriter_node


def build_graph() -> StateGraph:
    """
    Build the agent workflow graph with Iterative Drill-Down.

    Flow (v4 - Iterative Investigation):
        START -> analyze -> [conditional] -> execute -> grader -> [conditional] -> analyze (loop)
                               |                                       |
                               |                                       +-- rewrite (if bad)
                               |                                             |
                               +--- (simple_chat) ---------> respond --------+

    The Analyzer examines previous results and decides:
    - "I need more info" -> route: enhanced_analysis -> execute -> grader -> loop
    - "I have enough" -> route: simple_chat -> respond

    Safety valves:
    - Max 3 query rewrites
    - Max 5 investigation depth

    Returns:
        StateGraph ready for compilation.
    """
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("rewriter", rewriter_node)
    workflow.add_node("respond", respond_node)

    # 2. Add Edges

    # Entry point: START -> analyze
    workflow.add_edge(START, "analyze")

    # Analyze -> Execute OR Respond
    # If analyzer says "enhanced_analysis" -> go execute tools
    # If analyzer says "simple_chat" -> go respond (we have enough info)
    workflow.add_conditional_edges(
        "analyze",
        route_decision,
        {
            "execute": "execute",
            "respond": "respond",
        },
    )

    # Execute -> Grader (evaluate results)
    workflow.add_edge("execute", "grader")

    # Grader -> Analyze OR Rewrite
    # If data is good -> loop back to analyzer (decide if more investigation needed)
    # If data is bad -> rewrite query and try again
    workflow.add_conditional_edges(
        "grader",
        grader_decision,
        {
            "analyze": "analyze",   # Good data -> let analyzer decide next step
            "rewrite": "rewriter",  # Bad data -> fix the query
        },
    )

    # Rewriter -> Analyze (try again with improved query)
    workflow.add_edge("rewriter", "analyze")

    # Respond is the terminal node
    workflow.add_edge("respond", END)

    return workflow


# Memory checkpointer for conversation persistence & HITL
checkpointer = MemorySaver()

# Compile two versions of the graph:
# 1. graph_with_hitl: includes checkpointer (for HITL workflows with thread_id)
# 2. graph: stateless version for LangServe (no checkpointer = no thread_id required)
graph_with_hitl = build_graph().compile(
    checkpointer=checkpointer,
    interrupt_before=["execute"],  # HITL: pause before tool execution
)

# Default graph for LangServe (stateless, no checkpointer = no thread_id required)
graph = build_graph().compile()
