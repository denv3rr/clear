# Feed Registry

This document describes the feed registry and health signals used across CLI, API, and web UI.

## Sources
- Market data (Finnhub, Yahoo Finance)
- Trackers (OpenSky, flight URLs/files, shipping feeds)
- Intel (Open-Meteo, GDELT)
- News RSS collectors

## Health Status
- `ok`: last fetch successful
- `degraded`: failures observed
- `backoff`: temporary cooldown after repeated failures
- `unknown`: no recent health signal

## Registry Output
- `sources`: array of sources with `id`, `label`, `category`, `configured`, `notes`, and optional `health/status`.
- `summary`: total/configured counts, per-category counts, `health_counts`, and warnings.

## Usage
- API diagnostics includes registry + summary in `feeds`.
- CLI diagnostics displays summary counts and warnings.
- Web System page shows registry counts and issues.
