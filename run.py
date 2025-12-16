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
    
    print(">> Verifying Required Libraries...")
    if not os.path.exists(req_file):
        print(f"Error: {req_file} not found.")
        sys.exit(1)

    with open(req_file, "r") as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    missing = []
    
    # Map for known discrepancies between pip name and import name
    pkg_map = {
        "python-dotenv": "dotenv",
        "finnhub-python": "finnhub",
        "psutil": "psutil" 
    }

    for pkg in packages:
        pkg_name = pkg.split("=")[0].split(">")[0].split("<")[0]
        import_name = pkg_map.get(pkg_name, pkg_name)

        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg)

    if missing:
        print(f">> Installing missing modules: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print(">> Dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(">> Error installing packages. Please check your internet connection or requirements.txt.")
            sys.exit(1)
    else:
        print(">> All Dependencies Verified.")
        

# --- 2. Environment Loader ---
def load_environment():
    """Safely loads .env variables."""
    try:
        # Lazy import dotenv
        from dotenv import load_dotenv
        load_dotenv()
        print(">> Environment variables loaded.")
    except ImportError:
        pass 

# --- 3. Main Application Launcher ---
if __name__ == "__main__":
    
    # A. Check Libs
    check_and_install_packages()
    
    # B. Load Env
    load_environment()

    # C. Start App 
    try:
        from interfaces.welcome import StartupScreen
        from core.app import ClearApp
        
        # Prints system info using SystemHost
        welcome = StartupScreen()
        welcome.render() 
        
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
        console.print(f"\n[red]>> CRITICAL ERROR: {e}[/red]")
        sys.exit(1)