"""
Graph orchestration for mit-aichat.

Builds and compiles the LangGraph workflow that connects
Analyzer -> Executor -> Responder with conditional routing.
"""

from langgraph.graph import END, START, StateGraph

from app.core.edges import route_decision
from app.core.state import AgentState
from app.core.nodes.analyzer import analyze_node
from app.core.nodes.executor import execute_node
from app.core.nodes.responder import respond_node


def build_graph() -> StateGraph:
    """
    Build the agent workflow graph.

    Flow:
        START -> analyze -> [conditional] -> execute -> respond -> END
                               |                          ^
                               +--- (simple_chat) --------+

    Returns:
        Compiled StateGraph ready for invocation.
    """
    # Initialize graph with state schema
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("respond", respond_node)

    # Add edges
    # Entry point: START -> analyze
    workflow.add_edge(START, "analyze")

    # Conditional routing from analyze based on route_decision
    workflow.add_conditional_edges(
        "analyze",
        route_decision,
        {
            "execute": "execute",
            "respond": "respond",
        },
    )

    # Execute always feeds into respond
    workflow.add_edge("execute", "respond")

    # Respond is the terminal node
    workflow.add_edge("respond", END)

    return workflow


# Compile the graph for use
graph = build_graph().compile()
