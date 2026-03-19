# cli.py - 命令行交互界面
"""
CLI 界面：
- 欢迎信息和配置展示
- 对话循环
- 命令处理
"""

import asyncio
import sys
from typing import Optional

from .logger import get_logger

logger = get_logger("cli")


class ChatCLI:
    """命令行聊天界面"""
    
    # 表情符号映射
    EMOJI = {
        'user': '👤',
        'ai': '🤖',
        'tool': '🛠️',
        'system': '⚙️',
        'error': '❌',
        'success': '✅',
        'info': 'ℹ️',
        'warning': '⚠️',
        'prompt': '➜',
    }
    
    def __init__(self, config, llm, mcp):
        self.config = config
        self.llm = llm
        self.mcp = mcp
        self.running = False
        
        self._setup_system_prompt()
        logger.debug("ChatCLI 初始化完成")
    
    def _setup_system_prompt(self):
        """设置系统提示词"""
        system_prompt = """你是一个智能助手，可以通过工具帮助用户解决问题。

当前可用的工具包括：
1. calculate - 执行数学计算
2. get_weather - 获取天气信息
3. analyze_code - 分析代码统计信息
4. smart_search - 搜索知识库

当用户的问题需要工具时，请主动调用合适的工具。回答要简洁明了。"""
        
        self.llm.add_system_message(system_prompt)
    
    def print_welcome(self):
        """打印欢迎信息"""
        from .providers import get_provider
        
        provider = get_provider(self.config.llm_provider)
        provider_emoji = {
            'kimi_code': '⭐',
            'moonshot': '🌙',
            'claude': '🧠', 
            'gemini': '💎'
        }.get(self.config.llm_provider, '🤖')
        
        print()
        print("=" * 60)
        print(f"{self.EMOJI['system']} 欢迎使用 GDELT MCP Client v1")
        print("=" * 60)
        print()
        print("📋 配置摘要:")
        print(f"   {provider_emoji} LLM 提供商: {provider.name if provider else self.config.llm_provider}")
        print(f"   🔑 API Key: {self.config.get_masked_api_key()}")
        print(f"   🤖 LLM 模型: {self.config.llm_model}")
        print(f"   🔧 MCP Server: {self.config.mcp_transport}模式")
        print()
        print("💡 可用命令:")
        print("   /help    - 显示帮助信息")
        print("   /clear   - 清空对话历史")
        print("   /tools   - 显示可用工具列表")
        print("   /status  - 显示状态信息")
        print("   /quit    - 退出程序")
        print()
        print("📝 直接输入消息开始对话...")
        print("-" * 60)
        print()
        
        logger.info("欢迎界面已显示")
    
    def print_help(self):
        """打印帮助信息"""
        print()
        print("📖 帮助信息")
        print("-" * 40)
        print("本应用是一个 MCP 客户端，集成了 Kimi AI 和工具调用功能。")
        print()
        print("💬 对话命令:")
        print("   /help    - 显示此帮助")
        print("   /clear   - 清空对话历史")
        print("   /tools   - 列出可用工具")
        print("   /status  - 显示当前状态")
        print("   /quit    - 退出应用")
        print()
        print("🔧 工具使用:")
        print("   AI 会自动判断是否需要调用工具，你也可以明确要求。")
        print()
        print("⚙️  配置:")
        print("   编辑 .env 文件修改 API Key 和其他设置")
        print("-" * 40)
        print()
    
    def print_tools(self):
        """打印工具列表"""
        print()
        print("🔧 可用工具列表")
        print("-" * 40)
        
        if not self.mcp.tools:
            print("暂无可用工具")
            return
        
        for i, tool in enumerate(self.mcp.tools, 1):
            func = tool["function"]
            print(f"{i}. {func['name']}")
            print(f"   描述: {func['description']}")
            if 'parameters' in func and 'properties' in func['parameters']:
                print(f"   参数:")
                for param_name, param_info in func['parameters']['properties'].items():
                    desc = param_info.get('description', '无描述')
                    required = param_name in func['parameters'].get('required', [])
                    req_mark = "*" if required else ""
                    print(f"      - {param_name}{req_mark}: {desc}")
            print()
        
        print("-" * 40)
        print()
    
    def print_status(self):
        """打印状态信息"""
        print()
        print("📊 当前状态")
        print("-" * 40)
        print(f"MCP Server: {'✅ 已连接' if self.mcp.session else '❌ 未连接'}")
        print(f"可用工具: {len(self.mcp.tools)} 个")
        print(f"对话历史: {self.llm.get_history_length()} 条消息")
        print(f"日志级别: {self.config.log_level}")
        print("-" * 40)
        print()
    
    def handle_command(self, command: str) -> bool:
        """
        处理命令
        
        Returns:
            False 表示退出程序，True 表示继续
        """
        cmd = command.lower().strip()
        
        if cmd in ['/quit', '/exit', '/q', 'quit', 'exit']:
            print(f"\n{self.EMOJI['success']} 再见！")
            logger.info("用户退出")
            self.running = False
            return False
        
        elif cmd in ['/help', '/h', 'help']:
            self.print_help()
        
        elif cmd in ['/clear', '/c', 'clear']:
            self.llm.clear_history()
            self._setup_system_prompt()
            print(f"{self.EMOJI['success']} 对话历史已清空\n")
            logger.info("对话历史已清空")
        
        elif cmd in ['/tools', '/t', 'tools']:
            self.print_tools()
        
        elif cmd in ['/status', '/s', 'status']:
            self.print_status()
        
        else:
            print(f"{self.EMOJI['error']} 未知命令: {command}")
            print("   输入 /help 查看可用命令\n")
        
        return True
    
    async def chat_loop(self):
        """主对话循环"""
        self.running = True
        self.print_welcome()
        
        # 创建工具执行器
        tool_executor = self.mcp.create_tool_executor()
        
        while self.running:
            try:
                # 获取用户输入（使用 to_thread 避免阻塞事件循环）
                user_input = await asyncio.to_thread(
                    input, f"{self.EMOJI['user']} 你: "
                )
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                # 检查是否是命令
                if user_input.startswith('/'):
                    if not self.handle_command(user_input):
                        break
                    continue
                
                logger.info(f"用户输入: {user_input[:50]}...")
                
                # 添加用户消息
                self.llm.add_user_message(user_input)
                
                # 调用 LLM
                print(f"{self.EMOJI['ai']} AI: ", end="", flush=True)
                
                response = await self.llm.chat(
                    tools=self.mcp.tools,
                    tool_executor=tool_executor
                )
                
                print(response)
                print()
                
            except KeyboardInterrupt:
                print(f"\n\n{self.EMOJI['info']} 收到中断信号")
                logger.info("收到键盘中断")
                break
            except EOFError:
                print(f"\n\n{self.EMOJI['info']} 输入结束")
                logger.info("收到 EOF")
                break
            except Exception as e:
                logger.exception(f"对话循环错误: {e}")
                print(f"\n{self.EMOJI['error']} 错误: {e}\n")
        
        print(f"{self.EMOJI['success']} 正在退出...")
        logger.info("CLI 循环结束")
