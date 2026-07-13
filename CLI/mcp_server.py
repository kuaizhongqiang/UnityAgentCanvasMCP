#!/usr/bin/env python3
"""
AgentCanvas MCP Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MCP protocol adapter that exposes all AgentCanvas CLI commands as
MCP tools via stdio transport. This is the production entry point
started by Unity's GlobalCLIMgr.

Agent ← MCP (stdio) → MCP Server (this file) ← HTTP/WS → Unity

Usage:
    python mcp_server.py                # Start MCP Server
    python mcp_server.py --dev-mode     # Start with debug logging

Environment:
    All config via .env file or environment variables.
    See .env.example for all options.
"""


import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from cli_core import Config, UnityClient
from embedding_client import EmbeddingClient

# ── Logging ─────────────────────────────────────────────────────────────────

logger = logging.getLogger("agentcanvas.mcp_server")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── MCP Server ──────────────────────────────────────────────────────────────


class AgentCanvasMCPServer:
    """
    MCP Server for AgentCanvas.

    Manages:
    - UnityClient for HTTP/WS communication with Unity
    - EmbeddingClient for semantic search
    - Tool definitions exposed to the Agent via stdio MCP transport
    """

    def __init__(self, config: Config):
        self.config = config
        self.unity: Optional[UnityClient] = None
        self.embedding: Optional[EmbeddingClient] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize all clients and index."""
        logger.info(
            "AgentCanvas MCP Server starting (port=%d, log=%s)",
            self.config.cli_port,
            self.config.log_level,
        )

        # Unity client
        self.unity = UnityClient(self.config)
        await self.unity.connect_ws()

        # Initialize dialog logging
        self.unity.set_dialog(self.config.dialog_id)

        # Embedding client
        self.embedding = EmbeddingClient(self.config)
        await self.embedding.build_index()

        logger.info("AgentCanvas MCP Server ready")

    async def stop(self) -> None:
        """Clean shutdown of all clients."""
        logger.info("AgentCanvas MCP Server stopping")
        if self.unity:
            await self.unity.close()
        if self.embedding:
            await self.embedding.close()
        logger.info("AgentCanvas MCP Server stopped")

    # ── Tool Implementations ────────────────────────────────────────────────

    async def _exec(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a command against Unity and return the result."""
        async with self._lock:
            if self.unity is None:
                return {"status": "error", "code": 503, "message": "Server not initialized"}
            return await self.unity.execute(command, params or {})

    # ── Help ──

    async def tool_help(self) -> str:
        """List all available commands and usage."""
        from cli_core import list_commands
        return list_commands()

    async def tool_docs(self) -> str:
        """List all available documentation."""
        result = await self._exec("docs")
        if result.get("status") == "error":
            return json.dumps(result, ensure_ascii=False)
        return json.dumps(result.get("data", result), ensure_ascii=False, indent=2)

    async def tool_docs_get(self, name: str) -> str:
        """Get full documentation by name."""
        result = await self._exec("docs_get", {"name": name})
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Query ──

    async def tool_whoami(self) -> str:
        """Return current agent identity and permissions."""
        result = await self._exec("whoami")
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_dialog_list(self) -> str:
        """List all dialogs."""
        result = await self._exec("dialog")
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_dialog_get(self, dialog_id: str) -> str:
        """Get details for a specific dialog."""
        result = await self._exec("dialog", {"dialogId": dialog_id})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_list_templates(self) -> str:
        """List all available UI templates."""
        result = await self._exec("list.templates")
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_search_data(self, query: str) -> str:
        """
        Semantic search across data.

        Uses LM Studio for embedding-powered search, falls back to
        keyword matching if LM Studio is unavailable.
        """
        if self.embedding:
            try:
                results = await self.embedding.search(query)
                output = []
                for r in results:
                    output.append({
                        "id": r.id,
                        "desc": r.desc,
                        "tag": r.tag,
                        "data": r.data,
                        "knowledgeOriginal": r.knowledge_original,
                        "score": r.score,
                        "templateType": r.template_type,
                    })
                return json.dumps(
                    {"status": "completed", "data": output},
                    ensure_ascii=False,
                    indent=2,
                )
            except Exception as e:
                logger.warning("Embedding search failed, falling back to Unity search: %s", e)

        # Fallback: let Unity handle it (keyword match on Unity side)
        result = await self._exec("search.data", {"query": query})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_get_data(self, data_id: str) -> str:
        """Get full data record by ID (ground truth from Unity)."""
        result = await self._exec("get.data", {"dataId": data_id})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_usage(self) -> str:
        """Get usage statistics."""
        result = await self._exec("usage")
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Page Operations ──

    async def tool_status_list(self, dialog_id: str = "") -> str:
        """Query command status by dialogId (for WS reconnect recovery)."""
        result = await self._exec("status.list", {"dialogId": dialog_id})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_page_create(self, page_id: str) -> str:
        """Create a new blank page."""
        result = await self._exec("page.create", {"pageId": page_id})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_page_list(self) -> str:
        """List all pages and their status."""
        result = await self._exec("page.list")
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_run(self, page_id: str, file_path: Optional[str] = None) -> str:
        """Execute/render a page in Unity UI."""
        params: Dict[str, Any] = {"pageId": page_id}
        if file_path:
            params["filePath"] = file_path
        result = await self._exec("run", params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_run_file(self, page_id: str, file_path: str) -> str:
        """Load page config from a JSON file and render it."""
        result = await self._exec("run", {"pageId": page_id, "filePath": file_path})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_update(self, page_id: str, patch: str) -> str:
        """Incrementally update a page (JSON Merge Patch).

        Args:
            page_id: The page to update
            patch: JSON Merge Patch object as a JSON string
        """
        try:
            patch_obj = json.loads(patch)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"status": "error", "code": 400, "message": f"Invalid JSON patch: {e}"},
                ensure_ascii=False,
            )
        result = await self._exec("update", {"pageId": page_id, "patch": patch_obj})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_clear(self, page_id: str, scope: Optional[str] = None) -> str:
        """Clear page content, optionally scoped."""
        params: Dict[str, Any] = {"pageId": page_id}
        if scope:
            params["scope"] = scope
        result = await self._exec("clear", params)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_result_show(
        self,
        page_id: str,
        element_id: str,
        result: str,
    ) -> str:
        """Show quiz result feedback on a specific element.

        Args:
            page_id: The page containing the element
            element_id: The element to show result on
            result: JSON object with result data (isCorrect, correctAnswer, etc.)
        """
        try:
            result_obj = json.loads(result)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"status": "error", "code": 400, "message": f"Invalid JSON result: {e}"},
                ensure_ascii=False,
            )
        exec_result = await self._exec(
            "result.show",
            {
                "pageId": page_id,
                "elementId": element_id,
                "result": result_obj,
            },
        )
        return json.dumps(exec_result, ensure_ascii=False, indent=2)

    async def tool_page_delete(self, page_id: str) -> str:
        """Delete a page and its configuration."""
        result = await self._exec("page.delete", {"pageId": page_id})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_stop(self) -> str:
        """Stop the currently executing task."""
        result = await self._exec("stop")
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Queue ──

    async def tool_queue_list(self) -> str:
        """List queued commands."""
        result = await self._exec("queue")
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_queue_push(self, commands: str) -> str:
        """Submit batch commands for sequential execution.

        Args:
            commands: JSON array of command objects, e.g.
                [{"command": "page.create", "params": {"pageId": "page_1"}}]
        """
        try:
            cmds = json.loads(commands)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"status": "error", "code": 400, "message": f"Invalid JSON: {e}"},
                ensure_ascii=False,
            )
        if not isinstance(cmds, list):
            return json.dumps(
                {"status": "error", "code": 400, "message": "commands must be a JSON array"},
                ensure_ascii=False,
            )
        result = await self._exec("queue.push", {"commands": cmds})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_queue_get(self, command_id: str) -> str:
        """Get status of a queued command by its ID."""
        result = await self._exec("queue", {"commandId": command_id})
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Config ──

    async def tool_init(self, config: str) -> str:
        """Persist agent configuration.

        Args:
            config: JSON object with agent config
                (name, role, preferences, etc.)
        """
        try:
            config_obj = json.loads(config)
        except json.JSONDecodeError as e:
            return json.dumps(
                {"status": "error", "code": 400, "message": f"Invalid JSON config: {e}"},
                ensure_ascii=False,
            )
        result = await self._exec("init", {"config": config_obj})
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def tool_restart(self) -> str:
        """Restart current session (keeps init config)."""
        result = await self._exec("restart")
        return json.dumps(result, ensure_ascii=False, indent=2)


