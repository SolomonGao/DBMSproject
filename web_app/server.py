from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mcp_app.client import MCPClient
from mcp_app.config import load_config
from mcp_app.llm import LLMClient
from mcp_app.logger import get_logger, sanitize_for_log, setup_logging
from mcp_app.router import OllamaRouter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "web_app" / "static"
LANDING_PAGE = PROJECT_ROOT / "index.html"
CHAT_PAGE = STATIC_DIR / "index.html"
MAX_HISTORY_MESSAGES = 12
MAX_REQUEST_BYTES = 1_000_000

SYSTEM_PROMPT = """You are an intelligent GDELT Spatio-Temporal Narrative AI Assistant with RAG capabilities. Your primary language is English.

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


class WebChatService:
    """Coordinates config loading, chat requests, and lightweight health checks."""

    def __init__(self) -> None:
        self.config = load_config(PROJECT_ROOT / ".env")
        log_dir = self.config.log_dir if self.config.log_to_file else None
        setup_logging(level=self.config.log_level, log_dir=log_dir, console=True)
        self.logger = get_logger("web")

        # Initialize Router (same as CLI)
        ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
        try:
            self.router = OllamaRouter(base_url=ollama_host, model="qwen2.5:3b")
            self.logger.info(f"Router initialized: {ollama_host}")
        except Exception as e:
            self.logger.warning(f"Router initialization failed: {e}")
            self.router = None

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "transport": self.config.mcp_transport,
            "server_path": self.config.mcp_server_path,
            "landing_page": LANDING_PAGE.exists(),
            "chat_page": CHAT_PAGE.exists(),
            "router_configured": self.router is not None,
        }

    async def generate_reply(
        self,
        history: list[dict[str, Any]],
        message: str,
    ) -> dict[str, Any]:
        prompt = sanitize_for_log(message or "").strip()
        if not prompt:
            raise ValueError("Message cannot be empty.")

        llm_client = self._build_llm_client()
        mcp_client = MCPClient(
            server_path=self.config.mcp_server_path,
            transport=self.config.mcp_transport,
            port=self.config.mcp_port,
        )

        # Collect thinking steps for UI display
        thinking_steps: list[dict[str, Any]] = []

        try:
            connected = await mcp_client.connect()
            if not connected:
                raise RuntimeError(
                    "Unable to connect to the MCP server. "
                    "Please confirm the server path, Python environment, and database settings."
                )

            await mcp_client.discover_tools()
            tool_names = [
                tool["function"]["name"]
                for tool in mcp_client.tools
                if tool.get("function", {}).get("name")
            ]

            # ====== Router Processing (inherited from CLI) ======
            router_decision = None
            if self.router:
                try:
                    router_decision = await self.router.route(
                        prompt,
                        context=history[-6:] if isinstance(history, list) else None,
                    )
                    self.logger.info(
                        f"Router decision: {router_decision.intent} (confidence: {router_decision.confidence:.2f})"
                    )
                    thinking_steps.append({
                        "type": "router_decision",
                        "intent": router_decision.intent,
                        "confidence": router_decision.confidence,
                        "suggested_tools": router_decision.suggested_tools,
                        "reasoning": router_decision.reasoning,
                    })

                    # Force direct tool execution for get_event_detail with fingerprint (bypass LLM laziness)
                    if router_decision and "get_event_detail" in router_decision.suggested_tools:
                        fp_match = re.search(r'(?:EVT|US)-\d{4}(?:-\d{2}-\d{2})?-[A-Z]*-*\d+', prompt)
                        if fp_match:
                            fingerprint = fp_match.group(0)
                            self.logger.info(f"Directly executing get_event_detail({fingerprint})")
                            thinking_steps.append({
                                "type": "direct_tool_execution",
                                "tool": "get_event_detail",
                                "fingerprint": fingerprint,
                            })
                            try:
                                result = await mcp_client.call_tool(
                                    "get_event_detail",
                                    {"params": {"fingerprint": fingerprint, "include_causes": True}}
                                )
                                return {
                                    "reply": result,
                                    "provider": self.config.llm_provider,
                                    "model": self.config.llm_model,
                                    "tool_names": tool_names,
                                    "thinking_process": thinking_steps,
                                }
                            except Exception as exc:
                                self.logger.exception(f"Direct get_event_detail failed: {exc}")

                    # If Router suggests skipping LLM (e.g., safety filter, direct response)
                    if router_decision.skip_llm:
                        direct = router_decision.direct_response or ""
                        return {
                            "reply": direct,
                            "provider": self.config.llm_provider,
                            "model": self.config.llm_model,
                            "tool_names": tool_names,
                            "thinking_process": thinking_steps,
                        }
                except Exception as e:
                    self.logger.error(f"Router error: {e}")
                    thinking_steps.append({"type": "router_error", "error": str(e)})
                    router_decision = None

            # If Router suggests direct response (non skip_llm case)
            if router_decision and router_decision.direct_response:
                return {
                    "reply": router_decision.direct_response,
                    "reply_length": len(router_decision.direct_response),
                    "provider": self.config.llm_provider,
                    "model": self.config.llm_model,
                    "tool_names": tool_names,
                    "thinking_process": thinking_steps,
                }

            # Build enhanced user message (with Router suggestions)
            enhanced_input = prompt
            if router_decision and router_decision.suggested_tools:
                tools_hint = ", ".join(router_decision.suggested_tools)
                enhanced_input = f"""[System hint: Based on user input, suggested tools: {tools_hint}]

