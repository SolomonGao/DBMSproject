"""MCP Client for communicating with FastMCP Server."""

import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from gdelt_api.config import Settings, get_project_root, get_settings
from gdelt_api.core.exceptions import MCPError
from gdelt_api.core.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """Client for communicating with FastMCP Server."""
    
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.tools: list[Any] = []
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected
    
    async def connect(self, server_script: str | None = None) -> None:
        """Connect to MCP Server."""
        if self._connected:
            logger.warning("already_connected")
            return
        
        script_path = server_script or self._get_default_server_path()
        
        if not os.path.exists(script_path):
            raise MCPError(f"MCP Server script not found: {script_path}")
        
        logger.info("connecting_to_mcp_server", script=script_path)
        
        try:
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[os.path.abspath(script_path)],
                env={**os.environ, "PYTHONPATH": get_project_root()},
                stderr=sys.stderr,
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = stdio_transport
            
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            await self.session.initialize()
            
            # Get available tools
            tools_result = await self.session.list_tools()
            self.tools = tools_result.tools
            self._connected = True
            
            logger.info(
                "mcp_connected",
                tool_count=len(self.tools),
                tool_names=[t.name for t in self.tools],
            )
            
        except Exception as e:
            logger.error("mcp_connection_failed", error=str(e))
            await self.close()
            raise MCPError(f"Failed to connect to MCP Server: {e}")
    
    def _get_default_server_path(self) -> str:
        """Get default MCP server script path."""
        project_root = get_project_root()
        return os.path.join(
            project_root,
            self.settings.mcp.server_script_path,
        )
    
    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Convert MCP tools to OpenAI function format."""
        if not self.tools:
            return []
        
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in self.tools
        ]
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool."""
        if not self._connected or not self.session:
            raise MCPError("Not connected to MCP Server")
        
        logger.debug("calling_tool", tool=name, args=arguments)
        
        try:
            result = await self.session.call_tool(name, arguments)
            
            # Extract text content
            text_parts = [
                content.text 
                for content in result.content 
                if isinstance(content, TextContent)
            ]
            
            output = "".join(text_parts)
            
            logger.debug("tool_result", tool=name, result_length=len(output))
            
            return output
            
        except Exception as e:
            logger.error("tool_call_failed", tool=name, error=str(e))
            raise MCPError(f"Tool '{name}' failed: {e}")
    
    async def list_resources(self) -> list[Any]:
        """List available resources."""
        if not self._connected or not self.session:
            raise MCPError("Not connected to MCP Server")
        
        result = await self.session.list_resources()
        return result.resources
    
    async def read_resource(self, uri: str) -> str:
        """Read a resource."""
        if not self._connected or not self.session:
            raise MCPError("Not connected to MCP Server")
        
        result = await self.session.read_resource(uri)
        return result.content
    
    async def close(self) -> None:
        """Close MCP connection."""
        if self.exit_stack:
            await self.exit_stack.aclose()
            self._connected = False
            self.session = None
            self.tools = []
            logger.info("mcp_disconnected")


# Singleton instance
_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    """Get or create MCP client singleton."""
    global _mcp_client
    
    if _mcp_client is None:
        _mcp_client = MCPClient()
    
    return _mcp_client


async def close_mcp_client() -> None:
    """Close global MCP client."""
    global _mcp_client
    
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
