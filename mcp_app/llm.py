# llm.py - LLM 接口模块
"""
LLM 客户端：
- Moonshot AI (Kimi) API 封装
- 工具调用处理
- 对话历史管理
"""

import json
from typing import List, Dict, Any, Optional, Callable

from openai import OpenAI

from .logger import get_logger

logger = get_logger("llm")


class LLMClient:
    """Kimi LLM 客户端"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.messages: List[Dict[str, Any]] = []
        
        logger.debug(f"初始化 LLMClient: model={model}, temp={temperature}")
    
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
    
    def chat(
        self,
        tools: Optional[List[Dict]] = None,
        tool_executor: Optional[Callable[[str, Dict], str]] = None
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
            logger.info(f"发送请求到 LLM (历史消息: {len(self.messages)}条)")
            
            response = self.client.chat.completions.create(
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
                return self._handle_tool_calls(message, tools, tool_executor)
            
            # 普通回复
            content = message.content or ""
            self.add_assistant_message(content)
            logger.info(f"收到回复: {content[:100]}{'...' if len(content) > 100 else ''}")
            
            return content
            
        except Exception as e:
            logger.exception(f"LLM API 错误: {e}")
            return f"❌ LLM 请求失败: {e}"
    
    def _handle_tool_calls(
        self,
        message,
        tools: Optional[List[Dict]],
        tool_executor: Callable[[str, Dict], str]
    ) -> str:
        """处理工具调用"""
        # 添加助手的工具调用请求
        self.messages.append({
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
        })
        
        logger.info(f"AI 请求调用 {len(message.tool_calls)} 个工具")
        
        # 执行工具调用
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"🛠️  调用工具: {tool_name}")
            logger.debug(f"   参数: {json.dumps(tool_args, ensure_ascii=False)}")
            
            result = tool_executor(tool_name, tool_args)
            
            logger.info(f"✅ 工具返回: {result[:80]}{'...' if len(result) > 80 else ''}")
            
            self.add_tool_result(tool_call.id, result)
        
        # 再次请求获取最终回复
        return self.chat(tools=None, tool_executor=None)
