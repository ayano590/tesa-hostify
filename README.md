# Tesa Hostify

Tesa Hostify receives Hostify reservation webhooks, stores reservations in SQLite, and synchronizes active door codes with TESA and TTLock. The repository also includes an Android client for viewing provider codes and active reservations and requesting a Discord CSV report.

## Quick start

Install dependencies from the repository root:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `.env` in the project root and configure credentials there (see [configuration and setup](./docs/project-guide.md#setup-and-configuration)), then run from the repository root:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The repository root is the working directory, so SQLite and logs are stored there.

Do not commit `.env` or share its provider credentials and Discord webhook. Set `READ_API_TOKEN` to a randomly generated value of at least 32 characters before using the Android API.

## Documentation

- [Project guide](./docs/project-guide.md) — architecture, reservation and provider flows, configuration, API, storage, Android app, and troubleshooting.
- [Running on Windows](./docs/windows-running.md) — Task Scheduler setup, working directory, restart behavior, and log rotation.
- [Android app](./android-app) — Android Studio project.

## API overview

| Endpoint | Purpose |
|---|---|
| `POST /webhook/hostify` | Validate and process Hostify reservation events. |
| `GET /api/ttlock-pins` | Read TTLock door codes for rooms 2 and 6. |
| `GET /api/tesa-pins` | Read TESA door pins. |
| `GET /api/reservations` | List active reservations. |
| `POST /api/reservations/report` | Send a CSV of up to 30 upcoming reservations to Discord. |

All `/api/` endpoints require the configured bearer token. See the [project guide](./docs/project-guide.md#http-endpoints) for endpoint behavior and security details.

## License

GNU General Public License v3.0 or later. See [LICENSE](./LICENSE).