# ── FastMCP Integration ─────────────────────────────────────────────────────


def _probe_fastmcp_api() -> bool:
    """
    Probe whether the installed FastMCP supports the modern API
    (on_startup/on_shutdown decorators, transport= param in run()).

    Returns True for modern API (mcp >= ~1.20), False for legacy.
    """
    try:
        from mcp.server.fastmcp import FastMCP
        probe = FastMCP("probe")
        return callable(getattr(probe, "on_startup", None))
    except Exception:
        return False


def create_mcp_app(config: Config):
    """
    Create and configure a FastMCP application with all AgentCanvas tools.

    Returns (app, server, new_api) tuple.
    new_api=True means on_startup/on_shutdown + transport= are supported.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.error(
            "mcp[fastmcp] package not found. Install with: "
            "pip install 'mcp>=1.0'"
        )
        sys.exit(1)

    new_api = _probe_fastmcp_api()
    server = AgentCanvasMCPServer(config)

    if new_api:
        try:
            app = FastMCP(
                "agentcanvas",
                description="AgentCanvas MCP Server — AI Agent driving Unity UI Toolkit",
                version="0.1.0",
            )
        except TypeError:
            app = FastMCP("agentcanvas")
    else:
        app = FastMCP("agentcanvas")

    # ── Startup / Shutdown ──

    if new_api:
        @app.on_startup
        async def startup():
            await server.start()

        @app.on_shutdown
        async def shutdown():
            await server.stop()
    else:
        # Legacy FastMCP: lifecycle managed in main()
        pass

    # ── Tool Registrations ──

    # Help
    @app.tool(
        name="help",
        description="List all available commands and usage for the AgentCanvas CLI.",
    )
    async def help_tool() -> str:
        return await server.tool_help()

    @app.tool(
        name="docs",
        description="List all available documentation.",
    )
    async def docs_tool() -> str:
        return await server.tool_docs()

    @app.tool(
        name="docs_get",
        description="Get full documentation by name.",
    )
    async def docs_get_tool(name: str) -> str:
        return await server.tool_docs_get(name)

    # Query
    @app.tool(
        name="whoami",
        description="Return current agent identity and permissions.",
    )
    async def whoami_tool() -> str:
        return await server.tool_whoami()

    @app.tool(
        name="dialog_list",
        description="List all dialogs.",
    )
    async def dialog_list_tool() -> str:
        return await server.tool_dialog_list()

    @app.tool(
        name="dialog_get",
        description="Get details for a specific dialog by ID.",
    )
    async def dialog_get_tool(dialogId: str) -> str:
        return await server.tool_dialog_get(dialogId)

    @app.tool(
        name="list_templates",
        description="List all available UI templates.",
    )
    async def list_templates_tool() -> str:
        return await server.tool_list_templates()

    @app.tool(
        name="search_data",
        description="Semantic search across data using natural language. Uses Embedding engine (LM Studio) when available, falls back to keyword matching.",
    )
    async def search_data_tool(query: str) -> str:
        return await server.tool_search_data(query)

    @app.tool(
        name="get_data",
        description="Get full data record by ID from Unity (ground truth).",
    )
    async def get_data_tool(dataId: str) -> str:
        return await server.tool_get_data(dataId)

    @app.tool(
        name="usage",
        description="Get usage statistics for the current session.",
    )
    async def usage_tool() -> str:
        return await server.tool_usage()

    # Page Operations
    @app.tool(
        name="status_list",
        description="Query command status by dialogId (for WS reconnect recovery).",
    )
    async def status_list_tool(dialogId: str = "") -> str:
        return await server.tool_status_list(dialogId)

    @app.tool(
        name="page_create",
        description="Create a new blank page.",
    )
    async def page_create_tool(pageId: str) -> str:
        return await server.tool_page_create(pageId)

    @app.tool(
        name="page_list",
        description="List all pages and their status.",
    )
    async def page_list_tool() -> str:
        return await server.tool_page_list()

    @app.tool(
        name="run",
        description="Execute/render a page in Unity UI.",
    )
    async def run_tool(pageId: str, filePath: Optional[str] = None) -> str:
        return await server.tool_run(pageId, filePath)

    @app.tool(
        name="run_file",
        description="Load page config from a JSON file (relative to StreamingAssets) and render it.",
    )
    async def run_file_tool(pageId: str, filePath: str) -> str:
        return await server.tool_run_file(pageId, filePath)

    @app.tool(
        name="update",
        description="Incrementally update a page using JSON Merge Patch (RFC 7396).",
    )
    async def update_tool(pageId: str, patch: str) -> str:
        return await server.tool_update(pageId, patch)

    @app.tool(
        name="clear",
        description="Clear page content, optionally scoped to specific elements.",
    )
    async def clear_tool(pageId: str, scope: Optional[str] = None) -> str:
        return await server.tool_clear(pageId, scope)

    @app.tool(
        name="result_show",
        description="Show quiz/result feedback on a specific element (e.g., correct/incorrect answer).",
    )
    async def result_show_tool(pageId: str, elementId: str, result: str) -> str:
        return await server.tool_result_show(pageId, elementId, result)

    @app.tool(
        name="page_delete",
        description="Delete a page and its configuration.",
    )
    async def page_delete_tool(pageId: str) -> str:
        return await server.tool_page_delete(pageId)

    @app.tool(
        name="stop",
        description="Stop the currently executing task in Unity.",
    )
    async def stop_tool() -> str:
        return await server.tool_stop()

    # Queue
    @app.tool(
        name="queue_list",
        description="View the command queue.",
    )
    async def queue_list_tool() -> str:
        return await server.tool_queue_list()

    @app.tool(
        name="queue_push",
        description="Submit batch commands for sequential execution.",
    )
    async def queue_push_tool(commands: str) -> str:
        return await server.tool_queue_push(commands)

    @app.tool(
        name="queue_get",
        description="Get the status of a specific queued command by its ID.",
    )
    async def queue_get_tool(commandId: str) -> str:
        return await server.tool_queue_get(commandId)

    # Config
    @app.tool(
        name="init",
        description="Persist agent configuration (name, role, preferences, defaultLayout, etc.).",
    )
    async def init_tool(config: str) -> str:
        return await server.tool_init(config)

    @app.tool(
        name="restart",
        description="Restart the current session, keeping init config but clearing page state.",
    )
    async def restart_tool() -> str:
        return await server.tool_restart()

    return app, server, new_api


# ── Main Entry Point ────────────────────────────────────────────────────────


async def _run_legacy(app, server):
    """Run with legacy FastMCP that doesn't support modern lifecycle."""
    await server.start()
    try:
        await app.run(transport="stdio")
    except TypeError:
        # Even older: run() doesn't accept transport=
        await app.run()
    finally:
        await server.stop()


def main():
    # Parse CLI args
    import argparse

    parser = argparse.ArgumentParser(description="AgentCanvas MCP Server")
    parser.add_argument(
        "--dotenv", "-e",
        default=".env",
        help="Path to .env configuration file",
    )
    parser.add_argument(
        "--dev-mode",
        action="store_true",
        help="Enable debug logging and verbose output",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override Unity CLI port",
    )
    args = parser.parse_args()

    # Load config
    env_path = Path(args.dotenv) if args.dotenv != ".env" else Path(".env")
    config = Config.from_env(env_path)

    if args.dev_mode:
        config.log_level = "DEBUG"
    if args.port:
        config.cli_port = args.port

    setup_logging(config.log_level)
    logger.info("Starting AgentCanvas MCP Server (dev-mode=%s)", args.dev_mode)

    # Create and run MCP app
    app, server, new_api = create_mcp_app(config)

    try:
        if new_api:
            # Modern FastMCP: on_startup/on_shutdown + transport= supported
            app.run(transport="stdio")
        else:
            # Legacy FastMCP: manual lifecycle
            asyncio.run(_run_legacy(app, server))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Fatal error: %s\n%s", e, traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
