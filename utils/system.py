import socket
import getpass
import platform
import os
import shutil
from datetime import datetime
from typing import Dict, Optional

# Attempt to import psutil, which is needed for hardware info
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    
class SystemHost:
    """
    Retrieves and stores system information for the session context,
    now including detailed hardware/performance metrics.
    """

    @staticmethod
    def get_info():
        """Returns a dictionary of safe system information, including hardware info."""
        
        user = getpass.getuser()
        hostname = socket.gethostname()
        
        # Determine OS info based on psutil availability
        os_info_base = f"{platform.system()} {platform.release()}"
        if PSUTIL_AVAILABLE:
            # Added machine architecture for more detail
            os_info_full = f"{os_info_base} ({platform.machine()})"
        else:
            os_info_full = f"{os_info_base}"
            
        try:
            # Dummy connection to get local IP (does not send data)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"
            
        # Initialize hardware info variables
        cpu_usage = "N/A"
        mem_usage = "N/A"
        cpu_cores = "N/A"

        # Hardware Information - ONLY if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                cpu_usage = f"{psutil.cpu_percent(interval=None):.1f}%"
                cpu_cores = psutil.cpu_count()
                
                mem_info = psutil.virtual_memory()
                # Calculate Used/Total RAM in GB
                total_ram_gb = mem_info.total / (1024.0 ** 3)
                used_ram_gb = (mem_info.total - mem_info.available) / (1024.0 ** 3)

                # Format as a single string to match 'RAM USAGE' display
                mem_usage = f"{mem_info.percent:.1f}% ({used_ram_gb:.2f} GB / {total_ram_gb:.2f} GB)" 

            except Exception:
                cpu_usage = "Error"
                mem_usage = "Error"
                cpu_cores = "Error"
        else:
            mem_usage = "N/A (psutil missing)"

        # Python Information
        python_version = platform.python_version()

        # Check API Key Presence
        has_finnhub = False
        if os.getenv("FINNHUB_API_KEY"):
            has_finnhub = True
            
        return {
            "user": user,
            "hostname": hostname,
            "os": os_info_full,
            "ip": local_ip,
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finnhub_status": has_finnhub,
            
            # New Hardware Metrics
            "cpu_usage": cpu_usage,
            "cpu_cores": cpu_cores,
            "mem_usage": mem_usage,
            "python_version": python_version,
            "psutil_available": PSUTIL_AVAILABLE
        }

    @staticmethod
    def get_metrics(path: Optional[str] = None) -> Dict[str, Optional[float]]:
        metrics: Dict[str, Optional[float]] = {
            "cpu_percent": None,
            "mem_percent": None,
            "mem_used_gb": None,
            "mem_total_gb": None,
            "swap_percent": None,
            "disk_used_gb": None,
            "disk_total_gb": None,
            "disk_free_gb": None,
            "disk_percent": None,
        }

        if PSUTIL_AVAILABLE:
            try:
                metrics["cpu_percent"] = round(float(psutil.cpu_percent(interval=None)), 1)
                mem_info = psutil.virtual_memory()
                metrics["mem_percent"] = round(float(mem_info.percent), 1)
                metrics["mem_total_gb"] = round(mem_info.total / (1024.0 ** 3), 2)
                metrics["mem_used_gb"] = round((mem_info.total - mem_info.available) / (1024.0 ** 3), 2)
                swap_info = psutil.swap_memory()
                metrics["swap_percent"] = round(float(swap_info.percent), 1)
            except Exception:
                metrics["cpu_percent"] = None

        disk_path = path or os.getcwd()
        try:
            disk = shutil.disk_usage(disk_path)
            metrics["disk_total_gb"] = round(disk.total / (1024.0 ** 3), 2)
            metrics["disk_used_gb"] = round(disk.used / (1024.0 ** 3), 2)
            metrics["disk_free_gb"] = round(disk.free / (1024.0 ** 3), 2)
            if disk.total:
                metrics["disk_percent"] = round((disk.used / disk.total) * 100.0, 1)
        except Exception:
            metrics["disk_total_gb"] = None

        return metrics
