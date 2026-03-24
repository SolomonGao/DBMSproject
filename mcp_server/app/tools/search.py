"""
智能搜索工具

使用装饰器模式注册 MCP 工具。
"""

from app.models import SearchInput
from app.services.analysis import AnalysisService

# 服务实例
analysis_service = AnalysisService()


def create_smart_search_tool(mcp):
    """创建 smart_search 工具（使用装饰器模式）"""
    
    @mcp.tool()
    async def smart_search(params: SearchInput, ctx) -> str:
        """
        智能知识库搜索工具
        
        支持搜索: mcp, kimi, fastmcp 等相关知识
        """
        # 使用 ctx.info 发送进度信息到客户端 UI
        ctx.info("正在调起分析服务...")
        
        result = analysis_service.smart_search(
            query=params.query, 
            logger=ctx.info
        )
        
        return result
    
    return smart_search
