from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mcp_app.client import MCPClient
from mcp_app.config import load_config
from mcp_app.llm import LLMClient
from mcp_app.logger import get_logger, sanitize_for_log, setup_logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "web_app" / "static"
LANDING_PAGE = PROJECT_ROOT / "index.html"
CHAT_PAGE = STATIC_DIR / "index.html"
MAX_HISTORY_MESSAGES = 12
MAX_REQUEST_BYTES = 1_000_000

SYSTEM_PROMPT = (
    "You are the web assistant for the GDELT MCP project. "
    "Help users analyze North America 2024 event data through the available MCP tools. "
    "When a question needs database-backed evidence, actively call the relevant tools. "
    "Keep answers grounded, concise, and explicit about uncertainty."
)


class WebChatService:
    """Coordinates config loading, chat requests, and lightweight health checks."""

    def __init__(self) -> None:
        self.config = load_config(PROJECT_ROOT / ".env")
        log_dir = self.config.log_dir if self.config.log_to_file else None
        setup_logging(level=self.config.log_level, log_dir=log_dir, console=True)
        self.logger = get_logger("web")

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "transport": self.config.mcp_transport,
            "server_path": self.config.mcp_server_path,
            "landing_page": LANDING_PAGE.exists(),
            "chat_page": CHAT_PAGE.exists(),
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

        try:
            connected = await mcp_client.connect()
            if not connected:
                raise RuntimeError(
                    "Unable to connect to the MCP server. "
                    "Please confirm the server path, Python environment, and database settings."
                )

            await mcp_client.discover_tools()

            llm_client.add_system_message(SYSTEM_PROMPT)
            for item in self._sanitize_history(history):
                if item["role"] == "user":
                    llm_client.add_user_message(item["content"])
                else:
                    llm_client.add_assistant_message(item["content"])

            llm_client.add_user_message(prompt)
            reply = await llm_client.chat(
                tools=mcp_client.tools,
                tool_executor=mcp_client.create_tool_executor(),
            )

            return {
                "reply": reply,
                "provider": self.config.llm_provider,
                "model": self.config.llm_model,
                "tool_names": [
                    tool["function"]["name"]
                    for tool in mcp_client.tools
                    if tool.get("function", {}).get("name")
                ],
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
