"""
GDELT MCP Server - 工具注册模块

使用装饰器模式注册所有 MCP 工具。
"""

from fastmcp import FastMCP


def init_tools(mcp: FastMCP):
    """
    初始化所有 GDELT 工具
    
    Args:
        mcp: FastMCP 实例
    """
    # 只注册优化版工具（包含所有原始功能 + 缓存 + 并行查询）
    from .gdelt_optimized import create_optimized_tools
    create_optimized_tools(mcp)
    
    # 注意：原始工具已合并到优化版中
    # from .gdelt import create_gdelt_tools
    # create_gdelt_tools(mcp)
