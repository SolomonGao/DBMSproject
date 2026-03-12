
import asyncio
import json
import os
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

class FastMCPClient:
    """与 FastMCP Server 通信的客户端"""
    
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.tools = []
        
    async def connect(self, server_script: str):
        """连接到 FastMCP Server"""
        server_params = StdioServerParameters(
            command="python",
            args=[server_script],
            env={**os.environ, "PYTHONPATH": "."}
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        
        await self.session.initialize()
        
        # 获取工具列表（FastMCP 自动生成的 Schema）
        tools_result = await self.session.list_tools()
        self.tools = tools_result.tools
        print(f"✅ 已连接 FastMCP Server，发现 {len(self.tools)} 个工具")
        
    def get_openai_tools(self):
        """转换为 Kimi/OpenAI 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            for tool in self.tools
        ]
    
    async def call_tool(self, name: str, arguments: dict):
        """调用 FastMCP 工具"""
        result = await self.session.call_tool(name, arguments)
        return "".join([c.text for c in result.content if hasattr(c, 'text')])
    
    async def get_resources(self):
        """获取 FastMCP 注册的资源"""
        resources = await self.session.list_resources()
        return resources.resources
    
    async def read_resource(self, uri: str):
        """读取资源内容"""
        return await self.session.read_resource(uri)
    
    async def close(self):
        await self.exit_stack.aclose()

# 主程序（与 Kimi 集成）
async def main():
    client = FastMCPClient()
    kimi = AsyncOpenAI(
        api_key=os.getenv("API_KEY"),
        base_url="https://api.moonshot.cn/v1"
    )
    
    try:
        await client.connect("mcp_server/server.py")
        
        # 对话循环
        messages = [{"role": "system", "content": "使用可用工具帮助用户"}]
        
        while True:
            user = input("\n👤 用户: ")
            if user == "quit":
                break
                
            messages.append({"role": "user", "content": user})
            
            # 调用 Kimi，传入 FastMCP 工具
            response = await kimi.chat.completions.create(
                model="kimi-k2-0905-preview",
                messages=messages,
                tools=client.get_openai_tools(),
                tool_choice="auto"
            )
            
            msg = response.choices[0].message
            
            # 处理工具调用（FastMCP 会自动处理参数验证）
            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                })
                
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    print(f"\n🔧 调用 FastMCP 工具: {tc.function.name}")
                    
                    # 调用 FastMCP Server
                    result = await client.call_tool(tc.function.name, args)
                    print(f"📊 结果: {result[:200]}...")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result
                    })
                
                # 获取最终回答
                final = await kimi.chat.completions.create(
                    model="kimi-k2-0905-preview",
                    messages=messages
                )
                print(f"\n🤖 Kimi: {final.choices[0].message.content}")
                messages.append({
                    "role": "assistant", 
                    "content": final.choices[0].message.content
                })
            else:
                print(f"\n🤖 Kimi: {msg.content}")
                messages.append({"role": "assistant", "content": msg.content})
                
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())