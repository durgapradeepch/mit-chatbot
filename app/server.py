"""
Enterprise server for mit-aichat.

Uses LangServe to expose standard production endpoints:
- /agent/invoke
- /agent/stream
- /agent/stream_events
"""

from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes
from pydantic import BaseModel, Field

from app.core.graph import graph


# ============================================================
# Input/Output Schemas for LangServe (fixes playground error)
# ============================================================


class ChatInput(BaseModel):
    """Input schema for the agent."""

    user_query: str = Field(description="The user's query or question")
    messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chat history (optional)"
    )


class ChatOutput(BaseModel):
    """Output schema for the agent."""

    final_response: str = Field(description="The agent's response")
    route: str = Field(description="The route taken (simple_chat or enhanced_analysis)")
    tool_results: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Results from tool executions (if any)"
    )


app = FastAPI(
    title="MIT AI Chat",
    version="1.0",
    description="AI Observability Agent with LangGraph and LangServe",
)

# CORS configuration for frontend dev environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LangServe routes - automatically generates:
# - POST /agent/invoke
# - POST /agent/stream
# - POST /agent/stream_events
add_routes(
    app,
    graph.with_types(input_type=ChatInput, output_type=ChatOutput),
    path="/agent",
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
