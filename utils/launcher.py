from __future__ import annotations

import os
import re
import socket
import subprocess
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
    if find_pids_by_port(port):
        return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(port, host=host):
            return True
        time.sleep(0.1)
    return False


def find_pids_by_port(port: int) -> list[int]:
    pids: list[int] = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if not conn.laddr:
                continue
            if conn.laddr.port != port:
                continue
            if conn.pid and conn.pid > 0:
                pids.append(conn.pid)
    except Exception:
        pids = []
    if pids:
        return sorted(set(pids))
    if os.name != "nt":
        return []
    try:
        output = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            errors="ignore",
        )
    except Exception:
        return []
    pattern = re.compile(rf":{port}$")
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        if not (local_addr.endswith(f":{port}") or pattern.search(local_addr)):
            continue
        pid = parts[-1]
        if pid.isdigit():
            pid_value = int(pid)
            if pid_value > 0:
                pids.append(pid_value)
    return sorted(set(pids))


def pid_cmdline(pid: int) -> list[str]:
    try:
        proc = psutil.Process(pid)
        return [part.lower() for part in (proc.cmdline() or [])]
    except Exception:
        return []


def pid_matches(pid: int, tokens: Iterable[str]) -> bool:
    cmdline = pid_cmdline(pid)
    if not cmdline:
        return False
    cmd_text = " ".join(cmdline)
    return all(token.lower() in cmd_text for token in tokens)


def filter_matching_pids(pids: Iterable[int], tokens: Iterable[str]) -> list[int]:
    matched = []
    for pid in pids:
        if pid_matches(pid, tokens):
            matched.append(pid)
    return matched


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


def wait_for_exit(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not process_alive(pid):
            return True
        time.sleep(0.1)
    return not process_alive(pid)


def terminate_pid(pid: int, timeout: float = 5.0) -> bool:
    if pid <= 0:
        return True
    try:
        proc = psutil.Process(pid)
    except Exception:
        return True
    try:
        children = proc.children(recursive=True)
        for child in children:
            child.terminate()
        proc.terminate()
        _, alive = psutil.wait_procs(children + [proc], timeout=timeout)
        if alive:
            for target in alive:
                target.kill()
        return not process_alive(pid)
    except Exception:
        return False


def terminate_pids_by_port(
    port: int, tokens: Optional[Iterable[str]] = None, timeout: float = 8.0
) -> list[int]:
    pids = find_pids_by_port(port)
    if tokens:
        pids = filter_matching_pids(pids, tokens)
    stopped: list[int] = []
    for pid in pids:
        terminate_pid(pid, timeout=timeout)
        wait_for_exit(pid, timeout=timeout)
        if not process_alive(pid):
            stopped.append(pid)
    return stopped


def wait_for_port_release(
    port: int, host: str = "127.0.0.1", timeout: float = 8.0
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_in_use(port, host=host):
            return True
        time.sleep(0.2)
    return not port_in_use(port, host=host)


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
