# llm.py - LLM 接口模块
"""
LLM 客户端：
- 使用 OpenAI 客户端封装
- 通过 http_client 传递伪装 headers
- 工具调用处理
- 对话历史管理
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable, Awaitable

import httpx
from openai import AsyncOpenAI

from .logger import get_logger

logger = get_logger("llm")


class LLMClient:
    """LLM 客户端 - 使用 OpenAI 封装，伪装成 Claude Code"""
    
    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self.provider = provider.lower()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 初始化 OpenAI 客户端
        # 使用 default_headers 伪装成 Claude Code
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            default_headers={
                "User-Agent": "claude-code/1.0",
                "X-Client-Name": "claude-code",
            },
        )
        
        self.messages: List[Dict[str, Any]] = []
        
        logger.debug(f"初始化 LLMClient: provider={provider}, model={model}")
    
    def add_system_message(self, content: str):
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})
        logger.debug(f"添加系统消息: {content[:50]}...")
    
    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        logger.debug(f"添加用户消息: {content[:50]}...")
    
    def add_assistant_message(self, content: str):
        """添加助手消息"""
        self.messages.append({"role": "assistant", "content": content})
    
    def add_tool_result(self, tool_call_id: str, content: str):
        """添加工具调用结果"""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })
        logger.debug(f"添加工具结果 [{tool_call_id}]: {content[:50]}...")
    
    def clear_history(self, keep_system: bool = True):
        """清空对话历史"""
        if keep_system:
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            self.messages = system_msgs
            logger.info("对话历史已清空（保留系统消息）")
        else:
            self.messages.clear()
            logger.info("对话历史已完全清空")
    
    def get_history_length(self) -> int:
        """获取对话历史长度"""
        return len(self.messages)
    
    def truncate_history(self, max_messages: int = 10, keep_system: bool = True):
        """
        截断对话历史，只保留最近 N 条
        
        Args:
            max_messages: 保留的最大消息数（不含系统消息）
            keep_system: 是否保留系统消息
        """
        system_msgs = [m for m in self.messages if m["role"] == "system"] if keep_system else []
        non_system_msgs = [m for m in self.messages if m["role"] != "system"]
        
        # 只保留最近 N 条非系统消息
        if len(non_system_msgs) > max_messages:
            kept_msgs = non_system_msgs[-max_messages:]
            self.messages = system_msgs + kept_msgs
            logger.info(f"历史已截断: 保留最近 {max_messages} 条消息")
        
        return len(self.messages)
    
    async def chat(
        self,
        tools: Optional[List[Dict]] = None,
        tool_executor: Optional[Callable[[str, Dict], Awaitable[str]]] = None
    ) -> str:
        """
        发送对话请求
        
        Args:
            tools: 可用工具列表
            tool_executor: 工具执行函数
        
        Returns:
            AI 回复内容
        """
        try:
            logger.info(f"发送请求到 {self.provider} (历史消息: {len(self.messages)}条)")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )
            
            message = response.choices[0].message
            
            # 处理工具调用
            if message.tool_calls and tool_executor:
                return await self._handle_tool_calls(message, tools, tool_executor)
            
            # 普通回复
            content = message.content or ""
            
            # Kimi 特有的 reasoning_content
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                logger.debug(f"模型思考过程: {message.reasoning_content[:100]}...")
            
            self.add_assistant_message(content)
            logger.info(f"收到回复: {content[:100]}{'...' if len(content) > 100 else ''}")
            
            return content
            
        except Exception as e:
            logger.exception(f"LLM API 错误: {e}")
            return f"LLM 请求失败: {e}"
    
    async def _handle_tool_calls(
        self,
        message,
        tools: Optional[List[Dict]],
        tool_executor: Callable[[str, Dict], Awaitable[str]]
    ) -> str:
        """处理工具调用"""
        # 构建助手的工具调用请求消息
        assistant_msg = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        }
        
        # 如果启用了 thinking 功能，需要包含 reasoning_content
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            assistant_msg["reasoning_content"] = message.reasoning_content
            logger.debug(f"工具调用思考过程: {message.reasoning_content[:100]}...")
        
        self.messages.append(assistant_msg)
        
        logger.info(f"AI 请求调用 {len(message.tool_calls)} 个工具")
        
        # 并行执行工具调用
        async def execute_single_tool(tool_call):
            """执行单个工具调用"""
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"[并行] 调用工具: {tool_name}")
            logger.debug(f"参数: {json.dumps(tool_args, ensure_ascii=False)}")
            
            start_time = asyncio.get_event_loop().time()
            result = await tool_executor(tool_name, tool_args)
            elapsed = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"[并行] 工具 {tool_name} 返回 ({elapsed:.2f}s): {result[:80]}{'...' if len(result) > 80 else ''}")
            
            return tool_call.id, result
        
        # 并行执行所有工具
        results = await asyncio.gather(*[
            execute_single_tool(tc) for tc in message.tool_calls
        ])
        
        # 按原始顺序添加结果（保持 tool_call_id 对应）
        for tool_call in message.tool_calls:
            for tc_id, result in results:
                if tc_id == tool_call.id:
                    self.add_tool_result(tool_call.id, result)
                    break
        
        # 再次请求获取最终回复
        return await self.chat(tools=None, tool_executor=None)
    
    async def close(self):
        """关闭 LLM 客户端连接"""
        if hasattr(self, 'client'):
            await self.client.close()
