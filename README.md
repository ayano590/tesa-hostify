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
- [app/main.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/main.py) — FastAPI application and webhook endpoint.
- [app/config.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/config.py) — Loads configuration from environment variables using python-dotenv.
- [app/tesa_client.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/tesa_client.py) — Wrapper for TESA REST calls.
- [app/ttlock_client.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/ttlock_client.py) — Wrapper for TTLock API interactions.
- [app/database.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/database.py) — Lightweight SQLite access for reservations.
- [app/monitoring.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/monitoring.py) — Sends Discord alerts and pings healthchecks.
- Other modules: [app/models.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/models.py), scheduler, sync, reservation_service, etc.

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

Example local .env (DO NOT commit the real file):

# .env (example - do not commit)
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
- POST /webhook/hostify — the primary webhook endpoint (see [app/main.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/main.py)). This endpoint expects Hostify-style webhook payloads and enqueues background tasks to process reservations and door code updates.

Storage and data
----------------
- Local SQLite database: hotel.db (file at repository root). The database schema is created automatically by [app/database.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/database.py).
- app/database.py is configured to use WAL mode and creates the reservations table if missing.

Security & Credentials audit (what was checked)
------------------------------------------------
A quick scan was performed across repository files to locate potential hard-coded credentials and sensitive tokens. Findings:

- No hard-coded passwords, client secrets, API keys, tokens, or webhook URLs were found in the Python source files.
- The configuration values are read from environment variables via [app/config.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/config.py) and python-dotenv; this is the correct pattern for avoiding checked-in secrets.
- The existing README previously contained example curl commands that used the literal placeholder value "api-key". These lines were placeholders and not real secrets. They were replaced by this comprehensive README.
- .gitignore contains an entry for .env and for the local database file (app/hotel.db), which prevents accidental commits of local credentials and the DB file.

Actionable recommendations (if any credentials were accidentally committed)
- If a .env or other file containing real secrets was ever committed and pushed to any remote, you must:
  1. Rotate the exposed credentials immediately (invalidate the leaked API keys, client secrets, or passwords).
  2. Remove the secrets from the Git history. Recommended tools:
     - git filter-repo (preferred): https://github.com/newren/git-filter-repo
       Example: git filter-repo --invert-paths --path path/to/file-with-secret --force
     - BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
  3. After rewriting history, force-push the cleaned branches and inform all collaborators to reclone or reset their local clones.

- If you are unsure whether secrets were committed in the past, run a targeted scan (truffleHog, git-secrets, or `git grep` for likely patterns) before rewriting history.

Operational notes and troubleshooting
-----------------------------------
- SSL verification for httpx clients is disabled in the code (verify=False) for the TESA and TTLock clients. This is likely intentional for environments with self-signed certs, but it is a security risk in production. If the upstream endpoints use valid TLS certs, enable verification.
- Logging: see [app/logging_setup.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/logging_setup.py). Ensure logs do not contain secrets — sanitize or redact when necessary.
- Database file: app/hotel.db is ignored by .gitignore, but confirm backups and deployment artifacts also do not include it.

Testing
-------
- No test suite is included in the repository root. For manual testing:
  - Start the server locally and send a sample webhook payload to POST /webhook/hostify.
  - Confirm that the DB is updated and that TTLock/TTESA client calls are made (or stub them out during local testing).

Development notes
-----------------
- Key source files to inspect while changing behavior: [app/main.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/main.py), [app/sync.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/sync.py), and the client wrappers in [app/tesa_client.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/tesa_client.py) and [app/ttlock_client.py](C:/Users/ayano/Documents/dev/tesa-hostify.worktrees/project-analysis-remove-credentials-readme/app/ttlock_client.py).

- When adding new secrets or keys for CI or deployment, use your CI provider's secret storage, or environment variables in deployment manifests, never plaintext in the repo.

How to proceed if you want credentials removed for real (I can help)
-----------------------------------------------------------------
If any secret was actually committed and you want help removing it from the repository history, provide:
- Which file(s) contain the secret (path), and
- Which branch(es) should be cleaned.

I can provide exact commands and help craft the git filter-repo or BFG commands and a safe step-by-step plan to rotate keys and force-push the cleaned history.

License & contact
-----------------
- No license file detected in this repository. Add a LICENSE file if you intend to publish or share this code under a specific license.

- For questions about the repository structure, refer to the files in the app/ directory, or open an issue in your project's issue tracker.


Notes about this audit
---------------------
- This is a static scan of the repository contents in the worktree and is not exhaustive for secrets that may have been present in previous commits on remote branches. If you want a thorough historical scan, run a secrets scanner over the git history (truffleHog, git-secrets, or custom `git log -S` searches) and then follow the remediation steps above.

Thank you — if you'd like, next steps can be:
- Run a historical secrets scan across git history.
- Assist with removing specific leaked files from history and rotating credentials.
- Add a CONTRIBUTING.md or SECURITY.md with guidelines for secret handling.

