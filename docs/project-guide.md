# Project guide

Tesa Hostify is a small Python service that receives reservation webhooks from Hostify, stores reservation data in SQLite, and synchronizes active reservation door codes with TESA and TTLock. An Android app provides a protected view of provider codes and active reservations and can send a reservation CSV to Discord.

## How the service works

```text
Hostify
  └─ POST /webhook/hostify
       └─ validate payload, then upsert reservation in SQLite

Every 5 minutes
  └─ update reservation lifecycle statuses
       └─ sync currently active reservations to TESA and TTLock

Android app
  └─ bearer-token-protected API
       ├─ read TTLock codes from TTLock
       ├─ read TESA pins from TESA
       ├─ list active reservations from SQLite
       └─ request a CSV report sent to Discord
```

### Reservation intake and scheduling

The webhook accepts `new_reservation`, `update_reservation`, and `move_reservation` actions. It checks that the body is valid JSON with the required reservation shape and a non-empty `door_code` custom field. Invalid requests generate a Discord notification and return HTTP 200 with an error result in the response body; they are not queued for database upsert. Unsupported actions are also reported and not queued.

Valid events are scheduled as FastAPI background tasks. The service upserts the reservation using its Hostify reservation ID as the unique key. Planned arrival defaults to 14:00 and planned departure defaults to 10:00 when Hostify sends an empty or midnight value.

The scheduler checks reservations every five minutes. It marks them `accepted` before check-in, `active` from check-in through check-out (inclusive), `completed` after check-out, and preserves `cancelled`. Only active reservations are synchronized. The service uses the PC's local timezone for these comparisons, so configure Windows to the intended local timezone.

Once a day, the scheduler removes reservations whose check-out was more than 30 days ago and checkpoints the SQLite write-ahead log.

### Provider synchronization

- **TESA:** Rooms map to shared pins as follows: room 1 → `pin2`, room 2 → `pin6`, room 3 → `pin3`, room 4 → `pin4`, room 5 → `pin5`, room 6 → `pin7`. Before updating, the service reads the current pin set and skips the write if the requested values already match. After a write, it waits 60 seconds and reads back the pins for verification.
- **TTLock:** Only rooms 2 and 6 are configured for TTLock. The service reads each current code first and skips an update if it already matches. Otherwise, it updates the configured keyboard password, waits 60 seconds, then reads it back for verification.

Provider writes are HTTP/API operations and may take time to apply. The one-minute wait is deliberate. Provider synchronization failures and read-back mismatches send Discord error notifications that include affected rooms. The app's read-only provider endpoints return provider errors to the app and write them to the server log; those read failures do not currently send Discord notifications.

## Application layout

| Path | Responsibility |
|---|---|
| `app/main.py` | FastAPI app, Hostify webhook, protected mobile API, scheduler lifecycle |
| `app/reservation_service.py` | Hostify-to-database conversion, lifecycle status calculation, sync dispatch |
| `app/database.py` | SQLite schema and reservation CRUD |
| `app/sync.py` | TESA and TTLock synchronization and provider read functions |
| `app/tesa_client.py` | TESA login, common-pin read, and common-pin update calls |
| `app/ttlock_client.py` | TTLock token, keypad-code read, and keypad-code update calls |
| `app/monitoring.py` | Discord webhook notifications, CSV attachment, and heartbeat |
| `app/scheduler.py` | Five-minute status and daily maintenance jobs |
| `app/logging_setup.py` | Console logging and bounded rotating file logging |
| `android-app/` | Android UI for provider codes, active reservations, and Discord reports |

## Setup and configuration

Install Python and the dependencies from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create an `app/.env` file with the provider credentials and settings below. Do not commit real credentials. The configuration module loads `.env` with `python-dotenv`.

| Variable | Purpose |
|---|---|
| `TESA_BASE_URL` | TESA API base URL; the client has a default when omitted |
| `TESA_USERNAME`, `TESA_PASSWORD` | TESA login |
| `TTLOCK_BASE_URL` | TTLock API base URL; defaults to the EU API |
| `TTLOCK_CLIENT_ID`, `TTLOCK_CLIENT_SECRET` | TTLock OAuth client |
| `TTLOCK_USERNAME`, `TTLOCK_PASSWORD_MD5` | TTLock account credentials expected by its token API |
| `TTLOCK_ROOM2_LOCK_ID`, `TTLOCK_ROOM2_PWD_ID` | TTLock lock and keyboard-password IDs for room 2 |
| `TTLOCK_ROOM6_LOCK_ID`, `TTLOCK_ROOM6_PWD_ID` | TTLock lock and keyboard-password IDs for room 6 |
| `DISCORD_WEBHOOK_URL` | Discord webhook for alerts and requested reservation CSV reports |
| `HEALTHCHECKS_URL` | Optional health-check ping |
| `READ_API_TOKEN` | Shared bearer token for Android API calls; configure at least 32 random characters |

The mobile API refuses requests with HTTP 503 when `READ_API_TOKEN` is missing or shorter than 32 characters, and HTTP 401 for a missing or incorrect bearer token.

## Run the service

Run Uvicorn from the repository root so package imports resolve correctly:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The repository root remains the process working directory, so relative data and log files are created there. For a Windows PC that should keep running without an open terminal, configure Task Scheduler to start the process at boot and restart it on failure. See [Running on Windows](./windows-running.md).

## HTTP endpoints

| Method and path | Authentication | Behavior |
|---|---|---|
| `POST /webhook/hostify` | Hostify webhook | Validate supported reservation event and queue its database upsert. Malformed/unsupported payloads return HTTP 200 with an error/ignored result. |
| `GET /api/ttlock-pins` | Bearer `READ_API_TOKEN` | Read configured TTLock codes for rooms 2 and 6. |
| `GET /api/tesa-pins` | Bearer `READ_API_TOKEN` | Read TESA pins mapped to rooms 1–6. |
| `GET /api/reservations` | Bearer `READ_API_TOKEN` | Return reservations active at request time, including their door codes. |
| `POST /api/reservations/report` | Bearer `READ_API_TOKEN` | Send a CSV of up to 30 upcoming bookings to Discord. |

The Android app stores the server address and API token on the device; the token is encrypted with Android Keystore-backed storage. It does not store TTLock or TESA provider credentials. Provider credentials stay in the server's `.env`.

## Data, logs, and troubleshooting

- SQLite uses a single `reservations` table and write-ahead logging. The database is created at startup if it does not exist. There is no schema migration system; back up `hotel.db` before replacing or changing the database schema.
- Database and log paths are relative to the process working directory. Running from the repository root stores them in `hotel.db` and `app.log` at the root.
- Logs are written both to the console and to `app.log`. File logging rotates at a 2 MiB threshold and keeps four rotated files plus the active file (about 10 MiB maximum total). Console scrollback is controlled separately by the terminal.
- A successful Android request is not evidence of provider success unless its response contains the expected provider rows. Provider read failures are returned in `provider_errors` and displayed by the app.
- Check the server log around the request or scheduler time, verify the server's `.env` and working directory, then check the provider's current code using the app.

The TESA HTTP client currently disables TLS certificate verification; TTLock and the Android-to-server connection use HTTPS verification. Treat access to the server machine and its `.env` file as sensitive.

## Android app

The Android project is under `android-app/` and can be opened in Android Studio. Its main screen provides buttons to show TTLock codes, TESA codes, and active reservations. The settings page stores the server URL and read API token; the report action asks the server to send the CSV to Discord.
