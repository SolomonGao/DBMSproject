# app/services/calculator.py
import math

class CalculatorService:
    def __init__(self):
        self.safe_dict = {
            'sqrt': math.sqrt, 'pow': math.pow, 'abs': abs, 
            'round': round, 'pi': math.pi, 'e': math.e
        }

    def eval_expression(self, expression: str, precision: int) -> str:
        try:
            result = eval(expression, {"__builtins__": {}}, self.safe_dict)
            return str(round(result, precision) if isinstance(result, float) else result)
        except Exception as e:
            return f"计算错误: {str(e)}"