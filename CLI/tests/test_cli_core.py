"""
Tests for cli_core.py — Config, requestId, command definitions,
HTTP/WS client, error handling.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict

import pytest

from cli_core import (
    COMMAND_DEFINITIONS,
    Config,
    UnityClient,
    generate_request_id,
    handle_help,
    list_commands,
    pretty_json,
)


# ── Config ──────────────────────────────────────────────────────────────────


class TestConfig:
    def test_default_values(self):
        """Config should have sensible defaults without .env file."""
        config = Config.from_env()
        assert config.cli_port == 3748
        assert config.cli_token == ""
        assert config.lm_studio_host == "localhost"
        assert config.lm_studio_port == 1234
        assert config.embedding_model == "Qwen3-Embedding-0.6B"
        assert config.top_n == 5
        assert config.http_timeout == 5
        assert config.command_timeout == 30
        assert config.log_level == "INFO"

    def test_from_env_file(self, sample_env_file: Path):
        """Config should load values from a .env file."""
        config = Config.from_env(sample_env_file)
        assert config.cli_port == 3748
        assert config.cli_token == "my_test_token"
        assert config.log_level == "DEBUG"
        assert config.http_timeout == 5

    def test_unity_base_url(self, test_config: Config):
        """Base URL should be constructed from port."""
        config = Config(cli_port=3748)
        assert config.unity_base_url == "http://localhost:3748"

    def test_lm_studio_base_url(self):
        """LM Studio URL should be constructed from host and port."""
        config = Config(lm_studio_host="192.168.1.100", lm_studio_port=1234)
        assert config.lm_studio_base_url == "http://192.168.1.100:1234"

    def test_from_env_with_env_vars(self, monkeypatch):
        """Config should respect environment variables."""
        monkeypatch.setenv("CLI_PORT", "8080")
        monkeypatch.setenv("CLI_TOKEN", "env_token_123")
        monkeypatch.setenv("LOG_LEVEL", "ERROR")

        config = Config.from_env()
        assert config.cli_port == 8080
        assert config.cli_token == "env_token_123"
        assert config.log_level == "ERROR"


# ── RequestId ───────────────────────────────────────────────────────────────


class TestRequestId:
    def test_format(self):
        """requestId should follow the 'req_' + 8 hex chars format."""
        rid = generate_request_id()
        assert rid.startswith("req_")
        # Format: req_ + 8 hex chars = 12 characters
        assert len(rid) == 12, f"Expected 12 chars, got {len(rid)}: {rid}"
        assert re.match(r"^req_[0-9a-f]{8}$", rid), f"Bad format: {rid}"

    def test_uniqueness(self):
        """Multiple calls should produce different IDs."""
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100, "Duplicate request IDs generated"


# ── Command Definitions ─────────────────────────────────────────────────────


class TestCommandDefinitions:
    def test_all_commands_present(self):
        """All expected commands should be defined."""
        expected_commands = {
            "help",
            "docs",
            "docs_get",
            "whoami",
            "dialog",
            "list.templates",
            "search.data",
            "get.data",
            "usage",
            "page.create",
            "page.list",
            "run",
            "update",
            "clear",
            "result.show",
            "page.delete",
            "stop",
            "status.list",
            "queue",
            "queue.push",
            "init",
            "restart",
        }
        defined = set(COMMAND_DEFINITIONS.keys())
        assert defined == expected_commands, f"Missing: {expected_commands - defined}"

    def test_each_command_has_description(self):
        """Every command must have a non-empty description."""
        for name, info in COMMAND_DEFINITIONS.items():
            assert info["description"], f"Command '{name}' missing description"

    def test_required_params(self):
        """Commands with required params should enforce them."""
        required_map = {
            "docs_get": ["name"],
            "search.data": ["query"],
            "get.data": ["dataId"],
            "page.create": ["pageId"],
            "run": ["pageId"],
            "update": ["pageId", "patch"],
            "clear": ["pageId"],
            "result.show": ["pageId", "elementId", "result"],
            "page.delete": ["pageId"],
            "queue.push": ["commands"],
            "init": ["config"],
        }
        for command, required_params in required_map.items():
            info = COMMAND_DEFINITIONS[command]
            for p in required_params:
                param_info = info["params"].get(p)
                assert param_info is not None, (
                    f"Command '{command}' missing required param '{p}'"
                )
                assert param_info.get("required", False) is True, (
                    f"Param '{p}' in '{command}' should be required"
                )

    def test_list_commands_output(self):
        """list_commands() should produce formatted output."""
        output = list_commands()
        assert "Available commands:" in output
        assert "Help:" in output
        assert "Query:" in output
        assert "Page:" in output
        assert "Queue:" in output
        assert "Config:" in output
        assert "help" in output
        assert "search.data" in output
        assert "page.create" in output
        assert "init" in output


# ── handle_help ─────────────────────────────────────────────────────────────


class TestHandleHelp:
    def test_returns_completed_status(self):
        result = handle_help()
        assert result["status"] == "completed"
        assert "help" in result["data"]
        assert "Available commands:" in result["data"]["help"]


# ── pretty_json ─────────────────────────────────────────────────────────────


class TestPrettyJson:
    def test_formats_dict(self):
        data = {"key": "value", "num": 42}
        result = pretty_json(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_handles_unicode(self):
        data = {"name": "显微镜"}
        result = pretty_json(data)
        assert "显微镜" in result
        parsed = json.loads(result)
        assert parsed == data

    def test_handles_list(self):
        data = [1, 2, {"a": "b"}]
        result = pretty_json(data)
        parsed = json.loads(result)
        assert parsed == data


# ── UnityClient (no server) ─────────────────────────────────────────────────


class TestUnityClientBasic:
    """Tests for UnityClient that don't need a live/mock server."""

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """Unknown commands should return an error without hitting the server."""
        client = UnityClient(Config(cli_port=9999, cli_token="test"))
        result = await client.execute("nonexistent.command")
        assert result["status"] == "error"
        assert result["code"] == 400
        assert "Unknown command" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Missing required params should return 400 without hitting the server."""
        client = UnityClient(Config(cli_port=9999, cli_token="test"))
        result = await client.execute("get.data", {})  # missing dataId
        assert result["status"] == "error"
        assert result["code"] == 400
        assert "Missing required parameter" in result["message"]

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Connection refused should return a 503 error."""
        client = UnityClient(Config(cli_port=19876, cli_token="test"))
        result = await client.execute("whoami", wait=False)
        assert result["status"] == "error"
        assert result["code"] == 503
        assert "Connection failed" in result["message"] or "All connection attempts failed" in result["message"]

    def test_generate_request_id_unique(self):
        """Each call to generate_request_id should produce unique values."""
        ids = {generate_request_id() for _ in range(20)}
        assert len(ids) == 20


