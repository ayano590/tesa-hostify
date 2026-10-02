# Project structure

## Repository overview

This repository is a small Python service that bridges Hostify reservation events to property access control systems. It receives Hostify webhooks, stores reservation state in SQLite, derives active guest access windows, and pushes door-code updates to TESA and TTLock.

## Top-level layout

- `app/` — runtime Python modules for the service
- `android-app/` — native Android client for the authenticated read-only API
- `README.md` — project overview, setup steps, configuration, and usage
- `ToDo.md` — current engineering checklist and roadmap
- `requirements.txt` — Python runtime dependencies
- `LICENSE` — GPL-3.0-or-later licensing
- `.gitignore` — ignores runtime secrets such as `.env` and database artifacts

## Runtime modules

### `app/main.py`

- Defines the FastAPI application.
- Starts the scheduler on startup with a lifespan handler.
- Exposes `POST /webhook/hostify` for incoming Hostify events.
- Uses background tasks to process reservations without blocking the HTTP response.

### `app/config.py`

- Loads environment variables via `python-dotenv`.
- Centralizes configuration for TESA, TTLock, Discord, and health checks.
- Uses environment-based settings instead of a config file.

### `app/database.py`

- Creates and maintains the SQLite metadata store.
- Uses `hotel.db` plus `PRAGMA journal_mode=WAL` for write-ahead logging.
- Stores reservation records plus `access_state` and `actual_state` tables for desired-state and provider-read state tracking.
- Supports mismatch queries that surface missing, stale, or value-mismatched credentials.

### `app/reservation_service.py`

- Handles reservation payload ingestion.
- Parses Hostify event data into SQLite rows.
- Recomputes reservation lifecycle state (`accepted`, `active`, `completed`, `cancelled`) from the current time and reservation dates.
- Generates provider-specific desired access records for TESA and TTLock.
- Replaces access state and actual state for each reservation, including revoke semantics for room moves.
- Triggers reconciliation through the sync layer when reservations require updates.

### `app/sync.py`

- Implements the provider sync layer used by the reconciliation flow.
- Maps room numbers to TESA pin slots and TTLock room IDs.
- Calls TESA and TTLock update functions for active or revoked credentials.
- Uses retry decorators for transient failures.

### `app/tesa_client.py`

- Thin HTTP wrapper for the TESA REST API.
- Logs in to TESA, reads `commonPins`, and sends an updated pin map back.
- Uses an HTTP client configured with `verify=False` by default.

### `app/ttlock_client.py`

- Thin HTTP wrapper for TTLock OAuth and keyboard password updates.
- Requests an access token and updates the door-code credential for fixed room IDs.
- Uses specific `lockId` and `keyboardPwdId` values from environment configuration.

### `app/monitoring.py`

- Publishes value-redacted Discord alerts and health-check pings.
- Reports operational failures and health-check state transitions without sending door codes, guest names, reservation IDs, raw provider responses, or raw exception messages.

### `app/scheduler.py`

- Starts a background APScheduler instance.
- Runs a periodic status job and a maintenance job.
- Encapsulates lifecycle scheduling but not the full domain logic.

### `app/models.py`

- Defines Pydantic webhook payload models used to validate and normalize Hostify events at the HTTP boundary.

### `app/logging_setup.py`

- Configures app-wide logging to both stdout and `app.log`.

## Data flow

1. Hostify sends an event webhook to `POST /webhook/hostify`.
2. `main.py` validates the action and dispatches background processing.
3. `ReservationService.upsert_reservation()` parses the payload, derives room/date metadata, and upserts the row into SQLite.
4. The scheduler periodically invokes `process_status_changes()`.
5. Reservations are classified as accepted, active, completed, or cancelled based on current time windows.
6. Active reservations are sent to `sync_to_tesa()` and `sync_to_ttlock()`.
7. TESA and TTLock update the actual keycodes or credentials in external systems.
8. Errors are reported through monitoring and logged for follow-up.

## Key assumptions and constraints

- The project is intentionally small and keeps SQLite as the persistence layer.
- Room mappings are static and configured by environment variables.
- Synchronization is now driven by desired-access state plus sync metadata, even though the model is still tuned to the current TESA/TTLock room map.
- Webhook payloads are validated through Pydantic models before processing.
- The current implementation assumes specific Hostify payload shapes for `new_reservation`, `update_reservation`, and `move_reservation` events.

## Typical operational settings

The service expects configuration values such as:

- `TESA_BASE_URL`, `TESA_USERNAME`, `TESA_PASSWORD`
- `TTLOCK_BASE_URL`, `TTLOCK_CLIENT_ID`, `TTLOCK_CLIENT_SECRET`, `TTLOCK_USERNAME`, `TTLOCK_PASSWORD_MD5`
- `TTLOCK_ROOM*_LOCK_ID`, `TTLOCK_ROOM*_PWD_ID`
- `DISCORD_WEBHOOK_URL`, `HEALTHCHECKS_URL`

These variables are defined in `README.md` and loaded from the environment or `.env`.
