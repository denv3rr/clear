import os

from interfaces.gui_tracker import launch_tracker_gui


if __name__ == "__main__":
    refresh = int(os.getenv("CLEAR_GUI_REFRESH", "10"))
    start_paused = os.getenv("CLEAR_GUI_PAUSED", "0") == "1"
    launch_tracker_gui(refresh_seconds=refresh, start_paused=start_paused)