User input: {prompt}"""
                thinking_steps.append({
                    "type": "system_hint",
                    "suggested_tools": router_decision.suggested_tools,
                })

            llm_client.add_system_message(SYSTEM_PROMPT)
            for item in self._sanitize_history(history):
                if item["role"] == "user":
                    llm_client.add_user_message(item["content"])
                else:
                    llm_client.add_assistant_message(item["content"])

            # Auto-truncate history (same as CLI)
            if llm_client.get_history_length() > 12:
                llm_client.truncate_history(max_messages=10)
                self.logger.info("History too long, auto-truncated")
                thinking_steps.append({"type": "history_truncated", "max_messages": 10})

            llm_client.add_user_message(enhanced_input)

            def on_step(step_type: str, data: dict[str, Any]):
                thinking_steps.append({"type": step_type, **data})

            reply = await llm_client.chat(
                tools=mcp_client.tools,
                tool_executor=mcp_client.create_tool_executor(),
                on_step=on_step,
            )

            # Server-side fallback for get_event_detail empty responses
            if not reply.strip() and router_decision and "get_event_detail" in router_decision.suggested_tools:
                fp_match = re.search(r'(?:EVT|US)-\d{4}(?:-\d{2}-\d{2})?-[A-Z]*-*\d+', prompt)
                if fp_match:
                    fingerprint = fp_match.group(0)
                    self.logger.warning(f"Server forcing get_event_detail({fingerprint})")
                    thinking_steps.append({
                        "type": "server_force_execution",
                        "tool": "get_event_detail",
                        "fingerprint": fingerprint,
                    })
                    try:
                        tool_result = await mcp_client.call_tool(
                            "get_event_detail",
                            {"params": {"fingerprint": fingerprint, "include_causes": True}}
                        )
                        llm_client.add_assistant_message(f"Retrieved event details for {fingerprint}.")
                        llm_client.add_user_message(
                            f"Raw data:\n{tool_result}\n\nSummarize clearly."
                        )
                        reply = await llm_client.chat(tools=None, tool_executor=None, on_step=on_step)
                    except Exception as exc:
                        self.logger.exception(f"Server forced execution failed: {exc}")
                        reply = f"Failed to retrieve details: {exc}"

            return {
                "reply": reply,
                "provider": self.config.llm_provider,
                "model": self.config.llm_model,
                "tool_names": tool_names,
                "thinking_process": thinking_steps,
            }
        finally:
            await mcp_client.close()
            await llm_client.close()

    def _build_llm_client(self) -> LLMClient:
        return LLMClient(
            provider=self.config.llm_provider,
            api_key=self.config.get_api_key(),
            base_url=self.config.llm_base_url,
            model=self.config.llm_model,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_max_tokens,
        )

    def _sanitize_history(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        sanitized: list[dict[str, str]] = []

        for item in history[-MAX_HISTORY_MESSAGES:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = sanitize_for_log(item.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue

            sanitized.append(
                {
                    "role": role,
                    "content": content[:8000],
                }
            )

        return sanitized


class GDELTWebServer(ThreadingHTTPServer):
    daemon_threads = True


class GDELTWebHandler(BaseHTTPRequestHandler):
    service: WebChatService
    server_version = "GDELTWeb/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path

        if path in {"/", "/index.html"}:
            self._serve_file(LANDING_PAGE)
            return

        if path in {"/chat", "/chat/"}:
            self._serve_file(CHAT_PAGE)
            return

        if path.startswith("/static/"):
            relative_path = path.removeprefix("/static/")
            file_path = self._resolve_static_path(relative_path)
            if file_path is None:
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error": "Static asset not found."},
                )
                return

            self._serve_file(file_path)
            return

        if path == "/api/health":
            self._send_json(HTTPStatus.OK, self.service.health())
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": "Route not found."},
        )

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path != "/api/chat":
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "Route not found."},
            )
            return

        try:
            payload = self._read_json_payload()
            history = payload.get("history", [])
            if not isinstance(history, list):
                raise ValueError("history must be a list.")

            response = asyncio.run(
                self.service.generate_reply(
                    history=history,
                    message=payload.get("message", ""),
                )
            )
            self._send_json(HTTPStatus.OK, {"ok": True, **response})
        except ValueError as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            self.service.logger.exception("Web chat request failed: %s", exc)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc)},
            )

    def log_message(self, format: str, *args: Any) -> None:
        self.service.logger.info(
            "%s - %s",
            self.address_string(),
            format % args,
        )

    def _read_json_payload(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            raise ValueError("Request body is required.")
        if content_length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large.")

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc

        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")

        return payload

    def _resolve_static_path(self, relative_path: str) -> Path | None:
        safe_root = STATIC_DIR.resolve()
        candidate = (safe_root / relative_path).resolve()
        if candidate == safe_root or safe_root in candidate.parents:
            return candidate if candidate.is_file() else None
        return None

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": f"File not found: {path.name}"},
            )
            return

        body = path.read_bytes()
        content_type, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            f"{content_type or 'application/octet-stream'}; charset=utf-8",
        )
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the GDELT web chat server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    service = WebChatService()
    GDELTWebHandler.service = service

    server = GDELTWebServer((args.host, args.port), GDELTWebHandler)
    logger = get_logger("web")
    logger.info("Web server ready at http://%s:%s/chat", args.host, args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down the web server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
