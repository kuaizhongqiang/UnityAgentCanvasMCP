#!/usr/bin/env python3
"""
AgentCanvas CLI — Debug & Development Tool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLI for manually testing AgentCanvas commands against a running Unity instance.

Usage:
    python main.py help
    python main.py get.data equipment_03
    python main.py search.data "显微镜"
    python main.py page.create my_page
    python main.py run my_page

Dot-notation and underscore-notation are interchangeable: `get.data` = `get_data`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import click

from cli_core import Config, UnityClient, list_commands, pretty_json

# ── Setup ───────────────────────────────────────────────────────────────────


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Command mapping: dot-notation → underscore-notation ─────────────────────

DOT_TO_UNDERSCORE: Dict[str, str] = {
    "search.data": "search_data",
    "get.data": "get_data",
    "page.create": "page_create",
    "page.list": "page_list",
    "page.delete": "page_delete",
    "list.templates": "list_templates",
    "result.show": "result_show",
    "queue.push": "queue_push",
}

UNDERSCORE_TO_DOT = {v: k for k, v in DOT_TO_UNDERSCORE.items()}


# ── Async runner ────────────────────────────────────────────────────────────


class CLIState:
    """Shared state for CLI commands."""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[UnityClient] = None

    async def get_client(self) -> UnityClient:
        if self.client is None:
            self.client = UnityClient(self.config)
            await self.client.connect_ws()
        return self.client

    async def close(self) -> None:
        if self.client:
            await self.client.close()


pass_state = click.make_pass_decorator(CLIState, ensure=True)


# ── Helper: run async command ───────────────────────────────────────────────


def async_cmd(f):
    """Decorator: wrap an async Click command callback to run with asyncio.run."""
    return click.pass_context(  # type: ignore[return]
        lambda ctx, *a, **kw: asyncio.run(f(ctx, *a, **kw))
    )


# ── Utility: print result ───────────────────────────────────────────────────


def print_result(result: Dict[str, Any], command: str = "") -> None:
    """Pretty-print a command result."""
    status = result.get("status", "?")
    code = result.get("code", 200)

    if status == "error":
        click.secho(f"✗ Error [{code}]: {result.get('message', 'Unknown')}", fg="red")
        return

    if "data" in result:
        data = result["data"]
        if isinstance(data, dict) and "note" in data and len(data) == 1:
            click.echo(data["note"])
        else:
            click.echo(pretty_json(data))
    else:
        click.echo(pretty_json(result))


# ── Main CLI Group ──────────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--dotenv", "-e", default=".env", help="Path to .env file")
@click.option("--log-level", "-l", default=None, help="Override log level")
@click.version_option(version="0.1.0", prog_name="agentcanvas")
@click.pass_context
def cli(ctx, dotenv: str, log_level: Optional[str]):
    """AgentCanvas CLI — debug tool for AgentCanvas MCP system.

    Connects to a running Unity instance via HTTP/WebSocket.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand: show help
        click.echo(ctx.get_help())
        return

    # Load config
    env_path = Path(dotenv) if dotenv != ".env" else Path(".env")
    config = Config.from_env(env_path)

    if log_level:
        config.log_level = log_level

    setup_logging(config.log_level)

    # Store config in CLIState
    state = ctx.find_object(CLIState)
    if state is None:
        state = CLIState(config)
        ctx.obj = state
    else:
        state.config = config


# ── Resolve dot-notation commands via a catch-all ───────────────────────────


@cli.result_callback()
@click.pass_context
def process_result(ctx, result, **kwargs):
    """After all subcommand processing, clean up."""
    state = ctx.find_object(CLIState)
    if state and state.client:
        asyncio.run(state.close())


# ── Help ──


@cli.command("help")
def cmd_help():
    """List all available commands and usage."""
    click.echo(list_commands())


# ── Docs ──


@cli.group("docs")
def cmd_docs():
    """List or get documentation."""


