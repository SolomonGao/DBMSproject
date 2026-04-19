"""
GDELT MCP Server - toolRegistermodelblock

useinstalldecoratehandlermodelpatternRegistersohas MCP tool。
"""

from fastmcp import FastMCP


def init_tools(mcp: FastMCP):
    """
    Initialize GDELT tool - V2 intentdrivenversionthis
    
    Args:
        mcp: FastMCP realexample
    """
    # V2: 5intent-driven tools（newframeworkstructure）
    from .core_tools_v2 import register_core_tools
    register_core_tools(mcp)
    
    # All tools now use core_queries.py as the shared SQL layer
