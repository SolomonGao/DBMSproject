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
    from .gdelt import create_gdelt_tools
    
    # 注册所有 GDELT 数据库工具
    create_gdelt_tools(mcp)
