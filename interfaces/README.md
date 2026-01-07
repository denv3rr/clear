# Interfaces

CLI interface layer: menus, layouts, and UI components used across the terminal
experience.

## Files
- `menus.py`, `menu_layout.py`: Menu definitions and layout helpers.
- `components.py`: Reusable CLI UI components.
- `navigator.py`: Navigation helpers (back/main/exit flow handling).
- `settings.py`: Interactive settings UI and config editing.
- `shell.py`: Terminal shell utilities and rendering.
- `gui_tracker.py`: Tracker UI and live feed presentation.
- `welcome.py`: Startup/welcome screen.
- `assistant.py`: CLI assistant UI surface.

## Usage notes
- Keep navigation consistent: `0` Back, `M` Main Menu, `X` Exit.
- CLI renderers should consume view-model data from `modules/` or `web_api/`.
