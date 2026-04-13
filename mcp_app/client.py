# client.py - MCP Client Core Module
"""
MCP Client:
- Supports stdio and sse transport modes
- Tool discovery and format conversion
- Async tool calling
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable, Awaitable
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from .logger import get_logger

logger = get_logger("mcp_client")


class MCPClient:
    """MCP Client"""
    
    def __init__(self, server_path: str, transport: str = "stdio", port: int = 8000):
        self.server_path = server_path
        self.transport = transport
        self.port = port
        
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools: List[Dict[str, Any]] = []
        self._tools_map: Dict[str, Any] = {}
        
        logger.debug(f"Initializing MCPClient: transport={transport}, port={port}")
    
    async def connect(self) -> bool:
        """
        Connect to MCP Server
        
        Returns:
            Whether connection succeeded
        """
        try:
            logger.info(f"Connecting to MCP Server ({self.transport} mode)...")
            
            if self.transport == "stdio":
                await self._connect_stdio()
            else:
                await self._connect_sse()
            
            # Initialize session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )
            await self.session.initialize()
            
            logger.info("✅ MCP Server connected")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to MCP Server: {e}")
            return False
    
    async def _connect_stdio(self):
        """stdio mode connection"""
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.read, self.write = stdio_transport
        logger.debug(f"stdio connection established: {self.server_path}")
    
    async def _connect_sse(self):
        """sse mode connection"""
        url = f"http://localhost:{self.port}/sse"
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(url)
        )
        self.read, self.write = sse_transport
        logger.debug(f"sse connection established: {url}")
    
    async def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Discover and convert tool definitions
        
        Returns:
            OpenAI format tool list
        """
        if not self.session:
            logger.error("Not connected to MCP Server, cannot discover tools")
            return []
        
        try:
            logger.info("Discovering tools...")
            
            tools_result = await self.session.list_tools()
            mcp_tools = tools_result.tools
            
            # Convert to OpenAI format
            openai_tools = []
            self._tools_map = {}
            
            for tool in mcp_tools:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                    }
                }
                openai_tools.append(openai_tool)
                self._tools_map[tool.name] = tool
            
            self.tools = openai_tools
            
            logger.info(f"Discovered {len(openai_tools)} tools:")
            for tool in openai_tools:
                name = tool['function']['name']
                desc = tool['function']['description'][:40] + "..."
                logger.info(f"  • {name}: {desc}")
            
            return openai_tools
            
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call MCP tool
        
        Args:
            tool_name: Tool name
            arguments: Tool arguments
        
        Returns:
            Tool execution result
        """
        if not self.session:
            error_msg = "Not connected to MCP Server"
            logger.error(error_msg)
            return error_msg
        
        logger.debug(f"Calling tool: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")
        
        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            
            # Extract text content
            texts = []
            for content in result.content:
                if content.type == "text":
                    texts.append(content.text)
            
            result_text = "\n".join(texts) if texts else "Tool executed, no content returned"
            logger.debug(f"Tool returned: {result_text[:100]}{'...' if len(result_text) > 100 else ''}")
            
            return result_text
            
        except Exception as e:
            error_msg = f"Tool call failed: {e}"
            logger.error(error_msg)
            return error_msg
    
    def create_tool_executor(self) -> Callable[[str, Dict], Awaitable[str]]:
        """
        Create async tool executor
        
        Returns:
            Async callback function returning Awaitable[str]
        """
        async def executor(tool_name: str, tool_args: Dict) -> str:
            try:
                # Directly await, no longer using future.result() to block thread
                return await self.call_tool(tool_name, tool_args)
            except Exception as e:
                logger.exception(f"Tool execution error: {e}")
                return f"Tool execution error: {e}"
        return executor
    
    async def close(self):
        """Close connection and cleanup resources"""
        try:
            await self.exit_stack.aclose()
            logger.info("🔌 MCP Server connection closed")
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