@cmd_docs.command("list")
@async_cmd
async def cmd_docs_list(ctx):
    """List all available documentation."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("docs", {})
    print_result(result, "docs")


@cmd_docs.command("get")
@click.argument("name")
@async_cmd
async def cmd_docs_get(ctx, name: str):
    """Get full documentation by name."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("docs_get", {"name": name})
    print_result(result, f"docs.get {name}")


# ── Query ──


@cli.command("whoami")
@async_cmd
async def cmd_whoami(ctx):
    """Return current agent identity and permissions."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("whoami")
    print_result(result, "whoami")


@cli.command("dialog")
@click.argument("dialog_id", required=False)
@async_cmd
async def cmd_dialog(ctx, dialog_id: Optional[str]):
    """List dialogs or get dialog details."""
    state = ctx.obj
    client = await state.get_client()
    params = {}
    if dialog_id:
        params["dialogId"] = dialog_id
    result = await client.execute("dialog", params)
    print_result(result, "dialog")


@cli.command("list_templates")
@async_cmd
async def cmd_list_templates(ctx):
    """List all available UI templates."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("list.templates")
    print_result(result, "list.templates")


@cli.command("search_data")
@click.argument("query")
@async_cmd
async def cmd_search_data(ctx, query: str):
    """Semantic search across data using natural language."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("search.data", {"query": query})
    print_result(result, "search.data")


@cli.command("get_data")
@click.argument("data_id")
@async_cmd
async def cmd_get_data(ctx, data_id: str):
    """Get full data record by ID."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("get.data", {"dataId": data_id})
    print_result(result, "get.data")


@cli.command("usage")
@async_cmd
async def cmd_usage(ctx):
    """Get usage statistics."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("usage")
    print_result(result, "usage")


# ── Page Operations ──


@cli.command("status_list")
@click.argument("dialog_id", required=False)
@async_cmd
async def cmd_status_list(ctx, dialog_id: Optional[str] = None):
    """Query command status by dialogId (for WS reconnect recovery)."""
    state = ctx.obj
    client = await state.get_client()
    params = {}
    if dialog_id:
        params["dialogId"] = dialog_id
    result = await client.execute("status.list", params)
    print_result(result, "status.list")


@cli.command("page_create")
@click.argument("page_id")
@async_cmd
async def cmd_page_create(ctx, page_id: str):
    """Create a new blank page."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("page.create", {"pageId": page_id})
    print_result(result, "page.create")


@cli.command("page_list")
@async_cmd
async def cmd_page_list(ctx):
    """List all pages and their status."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("page.list")
    print_result(result, "page.list")


@cli.command("run")
@click.argument("page_id")
@click.argument("file_path", required=False)
@async_cmd
async def cmd_run(ctx, page_id: str, file_path: Optional[str]):
    """Execute/render a page in Unity."""
    state = ctx.obj
    client = await state.get_client()
    params: Dict[str, Any] = {"pageId": page_id}
    if file_path:
        params["filePath"] = file_path
    result = await client.execute("run", params)
    print_result(result, "run")


@cli.command("update")
@click.argument("page_id")
@click.argument("patch")
@async_cmd
async def cmd_update(ctx, page_id: str, patch: str):
    """Incrementally update a page (JSON Merge Patch)."""
    state = ctx.obj
    client = await state.get_client()
    try:
        patch_obj = json.loads(patch)
    except json.JSONDecodeError as e:
        click.secho(f"✗ Invalid JSON patch: {e}", fg="red")
        return
    result = await client.execute("update", {"pageId": page_id, "patch": patch_obj})
    print_result(result, "update")


@cli.command("clear")
@click.argument("page_id")
@click.argument("scope", required=False)
@async_cmd
async def cmd_clear(ctx, page_id: str, scope: Optional[str]):
    """Clear page content, optionally scoped."""
    state = ctx.obj
    client = await state.get_client()
    params: Dict[str, Any] = {"pageId": page_id}
    if scope:
        params["scope"] = scope
    result = await client.execute("clear", params)
    print_result(result, "clear")


@cli.command("result_show")
@click.argument("page_id")
@click.argument("element_id")
@click.argument("result_json")
@async_cmd
async def cmd_result_show(ctx, page_id: str, element_id: str, result_json: str):
    """Show quiz result feedback on a specific element."""
    state = ctx.obj
    client = await state.get_client()
    try:
        result_obj = json.loads(result_json)
    except json.JSONDecodeError as e:
        click.secho(f"✗ Invalid JSON result: {e}", fg="red")
        return
    result = await client.execute(
        "result.show",
        {
            "pageId": page_id,
            "elementId": element_id,
            "result": result_obj,
        },
    )
    print_result(result, "result.show")


@cli.command("page_delete")
@click.argument("page_id")
@async_cmd
async def cmd_page_delete(ctx, page_id: str):
    """Delete a page and its configuration."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("page.delete", {"pageId": page_id})
    print_result(result, "page.delete")


