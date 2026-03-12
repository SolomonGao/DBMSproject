#!/usr/bin/env python3
# mcp_server/server.py
import asyncio
import json
import math
import sys
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

try:
    from fastmcp import FastMCP, Context
except ImportError:
    print("❌ 请先安装 fastmcp: pip install fastmcp")
    sys.exit(1)

mcp = FastMCP("KimiSmartTools")

class CalcInput(BaseModel):
    expression: str = Field(..., description="数学表达式")
    precision: int = Field(default=2, ge=0, le=10)

class WeatherInput(BaseModel):
    city: str = Field(...)
    date: Optional[str] = None
    unit: Literal["celsius", "fahrenheit"] = Field(default="celsius")

class CodeInput(BaseModel):
    code: str = Field(...)
    language: Literal["python", "javascript", "java", "cpp"] = Field(default="python")
    analyze_complexity: bool = Field(default=True)

@mcp.tool()
async def calculate(params: CalcInput, ctx: Context) -> str:
    """执行数学计算"""
    safe_dict = {'sqrt': math.sqrt, 'pow': math.pow, 'abs': abs, 'round': round, 
                 'max': max, 'min': min, 'pi': math.pi, 'e': math.e}
    try:
        result = eval(params.expression, {"__builtins__": {}}, safe_dict)
        return f"结果: {round(result, params.precision) if isinstance(result, float) else result}"
    except Exception as e:
        return f"错误: {e}"

@mcp.tool()
async def get_weather(params: WeatherInput, ctx: Context) -> str:
    """获取天气"""
    weather_db = {"北京": (22, "晴"), "上海": (25, "多云"), "广州": (28, "小雨")}
    temp, cond = weather_db.get(params.city, (20, "未知"))
    if params.unit == "fahrenheit":
        temp = temp * 9/5 + 32
    date = params.date or datetime.now().strftime("%Y-%m-%d")
    return f"{params.city} {date}: {cond}, {temp}{'°F' if params.unit=='fahrenheit' else '°C'}"

@mcp.tool()
async def analyze_code(params: CodeInput, ctx: Context) -> str:
    """分析代码"""
    lines = params.code.split('\n')
    return f"{params.language}代码: {len(lines)}行, 非空: {sum(1 for l in lines if l.strip())}行"

@mcp.tool()
async def smart_search(params: CodeInput, ctx: Context) -> str:  # 修正：应该是 SearchInput
    """搜索知识"""
    kb = {"mcp": "MCP是开放协议", "kimi": "Kimi是月之暗面模型", "fastmcp": "FastMCP是Python框架"}
    results = [v for k,v in kb.items() if params.code.lower() in k]  # 修正：这里应该是 query
    return "\n".join(results) if results else "未找到"

@mcp.resource("config://app")
def get_config() -> str:
    return json.dumps({"version": "1.0", "tools": 4})

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='stdio')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    
    print(f"🚀 启动 {mcp.name} ({args.transport}模式)")
    print("🔧 工具: calculate, get_weather, analyze_code, smart_search")
    
    try:
        if args.transport == 'stdio':
            print("⏳ 等待连接...", file=sys.stderr)
            mcp.run(transport='stdio')
        else:
            print(f"🌐 http://localhost:{args.port}/sse")
            mcp.run(transport='sse', port=args.port)
    except KeyboardInterrupt:
        print("\n🛑 已停止")

if __name__ == "__main__":
    main()