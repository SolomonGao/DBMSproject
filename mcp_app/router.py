"""
轻量级 Router - 基于 Ollama + Qwen 2.5B

职责：
1. 用户输入清理和标准化
2. 意图识别（查询/分析/闲聊）
3. 预选择工具（给大模型参考）
4. 安全过滤

架构：
User -> Router (Qwen 2.5B local) -> [可选] LLM (Kimi/Claude) -> MCP Server
"""

import json
import re
import aiohttp
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .logger import get_logger

logger = get_logger("router")


@dataclass
class RouterDecision:
    """路由决策结果"""
    intent: str                    # 意图: query | analysis | chat | direct
    cleaned_input: str             # 清理后的用户输入
    confidence: float              # 置信度 0-1
    suggested_tools: List[str]     # 建议工具
    direct_response: Optional[str] = None  # 直接回复（闲聊时）
    skip_llm: bool = False         # 是否跳过 LLM
    reasoning: str = ""            # 判断理由


class OllamaRouter:
    """
    Ollama 本地路由器
    
    使用 Qwen 2.5B 进行轻量级意图识别
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:3b"):
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api/chat"
        logger.info(f"Router initialized: {model} @ {base_url}")
    
    async def route(self, user_input: str, context: List[Dict] = None) -> RouterDecision:
        """
        主路由函数
        
        Returns:
            RouterDecision: 包含处理决策
        """
        # Step 1: 基础清理
        cleaned = self._basic_clean(user_input)
        
        # Step 2: 系统命令直接处理
        if cleaned.startswith('/'):
            return self._handle_command(cleaned)
        
        # Step 3: 安全检查
        safety_flags = self._safety_check(cleaned)
        if safety_flags:
            return RouterDecision(
                intent="blocked",
                cleaned_input=cleaned,
                confidence=1.0,
                suggested_tools=[],
                direct_response="⚠️ 输入包含不安全内容，请重新描述。",
                skip_llm=True,
                reasoning=f"Safety flags: {safety_flags}"
            )
        
        # Step 4: 简单规则快速判断（减少模型调用）
        rule_result = self._quick_check(cleaned)
        if rule_result:
            return rule_result
        
        # Step 5: 调用 Qwen 2.5B 进行意图识别
        try:
            return await self._call_ollama(cleaned, context)
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            # Fallback 到规则判断
            return self._fallback_classify(cleaned)
    
    def _basic_clean(self, text: str) -> str:
        """基础文本清理"""
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)  # 统一空格
        text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)  # 去除零宽字符
        return text
    
    def _safety_check(self, text: str) -> List[str]:
        """安全检查"""
        flags = []
        dangerous = ['drop table', 'delete from', 'truncate table', '--', ';--']
        if any(d in text.lower() for d in dangerous):
            flags.append("sql_injection")
        return flags
    
    def _handle_command(self, command: str) -> RouterDecision:
        """处理系统命令"""
        return RouterDecision(
            intent="command",
            cleaned_input=command,
            confidence=1.0,
            suggested_tools=[],
            skip_llm=True,
            reasoning="System command"
        )
    
    def _quick_check(self, text: str) -> Optional[RouterDecision]:
        """快速规则判断（避免模型调用）"""
        text_lower = text.lower()
        
        # CLI 命令（以 / 开头）
        if text.startswith('/'):
            return RouterDecision(
                intent="command",
                cleaned_input=text,
                confidence=1.0,
                suggested_tools=[],
                skip_llm=True,
                reasoning="CLI command"
            )
        
        # 简单问候
        greetings = ['你好', 'hello', 'hi', '在吗', '在么']
        if any(g in text_lower for g in greetings) and len(text) < 10:
            return RouterDecision(
                intent="chat",
                cleaned_input=text,
                confidence=0.95,
                suggested_tools=[],
                direct_response=None,  # 让 LLM 回复
                skip_llm=False,
                reasoning="Simple greeting"
            )
        
        # 明确的数据库查询
        if any(kw in text_lower for kw in ['查询', '查找', '搜索', '查一下']):
            return None  # 需要模型进一步分析
        
        return None
    
    async def _call_ollama(self, text: str, context: List[Dict] = None) -> RouterDecision:
        """调用本地 Ollama"""
        
        system_prompt = """你是一个智能路由助手。分析用户输入，输出 JSON 格式决策。

意图分类：
- query: 需要查询 GDELT 数据库（如"查 Virginia 的新闻"、"2024年1月有什么事件"）
- analysis: 需要统计分析（如"统计冲突趋势"、"Top 10 参与方"、"可视化热力图"）
- chat: 闲聊、问候、简单问答（如"你好"、"谢谢"、"你能做什么"）
- clarification: 需要用户澄清（输入模糊或不完整）

可用工具（merge-optimized 完整工具集）：

