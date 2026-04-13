"""
GDELT MCP Server - 工具Register模块

use装饰器模式Register所has MCP 工具。
"""

from fastmcp import FastMCP


def init_tools(mcp: FastMCP):
    """
    Initialize GDELT 工具 - V2 意图驱动版本
    
    Args:
        mcp: FastMCP 实例
    """
    # V2: 5intent-driven tools（新架构）
    from .core_tools_v2 import register_core_tools
    register_core_tools(mcp)
    
    # 旧工具已停用（gdelt_optimized.py - 15个Args化工具）
    # If you need to restore old tools，Cancel下面注释：
    # from .gdelt_optimized import create_optimized_tools
    # create_optimized_tools(mcp)
