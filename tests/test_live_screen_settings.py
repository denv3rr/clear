from __future__ import annotations

import ast
from pathlib import Path


def _iter_source_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    files = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def test_live_calls_disable_alt_screen():
    offenders = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name != "Live":
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            if "screen" not in keywords:
                offenders.append(f"{path}")
                continue
            value = keywords["screen"]
            if not isinstance(value, ast.Constant) or value.value is not False:
                offenders.append(f"{path}")
    assert not offenders, f"Live() must set screen=False to preserve scrollback: {offenders}"
