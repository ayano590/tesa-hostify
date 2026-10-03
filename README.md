Project: tesa-hostify (Hostify webhook -> TESA / TTLock integration)

Summary
-------
This repository implements a webhook consumer and synchronization service that processes Hostify (RMS) webhooks and updates door codes via TTLock and reservation data via TESA APIs. It is a small Python service that:

- Exposes an HTTP webhook endpoint to receive Hostify notifications.
- Validates and processes incoming reservation events.
- Calls the TESA API to read/update shared configuration when needed.
- Calls the TTLock API to create/update keypad (door) codes for rooms.
- Persists reservations locally in an SQLite database (hotel.db).
- Sends monitoring/alerts via a Discord webhook and optionally pings Healthchecks.

Repository layout
-----------------
- [app/main.py](./app/main.py) — FastAPI application and webhook endpoint.
- [app/config.py](./app/config.py) — Loads configuration from environment variables using python-dotenv.
- [app/scheduler.py](./app/scheduler.py) — Scheduler for reservation status updates and database maintenance.
- [app/reservation_service.py](./app/reservation_service.py) — Database management service.
- [app/sync.py](./app/sync.py) — Lock synchronization service.
- [app/tesa_client.py](./app/tesa_client.py) — Wrapper for TESA REST calls.
- [app/ttlock_client.py](./app/ttlock_client.py) — Wrapper for TTLock API interactions.
- [app/database.py](./app/database.py) — Lightweight SQLite access for reservations.
- [app/monitoring.py](./app/monitoring.py) — Sends Discord alerts and pings healthchecks.
- Other modules: [app/models.py](./app/models.py), [app/logging_setup.py](./app/logging_setup.py)

Prerequisites
-------------
- Python 3.10+ (the project uses modern type syntax)
- A virtual environment (recommended)
- Dependencies from `requirements.txt`

Installation
------------
1. Clone the repository (or use your worktree).
2. Create and activate a virtual environment:
   - Windows (PowerShell): `uv venv`; `.venv\Scripts\Activate.ps1`
   - Alternatively, use `python -m venv .venv` and activate the environment.
3. Install dependencies with `uv pip install -r requirements.txt` (or `python -m pip install -r requirements.txt`).

Configuration (important)
-------------------------
This project reads configuration from environment variables (it uses python-dotenv so a .env file is supported for local development). Do NOT commit a .env file with real credentials. The repository's .gitignore already contains an entry for .env.

Required environment variables
- TESA_BASE_URL — Base URL for TESA API (optional; default used when empty).
- TESA_USERNAME — Username for TESA login.
- TESA_PASSWORD — Password for TESA login.

- TTLOCK_BASE_URL — Base URL for TTLock API (optional; default used when empty).
- TTLOCK_CLIENT_ID — TTLock OAuth client id.
- TTLOCK_CLIENT_SECRET — TTLock OAuth client secret.
- TTLOCK_USERNAME — TTLock account username (used for token request).
- TTLOCK_PASSWORD_MD5 — MD5 of TTLock password (per TTLock API expectations).

- TTLOCK_ROOM2_LOCK_ID — Lock id for room 2 (used by update routine).
- TTLOCK_ROOM2_PWD_ID — Keyboard password id for room 2.
- TTLOCK_ROOM6_LOCK_ID — Lock id for room 6.
- TTLOCK_ROOM6_PWD_ID — Keyboard password id for room 6.
- READ_API_TOKEN — (required) shared bearer token for the read-only mobile API; use a random value of at least 32 characters.

- DISCORD_WEBHOOK_URL — (optional) webhook URL used by monitoring to post alerts to Discord.
- HEALTHCHECKS_URL — (optional) endpoint the service pings every five minutes.

# .env example
TESA_BASE_URL=https://tesa.example.com
TESA_USERNAME=your-tesa-user
TESA_PASSWORD=supersecret

TTLOCK_BASE_URL=https://euapi.ttlock.com
TTLOCK_CLIENT_ID=xxxxxxxx
TTLOCK_CLIENT_SECRET=xxxxxxxx
TTLOCK_USERNAME=your-ttlock-user
TTLOCK_PASSWORD_MD5=md5hex

