import argparse
import importlib.util
import os
import shutil
import subprocess
import httpx
import sys
import time
import webbrowser

from utils.launcher import (
    RUNTIME_DIR,
    ensure_runtime_dirs,
    filter_matching_pids,
    find_pids_by_port,
    process_alive,
    read_pid,
    terminate_pid,
    write_pid,
)

REQUIRED_PYTHON = ("fastapi", "uvicorn")
API_PID = RUNTIME_DIR / "api.pid"
WEB_PID = RUNTIME_DIR / "web.pid"


def _health_check() -> bool:
    try:
        response = httpx.get(
            "http://127.0.0.1:8000/api/health",
            timeout=2.0,
            trust_env=False,
        )
        return response.status_code == 200
    except Exception:
        return False


def _wait_for_api(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _health_check():
            return True
        time.sleep(0.4)
    return False


def _print_header() -> None:
    print(">> • CLEAR Web Launcher\n>> • Copyright © 2025 Seperet LLC • https://seperet.com/\n>>")


def _prompt_yes_no(message: str) -> bool:
    reply = input(f"{message} [y/N]: ").strip().lower()
    return reply in ("y", "yes")


def _python_deps_ready() -> bool:
    missing = [pkg for pkg in REQUIRED_PYTHON if importlib.util.find_spec(pkg) is None]
    if not missing:
        return True
    print(">> Missing Python dependencies:", ", ".join(missing))
    if _prompt_yes_no("Install Python dependencies from requirements.txt?"):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True
    print(">> Aborted. Install dependencies then retry.")
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


def _ensure_node_modules(web_dir: str, npm_path: str) -> bool:
    if os.path.isdir(os.path.join(web_dir, "node_modules")):
        required = ["react-markdown", "remark-gfm"]
        missing = [
            pkg for pkg in required if not os.path.isdir(os.path.join(web_dir, "node_modules", pkg))
        ]
        if not missing:
            return True
        print(">> Web dependencies missing:", ", ".join(missing))
        if _prompt_yes_no("Run npm install in ./web to update dependencies?"):
            try:
                subprocess.check_call([npm_path, "install"], cwd=web_dir)
                return True
            except FileNotFoundError:
                print(">> npm not found. Install Node.js (includes npm) and retry.")
            except subprocess.CalledProcessError:
                print(">> npm install failed. Fix npm/node setup and retry.")
            return False
        print(">> Aborted. Run npm install and retry.")
        return False
    print(">> Web dependencies not installed (node_modules missing).")
    if _prompt_yes_no("Run npm install in ./web?"):
        try:
            subprocess.check_call([npm_path, "install"], cwd=web_dir)
            return True
        except FileNotFoundError:
            print(">> npm not found. Install Node.js (includes npm) and retry.")
        except subprocess.CalledProcessError:
            print(">> npm install failed. Fix npm/node setup and retry.")
        return False
    print(">> Aborted. Run npm install and retry.")
    return False


def _spawn_process(cmd: list[str], cwd: str | None = None, env: dict | None = None, detach: bool = False) -> subprocess.Popen:
    kwargs: dict = {}
    if cwd:
        kwargs["cwd"] = cwd
    if env:
        kwargs["env"] = env
    if detach:
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _terminate_port_processes(
    port: int,
    label: str,
    tokens: list[str],
    auto_yes: bool,
) -> bool:
    pids = find_pids_by_port(port)
    if not pids:
        return True
    safe_pids = filter_matching_pids(pids, tokens)
    remaining = [pid for pid in pids if pid not in safe_pids]
    if safe_pids:
        pid_list = ", ".join(str(pid) for pid in safe_pids)
        print(f">> {label} port {port} in use by Clear process(es) {pid_list}. Terminating.")
        for pid in safe_pids:
            terminate_pid(pid)
    if remaining:
        pid_list = ", ".join(str(pid) for pid in remaining)
        if auto_yes or _prompt_yes_no(
            f"{label} port {port} in use by pid(s) {pid_list}. Terminate them?"
        ):
            for pid in remaining:
                terminate_pid(pid)
            return True
        print(f">> {label} port {port} in use by non-Clear process(es) {pid_list}.")
        return False
    return True


def _cleanup_existing_processes() -> None:
    for label, pid_path in (("API", API_PID), ("Web", WEB_PID)):
        pid = read_pid(pid_path)
        if pid and process_alive(pid):
            terminate_pid(pid)
            print(f">> Stopped {label} (pid {pid}).")
        if pid_path.exists():
            pid_path.unlink(missing_ok=True)


def _launch_processes(
    npm_path: str,
    detach: bool,
    auto_open: bool,
    reload_api: bool,
    auto_yes: bool,
) -> int:
    ensure_runtime_dirs()
    _cleanup_existing_processes()
    web_dir = os.path.join(os.getcwd(), "web")
    if not _terminate_port_processes(
        8000, "API", ["uvicorn", "web_api.app:app"], auto_yes
    ):
        return 1
    if not _terminate_port_processes(5173, "UI", ["vite"], auto_yes):
        return 1
    api_cmd = [sys.executable, "-m", "uvicorn", "web_api.app:app"]
    if reload_api:
        api_cmd.append("--reload")
    api_cmd.extend(["--port", "8000"])
    ui_cmd = [npm_path, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"]

    api_proc = _spawn_process(api_cmd, detach=detach)
    write_pid(API_PID, api_proc.pid)
    try:
        if not _wait_for_api():
            print(">> API failed to start on http://127.0.0.1:8000. Check logs/output.")
            if api_proc.poll() is None:
                terminate_pid(api_proc.pid)
            if API_PID.exists():
                API_PID.unlink(missing_ok=True)
            return 1
    except KeyboardInterrupt:
        print("\n>> Startup interrupted before API was ready.")
        if api_proc.poll() is None:
            terminate_pid(api_proc.pid)
        if API_PID.exists():
            API_PID.unlink(missing_ok=True)
        return 1
    ui_env = os.environ.copy()
    ui_env.setdefault("VITE_API_BASE", "http://127.0.0.1:8000")
    ui_proc = _spawn_process(ui_cmd, cwd=web_dir, env=ui_env, detach=detach)
    write_pid(WEB_PID, ui_proc.pid)
    print(">> Web UI: http://127.0.0.1:5173  |  API: http://127.0.0.1:8000")
    if auto_open:
        webbrowser.open("http://127.0.0.1:5173/")
    if detach:
        print(">> Running in background. Use Task Manager to stop processes.")
        return 0
    print(">> Press CTRL+C to stop.")

    try:
        while True:
            if api_proc.poll() is not None:
                return api_proc.returncode or 0
            if ui_proc.poll() is not None:
                return ui_proc.returncode or 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n>> Shutting down web stack...")
    finally:
        for proc in (api_proc, ui_proc):
            if proc.poll() is None:
                terminate_pid(proc.pid)
        for pid_path in (API_PID, WEB_PID):
            if pid_path.exists():
                pid_path.unlink(missing_ok=True)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the CLEAR web stack.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser.")
    parser.add_argument("--detach", action="store_true", help="Run API/UI in background and exit.")
    parser.add_argument("--reload", action="store_true", help="Reload the API on code changes.")
    parser.add_argument("--yes", action="store_true", help="Auto-terminate processes on required ports.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _print_header()
    if not _python_deps_ready():
        return
    npm_path = _npm_available()
    if not npm_path:
        print(">> npm not found. Install Node.js (includes npm) and retry.")
        print("   - Windows (winget): winget install OpenJS.NodeJS.LTS")
        print("   - Windows (scoop): scoop install nodejs-lts")
        print("   - macOS: brew install node")
        print("   - Linux: https://nodejs.org/en/download/package-manager")
        return
    web_dir = os.path.join(os.getcwd(), "web")
    if not os.path.isdir(web_dir):
        print(">> ./web directory missing. Cannot launch web UI.")
        return
    if not _ensure_node_modules(web_dir, npm_path):
        return
    exit_code = _launch_processes(
        npm_path,
        args.detach,
        not args.no_open,
        args.reload,
        args.yes,
    )
    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
