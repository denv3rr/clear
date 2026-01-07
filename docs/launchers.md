# Launcher Behavior

This document summarizes launcher behavior to keep startup/stop flows reliable and non-interactive.

## Commands
- `python clearctl.py start` starts API + UI in the foreground by default.
- `python clearctl.py stop` stops background services and verifies port release.
- `python clearctl.py web` starts the web stack (API + UI).
- `python clearctl.py cli` launches the CLI.

## Startup Guarantees
- Startup performs API health checks and fails fast if the API cannot come up.
- UI launch waits for API health before opening the UI.
- Startup cleans stale PID files and attempts to clear occupied ports.
- `.env` is loaded for API credentials and feed detection.

## Shutdown Guarantees
- Stop attempts to terminate process trees and verify port release.
- Shutdown handlers keep running on Ctrl+C to prevent orphan processes.

## Diagnostics
- `python clearctl.py status` reports health and running processes.
- `python clearctl.py doctor` validates deps, ports, and health checks.
