# Utils

Shared helper utilities used across CLI, launchers, and reporting.

## Files
- `launcher.py`, `gui_launcher.py`, `gui_bootstrap.py`: Process/launcher helpers.
- `input.py`: Input prompts with validation and interrupt handling.
- `layout.py`, `scroll_text.py`: Terminal layout and scrolling helpers.
- `charts.py`: ASCII chart helpers for CLI rendering.
- `report_synth.py`: Report summarization and scoring helpers.
- `system.py`: System metrics and health helpers.
- `world_clocks.py`: Time zone display helpers.

## Usage notes
- Keep helpers pure and reusable; avoid UI-specific assumptions here.