TTLOCK_ROOM2_LOCK_ID=111111
TTLOCK_ROOM2_PWD_ID=222222
TTLOCK_ROOM6_LOCK_ID=333333
TTLOCK_ROOM6_PWD_ID=444444

READ_API_TOKEN=replace-with-a-random-secret-of-at-least-32-characters

DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxxx/xxxxx
HEALTHCHECKS_URL=https://hc.example.com/ping/abcd-1234

At startup, the application validates the TESA and TTLock credentials, configured room 2/6 lock and keyboard-password IDs, the `READ_API_TOKEN`, any explicitly provided API base URLs, and TLS boolean settings. The read token must contain at least 32 characters. If required values are missing or malformed, startup stops with the affected variable names; secret values are not included in the error. `TESA_BASE_URL` and `TTLOCK_BASE_URL` may be omitted to use the client defaults. Set `READ_API_TOKEN` in the backend environment or secret manager; do not commit its generated value.

Generate a strong token locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Put that value in the backend's `READ_API_TOKEN` setting, then share the same value with authorized Android users through a secure channel. The app sends it as a bearer token; it is not tied to a specific sender.

Running the application
-----------------------
The application uses FastAPI and Uvicorn. From the repository root, activate the virtual environment and run `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Expose it to Android clients only through HTTPS; do not use a public HTTP deployment for these credential-bearing responses.

Endpoints
---------
- POST /webhook/hostify — the primary webhook endpoint (see [app/main.py](./app/main.py)). Valid reservation events are queued for processing; unsupported actions return `200` with `status: ignored`, malformed JSON returns `400`, invalid payloads or missing reservation IDs return `422`, and failures while queueing return `500`.
- GET /api/locks — returns current room/provider/door-code values read from TESA and TTLock.
- GET /api/reservations — returns reservation ID, room, check-in/out, lifecycle status, and door code for reservations checking out today or later.

The two GET endpoints require `Authorization: Bearer <READ_API_TOKEN>`. The token is shared by authorized clients rather than tied to a sender identity. Do not put it in the URL; expose these endpoints only over HTTPS and share the token with the Android app through a secure channel.

Responses are JSON objects with `locks` or `reservations` arrays. Each lock entry contains `room_number`, `provider`, and `door_code` (room 2/6 may appear once per provider). `/api/locks` can also include `provider_errors` when a provider or individual room could not be read; codes from available providers are still returned, and the Android app displays a warning for unavailable results. Each reservation contains `reservation_id`, `room_number`, `check_in`, `check_out`, `lifecycle_status`, and `door_code`.

Android app
-----------
The native Android client is in [android-app/](./android-app/). Open that folder in Android Studio, let Gradle sync, then run the `app` configuration on a device or emulator. On first launch, enter the backend's HTTPS base URL (for example, `https://hotel.example.com`) and the shared token configured as `READ_API_TOKEN` on the backend, then tap **Save connection**. Share the token out-of-band only with the intended users; do not include it in screenshots, source control, or support messages. The app encrypts the token with an Android Keystore key and stores the URL in app-private preferences. Its two home-screen buttons fetch and display door codes or upcoming reservations. The app accepts HTTPS URLs only.

Storage and data
----------------
- Local SQLite database: `hotel.db` (in `app/`). The schema is created automatically by [app/database.py](./app/database.py).
- SQLite uses WAL mode and stores reservations plus desired access (`access_state`) and provider read-back (`actual_state`) records.

Operational notes and troubleshooting
-----------------------------------
TLS verification is configurable with `TESA_VERIFY_SSL` and `TTLOCK_VERIFY_SSL`. TESA verification defaults to disabled for compatibility with the current endpoint; TTLock verification defaults to enabled. Enable TESA verification whenever the endpoint has a valid certificate, and do not expose the read API without HTTPS.

Development notes
-----------------
Key source files to inspect while changing behavior: [app/main.py](./app/main.py), [app/sync.py](./app/sync.py), and the client wrappers in [app/tesa_client.py](./app/tesa_client.py) and [app/ttlock_client.py](./app/ttlock_client.py).

Run the test suite with `uv run --with-requirements requirements.txt --with pytest pytest -q` (or install `pytest` in the active virtual environment and run `pytest -q`).

License & contact
-----------------
This project is licensed under the GNU General Public License v3.0 (GPL-3.0-or-later). See [LICENSE](./LICENSE) for the full license text.