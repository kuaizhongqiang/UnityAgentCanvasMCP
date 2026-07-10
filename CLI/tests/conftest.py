"""
pytest fixtures for AgentCanvas CLI tests.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from cli_core import Config, UnityClient
from tests.mock_unity_server import MockUnityServer

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def test_token() -> str:
    return "test-token-abc123"


@pytest.fixture
def test_config() -> Config:
    """Basic Config for tests that don't need a live server."""
    return Config(
        cli_port=0,
        cli_token="test-token",
    )


@pytest_asyncio.fixture
async def mock_unity(test_token: str) -> AsyncGenerator[MockUnityServer, None]:
    """
    Start a mock Unity server (HTTP + WS) for integration tests.

    Yields the MockUnityServer instance directly.
    """
    server = await MockUnityServer.start(
        token=test_token,
        receipt_delay=0.02,
    )
    try:
        yield server
    finally:
        await server.stop()


@pytest_asyncio.fixture
async def unity_client(
    mock_unity: MockUnityServer,
) -> AsyncGenerator[UnityClient, None]:
    """
    Create a UnityClient connected to the mock server.
    """
    config = Config(
        cli_port=mock_unity.http_port,
        cli_token=mock_unity.token,
    )

    client = UnityClient(config)

    # Patch WS connection to use mock server's WS port separately
    async def patched_connect():
        import websockets.client as ws_client
        ws_url = f"ws://localhost:{mock_unity.ws_port}/ws?token={config.cli_token}"
        try:
            client._ws = await ws_client.connect(ws_url, ping_interval=30)
            client._ws_connected.set()
            asyncio.create_task(client._ws_listen())
            logger = logging.getLogger("agentcanvas.tests")
            logger.debug("WS connected to mock at %s", ws_url)
        except Exception as e:
            logging.getLogger("agentcanvas.tests").warning(
                "WS connection to mock failed: %s", e
            )
            client._ws_connected.set()

    client.connect_ws = patched_connect
    await client.connect_ws()

    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def sample_env_file(tmp_path: Path) -> Path:
    """Create a temporary .env file for config loading tests."""
    env_content = """
CLI_PORT=3748
CLI_TOKEN=my_test_token
LM_STUDIO_HOST=localhost
LM_STUDIO_PORT=1234
EMBEDDING_MODEL=Qwen3-Embedding-0.6B
TOP_N=5
HTTP_TIMEOUT=5
COMMAND_TIMEOUT=30
LOG_LEVEL=DEBUG
"""
    env_path = tmp_path / ".env"
    env_path.write_text(env_content.strip(), encoding="utf-8")
    return env_path


@pytest.fixture
def sample_data_export(tmp_path: Path) -> Path:
    """Create a sample data_export.json for embedding tests."""
    export = [
        {
            "id": "equipment_01",
            "displayName": "显微镜",
            "description": "光学显微镜构造与成像原理",
            "tag": ["显微镜", "光学", "成像"],
            "data": {"imagePath": "textures/microscope.png"},
            "knowledgeOriginal": "显微镜由目镜、物镜、载物台、聚光镜和光源组成。",
            "templateType": "image_text",
        },
        {
            "id": "equipment_02",
            "displayName": "电压表",
            "description": "电压测量仪器",
            "tag": ["电压", "测量", "电路"],
            "data": {"imagePath": "textures/voltmeter.png"},
            "knowledgeOriginal": "电压表并联在被测电路两端。",
            "templateType": "image_text",
        },
        {
            "id": "principle_01",
            "displayName": "欧姆定律",
            "description": "导体中的电流与电压成正比，与电阻成反比",
            "tag": ["欧姆定律", "电路", "电流"],
            "data": {"formula": "I = V/R"},
            "knowledgeOriginal": "欧姆定律指出：I = V/R",
            "templateType": "subtitle_text",
        },
    ]
    path = tmp_path / "data_export.json"
    path.write_text(__import__("json").dumps(export, ensure_ascii=False), encoding="utf-8")
    return path
