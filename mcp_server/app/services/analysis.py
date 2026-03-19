from typing import Callable, Optional

class AnalysisService:
    def __init__(self):
        self._kb = {
            "mcp": "MCP (Model Context Protocol) 是开放协议", 
            "kimi": "Kimi 是月之暗面开发的大规模语言模型", 
            "fastmcp": "FastMCP 是基于 Python 的 MCP 快速开发框架"
        }

    def smart_search(self, query: str, logger: Optional[Callable[[str], None]] = None) -> str:
        """
        执行搜索逻辑
        :param query: 搜索关键词
        :param logger: 可选的日志回调函数 (通常传入 ctx.info)
        """
        if logger:
            logger(f"🚀 正在分析关键词: {query}")
        
        query_lower = query.lower()
        
        # 模拟一个复杂的处理过程
        results = [v for k, v in self._kb.items() if query_lower in k]
        
        if logger:
            logger(f"📊 检索完成，找到 {len(results)} 条匹配项")
            
        if not results:
            return f"❌ 未找到与 '{query}' 相关的结果。"
            
        return "\n".join(results)