【核心搜索工具】
- search_events: 智能事件搜索（核心入口）- 支持自然语言如"1月华盛顿的抗议"
- get_event_detail: 获取事件详情（通过指纹ID如 US-20240115-WDC-PROTEST-001）
- search_news_context: RAG语义搜索 - 查询新闻知识库获取真实报道细节

【分析统计工具】
- get_dashboard: 仪表盘数据 - 5个查询并行执行，快速获取多维度统计
- analyze_time_series: 时间序列分析 - 支持日/周/月粒度趋势分析
- get_geo_heatmap: 地理热力图 - 网格聚合展示事件密度
- analyze_conflict_cooperation: 冲突/合作趋势分析
- get_regional_overview: 区域态势概览（如"中东局势"）

【事件发现工具】
- get_hot_events: 热点事件推荐（单日）
- get_top_events: 时间段热度排行（跨时间范围，如"2024年最热事件"）
- get_daily_brief: 每日简报

【高级查询工具】
- stream_events: 流式查询 - 处理大数据量，内存友好
- query_by_time_range: 按时间范围查询
- query_by_actor: 按参与方查询
- query_by_location: 按地理位置查询（支持空间索引）

【诊断工具】
- get_cache_stats: 查看查询缓存统计
- clear_cache: 清空查询缓存

工具选择指南：
- 用户说"搜索"、"查找"、"查一下" → search_events
- 用户提到"详情"、"详细说说" + 指纹ID → get_event_detail
- 用户问"为什么"、"诉求"、"细节" → search_news_context (RAG)
- 用户问"统计"、"趋势"、"分析" → get_dashboard 或 analyze_time_series
- 用户问"地图"、"分布"、"热力" → get_geo_heatmap
- 用户问"局势"、"态势"、"怎么样" → get_regional_overview
- 用户问"热点"、"新闻"、"发生了什么"（单日）→ get_hot_events
- 用户问"最热的"、"Top"、"排行"（跨时间）→ get_top_events
- 用户要"简报"、"日报"、"总结" → get_daily_brief
- 用户说"大量数据"、"全部导出" → stream_events

工具组合建议：
- 深度事件分析: search_events → get_event_detail → search_news_context
- 区域态势: get_regional_overview + get_geo_heatmap
- 时间趋势: analyze_time_series + analyze_conflict_cooperation

输出格式（严格 JSON）：
{
    "intent": "query|analysis|chat|clarification",
    "confidence": 0.95,
    "suggested_tools": ["tool1", "tool2"],
    "needs_llm": true,
    "reasoning": "简要说明"
}

注意：
1. 只输出 JSON，不要其他内容
2. needs_llm: 复杂查询需要大模型推理时为 true，简单查询可为 false
3. confidence: 0-1 之间的数字
4. 优先使用新工具（V2），不要用旧的 query_by_actor 等"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户输入: {text}"}
        ]
        
        # 添加上下文（最近3轮）
        if context:
            recent = context[-6:] if len(context) > 6 else context
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if len(content) > 200:
                    content = content[:200] + "..."
                messages.insert(-1, {"role": role, "content": content})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=aiohttp.ClientTimeout(total=5)  # 5秒超时
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama error: {resp.status}")
                
                data = await resp.json()
                content = data["message"]["content"]
                
                # 解析 JSON
                try:
                    # 提取 JSON（防止有额外文本）
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        # 尝试修复不完整的 JSON（缺少结尾 }）
                        if not json_str.strip().endswith('}'):
                            json_str = json_str.strip() + '}'
                        result = json.loads(json_str)
                    else:
                        result = json.loads(content)
                    
                    return RouterDecision(
                        intent=result.get("intent", "query"),
                        cleaned_input=text,
                        confidence=result.get("confidence", 0.7),
                        suggested_tools=result.get("suggested_tools", []),
                        skip_llm=not result.get("needs_llm", True),
                        reasoning=result.get("reasoning", "")
                    )
                except json.JSONDecodeError:
                    # 静默处理，使用 fallback
                    logger.debug(f"Router JSON parse failed, using fallback: {content[:100]}...")
                    return self._fallback_classify(text)
    
    def _fallback_classify(self, text: str) -> RouterDecision:
        """规则 Fallback"""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ['统计', '分析', '趋势', 'dashboard', '可视化']):
            return RouterDecision(
                intent="analysis",
                cleaned_input=text,
                confidence=0.6,
                suggested_tools=["get_dashboard", "analyze_time_series"],
                skip_llm=False,
                reasoning="Fallback: analysis keywords"
            )
        
        return RouterDecision(
            intent="query",
            cleaned_input=text,
            confidence=0.6,
            suggested_tools=["query_by_actor", "query_by_time_range"],
            skip_llm=False,
            reasoning="Fallback: default to query"
        )
    
    async def health_check(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return self.model in models
                    return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
