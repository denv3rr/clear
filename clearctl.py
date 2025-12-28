from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from utils.launcher import (
    LOG_DIR,
    RUNTIME_DIR,
    ensure_runtime_dirs,
    filter_existing,
    port_in_use,
    process_alive,
    read_pid,
    safe_sleep,
    tail_lines,
    terminate_pid,
    write_pid,
)

API_PID = RUNTIME_DIR / "api.pid"
WEB_PID = RUNTIME_DIR / "web.pid"
API_LOG = LOG_DIR / "api.log"
WEB_LOG = LOG_DIR / "web.log"

DEFAULT_API_PORT = 8000
DEFAULT_UI_PORT = 5173


def _print_header() -> None:
    print(">> Clear")
    print(">> Seperet LLC | https://seperet.com/")


def _prompt_yes_no(message: str) -> bool:
    reply = input(f"{message} [y/N]: ").strip().lower()
    return reply in ("y", "yes")


def _python_deps_ready(auto_yes: bool) -> bool:
    missing = []
    for pkg in ("fastapi", "uvicorn", "httpx"):
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    if not missing:
        return True
    print(">> Missing Python dependencies:", ", ".join(missing))
    if auto_yes or _prompt_yes_no("Install Python dependencies from requirements.txt?"):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True
    return False


