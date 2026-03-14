# client.py - MCP 客户端核心模块
"""
MCP 客户端：
- 支持 stdio 和 sse 两种传输模式
- 工具发现和格式转换
- 异步工具调用
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from .logger import get_logger

logger = get_logger("mcp_client")


class MCPClient:
    """MCP 客户端"""
    
    def __init__(self, server_path: str, transport: str = "stdio", port: int = 8000):
        self.server_path = server_path
        self.transport = transport
        self.port = port
        
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools: List[Dict[str, Any]] = []
        self._tools_map: Dict[str, Any] = {}
        
        logger.debug(f"初始化 MCPClient: transport={transport}, port={port}")
    
    async def connect(self) -> bool:
        """
        连接到 MCP Server
        
        Returns:
            是否连接成功
        """
        try:
            logger.info(f"正在连接到 MCP Server ({self.transport}模式)...")
            
            if self.transport == "stdio":
                await self._connect_stdio()
            else:
                await self._connect_sse()
            
            # 初始化会话
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )
            await self.session.initialize()
            
            logger.info("✅ MCP Server 连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 连接 MCP Server 失败: {e}")
            return False
    
    async def _connect_stdio(self):
        """stdio 模式连接"""
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.read, self.write = stdio_transport
        logger.debug(f"stdio 连接已建立: {self.server_path}")
    
    async def _connect_sse(self):
        """sse 模式连接"""
        url = f"http://localhost:{self.port}/sse"
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(url)
        )
        self.read, self.write = sse_transport
        logger.debug(f"sse 连接已建立: {url}")
    
    async def discover_tools(self) -> List[Dict[str, Any]]:
        """
        发现并转换工具定义
        
        Returns:
            OpenAI 格式的工具列表
        """
        if not self.session:
            logger.error("未连接到 MCP Server，无法发现工具")
            return []
        
        try:
            logger.info("正在发现工具...")
            
            tools_result = await self.session.list_tools()
            mcp_tools = tools_result.tools
            
            # 转换为 OpenAI 格式
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
            
            logger.info(f"发现 {len(openai_tools)} 个工具:")
            for tool in openai_tools:
                name = tool['function']['name']
                desc = tool['function']['description'][:40] + "..."
                logger.info(f"  • {name}: {desc}")
            
            return openai_tools
            
        except Exception as e:
            logger.error(f"发现工具失败: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        if not self.session:
            error_msg = "未连接到 MCP Server"
            logger.error(error_msg)
            return error_msg
        
        logger.debug(f"调用工具: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")
        
        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            
            # 提取文本内容
            texts = []
            for content in result.content:
                if content.type == "text":
                    texts.append(content.text)
            
            result_text = "\n".join(texts) if texts else "工具执行完成，无返回内容"
            logger.debug(f"工具返回: {result_text[:100]}{'...' if len(result_text) > 100 else ''}")
            
            return result_text
            
        except Exception as e:
            error_msg = f"工具调用失败: {e}"
            logger.error(error_msg)
            return error_msg
    
    def create_tool_executor(self) -> Callable[[str, Dict], str]:
        """
        创建同步工具执行器
        
        Returns:
            同步回调函数
        """
        def executor(tool_name: str, tool_args: Dict) -> str:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self.call_tool(tool_name, tool_args), 
                        loop
                    )
                    return future.result(timeout=30)
                else:
                    return loop.run_until_complete(
                        self.call_tool(tool_name, tool_args)
                    )
            except Exception as e:
                logger.exception(f"工具执行错误: {e}")
                return f"工具执行错误: {e}"
        
        return executor
    
    async def close(self):
        """关闭连接并清理资源"""
        try:
            await self.exit_stack.aclose()
            logger.info("🔌 MCP Server 连接已关闭")
        except Exception as e:
            logger.warning(f"关闭连接时出错: {e}")
