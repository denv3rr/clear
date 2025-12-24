import sys
import subprocess
import importlib.util
import os
import platform

from rich.console import Console

console = Console()
console.clear()

# --- 1. Dependency Manager ---
def check_and_install_packages():
    """
    Reads requirements.txt and installs missing packages automatically.
    """
    req_file = "requirements.txt"
    
    print(">> Verifying installs...")
    if not os.path.exists(req_file):
        print(f"Error: {req_file} not found.")
        sys.exit(1)

    with open(req_file, "r") as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    def _parse_version(text: str):
        return tuple(int(part) for part in text.split(".") if part.isdigit())

    def _marker_allows(line: str) -> bool:
        if ";" not in line:
            return True
        marker = line.split(";", 1)[1].strip()
        if not marker.startswith("python_version"):
            return True
        parts = marker.split()
        if len(parts) != 3:
            return True
        _, op, raw = parts
        version = raw.strip("\"' ")
        py_ver = _parse_version(platform.python_version())
        target = _parse_version(version)
        if op == "<":
            return py_ver < target
        if op == "<=":
            return py_ver <= target
        if op == ">":
            return py_ver > target
        if op == ">=":
            return py_ver >= target
        if op == "==":
            return py_ver == target
        return True

    def _strip_marker(line: str) -> str:
        return line.split(";", 1)[0].strip()

    missing = []
    
    # Map for known discrepancies between pip name and import name
    pkg_map = {
        "python-dotenv": "dotenv",
        "finnhub-python": "finnhub",
        "psutil": "psutil" 
    }

    for pkg in packages:
        if not _marker_allows(pkg):
            continue
        pkg_name = _strip_marker(pkg).split("=")[0].split(">")[0].split("<")[0]
        import_name = pkg_map.get(pkg_name, pkg_name)

        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg)

    if missing:
        print(f">> Installing missing items: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print(">> Dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(">> Error installing packages. Please check your internet connection or requirements.txt.")
            sys.exit(1)

# --- 2. Environment Loader ---
def load_environment():
    """Safely loads .env variables."""
    try:
        # Lazy import dotenv
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass 

# --- 3. Main Application Launcher ---
if __name__ == "__main__":
    check_and_install_packages()

    load_environment()

    try:
        from core.app import ClearApp
        
        session = ClearApp()
        session.run()
        
    except KeyboardInterrupt:
        if os.name == 'nt':
            _ = os.system('cls')
        else:
            _ = os.system('clear')
        print("\n>> Goodbye.\n")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n>> CRITICAL ERROR: {e}", style="bold red", markup=False)
        sys.exit(1)
