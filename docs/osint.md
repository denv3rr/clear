# OSINT + Trackers

## Overview
The OSINT workspace groups trackers, intel, and news into a single surface. The
tracker module provides live aviation and maritime activity, but remains opt-in
and should only surface in reports when it matches account relevance tags.

## Tracker Data Sources
- **OpenSky** (default fallback): used when no custom flight feed is configured.
- **Flight feeds**: use `FLIGHT_DATA_URL` or `FLIGHT_DATA_PATH` to point at JSON
  payloads (list or `{ "data": [] }`).
- **Shipping feeds**: set `SHIPPING_DATA_URL` to enable vessel tracking.

## Relevance Tags
Tracker notes render in reports only when account tags map to relevance rules
and cached tracker data exists. Supported tags:

- `shipping`, `logistics`, `freight`, `cargo`
- `aviation`, `airline`
- `defense`, `military`
- `energy`, `tanker`, `ports`

Add these tags on accounts to opt in to tracker relevance.

## Environment Variables
- `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`: OAuth credentials for OpenSky.
- `OPENSKY_USERNAME` / `OPENSKY_PASSWORD`: legacy OpenSky basic auth.
- `OPENSKY_BBOX`, `OPENSKY_EXTENDED`, `OPENSKY_ICAO24`, `OPENSKY_TIME`: optional
  OpenSky query controls.
- `FLIGHT_DATA_URL`, `FLIGHT_DATA_PATH`: custom flight data sources.
- `SHIPPING_DATA_URL`: custom shipping feed.
- `CLEAR_INCLUDE_COMMERCIAL`: set to `1` to include commercial flights.
- `CLEAR_INCLUDE_PRIVATE`: set to `1` to include private flights.

## Report Integration
The weekly brief only includes aviation/maritime notes when:
1) Account tags match tracker relevance rules, and
2) Cached tracker data exists for those rules.

This keeps OSINT content out of unrelated portfolio reporting.
