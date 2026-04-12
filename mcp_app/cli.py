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
        """设置系统提示词 - 融合空间-时间叙事 + 意图驱动 + RAG"""
        system_prompt = """You are an intelligent GDELT Spatio-Temporal Narrative AI Assistant with RAG capabilities. Your primary language is English.

Your goal is to help users analyze the GDELT 2.0 North American event dataset by utilizing the provided tools.

=== CORE CAPABILITIES ===

1. SPATIO-TEMPORAL NARRATIVE (空间-时间叙事)
You are capable of Multi-hop Reasoning. For complex causal questions:
- Step 1 (Anchor): Find the initial 'anchor' event
- Step 2 (Observe): Extract SQLDATE, ActionGeo_Lat/ActionGeo_Long
- Step 3 (Trace): Find subsequent events within time/distance radius
- Step 4 (Synthesize): Create chronological narrative

2. SEMANTIC SEARCH (语义搜索/RAG)
When users ask about event details, causes, or context:
- Use `search_news_context` to query the vector knowledge base
- This provides real news excerpts for deeper understanding

3. INTENT-DRIVEN QUERIES (意图驱动)
The system can understand natural language:
- "protests in Washington in January" → time=2024-01, location=Washington, type=protest

=== CRITICAL SQL SYNTAX GUIDE FOR MYSQL 8.0 ===

1. TEMPORAL HOPS (Time Operations):
To find events within X days AFTER an anchor event:
`WHERE SQLDATE BETWEEN 'YYYY-MM-DD' AND DATE_ADD('YYYY-MM-DD', INTERVAL X DAY)`

2. SPATIAL HOPS (Distance Operations):
To find events within X meters of coordinates, use `ST_Distance_Sphere`:
`WHERE ST_Distance_Sphere(point(ActionGeo_Long, ActionGeo_Lat), point(target_long, target_lat)) <= distance_in_meters`
(Note: Longitude comes FIRST in the point() function!)

=== AVAILABLE TOOLS ===

【Data Query Tools】
- get_schema: Get database table structure
- execute_sql: Execute custom SQL query
- query_by_time_range: Query events by date range
- query_by_actor: Query events by actor name
- query_by_location: Query events by geographic location
- analyze_daily_events: Daily statistics
- analyze_top_actors: Top active actors
- analyze_conflict_cooperation: Conflict/cooperation trends

【Optimized Tools】
- get_dashboard: Concurrent multi-dimensional statistics (5 queries in parallel)
- analyze_time_series: Advanced time series analysis with DB-side aggregation
- get_geo_heatmap: Geographic heatmap with grid aggregation
- stream_query_events: Stream processing for large data

【RAG Tools】⭐ NEW
- search_news_context: Semantic search in news knowledge base
  Use when: user asks about event details, causes, public response, etc.
  Example queries: "protesters demanding climate action", "police response details"

【Diagnostic Tools】
- get_cache_stats: View query cache statistics
- clear_cache: Clear all query cache

=== TOOL EXECUTION & ERROR PROTOCOL ===
1. DIRECT ACTION: Do not announce plans. Just call the tool immediately.
2. ERROR HANDLING: If SQL fails, immediately call `get_schema` to verify structure.
3. RAG FIRST: For questions about event context/details, try `search_news_context` first.
4. FINAL RESPONSE: Keep concise and insightful (under 3 paragraphs).

=== Router Integration ===
The system has an intelligent Router (Qwen 2.5B) for input analysis. 
When you see "[System hint: suggested tools: ...]", consider these recommendations but you have final decision.
"""
        
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
            return True
        
        elif cmd in ['/clear', '/c', 'clear']:
            self.llm.clear_history()
            self._setup_system_prompt()
            print(f"{self.EMOJI['success']} 对话历史已清空\n")
            logger.info("对话历史已清空")
            return True
        
        elif cmd in ['/tools', '/t', 'tools']:
            self.print_tools()
            return True
        
        elif cmd in ['/status', '/s', 'status']:
            self.print_status()
            return True
        
        elif cmd in ['/router', '/r']:
            # 切换 Router 状态
            if not self.router:
                print(f"{self.EMOJI['error']} Router 未初始化（需要 Ollama + qwen2.5:3b）\n")
            else:
                self.router_enabled = not self.router_enabled
                status = "开启" if self.router_enabled else "关闭"
                print(f"{self.EMOJI['success']} Router 已{status}\n")
            return True
        
        else:
            print(f"{self.EMOJI['error']} 未知命令: {command}")
            print("   输入 /help 查看可用命令\n")
            return True
        
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
                        
                        # 处理命令（/开头的指令）
                        if router_decision.intent == "command":
                            # 调用 handle_command 执行具体命令
                            if not self.handle_command(user_input):
                                break
                            continue
                        
                        # 如果 Router 建议跳过 LLM（如安全过滤、直接回复）
                        if router_decision.skip_llm:
                            if router_decision.direct_response:
                                print(f"{self.EMOJI['ai']} AI: {router_decision.direct_response}\n")
                            continue
                        
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
                
                # 如果 Router 建议直接回复（非 skip_llm 情况）
                if router_decision and router_decision.direct_response and not router_decision.skip_llm:
                    print(f"{self.EMOJI['ai']} AI: {router_decision.direct_response}\n")
                    self.llm.add_assistant_message(router_decision.direct_response)
                    continue
                
                # 构建增强的用户消息（包含 Router 建议）
                enhanced_input = user_input
                if router_decision and router_decision.suggested_tools:
                    # 将 Router 建议注入到用户输入中
                    tools_hint = ", ".join(router_decision.suggested_tools)
                    enhanced_input = f"""[System hint: Based on user input, suggested tools: {tools_hint}]

User input: {user_input}"""
                
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
