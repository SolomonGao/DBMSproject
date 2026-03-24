"""
数学计算工具

使用装饰器模式注册 MCP 工具。
"""

from app.models import CalcInput
from app.services.calculator import CalculatorService

# 服务实例
calc_service = CalculatorService()


# 工具函数将通过装饰器在 main.py 中注册
def create_calculate_tool(mcp):
    """创建 calculate 工具（使用装饰器模式）"""
    
    @mcp.tool()
    async def calculate(params: CalcInput, ctx) -> str:
        """
        执行安全的数学计算
        
        支持函数: sqrt, pow, abs, round, pi, e
        示例: "sqrt(16) + pow(2, 3)"
        """
        return calc_service.eval_expression(params.expression, params.precision)
    
    return calculate
