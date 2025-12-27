from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Iterable, Optional

import psutil

RUNTIME_DIR = Path("data/runtime")
LOG_DIR = Path("data/logs")


def ensure_runtime_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def read_pid(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="ascii").strip())
    except Exception:
        return None


def write_pid(path: Path, pid: int) -> None:
    path.write_text(str(pid), encoding="ascii")


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if not psutil.pid_exists(pid):
        return False
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False


def terminate_pid(pid: int, timeout: float = 5.0) -> bool:
    if pid <= 0:
        return True
    try:
        proc = psutil.Process(pid)
    except Exception:
        return True
    try:
        for child in proc.children(recursive=True):
            child.terminate()
        proc.terminate()
        _, alive = psutil.wait_procs([proc], timeout=timeout)
        if alive:
            for target in alive:
                target.kill()
        return True
    except Exception:
        return False


def tail_lines(path: Path, limit: int = 200) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
        return lines[-limit:]
    except Exception:
        return []


def filter_existing(paths: Iterable[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def safe_sleep(seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(0.05)
