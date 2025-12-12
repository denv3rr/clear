import socket
import getpass
import platform
import os
import requests
from datetime import datetime

# Attempt to import psutil, which is needed for hardware info
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    
class SystemHost:
    """
    Retrieves and stores system information for the session context.
    """

    @staticmethod
    def get_info():
        """Returns a dictionary of safe system information, now including hardware info."""
        
        user = getpass.getuser()
        hostname = socket.gethostname()
        
        # Determine OS info based on psutil availability
        if PSUTIL_AVAILABLE:
            os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        else:
            os_info = f"{platform.system()} {platform.release()} (Details N/A)"
            
        try:
            # Dummy connection to get local IP (does not send data)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

        # Hardware Information - ONLY if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                cpu_percent = f"{psutil.cpu_percent()}%"
                
                # Convert bytes to Gigabytes
                mem_info = psutil.virtual_memory()
                total_ram_gb = mem_info.total / (1024.0 ** 3)
                # Calculate Used RAM
                used_ram_gb = (mem_info.total - mem_info.available) / (1024.0 ** 3)
                
                mem_usage = f"{mem_info.percent}% ({used_ram_gb:.2f}G / {total_ram_gb:.2f}G)" # <-- FIX APPLIED
            except Exception:
                # Fallback if psutil is available but fails to get data
                cpu_percent = "Error"
                mem_usage = "Error"
        else:
            # Fallback if psutil is not imported
            cpu_percent = "N/A (psutil missing)"
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
            "os": os_info,
            "ip": local_ip,
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finnhub_status": has_finnhub,
            "cpu_usage": cpu_percent,
            "mem_usage": mem_usage,
            "python_version": python_version
        }