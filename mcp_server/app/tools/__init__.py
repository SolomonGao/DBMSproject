"""
GDELT MCP Server - toolRegistermodel块

use装饰handlermodelpatternRegistersohas MCP tool。
"""

from fastmcp import FastMCP


def init_tools(mcp: FastMCP):
    """
    Initialize GDELT tool - V2 intentdriven版this
    
    Args:
        mcp: FastMCP realexample
    """
    # V2: 5intent-driven tools（new架structure）
    from .core_tools_v2 import register_core_tools
    register_core_tools(mcp)
    
    # oldtoolalreadydeprecated（gdelt_optimized.py - 15Argsizationtool）
    # If you need to restore old tools，Cancelunder面注释：
    # from .gdelt_optimized import create_optimized_tools
    # create_optimized_tools(mcp)
