from __future__ import annotations

import os
import shutil

from fastapi import APIRouter, Depends

from utils.system import SystemHost
from web_api.auth import require_api_key

router = APIRouter()


@router.get("/api/tools/diagnostics")
def diagnostics(_auth: None = Depends(require_api_key)):
    info = SystemHost.get_info()
    disk = shutil.disk_usage(os.getcwd())
    return {
        "system": info,
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
        },
    }
