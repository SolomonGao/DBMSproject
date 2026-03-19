from fastmcp import FastMCP
from app.tools.calculator import register_calculator_tools
from app.tools.search import register_analysis_tools


def init_tools(mcp: FastMCP):
    """一键初始化所有工具模块"""
    register_calculator_tools(mcp)
    register_analysis_tools(mcp)