@cli.command("stop")
@async_cmd
async def cmd_stop(ctx):
    """Stop the currently executing task."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("stop")
    print_result(result, "stop")


# ── Queue ──


@cli.command("queue")
@click.argument("command_id", required=False)
@async_cmd
async def cmd_queue(ctx, command_id: Optional[str]):
    """View or manage the command queue."""
    state = ctx.obj
    client = await state.get_client()
    params: Dict[str, Any] = {}
    if command_id:
        params["commandId"] = command_id
    result = await client.execute("queue", params)
    print_result(result, "queue")


@cli.command("queue_push")
@click.argument("commands_json")
@async_cmd
async def cmd_queue_push(ctx, commands_json: str):
    """Submit batch commands for sequential execution.

    COMMANDS_JSON is a JSON array of command objects.
    """
    state = ctx.obj
    client = await state.get_client()
    try:
        cmds = json.loads(commands_json)
    except json.JSONDecodeError as e:
        click.secho(f"✗ Invalid JSON: {e}", fg="red")
        return
    if not isinstance(cmds, list):
        click.secho("✗ commands_json must be a JSON array", fg="red")
        return
    result = await client.execute("queue.push", {"commands": cmds})
    print_result(result, "queue.push")


# ── Config ──


@cli.command("init")
@click.argument("config_json")
@async_cmd
async def cmd_init(ctx, config_json: str):
    """Persist agent configuration."""
    state = ctx.obj
    client = await state.get_client()
    try:
        config_obj = json.loads(config_json)
    except json.JSONDecodeError as e:
        click.secho(f"✗ Invalid JSON config: {e}", fg="red")
        return
    result = await client.execute("init", {"config": config_obj})
    print_result(result, "init")


@cli.command("restart")
@async_cmd
async def cmd_restart(ctx):
    """Restart current session (keeps init config)."""
    state = ctx.obj
    client = await state.get_client()
    result = await client.execute("restart")
    print_result(result, "restart")


# ── Dot-notation alias resolver ─────────────────────────────────────────────


class DotAliasGroup(click.Group):
    """
    Click Group that resolves dot-notation aliases.

    `python main.py search.data "query"` → routes to `search_data` command.
    """

    def resolve_command(self, ctx, args):
        # Check if the first arg is a dot-notation alias
        if args and args[0] in DOT_TO_UNDERSCORE:
            alias = args[0]
            target = DOT_TO_UNDERSCORE[alias]
            click.echo(f"({alias} → {target})", err=True)
            args[0] = target
        return super().resolve_command(ctx, args)


# ── Entry Point ─────────────────────────────────────────────────────────────


def main():
    # Replace the CLI group with the alias-aware version
    dot_cli = DotAliasGroup(
        params=cli.params,
        name=cli.name,
        callback=cli.callback,
        help=cli.help,
    )
    # Copy all commands from the original group
    for name, cmd in cli.commands.items():
        dot_cli.add_command(cmd, name)

    dot_cli()


if __name__ == "__main__":
    main()
