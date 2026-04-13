"""
GDELT MCP Server - toolRegister模块

use装饰器模式Register所has MCP tool。
"""

from fastmcp import FastMCP


def init_tools(mcp: FastMCP):
    """
    Initialize GDELT tool - V2 intentdriven版this
    
    Args:
        mcp: FastMCP 实例
    """
    # V2: 5intent-driven tools（新架构）
    from .core_tools_v2 import register_core_tools
    register_core_tools(mcp)
    
    # oldtoolalreadydeprecated（gdelt_optimized.py - 15个Args化tool）
    # If you need to restore old tools，Cancelunder面注释：
    # from .gdelt_optimized import create_optimized_tools
    # create_optimized_tools(mcp)
