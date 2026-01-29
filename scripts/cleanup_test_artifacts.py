from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    ROOT / ".pytest_cache",
    ROOT / ".coverage",
    ROOT / "coverage.xml",
    ROOT / "htmlcov",
    ROOT / "test-results",
    ROOT / "playwright-report",
    ROOT / "artifacts",
    ROOT / "web" / "test-results",
    ROOT / "web" / "playwright-report",
]


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            return


def main() -> None:
    for target in TARGETS:
        remove_path(target)


if __name__ == "__main__":
    main()
