from typing import Callable, Any

from rich.console import Console


def fit_renderable_to_height(
    console: Console,
    build_renderable: Callable[[int], Any],
    max_items: int,
    min_items: int = 1,
) -> int:
    if max_items <= 0:
        return 0
    low = max(1, int(min_items))
    high = max(low, int(max_items))
    best = low
    while low <= high:
        mid = (low + high) // 2
        renderable = build_renderable(mid)
        lines = console.render_lines(renderable, console.options)
        if len(lines) <= console.height:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return best
