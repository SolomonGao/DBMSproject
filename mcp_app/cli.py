# cli.py - Command Line Interface
"""
CLI Interface:
- Welcome message and configuration display
- Conversation loop
- Command handling
- Router integration (Qwen 2.5B local model)
"""

import asyncio
import re
import sys
from typing import Optional

from .logger import get_logger, sanitize_for_log
from .router import OllamaRouter

logger = get_logger("cli")


class ChatCLI:
    """Command Line Chat Interface"""
    
    # Emoji mapping
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
        logger.debug("ChatCLI initialized")
    
    def _setup_router(self):
        """Initialize Router (if Ollama is available)"""
        import os
        # Docker container accessing host Ollama needs host.docker.internal (Mac/Windows)
        # Linux needs host IP or --network host
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
        """Set system prompt - integrating spatio-temporal narrative + intent-driven + RAG"""
        system_prompt = """You are an intelligent GDELT Spatio-Temporal Narrative AI Assistant with RAG capabilities. Your primary language is English.

Your goal is to help users analyze the GDELT 2.0 North American event dataset by utilizing the provided tools.

=== CORE CAPABILITIES ===

1. SPATIO-TEMPORAL NARRATIVE
You are capable of Multi-hop Reasoning. For complex causal questions:
- Step 1 (Anchor): Find the initial 'anchor' event
- Step 2 (Observe): Extract SQLDATE, ActionGeo_Lat/ActionGeo_Long
- Step 3 (Trace): Find subsequent events within time/distance radius
- Step 4 (Synthesize): Create chronological narrative

2. SEMANTIC SEARCH (RAG)
When users ask about event details, causes, or context:
- Use `search_news_context` to query the vector knowledge base
- This provides real news excerpts for deeper understanding

3. INTENT-DRIVEN QUERIES
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

[Data Query Tools]
- get_schema: Get database table structure
- execute_sql: Execute custom SQL query
- query_by_time_range: Query events by date range
- query_by_actor: Query events by actor name
- query_by_location: Query events by geographic location
- analyze_daily_events: Daily statistics
- analyze_top_actors: Top active actors
- analyze_conflict_cooperation: Conflict/cooperation trends

[Optimized Tools]
- get_dashboard: Concurrent multi-dimensional statistics (5 queries in parallel)
- analyze_time_series: Advanced time series analysis with DB-side aggregation
- get_geo_heatmap: Geographic heatmap with grid aggregation
- stream_query_events: Stream processing for large data

[RAG Tools] ⭐ NEW
- search_news_context: Semantic search in news knowledge base
  Use when: user asks about event details, causes, public response, etc.
  Example queries: "protesters demanding climate action", "police response details"

[Diagnostic Tools]
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

=== DISPLAY GUIDELINES ===

1. FINGERPRINT DISPLAY
- Event fingerprints are CRITICAL identifiers for follow-up queries
- ALWAYS display the COMPLETE fingerprint ID, never truncate
- Correct: `US-20241218-FLO-INTENT-126`
- Incorrect: `US-20241...` (truncated)
- When showing event details, prominently display the full fingerprint in code blocks

2. LOCATION MATCHING
- The system uses index-optimized prefix matching for locations
- Supported formats: city names (Washington), country codes (US), state codes (DC, TX)
- Multiple variants are automatically expanded (e.g., "Washington" → Washington, DC)

3. RESPONSE FORMAT
- Keep responses concise (under 3 paragraphs)
- Use bullet points for structured data
- Include complete fingerprint IDs for any mentioned events
"""
        
        self.llm.add_system_message(system_prompt)

    
    def print_welcome(self):
        """Print welcome message"""
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
        print(f"{self.EMOJI['system']} Welcome to GDELT MCP Client v1")
        print("=" * 60)
        print()
        print("📋 Configuration Summary:")
        print(f"   {provider_emoji} LLM Provider: {provider.name if provider else self.config.llm_provider}")
        print(f"   🔑 API Key: {self.config.get_masked_api_key()}")
        print(f"   🤖 LLM Model: {self.config.llm_model}")
        print(f"   🔧 MCP Server: {self.config.mcp_transport} mode")
        # Show Router status
        if self.router:
            print(f"   🧠 Router: Configured ({self.router.model})")
        else:
            print(f"   🧠 Router: Not configured")
        print()
        print("💡 Available Commands:")
        print("   /help    - Show help information")
        print("   /clear   - Clear conversation history")
        print("   /tools   - Show available tools list")
        print("   /status  - Show status information")
        print("   /router  - Enable/Disable Router (Qwen 2.5B)")
        print("   /quit    - Exit program")
        print()
        print("📝 Start typing to chat...")
        print("-" * 60)
        print()
        
        logger.info("Welcome screen displayed")
    
    def print_help(self):
        """Print help information"""
        print()
        print("📖 Help Information")
        print("-" * 40)
        print("This application is an MCP client integrating Kimi AI and tool calling.")
        print()
        print("💬 Conversation Commands:")
        print("   /help    - Show this help")
        print("   /clear   - Clear conversation history")
        print("   /tools   - List available tools")
        print("   /status  - Show current status")
        print("   /router  - Enable/Disable Router (Qwen 2.5B)")
        print("   /quit    - Exit application")
        print()
        print("🧠 Router (Local Qwen 2.5B):")
        print("   Intelligent routing: Input cleaning → Intent recognition → Tool pre-selection")
        print("   Requires local install: ollama run qwen2.5:3b")
        print()
        print("🔧 Tool Usage:")
        print("   AI will automatically determine if tools are needed, or you can explicitly request.")
        print()
        print("⚙️  Configuration:")
        print("   Edit .env file to modify API Key and other settings")
        print("-" * 40)
        print()
    
    def print_tools(self):
        """Print tools list"""
        print()
        print("🔧 Available Tools List")
        print("-" * 40)
        
        if not self.mcp.tools:
            print("No tools available")
            return
        
        for i, tool in enumerate(self.mcp.tools, 1):
            func = tool["function"]
            print(f"{i}. {func['name']}")
            print(f"   Description: {func['description']}")
            if 'parameters' in func and 'properties' in func['parameters']:
                print(f"   Parameters:")
                for param_name, param_info in func['parameters']['properties'].items():
                    desc = param_info.get('description', 'No description')
                    required = param_name in func['parameters'].get('required', [])
                    req_mark = "*" if required else ""
                    print(f"      - {param_name}{req_mark}: {desc}")
            print()
        
        print("-" * 40)
        print()
    
    def print_status(self):
        """Print status information"""
        print()
        print("📊 Current Status")
        print("-" * 40)
        print(f"MCP Server: {'✅ Connected' if self.mcp.session else '❌ Not connected'}")
        print(f"Available Tools: {len(self.mcp.tools)}")
        print(f"Conversation History: {self.llm.get_history_length()} messages")
        print(f"Log Level: {self.config.log_level}")
        router_status = "✅ Enabled" if self.router_enabled else ("⚠️ Disabled" if self.router else "❌ Not installed")
        print(f"Router: {router_status}")
        print("-" * 40)
        print()
    
    def handle_command(self, command: str) -> bool:
        """
        Handle commands
        
        Returns:
            False to exit program, True to continue
        """
        cmd = command.lower().strip()
        
        if cmd in ['/quit', '/exit', '/q', 'quit', 'exit']:
            print(f"\n{self.EMOJI['success']} Goodbye!")
            logger.info("User exit")
            self.running = False
            return False
        
        elif cmd in ['/help', '/h', 'help']:
            self.print_help()
            return True
        
        elif cmd in ['/clear', '/c', 'clear']:
            self.llm.clear_history()
            self._setup_system_prompt()
            print(f"{self.EMOJI['success']} Conversation history cleared\n")
            logger.info("Conversation history cleared")
            return True
        
        elif cmd in ['/tools', '/t', 'tools']:
            self.print_tools()
            return True
        
        elif cmd in ['/status', '/s', 'status']:
            self.print_status()
            return True
        
        elif cmd in ['/router', '/r']:
            # Toggle Router status
            if not self.router:
                print(f"{self.EMOJI['error']} Router not initialized (requires Ollama + qwen2.5:3b)\n")
            else:
                self.router_enabled = not self.router_enabled
                status = "enabled" if self.router_enabled else "disabled"
                print(f"{self.EMOJI['success']} Router {status}\n")
            return True
        
        else:
            print(f"{self.EMOJI['error']} Unknown command: {command}")
            print("   Type /help to see available commands\n")
            return True
        
        return True

    
    async def chat_loop(self):
        """Main conversation loop (with Router integration)"""
        self.running = True
        self.print_welcome()
        
        # Create tool executor
        tool_executor = self.mcp.create_tool_executor()
        
        # Check Router health status
        if self.router:
            router_healthy = await self.router.health_check()
            if router_healthy:
                self.router_enabled = True
                print(f"{self.EMOJI['info']} Router enabled (Qwen 2.5B)\n")
            else:
                print(f"{self.EMOJI['warning']} Router unavailable, using direct mode\n")
        
        while self.running:
            try:
                # Get user input
                user_input = await asyncio.to_thread(
                    input, f"{self.EMOJI['user']} You: "
                )
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                # Check if it's a command
                if user_input.startswith('/'):
                    if not self.handle_command(user_input):
                        break
                    continue
                
                # ====== Router Processing ======
                router_decision = None
                if self.router_enabled and self.router:
                    try:
                        router_decision = await self.router.route(
                            user_input, 
                            context=self.llm.messages[-6:] if hasattr(self.llm, 'messages') else None
                        )
                        logger.info(f"Router decision: {router_decision.intent} (confidence: {router_decision.confidence:.2f})")
                        
                        # Handle commands (/ prefix)
                        if router_decision.intent == "command":
                            if not self.handle_command(user_input):
                                break
                            continue
                        
                        # Force direct tool execution for get_event_detail with fingerprint (bypass LLM laziness)
                        if router_decision and "get_event_detail" in router_decision.suggested_tools:
                            fp_match = re.search(r'(?:EVT|US)-\d{4}(?:-\d{2}-\d{2})?-[A-Z]*-*\d+', user_input)
                            if fp_match:
                                fingerprint = fp_match.group(0)
                                print(f"{self.EMOJI['info']} [Router] Retrieving event details for {fingerprint}...")
                                try:
                                    result = await self.mcp.call_tool("get_event_detail", {"params": {"fingerprint": fingerprint, "include_causes": True}})
                                    print(f"{self.EMOJI['ai']} AI: {result}")
                                    print()
                                    self.llm.add_assistant_message(result)
                                    continue
                                except Exception as exc:
                                    logger.error(f"Direct get_event_detail failed: {exc}")
                        
                        # If Router suggests skipping LLM (e.g., safety filter, direct response)
                        if router_decision.skip_llm:
                            if router_decision.direct_response:
                                print(f"{self.EMOJI['ai']} AI: {router_decision.direct_response}\n")
                            continue
                        
                        # Show routing info (for debugging, can be commented out)
                        if router_decision.intent == "chat":
                            print(f"{self.EMOJI['info']} [Router] Chat mode\n")
                        elif router_decision.intent == "query":
                            print(f"{self.EMOJI['info']} [Router] Data query: {router_decision.suggested_tools}\n")
                        elif router_decision.intent == "analysis":
                            print(f"{self.EMOJI['info']} [Router] Data analysis: {router_decision.suggested_tools}\n")
                        
                    except Exception as e:
                        logger.error(f"Router error: {e}")
                        router_decision = None
                
                # Clean input
                user_input = sanitize_for_log(user_input)
                
                # If Router suggests direct response (non skip_llm case)
                if router_decision and router_decision.direct_response and not router_decision.skip_llm:
                    print(f"{self.EMOJI['ai']} AI: {router_decision.direct_response}\n")
                    self.llm.add_assistant_message(router_decision.direct_response)
                    continue
                
                # Build enhanced user message (with Router suggestions)
                enhanced_input = user_input
                if router_decision and router_decision.suggested_tools:
                    # Inject Router suggestion into user input
                    tools_hint = ", ".join(router_decision.suggested_tools)
                    enhanced_input = f"""[System hint: Based on user input, suggested tools: {tools_hint}]

User input: {user_input}"""
                
                # Add user message
                self.llm.add_user_message(enhanced_input)
                
                # Auto-truncate history
                if self.llm.get_history_length() > 12:
                    self.llm.truncate_history(max_messages=10)
                    logger.info("History too long, auto-truncated")
                
                # Call LLM
                print(f"{self.EMOJI['ai']} AI: ", end="", flush=True)
                
                response = await self.llm.chat(
                    tools=self.mcp.tools,
                    tool_executor=tool_executor
                )
                
                print(response)
                print()
                
            except KeyboardInterrupt:
                print(f"\n\n{self.EMOJI['info']} Interrupt signal received")
                logger.info("Keyboard interrupt received")
                break
            except EOFError:
                print(f"\n\n{self.EMOJI['info']} Input ended")
                logger.info("EOF received")
                break
            except Exception as e:
                logger.exception(f"Chat loop error: {e}")
                print(f"\n{self.EMOJI['error']} Error: {e}\n")
        
        print(f"{self.EMOJI['success']} Exiting...")
        logger.info("CLI loop ended")
