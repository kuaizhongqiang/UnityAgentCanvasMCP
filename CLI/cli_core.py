"""
AgentCanvas CLI Core
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HTTP/WS client, command definitions, requestId management,
receipt matching, and error handling for the AgentCanvas system.

Agent ← MCP (stdio) → MCP Server (this module) ← HTTP/WS → Unity
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import websockets.client as ws_client
from dotenv import load_dotenv

from dialog_logger import DialogLogger

# ── Logger ──────────────────────────────────────────────────────────────────

logger = logging.getLogger("agentcanvas.cli_core")

# ── Config ──────────────────────────────────────────────────────────────────


@dataclass
class Config:
    """Configuration loaded from .env with sensible defaults."""

    # Unity connection
    cli_port: int = 3748
    cli_token: str = ""

    # Embedding engine (LM Studio)
    lm_studio_host: str = "localhost"
    lm_studio_port: int = 1234
    embedding_model: str = "Qwen3-Embedding-0.6B"

    # Search
    top_n: int = 5

    # Timeouts (seconds)
    http_timeout: int = 5
    command_timeout: int = 30

    # Logging
    log_level: str = "INFO"

    # Dialog
    dialog_id: str = "default"

    # Knowledge docs
    knowledge_path: str = ""

    # Paths
    persistent_data_path: str = ""
    streaming_assets_path: str = ""

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "Config":
        """Load config from .env file, falling back to environment variables."""
        if env_path and env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()  # try default locations

        def _env(key: str, default: Any) -> Any:
            return os.environ.get(key, str(default))

        return cls(
            cli_port=int(_env("CLI_PORT", 3748)),
            cli_token=_env("CLI_TOKEN", ""),
            lm_studio_host=_env("LM_STUDIO_HOST", "localhost"),
            lm_studio_port=int(_env("LM_STUDIO_PORT", 1234)),
            embedding_model=_env("EMBEDDING_MODEL", "Qwen3-Embedding-0.6B"),
            top_n=int(_env("TOP_N", 5)),
            http_timeout=int(_env("HTTP_TIMEOUT", 5)),
            command_timeout=int(_env("COMMAND_TIMEOUT", 30)),
            log_level=_env("LOG_LEVEL", "INFO"),
            persistent_data_path=_env(
                "PERSISTENT_DATA_PATH",
                str(Path.cwd() / "data"),
            ),
            streaming_assets_path=_env(
                "STREAMING_ASSETS_PATH",
                str(Path.cwd() / "StreamingAssets" / "AgentCanvas"),
            ),
        )

    @property
    def unity_base_url(self) -> str:
        return f"http://localhost:{self.cli_port}"

    @property
    def lm_studio_base_url(self) -> str:
        return f"http://{self.lm_studio_host}:{self.lm_studio_port}"


# ── RequestId ───────────────────────────────────────────────────────────────


def generate_request_id() -> str:
    """Generate a unique request ID: req_ + first 8 hex chars of a UUID."""
    return f"req_{uuid.uuid4().hex[:8]}"


# ── Command Definitions ─────────────────────────────────────────────────────


COMMAND_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # ── Help ──
    "help": {
        "description": "List all available commands and usage.",
        "params": {},
    },
    "docs": {
        "description": "List all available documentation.",
        "params": {},
    },
    "docs_get": {
        "description": "Get full documentation by name.",
        "params": {"name": {"type": "string", "required": True}},
    },
    # ── Query ──
    "whoami": {
        "description": "Return current agent identity and permissions.",
        "params": {},
    },
    "dialog": {
        "description": "List all dialogs, or get details for a specific dialog.",
        "params": {"dialogId": {"type": "string", "required": False}},
    },
    "list.templates": {
        "description": "List all available UI templates.",
        "params": {},
    },
    "search.data": {
        "description": "Semantic search across data using natural language.",
        "params": {"query": {"type": "string", "required": True}},
    },
    "get.data": {
        "description": "Get full data record by ID.",
        "params": {"dataId": {"type": "string", "required": True}},
    },
    "usage": {
        "description": "Get usage statistics.",
        "params": {},
    },
    # ── Page operations ──
    "status.list": {
        "description": "Query command status by dialogId (for WS reconnect recovery).",
        "params": {"dialogId": {"type": "string", "required": False}},
    },
    "page.create": {
        "description": "Create a new blank page.",
        "params": {
            "pageId": {"type": "string", "required": True},
            "dialogId": {"type": "string", "required": False},
        },
    },
    "page.list": {
        "description": "List all pages and their status.",
        "params": {"dialogId": {"type": "string", "required": False}},
    },
    "run": {
        "description": "Execute/render an existing page in Unity.",
        "params": {
            "pageId": {"type": "string", "required": True},
            "dialogId": {"type": "string", "required": False},
            "filePath": {"type": "string", "required": False},
        },
    },
    "update": {
        "description": "Incrementally update a page (JSON Merge Patch).",
        "params": {
            "pageId": {"type": "string", "required": True},
            "dialogId": {"type": "string", "required": False},
            "patch": {"type": "object", "required": True},
        },
    },
    "clear": {
        "description": "Clear page content, optionally scoped.",
        "params": {
            "pageId": {"type": "string", "required": True},
            "dialogId": {"type": "string", "required": False},
            "scope": {"type": "string", "required": False},
        },
    },
    "result.show": {
        "description": "Show quiz result feedback on a specific element.",
        "params": {
            "pageId": {"type": "string", "required": True},
            "dialogId": {"type": "string", "required": False},
            "elementId": {"type": "string", "required": True},
            "result": {"type": "object", "required": True},
        },
    },
    "page.delete": {
        "description": "Delete a page and its configuration.",
        "params": {
            "pageId": {"type": "string", "required": True},
            "dialogId": {"type": "string", "required": False},
        },
    },
    "stop": {
        "description": "Stop the currently executing task.",
        "params": {},
    },
    # ── Queue ──
    "queue": {
        "description": "View or manage the command queue.",
        "params": {
            "commandId": {"type": "string", "required": False},
        },
    },
    "queue.push": {
        "description": "Submit batch commands for sequential execution.",
        "params": {"commands": {"type": "array", "required": True}},
    },
    # ── Config ──
    "init": {
        "description": "Persist agent configuration.",
        "params": {"config": {"type": "object", "required": True}},
    },
    "restart": {
        "description": "Restart the current session (keeps init config).",
        "params": {},
    },
}


def list_commands() -> str:
    """Return a formatted string of all available commands."""
    lines = ["Available commands:", ""]
    categories = {
        "Help": ["help", "docs", "docs_get"],
        "Query": [
            "whoami",
            "dialog",
            "list.templates",
            "search.data",
            "get.data",
            "usage",
        ],
        "Page": [
            "page.create",
            "page.list",
            "run",
            "update",
            "clear",
            "result.show",
            "page.delete",
            "stop",
            "status.list",
        ],
        "Queue": ["queue", "queue.push"],
        "Config": ["init", "restart"],
    }
    for cat, cmds in categories.items():
        lines.append(f"  {cat}:")
        for cmd in cmds:
            info = COMMAND_DEFINITIONS[cmd]
            params = ", ".join(info["params"].keys()) if info["params"] else "(none)"
            lines.append(f"    {cmd:<20} {info['description']}")
            if info["params"]:
                lines.append(f"    {'':20} params: {params}")
        lines.append("")
    return "\n".join(lines)


# ── HTTP / WS Client ────────────────────────────────────────────────────────


class UnityClient:
    """
    HTTP + WebSocket client for communicating with the Unity EmbedIO server.

    Usage:
        client = UnityClient(config)
        result = await client.execute("get.data", {"dataId": "equipment_03"})
    """

    def __init__(self, config: Config):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws: Optional[ws_client.WebSocketClientProtocol] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._ws_connected = asyncio.Event()
        self._stop_event = asyncio.Event()
        self.dialog_logger: Optional[DialogLogger] = None

        # WS reconnect
        self._reconnect_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        self._reconnect_delay = 2.0
        self._reconnect_max_delay = 30.0

    # ── HTTP ──

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.http_timeout),
                headers={
                    "Authorization": f"Bearer {self.config.cli_token}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def send_command(
        self, command: str, params: Dict[str, Any], request_id: str
    ) -> Dict[str, Any]:
        """
        Send a command to Unity via HTTP POST /cmd.

        Returns the immediate response (typically {"status": "received"}).
        """
        client = await self._ensure_http()
        url = f"{self.config.unity_base_url}/cmd"
        payload = {
            "requestId": request_id,
            "command": command,
            "params": params,
        }

        logger.debug("HTTP → %s | req=%s | command=%s", url, request_id, command)

        # Log send (dialog logger)
        if self.dialog_logger:
            self.dialog_logger.log_send(request_id, command, params)

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.debug("HTTP ← %s | req=%s | status=%s", url, request_id, data.get("status"))

            # Log recv (dialog logger)
            if self.dialog_logger:
                self.dialog_logger.log_recv(request_id, data)

            return data
        except httpx.TimeoutException:
            logger.warning("HTTP timeout | req=%s | command=%s", request_id, command)
            err = {
                "requestId": request_id,
                "status": "error",
                "code": 408,
                "message": f"HTTP request timed out after {self.config.http_timeout}s",
            }
            if self.dialog_logger:
                self.dialog_logger.log_recv(request_id, err)
            return err
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error | req=%s | status=%d", request_id, e.response.status_code)
            try:
                err = e.response.json()
            except Exception:
                err = {
                    "requestId": request_id,
                    "status": "error",
                    "code": e.response.status_code,
                    "message": e.response.text,
                }
            if self.dialog_logger:
                self.dialog_logger.log_recv(request_id, err)
            return err
        except httpx.RequestError as e:
            logger.error("HTTP request failed | req=%s | %s", request_id, str(e))
            err = {
                "requestId": request_id,
                "status": "error",
                "code": 503,
                "message": f"Connection failed: {e}",
            }
            if self.dialog_logger:
                self.dialog_logger.log_recv(request_id, err)
            return err

    # ── WebSocket ──

    async def connect_ws(self) -> None:
        """Connect to the Unity WebSocket endpoint and start listening."""
        if self._ws is not None:
            return

        ws_url = (
            f"ws://localhost:{self.config.cli_port}/ws"
            f"?token={self.config.cli_token}"
        )
        logger.info("WS connecting to %s", ws_url)

        try:
            self._ws = await ws_client.connect(ws_url, ping_interval=30)
            self._ws_connected.set()
            logger.info("WS connected")
            # Start listening in background
            asyncio.create_task(self._ws_listen())
        except Exception as e:
            logger.warning("WS connection failed: %s (receipts disabled)", e)
            self._ws_connected.set()  # allow commands without WS

    async def _ws_listen(self) -> None:
        """Continuously read WebSocket messages and resolve pending futures."""
        ws = self._ws
        if ws is None:
            return

        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                    req_id = data.get("requestId", "")
                    event = data.get("event", data.get("status", ""))

                    logger.debug("WS ← | req=%s | event=%s", req_id, event)

                    # Resolve pending future if this is a completion/error
                    if req_id and req_id in self._pending:
                        future = self._pending.pop(req_id)
                        if not future.done():
                            future.set_result(data)

                    # Log receipt (dialog logger)
                    if self.dialog_logger and event in ("completed", "error"):
                        self.dialog_logger.log_receipt(req_id, data)

                    # Log interaction callbacks
                    if self.dialog_logger and data.get("event") == "interaction":
                        self.dialog_logger.log_interaction(
                            request_id=req_id,
                            page_id=data.get("pageId", ""),
                            element_id=data.get("elementId", ""),
                            action=data.get("action", ""),
                            data=data.get("data"),
                        )

                    # Log system events
                    if event in ("page.rendered", "page.error", "dialog.timeout", "system.error"):
                        logger.info("WS system event | event=%s | data=%s", event, data.get("data"))
                        if self.dialog_logger:
                            self.dialog_logger.log_system_event(event, data.get("data"))

                except json.JSONDecodeError:
                    logger.warning("WS received malformed JSON: %s", message[:200])
        except Exception as e:
            logger.warning("WS listener stopped: %s", e)
        finally:
            self._ws = None
            self._ws_connected.clear()
            # Auto-reconnect if enabled
            if self._should_reconnect:
                logger.info("WS disconnected — starting reconnection loop")
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def wait_for_receipt(
        self, request_id: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Wait for a WebSocket receipt matching the given requestId.

        Returns the receipt data, or a timeout error dict.
        """
        if timeout is None:
            timeout = float(self.config.command_timeout)

        # If WS never connected, return immediately with a placeholder
        await self._ws_connected.wait()
        if self._ws is None:
            return {
                "requestId": request_id,
                "status": "completed",
                "data": {"note": "WebSocket not available; result from HTTP only"},
            }

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning("Receipt timeout | req=%s | timeout=%ss", request_id, timeout)
            self._pending.pop(request_id, None)
            return {
                "requestId": request_id,
                "status": "error",
                "code": 408,
                "message": f"Command timed out after {timeout}s (no receipt)",
            }

    # ── WS Reconnect ──

    async def _reconnect_loop(self) -> None:
        """Background task that reconnects WS with exponential backoff."""
        delay = self._reconnect_delay
        attempt = 0
        while self._should_reconnect and not self._stop_event.is_set():
            attempt += 1
            logger.info("WS reconnect attempt %d in %.1fs", attempt, delay)
            await asyncio.sleep(delay)

            try:
                ws_url = (
                    f"ws://localhost:{self.config.cli_port}/ws"
                    f"?token={self.config.cli_token}"
                )
                self._ws = await ws_client.connect(ws_url, ping_interval=30)
                self._ws_connected.set()
                logger.info("WS reconnected (attempt %d)", attempt)
                asyncio.create_task(self._ws_listen())
                return
            except Exception as e:
                logger.warning("WS reconnect attempt %d failed: %s", attempt, e)
                delay = min(delay * 1.5, self._reconnect_max_delay)

        logger.warning("WS reconnect loop ended")

    def disable_reconnect(self) -> None:
        """Disable auto-reconnect (e.g., during shutdown)."""
        self._should_reconnect = False

    # ── Dialog Management ──

    def set_dialog(self, dialog_id: str) -> DialogLogger:
        """Set or change the current dialog ID and initialize its logger."""
        if self.dialog_logger:
            self.dialog_logger.close()
        self.dialog_logger = DialogLogger(
            dialog_id=dialog_id,
            streaming_assets_path=self.config.streaming_assets_path,
        )
        return self.dialog_logger

    # ── High-level execute ──

    async def execute(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        wait: bool = True,
    ) -> Dict[str, Any]:
        """
        Full command lifecycle: send HTTP → optionally wait for WS receipt.

        Returns the final result (receipt data, or HTTP response if wait=False).
        """
        if params is None:
            params = {}
        request_id = generate_request_id()

        # Auto-init dialog logger from config
        if self.dialog_logger is None:
            self.set_dialog(self.config.dialog_id)

        # Validate command
        if command not in COMMAND_DEFINITIONS:
            return {
                "requestId": request_id,
                "status": "error",
                "code": 400,
                "message": f"Unknown command: {command}. Use 'help' to list available commands.",
            }

        # Validate required params
        cmd_def = COMMAND_DEFINITIONS[command]
        for pname, pinfo in cmd_def["params"].items():
            if pinfo.get("required", False) and pname not in params:
                return {
                    "requestId": request_id,
                    "status": "error",
                    "code": 400,
                    "message": f"Missing required parameter: '{pname}'",
                }

        # Send HTTP command
        http_response = await self.send_command(command, params, request_id)
        if http_response.get("status") == "error":
            return http_response

        if not wait:
            return http_response

        # Wait for WS receipt
        receipt = await self.wait_for_receipt(request_id)
        return receipt

    # ── Lifecycle ──

    async def close(self) -> None:
        """Clean up HTTP client, WebSocket connection, and dialog logger."""
        self.disable_reconnect()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self.dialog_logger:
            self.dialog_logger.close()
            self.dialog_logger = None
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        if self._ws:
            await self._ws.close()
        self._stop_event.set()


# ── Built-in command handlers (no Unity needed) ─────────────────────────────


def handle_help() -> Dict[str, Any]:
    """Return the help text as a command result."""
    return {
        "status": "completed",
        "data": {
            "help": list_commands(),
        },
    }


# ── Utility: JSON helpers ───────────────────────────────────────────────────


def pretty_json(data: Any) -> str:
    """Format data as pretty-printed JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False)
