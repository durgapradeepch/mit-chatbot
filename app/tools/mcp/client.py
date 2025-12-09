"""
MCP Client for mit-aichat.

Async HTTP client to communicate with the Node.js MCP Server
running on port 3001. Provides tool discovery and execution capabilities.
"""

from typing import Any, Dict, List

import aiohttp

from app.core.config import get_settings


class MCPClient:
    """
    Async client for the MCP (Model Context Protocol) Server.

    Handles communication with the external Node.js MCP server
    for tool listing and execution.
    """

    def __init__(self) -> None:
        """Initialize MCP client with server URL from settings."""
        settings = get_settings()
        self.base_url = str(settings.MCP_SERVER_URL).rstrip("/")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Retrieve available tools from the MCP server.

        Returns:
            List of tool definitions with name, description, and parameters.
            Returns empty list on error to allow graceful degradation.
        """
        url = f"{self.base_url}/api/mcp/tools"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    print(f"MCP list_tools failed with status {response.status}")
                    return []
        except Exception as e:
            print(f"MCP list_tools error: {e}")
            return []

    async def get_tool_prompt(self) -> str:
        """
        Returns a detailed schema of all available tools with their parameters.

        Format:
        ### tool_name
        Description: ...
        Allowed Parameters:
          - param_1 (REQUIRED): description
          - param_2: description

        Returns:
            Formatted string with full tool schemas for LLM parameter awareness.
        """
        response = await self.list_tools()
        tools = response.get("tools", []) if isinstance(response, dict) else []

        if not tools:
            return "No tools available."

        prompt_lines = ["AVAILABLE TOOLS AND PARAMETERS:"]

        for tool in tools:
            name = tool.get("name")
            desc = tool.get("description", "No description")
            prompt_lines.append(f"\n### {name}")
            prompt_lines.append(f"Description: {desc}")

            # Extract allowed parameters from inputSchema
            schema = tool.get("inputSchema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            if properties:
                prompt_lines.append("Allowed Parameters:")
                for param, details in properties.items():
                    param_type = details.get("type", "any")
                    param_desc = details.get("description", "")
                    is_req = "(REQUIRED)" if param in required else ""
                    # Create a clear definition line for the LLM
                    prompt_lines.append(f"  - {param} [{param_type}] {is_req}: {param_desc}")
            else:
                prompt_lines.append("Parameters: None")

        return "\n".join(prompt_lines)

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool on the MCP server.

        Args:
            tool_name: The name of the tool to execute.
            arguments: Dictionary of parameters to pass to the tool.

        Returns:
            Tool execution result on success.
            Error dictionary with 'error' and 'success: False' on failure.
            Never raises exceptions to ensure graph continuity.
        """
        url = f"{self.base_url}/api/mcp/execute"
        payload = {
            "tool_name": tool_name,
            "parameters": arguments,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        return await response.json()

                    error_text = await response.text()
                    return {
                        "error": f"MCP server returned status {response.status}: {error_text}",
                        "success": False,
                    }
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
            }
