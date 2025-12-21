import time
from typing import Iterable, Optional, Dict

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
        band_width: int = 6,
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

        # Optional fixed highlights for key terms.
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
                    text.stylize("bold cyan", idx, idx + len(term))
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

            # Trailing fade (greyscale gradient)
            if trail > 0:
                for t in range(1, trail + 1):
                    pos = (start - t) % len(view)
                    if t == 1:
                        style = "white"
                    elif t == 2:
                        style = "grey70"
                    elif t == 3:
                        style = "grey50"
                    else:
                        style = "grey30"
                    text.stylize(style, pos, pos + 1)
        return text


SCROLL_PRESETS: Dict[str, Dict[str, object]] = {
    "prompt": {
        "speed": 9.0,
        "band_width": 1,
        "trail": 4,
        "highlight_style": "bold bright_white not dim",
        "base_style": "dim",
    },
    "warning": {
        "speed": 8.0,
        "band_width": 1,
        "trail": 4,
        "highlight_style": "bold bright_white not dim",
        "base_style": "dim",
    },
}


def build_scrolling_line(
    text: str,
    preset: str,
    width: Optional[int] = None,
    offset: Optional[int] = None,
    highlights: Optional[Iterable[str]] = None,
) -> Text:
    config = SCROLL_PRESETS.get(preset, SCROLL_PRESETS["prompt"])
    speed = float(config.get("speed", 4.0))
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
