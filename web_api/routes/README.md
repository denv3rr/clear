# Routes

FastAPI route modules grouped by feature domain.

## Modules
- `assistant.py`: Assistant query endpoints and metadata.
- `clients.py`: Client/account CRUD and analytics payloads.
- `health.py`: Health checks.
- `intel.py`: Intel metadata and news endpoints.
- `maintenance.py`: System maintenance actions.
- `reports.py`: Reports and exports.
- `settings.py`: Settings and system info.
- `stream.py`: Streaming endpoints.
- `tools.py`: Tools outputs and diagnostics helpers.
- `trackers.py`: Tracker feeds and status.

## Usage notes
- Add new endpoints here and wire them in `web_api/app.py`.
- Use shared auth helpers from `web_api/auth.py`.