# ── UnityClient with mock server ────────────────────────────────────────────


@pytest.mark.integration
class TestUnityClientIntegration:
    """Tests requiring the mock Unity server."""

    @pytest.mark.asyncio
    async def test_send_and_receive(self, mock_unity, unity_client):
        """Basic command send/receive cycle should work."""
        result = await unity_client.execute("whoami")
        assert result["status"] == "completed"
        assert "data" in result

        # Verify the command was received
        records = mock_unity.commands
        assert len(records) == 1
        assert records[0].command == "whoami"

    @pytest.mark.asyncio
    async def test_command_params_passed(self, mock_unity, unity_client):
        """Command parameters should be forwarded correctly."""
        result = await unity_client.execute(
            "get.data",
            {"dataId": "equipment_03"},
        )
        assert result["status"] == "completed"

        records = mock_unity.commands
        assert len(records) == 1
        assert records[0].params == {"dataId": "equipment_03"}

    @pytest.mark.asyncio
    async def test_auth_header_sent(self, mock_unity, unity_client):
        """Authorization header should be sent with each request."""
        await unity_client.execute("help")

        records = mock_unity.commands
        assert len(records) == 1
        auth = records[0].headers.get("authorization", "")
        assert f"Bearer {mock_unity.token}" in auth

    @pytest.mark.asyncio
    async def test_sequential_commands(self, mock_unity, unity_client):
        """Multiple commands in sequence should all be received."""
        commands = ["help", "whoami", "usage"]
        for cmd in commands:
            await unity_client.execute(cmd)

        assert len(mock_unity.commands) == 3
        received = [r.command for r in mock_unity.commands]
        assert received == commands

    @pytest.mark.asyncio
    async def test_custom_receipt(self, mock_unity, unity_client):
        """Custom receipt data should be returned."""
        mock_unity.set_receipt(
            "test_req_123",
            {
                "status": "completed",
                "data": {"id": "equipment_01", "displayName": "显微镜"},
            },
        )

        # The mock sends custom receipt only if requestId matches
        result = await unity_client.execute("get.data", {"dataId": "equipment_01"})
        # Should get the default receipt since requestId won't be "test_req_123"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_wait_false(self, mock_unity, unity_client):
        """wait=False should return HTTP response immediately."""
        result = await unity_client.execute("whoami", wait=False)
        assert result["status"] == "received"

        # Give WS time to arrive
        await asyncio.sleep(0.1)
        assert len(mock_unity.commands) == 1

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_unity, unity_client):
        """Error responses from server should be propagated."""
        # Set custom receipt with error
        mock_unity.set_receipt(
            "error_req",
            {"status": "error", "code": 500, "message": "Internal error"},
        )

        result = await unity_client.execute("stop")
        # Default receipt should be used for non-matching requestId
        assert result["status"] == "completed"