def _candidate_paths() -> list[str]:
    candidates: list[str] = []
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    exts = [".cmd", ".exe", ""]
    for entry in path_entries:
        entry = entry.strip('"')
        if not entry:
            continue
        for ext in exts:
            candidates.append(os.path.join(entry, f"npm{ext}"))
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidates.append(os.path.join(user_profile, "scoop", "shims", "npm.cmd"))
        candidates.append(os.path.join(user_profile, "scoop", "apps", "nodejs-lts", "current", "bin", "npm.cmd"))
    candidates.append(os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs", "npm.cmd"))
    return candidates


def _find_npm() -> str | None:
    direct = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.exe")
    if direct:
        return direct
    for candidate in _candidate_paths():
        if os.path.isfile(candidate):
            return candidate
    return None


def _npm_available() -> str | None:
    npm_path = _find_npm()
    if not npm_path:
        return None
    try:
        subprocess.check_output([npm_path, "--version"], stderr=subprocess.STDOUT)
    except Exception:
        return None
    return npm_path


def _ensure_node_modules(web_dir: Path, npm_path: str, auto_yes: bool) -> bool:
    if (web_dir / "node_modules").is_dir():
        return True
    print(">> Web dependencies not installed (node_modules missing).")
    if auto_yes or _prompt_yes_no("Run npm install in ./web?"):
        try:
            subprocess.check_call([npm_path, "install"], cwd=str(web_dir))
            return True
        except Exception:
            print(">> npm install failed. Fix npm/node setup and retry.")
            return False
    return False


def _spawn_process(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict | None = None,
    detach: bool = True,
    log_path: Path | None = None,
) -> subprocess.Popen:
    kwargs: dict = {}
    if cwd:
        kwargs["cwd"] = str(cwd)
    if env:
        kwargs["env"] = env
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(log_path, "a", encoding="ascii", errors="ignore")
        kwargs["stdout"] = log_handle
        kwargs["stderr"] = subprocess.STDOUT
    if detach:
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _playwright_installed(npm_path: str, web_dir: Path) -> bool:
    try:
        subprocess.check_output(
            [npm_path, "exec", "--", "playwright", "install", "--check"],
            cwd=str(web_dir),
            stderr=subprocess.STDOUT,
        )
        return True
    except Exception:
        return False


def _ensure_playwright(npm_path: str, web_dir: Path, auto_yes: bool) -> bool:
    if _playwright_installed(npm_path, web_dir):
        print(">> Playwright browsers installed.")
        return True
    print(">> Playwright browsers not installed.")
    if auto_yes or _prompt_yes_no("Install Playwright browsers now?"):
        try:
            subprocess.check_call([npm_path, "exec", "--", "playwright", "install"], cwd=str(web_dir))
            if _playwright_installed(npm_path, web_dir):
                print(">> Playwright browsers installed.")
                return True
            print(">> Playwright install completed but browsers not detected.")
            return True
        except Exception:
            print(">> Playwright install failed. Run: npx playwright install")
            return False
    return False


def _health_check(api_port: int) -> bool:
    url = f"http://127.0.0.1:{api_port}/api/health"
    headers = {}
    api_key = os.environ.get("CLEAR_WEB_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    try:
        response = httpx.get(url, headers=headers, timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def _start(args: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    if not _python_deps_ready(args.yes):
        return 1
    if port_in_use(args.api_port):
        print(f">> API port {args.api_port} already in use.")
        return 1
    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "web_api.app:app",
        "--reload",
        "--port",
        str(args.api_port),
    ]
    api_proc = _spawn_process(api_cmd, detach=not args.foreground, log_path=API_LOG)
    write_pid(API_PID, api_proc.pid)

    web_dir = Path("web")
    if args.no_web or not web_dir.exists():
        print(">> API started.")
        return 0

    npm_path = _npm_available()
    if not npm_path:
        print(">> npm not found. Install Node.js (includes npm) and retry.")
        return 1
    if port_in_use(args.ui_port):
        print(f">> UI port {args.ui_port} already in use.")
        return 1
    if not _ensure_node_modules(web_dir, npm_path, args.yes):
        return 1

    ui_env = os.environ.copy()
    ui_env.setdefault("VITE_API_BASE", f"http://127.0.0.1:{args.api_port}")
    ui_cmd = [npm_path, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(args.ui_port)]
    ui_proc = _spawn_process(ui_cmd, cwd=web_dir, env=ui_env, detach=not args.foreground, log_path=WEB_LOG)
    write_pid(WEB_PID, ui_proc.pid)

    print(f">> Web UI: http://127.0.0.1:{args.ui_port}")
    print(f">> API: http://127.0.0.1:{args.api_port}")
    if not args.no_open:
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{args.ui_port}/")
    if args.foreground:
        try:
            while True:
                safe_sleep(0.5)
        except KeyboardInterrupt:
            return _stop(args)
    return 0


def _stop(_: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    stopped = False
    for label, pid_path in (("API", API_PID), ("Web", WEB_PID)):
        pid = read_pid(pid_path)
        if pid and process_alive(pid):
            terminate_pid(pid)
            stopped = True
            print(f">> Stopped {label} (pid {pid}).")
        if pid_path.exists():
            pid_path.unlink(missing_ok=True)
    if not stopped:
        print(">> No running services detected.")
    return 0


def _status(_: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    api_pid = read_pid(API_PID)
    web_pid = read_pid(WEB_PID)
    api_alive = api_pid is not None and process_alive(api_pid)
    web_alive = web_pid is not None and process_alive(web_pid)
    print(f">> API: {'running' if api_alive else 'stopped'}" + (f" (pid {api_pid})" if api_pid else ""))
    print(f">> Web: {'running' if web_alive else 'stopped'}" + (f" (pid {web_pid})" if web_pid else ""))
    if api_alive:
        healthy = _health_check(DEFAULT_API_PORT)
        print(f">> Health: {'ok' if healthy else 'unreachable'}")
    return 0


def _logs(args: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    targets = []
    if args.api or not (args.api or args.web):
        targets.append(API_LOG)
    if args.web or not (args.api or args.web):
        targets.append(WEB_LOG)
    for path in filter_existing(targets):
        print(f"\n>> {path}")
        for line in tail_lines(path, limit=args.lines):
            print(line)
    return 0


def _doctor(args: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    ok = True
    if not _python_deps_ready(args.yes):
        ok = False
    npm_path = _npm_available()
    if not args.no_web:
        if not npm_path:
            print(">> npm missing.")
            ok = False
        else:
            if not _ensure_node_modules(Path("web"), npm_path, args.yes):
                ok = False
            if args.web_tests and not _ensure_playwright(npm_path, Path("web"), args.yes):
                ok = False
    if port_in_use(args.api_port):
        print(f">> API port {args.api_port} in use.")
    if not args.no_web and port_in_use(args.ui_port):
        print(f">> UI port {args.ui_port} in use.")
    if _health_check(args.api_port):
        print(">> API health: ok")
    else:
        print(">> API health: not running (start it with `python clearctl.py start`).")
    return 0 if ok else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear multi-platform launcher.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start API and web UI.")
    start.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    start.add_argument("--ui-port", type=int, default=DEFAULT_UI_PORT)
    start.add_argument("--no-web", action="store_true")
    start.add_argument("--no-open", action="store_true")
    start.add_argument("--foreground", action="store_true")
    start.add_argument("--yes", action="store_true", help="Auto-install deps when missing.")

    stop = sub.add_parser("stop", help="Stop API and web UI.")
    stop.add_argument("--yes", action="store_true")

    status = sub.add_parser("status", help="Show service status.")
    status.add_argument("--yes", action="store_true")

    logs = sub.add_parser("logs", help="Show service logs.")
    logs.add_argument("--api", action="store_true")
    logs.add_argument("--web", action="store_true")
    logs.add_argument("--lines", type=int, default=200)

    doctor = sub.add_parser("doctor", help="Run health and dependency checks.")
    doctor.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    doctor.add_argument("--ui-port", type=int, default=DEFAULT_UI_PORT)
    doctor.add_argument("--no-web", action="store_true")
    doctor.add_argument("--web-tests", action="store_true", help="Also validate Playwright browsers.")
    doctor.add_argument("--yes", action="store_true")

    return parser.parse_args()


def main() -> int:
    _print_header()
    args = _parse_args()
    if args.command == "start":
        return _start(args)
    if args.command == "stop":
        return _stop(args)
    if args.command == "status":
        return _status(args)
    if args.command == "logs":
        return _logs(args)
    if args.command == "doctor":
        return _doctor(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
