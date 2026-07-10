"""
Tests for dialog_logger.py — DialogLogger send/receive recording, summary, interaction logging.
"""

from __future__ import annotations

import json
from pathlib import Path


from dialog_logger import DialogLogger


class TestDialogLogger:
    def test_log_send(self, tmp_path: Path):
        """Log send should write a JSON line to the log file."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="test")
        dl.log_send("req_001", "get.data", {"dataId": "eq_01"})
        dl.close()

        lines = (tmp_path / "dialog_test.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["direction"] == "send"
        assert entry["requestId"] == "req_001"
        assert entry["command"] == "get.data"
        assert entry["params"] == {"dataId": "eq_01"}

    def test_log_recv(self, tmp_path: Path):
        """Log recv should record the response."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="test")
        dl.log_send("req_001", "whoami")
        dl.log_recv("req_001", {"status": "received"})
        dl.close()

        lines = (tmp_path / "dialog_test.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        entry = json.loads(lines[1])
        assert entry["direction"] == "recv"
        assert entry["response"]["status"] == "received"
        assert "duration_ms" in entry

    def test_log_receipt(self, tmp_path: Path):
        """Log receipt should record the WS receipt."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="test")
        dl.log_send("req_001", "run", {"pageId": "p1"})
        dl.log_recv("req_001", {"status": "received"})
        dl.log_receipt("req_001", {"status": "completed", "data": {"pageId": "p1"}})
        dl.close()

        lines = (tmp_path / "dialog_test.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        entry = json.loads(lines[2])
        assert entry["direction"] == "receipt"
        assert entry["receipt"]["status"] == "completed"

    def test_log_interaction(self, tmp_path: Path):
        """Log interaction should record student callbacks."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="test")
        dl.log_interaction(
            request_id="req_002",
            page_id="page_1",
            element_id="elem_3",
            action="submitted",
            data={"answer": "B", "questionId": "q_01"},
        )
        dl.close()

        lines = (tmp_path / "dialog_test.jsonl").read_text(encoding="utf-8").strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["direction"] == "interaction"
        assert entry["pageId"] == "page_1"
        assert entry["elementId"] == "elem_3"
        assert entry["data"]["answer"] == "B"

    def test_log_system_event(self, tmp_path: Path):
        """Log system event should work."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="test")
        dl.log_system_event("page.rendered", {"pageId": "page_1"})
        dl.close()

        lines = (tmp_path / "dialog_test.jsonl").read_text(encoding="utf-8").strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["direction"] == "system"
        assert entry["event"] == "page.rendered"

    def test_summary_written_on_close(self, tmp_path: Path):
        """Close should write a summary JSON file."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="test_summary")
        dl.log_send("req_001", "help")
        dl.log_recv("req_001", {"status": "completed"})
        summary = dl.close()

        assert summary["dialogId"] == "test_summary"
        assert summary["commandCount"] == 1
        assert summary["errorCount"] == 0

        # Check summary file
        summary_path = tmp_path / "dialog_test_summary.json"
        assert summary_path.exists()
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
        assert loaded["dialogId"] == "test_summary"

    def test_error_counting(self, tmp_path: Path):
        """Error responses should increment error count."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="errors")
        dl.log_send("req_001", "get.data")
        dl.log_recv("req_001", {"status": "error", "code": 404})
        summary = dl.close()

        assert summary["errorCount"] == 1
        assert summary["commandCount"] == 1

    def test_multiple_commands(self, tmp_path: Path):
        """Multiple commands should all be logged."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="multi")
        for i in range(5):
            dl.log_send(f"req_{i:03d}", "usage")
            dl.log_recv(f"req_{i:03d}", {"status": "completed"})
        summary = dl.close()

        assert summary["commandCount"] == 5

        lines = (tmp_path / "dialog_multi.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 10  # 5 send + 5 recv

    def test_double_close_safe(self, tmp_path: Path):
        """Calling close twice should be safe."""
        dl = DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="safe")
        dl.log_send("req_001", "help")
        dl.close()
        dl.close()  # should not raise
        assert True

    def test_context_manager(self, tmp_path: Path):
        """Context manager should work."""
        with DialogLogger(log_dir=str(tmp_path), dialog_dir=str(tmp_path), dialog_id="ctx") as dl:
            dl.log_send("req_001", "whoami")

        lines = (tmp_path / "dialog_ctx.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
