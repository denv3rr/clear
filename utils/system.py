import socket
import getpass
import platform
import os
import requests
from datetime import datetime

class SystemHost:
    """
    Retrieves and stores system information for the session context.
    """

    @staticmethod
    def get_info():
        """Returns a dictionary of safe system information."""
        
        user = getpass.getuser()
        hostname = socket.gethostname()
        os_info = f"{platform.system()} {platform.release()}"
        
        try:
            # Dummy connection to get local IP (does not send data)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "127.0.0.1"

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
            "finnhub_status": has_finnhub
        }