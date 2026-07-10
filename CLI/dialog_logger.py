"""
AgentCanvas Dialog Logger
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Records full send/receive transcripts per dialog session.

日志结构：
  logs/dialog_{dialogId}.jsonl     — 逐行 JSON，每条命令 + 响应
  dialogs/dialog_{dialogId}.json   — dialog 摘要（统计、时长等）

每行 JSONL 格式：
  {
    "timestamp": "2026-07-10T12:34:56.789Z",
    "dialogId": "default",
    "direction": "send" | "recv" | "receipt",
    "requestId": "req_a1b2c3d4",
    "command": "get.data",
    "params": {...},
    "response": {...},
    "duration_ms": 123
  }
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("agentcanvas.dialog_logger")


class DialogLogger:
    """
    Records full command/response transcripts per dialog session.

    Usage:
        dl = DialogLogger(log_dir="logs", dialog_dir="dialogs", dialog_id="default")
        dl.log_send("req_123", "get.data", {"dataId": "equipment_01"})
        dl.log_recv("req_123", {"status": "received"})
        dl.log_receipt("req_123", {"status": "completed", "data": {...}})
        dl.close()  # writes summary
    """

    def __init__(
        self,
        log_dir: str = "",
        dialog_dir: str = "",
        dialog_id: str = "default",
        streaming_assets_path: str = "",
    ):
        self.dialog_id = dialog_id
        self._start_time = time.time()
        self._command_count = 0
        self._error_count = 0
        self._active_commands: Dict[str, float] = {}

        # Determine base path
        base = Path(streaming_assets_path) if streaming_assets_path else Path.cwd()

        # Logs directory
        self._log_dir = Path(log_dir) if log_dir else (base / "logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Dialogs directory
        self._dialog_dir = Path(dialog_dir) if dialog_dir else (base / "dialogs")
        self._dialog_dir.mkdir(parents=True, exist_ok=True)

        # Open JSONL file
        self._log_path = self._log_dir / f"dialog_{dialog_id}.jsonl"
        self._log_file = open(self._log_path, "a", encoding="utf-8")
        self._closed = False

        logger.info(
            "DialogLogger started | dialog=%s | log=%s",
            dialog_id,
            self._log_path,
        )

    # ── Timestamp ──

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # ── Log methods ──

    def log_send(
        self,
        request_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an outgoing command."""
        if self._closed:
            return

        self._command_count += 1
        self._active_commands[request_id] = time.time()

        entry = {
            "timestamp": self._timestamp(),
            "dialogId": self.dialog_id,
            "direction": "send",
            "requestId": request_id,
            "command": command,
            "params": params or {},
        }
        self._write_line(entry)

    def log_recv(
        self,
        request_id: str,
        response: Dict[str, Any],
    ) -> None:
        """Log an HTTP response received for a command."""
        if self._closed:
            return

        start = self._active_commands.pop(request_id, None)
        duration_ms = round((time.time() - start) * 1000) if start else 0

        if response.get("status") == "error":
            self._error_count += 1

        entry = {
            "timestamp": self._timestamp(),
            "dialogId": self.dialog_id,
            "direction": "recv",
            "requestId": request_id,
            "response": response,
            "duration_ms": duration_ms,
        }
        self._write_line(entry)

    def log_receipt(
        self,
        request_id: str,
        receipt: Dict[str, Any],
    ) -> None:
        """Log a WebSocket receipt received for a command."""
        if self._closed:
            return

        entry = {
            "timestamp": self._timestamp(),
            "dialogId": self.dialog_id,
            "direction": "receipt",
            "requestId": request_id,
            "receipt": receipt,
        }
        self._write_line(entry)

    def log_interaction(
        self,
        request_id: str,
        page_id: str,
        element_id: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a student interaction callback from Unity."""
        if self._closed:
            return

        entry = {
            "timestamp": self._timestamp(),
            "dialogId": self.dialog_id,
            "direction": "interaction",
            "requestId": request_id,
            "pageId": page_id,
            "elementId": element_id,
            "action": action,
            "data": data or {},
        }
        self._write_line(entry)

    def log_system_event(
        self,
        event: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a system event (page.rendered, page.error, etc.)."""
        if self._closed:
            return

        entry = {
            "timestamp": self._timestamp(),
            "dialogId": self.dialog_id,
            "direction": "system",
            "event": event,
            "data": data or {},
        }
        self._write_line(entry)

    def _write_line(self, entry: Dict[str, Any]) -> None:
        """Write a single JSON line to the log file."""
        try:
            line = json.dumps(entry, ensure_ascii=False)
            self._log_file.write(line + "\n")
            self._log_file.flush()
        except Exception as e:
            logger.error("Failed to write log entry: %s", e)

    # ── Summary ──

    def _summary_path(self) -> Path:
        return self._dialog_dir / f"dialog_{self.dialog_id}.json"

    def write_summary(self) -> Dict[str, Any]:
        """Write a dialog summary JSON file."""
        elapsed = time.time() - self._start_time
        summary = {
            "dialogId": self.dialog_id,
            "startedAt": self._timestamp(),
            "elapsed_seconds": round(elapsed, 1),
            "commandCount": self._command_count,
            "errorCount": self._error_count,
            "logPath": str(self._log_path),
        }
        try:
            self._summary_path().write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to write dialog summary: %s", e)
        return summary

    # ── Lifecycle ──

    def close(self) -> Dict[str, Any]:
        """Close the logger and write the summary."""
        if self._closed:
            return {}
        self._closed = True
        summary = self.write_summary()
        try:
            self._log_file.close()
        except Exception:
            pass
        logger.info(
            "DialogLogger closed | dialog=%s | commands=%d | errors=%d",
            self.dialog_id,
            self._command_count,
            self._error_count,
        )
        return summary

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
