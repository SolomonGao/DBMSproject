# cli.py - 命令行交互界面
"""
CLI 界面：
- 欢迎信息和配置展示
- 对话循环
- 命令处理
- Router 集成（Qwen 2.5B 本地模型）
"""

import asyncio
import sys
from typing import Optional

from .logger import get_logger, sanitize_for_log
from .router import OllamaRouter

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
        self.router: Optional[OllamaRouter] = None
        self.router_enabled = False
        
        self._setup_router()
        self._setup_system_prompt()
        logger.debug("ChatCLI 初始化完成")
    
    def _setup_router(self):
        """初始化 Router（如果 Ollama 可用）"""
        import os
        # Docker 容器访问宿主机 Ollama 需要用 host.docker.internal (Mac/Windows)
        # Linux 需要用宿主机 IP 或 --network host
        ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
        
        try:
            self.router = OllamaRouter(
                base_url=ollama_host,
                model="qwen2.5:3b"
            )
            logger.info(f"Router initialized: {ollama_host}")
        except Exception as e:
            logger.warning(f"Router initialization failed: {e}")
            self.router = None
    
    def _setup_system_prompt(self):
        """设置系统提示词"""
        system_prompt = """你是一个 GDELT 数据分析助手，专门帮助用户查询和分析全球事件数据。

当前可用的工具包括：

【基础查询】
- get_schema: 获取数据库表结构
- execute_sql: 执行自定义 SQL 查询

【便捷查询】
- query_by_actor: 按参与方名称查询事件
- query_by_time_range: 按时间范围查询事件  
- query_by_location: 按地理位置查询事件（使用空间索引 MBRContains + ST_Distance_Sphere）
- **query_by_location_and_time**: 【推荐】按地理位置+时间范围组合查询（最高效！）
  - 适用于："1月份DC附近的新闻"、"2024年3月纽约附近的事件"
  - 性能：比分别调用 query_by_time_range + query_by_location 快 10-50 倍
  - 工作原理：时间索引 + 空间索引(MBRContains) + 精确距离计算

【统计分析】
- analyze_daily_events: 每日事件统计分析
- analyze_top_actors: 统计最活跃的参与方
- analyze_conflict_cooperation: 分析冲突/合作趋势
- get_dashboard: 仪表盘数据（并发获取多维度统计）
- analyze_time_series: 高级时间序列分析
- get_geo_heatmap: 地理热力图数据

【其他】
- generate_chart: 生成数据可视化配置
- stream_query_events: 流式查询（处理大量数据）
- get_cache_stats: 查看缓存统计
- clear_cache: 清除查询缓存

【Router 建议】
系统配置了智能 Router（Qwen 2.5B）进行输入分析。当用户输入中包含 "[系统提示：建议优先使用以下工具: ...]" 时，请优先考虑这些工具建议，但你有最终决定权。

【重要提示】
当用户查询同时包含"时间范围"和"地理位置"时（如"1月份DC附近的新闻"），
务必使用 query_by_location_and_time 组合查询工具，不要并行调用 query_by_time_range 和 query_by_location。
组合查询性能提升 10-50 倍！

当用户的问题需要查询数据时，请主动调用合适的工具。优先使用便捷查询工具（如 query_by_actor）而不是 execute_sql。回答要简洁明了。"""
        
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
        # 显示 Router 状态
        if self.router:
            print(f"   🧠 Router: 已配置 ({self.router.model})")
        else:
            print(f"   🧠 Router: 未配置")
        print()
        print("💡 可用命令:")
        print("   /help    - 显示帮助信息")
        print("   /clear   - 清空对话历史")
        print("   /tools   - 显示可用工具列表")
        print("   /status  - 显示状态信息")
        print("   /router  - 开启/关闭 Router (Qwen 2.5B)")
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
        print("   /router  - 开启/关闭 Router (Qwen 2.5B)")
        print("   /quit    - 退出应用")
        print()
        print("🧠 Router (本地 Qwen 2.5B):")
        print("   智能路由：输入清理 → 意图识别 → 工具预选择")
        print("   需要本地安装: ollama run qwen2.5:3b")
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
        router_status = "✅ 开启" if self.router_enabled else ("⚠️ 关闭" if self.router else "❌ 未安装")
        print(f"Router: {router_status}")
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
        
        elif cmd in ['/router', '/r']:
            # 切换 Router 状态
            if not self.router:
                print(f"{self.EMOJI['error']} Router 未初始化（需要 Ollama + qwen2.5:3b）\n")
            else:
                self.router_enabled = not self.router_enabled
                status = "开启" if self.router_enabled else "关闭"
                print(f"{self.EMOJI['success']} Router 已{status}\n")
        
        else:
            print(f"{self.EMOJI['error']} 未知命令: {command}")
            print("   输入 /help 查看可用命令\n")
        
        return True
    
    async def chat_loop(self):
        """主对话循环（集成 Router）"""
        self.running = True
        self.print_welcome()
        
        # 创建工具执行器
        tool_executor = self.mcp.create_tool_executor()
        
        # 检查 Router 健康状态
        if self.router:
            router_healthy = await self.router.health_check()
            if router_healthy:
                self.router_enabled = True
                print(f"{self.EMOJI['info']} Router enabled (Qwen 2.5B)\n")
            else:
                print(f"{self.EMOJI['warning']} Router unavailable, using direct mode\n")
        
        while self.running:
            try:
                # 获取用户输入
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
                
                # ====== Router 处理 ======
                router_decision = None
                if self.router_enabled and self.router:
                    try:
                        router_decision = await self.router.route(
                            user_input, 
                            context=self.llm.messages[-6:] if hasattr(self.llm, 'messages') else None
                        )
                        logger.info(f"Router decision: {router_decision.intent} (confidence: {router_decision.confidence:.2f})")
                        
                        # 显示路由信息（调试用，可注释掉）
                        if router_decision.intent == "chat":
                            print(f"{self.EMOJI['info']} [Router] 闲聊模式\n")
                        elif router_decision.intent == "query":
                            print(f"{self.EMOJI['info']} [Router] 数据查询: {router_decision.suggested_tools}\n")
                        elif router_decision.intent == "analysis":
                            print(f"{self.EMOJI['info']} [Router] 数据分析: {router_decision.suggested_tools}\n")
                        
                    except Exception as e:
                        logger.error(f"Router error: {e}")
                        router_decision = None
                
                # 清理输入
                user_input = sanitize_for_log(user_input)
                
                # 如果 Router 建议直接回复
                if router_decision and router_decision.direct_response:
                    print(f"{self.EMOJI['ai']} AI: {router_decision.direct_response}\n")
                    continue
                
                # 构建增强的用户消息（包含 Router 建议）
                enhanced_input = user_input
                if router_decision and router_decision.suggested_tools:
                    # 将 Router 建议注入到用户输入中
                    tools_hint = ", ".join(router_decision.suggested_tools)
                    enhanced_input = f"""[系统提示：根据用户输入，建议优先使用以下工具: {tools_hint}]

用户输入: {user_input}"""
                
                # 添加用户消息
                self.llm.add_user_message(enhanced_input)
                
                # 自动截断历史
                if self.llm.get_history_length() > 12:
                    self.llm.truncate_history(max_messages=10)
                    logger.info("历史消息过多，已自动截断")
                
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
