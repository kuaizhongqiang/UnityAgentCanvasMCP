"""
Mock Unity Server for Integration Testing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A lightweight HTTP/WebSocket server that mimics Unity's EmbedIO
endpoints for testing the AgentCanvas CLI without a running Unity instance.

Endpoints:
  POST /cmd   — accepts commands, returns {"status": "received"}
  GET  /ws    — WebSocket upgrade, sends completed receipts

Uses http.server (threaded) for HTTP + websockets (async) for WS.
Both run on separate ports; the caller must configure the client accordingly.

Usage (with pytest):
    server = await MockUnityServer.start()
    try:
        # ... tests pointing at server.http_port and server.ws_port ...
        assert len(server.commands) == 1
    finally:
        await server.stop()
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional

import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger("agentcanvas.tests.mock_unity")


# ── Data Structures ─────────────────────────────────────────────────────────


class CommandRecord:
    """Record of a command received by the mock server."""

    def __init__(
        self,
        request_id: str,
        command: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ):
        self.request_id = request_id
        self.command = command
        self.params = params
        self.headers = headers


# ── Mock Unity Server ───────────────────────────────────────────────────────


class MockUnityServer:
    """
    Mock Unity EmbedIO server for CLI testing.

    Combines a threaded HTTP server (for /cmd) with an async WebSocket
    server (for /ws receipts). Both run on separate ports.

    Usage via pytest fixture:
        server = await MockUnityServer.start()
        # or use the `mock_unity` fixture from conftest.py
    """

    def __init__(
        self,
        token: str = "test-token",
        receipt_delay: float = 0.05,
    ):
        self.token = token
        self.receipt_delay = receipt_delay
        self.http_port: int = 0
        self.ws_port: int = 0
        self.commands: List[CommandRecord] = []
        self.custom_receipts: Dict[str, Dict[str, Any]] = {}

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_server: Optional[websockets.WebSocketServer] = None
        self._http_server: Optional[HTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._ws_connections: List[WebSocketServerProtocol] = []

    # ── Lifecycle ──

    @classmethod
    async def start(
        cls,
        token: str = "test-token",
        receipt_delay: float = 0.05,
        http_port: int = 0,
        ws_port: int = 0,
    ) -> "MockUnityServer":
        """Start both HTTP and WS servers on available ports."""
        self = cls(token=token, receipt_delay=receipt_delay)
        self._loop = asyncio.get_running_loop()

        # Start WS server (async)
        self._ws_server = await websockets.serve(
            self._handle_ws,
            host="127.0.0.1",
            port=ws_port,
        )
        self.ws_port = self._ws_server.sockets[0].getsockname()[1]

        # Start HTTP server (threaded, using http.server)
        self._http_server = _make_http_server(self, http_port)
        self.http_port = self._http_server.server_address[1]
        self._http_thread = threading.Thread(
            target=self._http_server.serve_forever,
            daemon=True,
        )
        self._http_thread.start()

        logger.info(
            "Mock Unity server started — HTTP:%d WS:%d",
            self.http_port,
            self.ws_port,
        )
        return self

    async def stop(self) -> None:
        """Stop both HTTP and WS servers."""
        # Stop WS
        for ws in self._ws_connections[:]:
            try:
                await ws.close()
            except Exception:
                pass
        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()

        # Stop HTTP
        if self._http_server:
            self._http_server.shutdown()
            self._http_server.server_close()

        logger.info("Mock Unity server stopped")

    def set_receipt(self, request_id: str, data: Dict[str, Any]) -> None:
        """Set a custom receipt for a specific requestId."""
        self.custom_receipts[request_id] = data

    def clear_commands(self) -> None:
        """Clear recorded commands."""
        self.commands.clear()

    def get_command(self, index: int = 0) -> Optional[CommandRecord]:
        """Get the nth received command (0 = first)."""
        if index < len(self.commands):
            return self.commands[index]
        return None

    # ── WebSocket Handler ──

    async def _handle_ws(self, ws: WebSocketServerProtocol) -> None:
        """Handle WebSocket connection from the CLI client."""
        # In websockets v15+, access the request path via ws.request
        token_param = ""
        if ws.request:
            path = ws.request.path
            if "?" in path:
                qs = path.split("?", 1)[1]
                for part in qs.split("&"):
                    if part.startswith("token="):
                        token_param = part.split("=", 1)[1]

        if token_param != self.token:
            await ws.close(4001, "Unauthorized")
            return

        self._ws_connections.append(ws)
        logger.debug("Mock WS client connected")

        try:
            async for _ in ws:
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if ws in self._ws_connections:
                self._ws_connections.remove(ws)

    async def send_receipt(
        self,
        request_id: str,
        status: str = "completed",
        data: Optional[Dict] = None,
    ) -> bool:
        """Send a WebSocket receipt to connected CLI clients."""
        if not self._ws_connections:
            return False

        payload = {"requestId": request_id, "status": status}
        if data:
            payload["data"] = data

        message = json.dumps(payload)
        sent = False
        for ws in self._ws_connections[:]:
            try:
                await ws.send(message)
                sent = True
            except websockets.exceptions.ConnectionClosed:
                self._ws_connections.remove(ws)
        return sent

    # ── Command processing (called from HTTP handler) ──

    def process_command(
        self,
        request_id: str,
        command: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """Record a command and schedule its WS receipt."""
        record = CommandRecord(
            request_id=request_id,
            command=command,
            params=params,
            headers=headers,
        )
        self.commands.append(record)

        # Schedule WS receipt on the asyncio event loop
        asyncio.run_coroutine_threadsafe(
            self._delayed_receipt(request_id, command),
            self._loop,
        )

        return {"requestId": request_id, "status": "received"}

    async def _delayed_receipt(self, request_id: str, command: str) -> None:
        """Send a receipt after the configured delay."""
        await asyncio.sleep(self.receipt_delay)

        if request_id in self.custom_receipts:
            receipt_data = self.custom_receipts[request_id]
            await self.send_receipt(
                request_id=request_id,
                status=receipt_data.get("status", "completed"),
                data=receipt_data.get("data"),
            )
        else:
            await self.send_receipt(
                request_id=request_id,
                status="completed",
                data={"note": f"Mock completed: {command}"},
            )


# ── HTTP Server (threaded, using http.server) ────────────────────────────────


def _make_http_server(mock_server: MockUnityServer, port: int) -> HTTPServer:
    """Create a configured HTTP server for the mock."""

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/cmd":
                self._handle_cmd()
            else:
                self._send_json(404, {"error": "not found"})

        def _handle_cmd(self):
            # Read body
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)

            # Verify auth
            auth = self.headers.get("Authorization", "")
            expected = f"Bearer {mock_server.token}"
            if auth != expected:
                self._send_json(401, {
                    "status": "error", "code": 401, "message": "Unauthorized",
                })
                return

            # Parse JSON
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self._send_json(400, {
                    "status": "error", "code": 400, "message": "Invalid JSON",
                })
                return

            command = payload.get("command", "")
            request_id = payload.get("requestId", "")
            params = payload.get("params", {})

            # Forward to mock server (normalize header keys to lowercase)
            headers = {k.lower(): v for k, v in self.headers.items()}
            result = mock_server.process_command(
                request_id=request_id,
                command=command,
                params=params,
                headers=headers,
            )
            self._send_json(200, result)

        def _send_json(self, status_code: int, data: dict) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # Suppress default logging for each request
        def log_message(self, format, *args):
            logger.debug("HTTP: %s", format % args)

    return HTTPServer(("127.0.0.1", port), _Handler)


# ── Fixture helpers ─────────────────────────────────────────────────────────


def config_for_mock(
    config: Any, mock_server: MockUnityServer
) -> None:
    """Update a Config object to point at the mock server's ports."""
    config.cli_port = mock_server.http_port
    config.cli_token = mock_server.token
