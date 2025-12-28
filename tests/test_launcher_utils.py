import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from utils import launcher


def test_port_in_use_detects_listener() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert launcher.port_in_use(port) is True
    finally:
        sock.close()


def test_read_write_pid_roundtrip(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid.txt"
    launcher.write_pid(pid_file, 12345)
    assert launcher.read_pid(pid_file) == 12345


def test_tail_lines_returns_last_lines(tmp_path: Path) -> None:
    file_path = tmp_path / "log.txt"
    file_path.write_text("\n".join([f"line-{i}" for i in range(10)]), encoding="ascii")
    assert launcher.tail_lines(file_path, limit=3) == ["line-7", "line-8", "line-9"]


def test_process_alive_current_pid() -> None:
    assert launcher.process_alive(os.getpid()) is True


def test_terminate_pid_stops_process() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert launcher.process_alive(proc.pid) is True
        assert launcher.terminate_pid(proc.pid, timeout=2.0) is True
        time.sleep(0.2)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_pid_matches_tokens(monkeypatch) -> None:
    monkeypatch.setattr(
        launcher,
        "pid_cmdline",
        lambda pid: ["python", "-m", "uvicorn", "web_api.app:app"],
    )
    assert launcher.pid_matches(123, ["uvicorn", "web_api.app:app"]) is True
    assert launcher.pid_matches(123, ["vite"]) is False


def test_filter_matching_pids(monkeypatch) -> None:
    def fake_cmdline(pid: int) -> list[str]:
        if pid == 1:
            return ["python", "-m", "uvicorn", "web_api.app:app"]
        if pid == 2:
            return ["node", "vite"]
        return ["other"]

    monkeypatch.setattr(launcher, "pid_cmdline", fake_cmdline)
    assert launcher.filter_matching_pids([1, 2, 3], ["uvicorn"]) == [1]


def test_wait_for_port_succeeds_after_retry(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
        calls["count"] += 1
        return calls["count"] >= 2

    monkeypatch.setattr(launcher, "port_in_use", fake_port_in_use)
    assert launcher.wait_for_port(8000, timeout=0.2) is True
