import time
import os
import json
from typing import Iterable, Optional, Dict, Any

from rich.text import Text


class ScrollingText:
    """Builds a static line with a moving highlight band."""

    def __init__(self, text: str, separator: str = "   "):
        self.base = text or ""
        self.separator = separator

    def build(
        self,
        width: int,
        offset: int = 0,
        highlights: Optional[Iterable[str]] = None,
        highlight_style: str = "bold yellow",
        base_style: Optional[str] = None,
        band_width: int = 2,
        trail: int = 4,
    ) -> Text:
        if width <= 0:
            return Text("")
        line = self.base
        if len(line) < width:
            line = line.ljust(width)
        view = line[:width]
        text = Text(view)
        if base_style and view:
            text.stylize(base_style, 0, len(view))

        # Optional fixed highlights for key terms (follows highlight style).
        if highlights:
            for term in highlights:
                if not term:
                    continue
                term = str(term)
                idx = 0
                while True:
                    idx = view.lower().find(term.lower(), idx)
                    if idx == -1:
                        break
                    text.stylize(highlight_style, idx, idx + len(term))
                    idx += len(term)

        # Moving highlight band across the static text (applied last).
        if view:
            band = max(1, min(band_width, len(view)))
            start = offset % len(view)

            # Bright core
            for i in range(band):
                pos = (start + i) % len(view)
                text.stylize(highlight_style, pos, pos + 1)
                text.stylize("not dim", pos, pos + 1)

        # Trailing band (kept within light/bold palette)
        if trail > 0:
            for t in range(1, trail + 1):
                pos = (start - t) % len(view)
                text.stylize("bright_white", pos, pos + 1)

        # Slightly dim center character for the highlight band.
        if band > 0:
            center = (start + (band // 2)) % len(view)
            text.stylize("grey70", center, center + 1)
        return text


DEFAULT_SCROLL_PRESETS: Dict[str, Dict[str, object]] = {
    "prompt": {
        "speed": 8.0,
        "band_width": 3,
        "trail": 0,
        "highlight_style": "bold bright_white",
        "base_style": "dim",
    },
    "warning": {
        "speed": 8.0,
        "band_width": 3,
        "trail": 0,
        "highlight_style": "bold bright_white",
        "base_style": "dim",
    },
}

SETTINGS_PATH = os.path.join(os.getcwd(), "config", "settings.json")
_SCROLL_SETTINGS_CACHE: Dict[str, Any] = {"mtime": None, "data": None}


def _load_scroll_settings() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        mtime = os.path.getmtime(SETTINGS_PATH)
        cached = _SCROLL_SETTINGS_CACHE
        if cached.get("mtime") == mtime and isinstance(cached.get("data"), dict):
            return cached["data"]
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        display = data.get("display", {}) if isinstance(data, dict) else {}
        scroll = display.get("scroll_text", {}) if isinstance(display, dict) else {}
        scroll = scroll if isinstance(scroll, dict) else {}
        _SCROLL_SETTINGS_CACHE["mtime"] = mtime
        _SCROLL_SETTINGS_CACHE["data"] = scroll
        return scroll
    except Exception:
        return {}


def _get_scroll_preset(name: str) -> Dict[str, Any]:
    preset = str(name or "prompt").lower()
    base = DEFAULT_SCROLL_PRESETS.get(preset, DEFAULT_SCROLL_PRESETS["prompt"]).copy()
    settings = _load_scroll_settings()
    override = settings.get(preset, {}) if isinstance(settings, dict) else {}
    if isinstance(override, dict):
        base.update(override)
    base["band_width"] = max(1, int(base.get("band_width", 1)))
    base["trail"] = max(0, int(base.get("trail", 0)))
    base["speed"] = max(0.1, float(base.get("speed", 1.0)))
    return base


def build_scrolling_line(
    text: str,
    preset: str,
    width: Optional[int] = None,
    offset: Optional[int] = None,
    highlights: Optional[Iterable[str]] = None,
) -> Text:
    config = _get_scroll_preset(preset)
    speed = float(config.get("speed", 1.0))
    if offset is None:
        offset = int(time.time() * speed)
    scroller = ScrollingText(text)
    return scroller.build(
        width=width or len(text),
        offset=offset,
        highlights=highlights,
        highlight_style=str(config.get("highlight_style", "bold bright_yellow")),
        base_style=str(config.get("base_style", "dim")),
        band_width=int(config.get("band_width", 6)),
        trail=int(config.get("trail", 4)),
    )
