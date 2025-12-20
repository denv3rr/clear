import json
import os
from typing import Any, Dict


class ClearAccessManager:
    DEFAULT_PATH = os.path.join("config", "clear_access.json")
    PRODUCT_URL = "https://seperet.com/shop/p/clear-access"

    def __init__(self, path: str = None):
        self.path = path or self.DEFAULT_PATH
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            return

    def has_access(self) -> bool:
        return bool(self.data.get("code"))

    def set_code(self, code: str) -> None:
        cleaned = str(code or "").strip()
        if not cleaned:
            return
        self.data["code"] = cleaned
        self._save()

    def clear_code(self) -> None:
        if "code" in self.data:
            self.data.pop("code", None)
            self._save()
