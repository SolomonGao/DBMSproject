"""
工具注册模块

使用装饰器模式注册所有 MCP 工具。
"""

from fastmcp import FastMCP


def init_tools(mcp: FastMCP):
    """
    使用装饰器模式初始化所有工具
    
    Args:
        mcp: FastMCP 实例
    """
    # 延迟导入避免循环依赖
    from .calculator import create_calculate_tool
    from .search import create_smart_search_tool
    from .database import create_database_tools
    
    # 创建工具（装饰器自动注册到 mcp）
    create_calculate_tool(mcp)
    create_smart_search_tool(mcp)
    create_database_tools(mcp)
