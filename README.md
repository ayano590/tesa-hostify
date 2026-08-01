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
- Python 3.9+ (the project uses modern stdlib features)
- A virtual environment (recommended)
- Dependencies from requirements.txt: pip install -r requirements.txt

Installation
------------
1. Clone the repository (or use your worktree).
2. Create and activate a virtual environment:
   - Windows (cmd): python -m venv .venv && .\.venv\Scripts\activate
3. Install dependencies:
   - pip install -r requirements.txt

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

- DISCORD_WEBHOOK_URL — (optional) webhook URL used by monitoring to post alerts to Discord.
- HEALTHCHECKS_URL — (optional) healthcheck URL to ping on successful runs.

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

DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxxx/xxxxx
HEALTHCHECKS_URL=https://hc.example.com/ping/abcd-1234

Running the application
-----------------------
The application uses FastAPI (uvicorn). Recommended environment variable for Python UTF-8 behavior:

- Windows (cmd):
  set PYTHONUTF8=1
  set FLASK_ENV=development  (if you use that pattern locally)

To run locally:
- From repository root: set PYTHONUTF8=1
- Activate virtualenv
- uvicorn app.main:app --host 0.0.0.0 --port 8000

(If running via module path, ensure current directory in PYTHONPATH so imports resolve correctly.)

Endpoints
---------
- POST /webhook/hostify — the primary webhook endpoint (see [app/main.py](./app/main.py)). This endpoint expects Hostify-style webhook payloads and enqueues background tasks to process reservations and door code updates.

Storage and data
----------------
- Local SQLite database: hotel.db (file in app/). The database schema is created automatically by [app/database.py](./app/database.py).
- app/database.py is configured to use WAL mode and creates the reservations table if missing.

Operational notes and troubleshooting
-----------------------------------
SSL verification for httpx clients is disabled in the code (verify=False) for the TESA client, since the local server is running on HTTP.

Development notes
-----------------
Key source files to inspect while changing behavior: [app/main.py](./app/main.py), [app/sync.py](./app/sync.py), and the client wrappers in [app/tesa_client.py](./app/tesa_client.py) and [app/ttlock_client.py](./app/ttlock_client.py).

License & contact
-----------------
This project is licensed under the GNU General Public License v3.0 (GPL-3.0-or-later). See [LICENSE](./LICENSE) for the full license text.