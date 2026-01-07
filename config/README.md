# Config

Configuration files that drive default behavior for feeds, tax rules, and UI
aliases. These files are read by both the CLI and API.

## Files
- `settings.json`: Local runtime settings (API key flags, feature toggles, etc.).
- `news_aliases.json`: Source and taxonomy aliases used by news/intel parsing.
- `tax_rules.json`: Tax categories and rule mappings used in reporting.
- `flight_operators.example.json`: Example operator metadata for flight feeds.

## Usage notes
- Keep JSON UTF-8 encoded.
- Do not store secrets here; use environment variables instead.
