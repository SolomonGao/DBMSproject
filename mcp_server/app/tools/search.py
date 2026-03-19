from fastmcp import FastMCP, Context
from app.models import SearchInput
from app.services.analysis import AnalysisService

analysis_service = AnalysisService()

def register_analysis_tools(mcp: FastMCP):
    @mcp.tool()
    async def smart_search(params: SearchInput, ctx: Context) -> str:
        """
        智能知识库搜索工具
        """
        # 1. 直接使用 ctx 发送控制台消息
        ctx.info("正在调起分析服务...")
        
        # 2. 将 ctx.info 作为 logger 传入 Service
        # 这样 Service 内部的进度会实时显示在客户端（如 Claude/Kimi）的 UI 上
        result = analysis_service.smart_search(
            query=params.query, 
            logger=ctx.info
        )
        
        return result