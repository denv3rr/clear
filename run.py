import sys
import subprocess
import importlib.util
import os

from rich.console import Console

console = Console()
console.clear()

# --- 1. Dependency Manager ---
def check_and_install_packages():
    """
    Reads requirements.txt and installs missing packages automatically.
    """
    req_file = "requirements.txt"
    
    print("\n>> Running...")
    print(">> Verifying Required Libraries...")
    if not os.path.exists(req_file):
        print(f"Error: {req_file} not found.")
        sys.exit(1)

    with open(req_file, "r") as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    missing = []
    
    # Simple check: try to import the package name. 
    # Note: Some pip names differ from import names (e.g. python-dotenv -> dotenv).
    # We maintain a map for known discrepancies.
    pkg_map = {
        "python-dotenv": "dotenv",
        "finnhub-python": "finnhub",
        "scikit-learn": "sklearn"
    }

    print(">> Checking System Integrity & Dependencies...")

    for pkg in packages:
        # Handle version specifiers (e.g. pandas>=1.0)
        pkg_name = pkg.split("=")[0].split(">")[0].split("<")[0]
        import_name = pkg_map.get(pkg_name, pkg_name)

        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg)

    if missing:
        print(f">> Installing missing modules: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print(">> Dependencies installed successfully.\n")
        except subprocess.CalledProcessError as e:
            print(">> Error installing packages. Please check your internet connection.")
            sys.exit(1)
    else:
        print(">> All Dependencies Verified.\n\n")

# --- 2. Environment Loader ---
def load_environment():
    """Safely loads .env variables."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass # Should be handled by dependency checker above

# --- 3. Main Application Launcher ---
if __name__ == "__main__":
    # A. Check Libs
    check_and_install_packages()
    
    # B. Load Env
    load_environment()

    # C. Start App (Lazy import so it only happens after checks pass)
    try:
        from interfaces.welcome import StartupScreen
        welcome = StartupScreen()
        welcome.render()
        
        # 2. Launch Main Core
        from core.app import ClearApp
        session = ClearApp()
        session.run()
        
    except KeyboardInterrupt:
        # Windows
        if os.name == 'nt':
            _ = os.system('cls')
        # macOS and Linux
        else:
            _ = os.system('clear')
        print("\n>> Goodbye.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n>> CRITICAL ERROR: {e}")