from fastmcp import FastMCP, Context
from app.models import CalcInput
from app.services.calculator import CalculatorService

calc_service = CalculatorService()

def register_calculator_tools(mcp: FastMCP):
    @mcp.tool()
    async def calculate(params: CalcInput, ctx: Context) -> str:
        """执行安全的数学计算"""
        return calc_service.eval_expression(params.expression, params.precision)