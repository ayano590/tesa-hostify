# Credential and room operations runbook

## Room mapping

The service currently maps reservations to a fixed set of room IDs and provider credentials.

- TESA room-to-pin mapping
  - room 1 -> pin2
  - room 2 -> pin6
  - room 3 -> pin3
  - room 4 -> pin4
  - room 5 -> pin5
  - room 6 -> pin7
- TTLock room support
  - room 2 -> configured lock/password pair from `TTLOCK_ROOM2_LOCK_ID` and `TTLOCK_ROOM2_PWD_ID`
  - room 6 -> configured lock/password pair from `TTLOCK_ROOM6_LOCK_ID` and `TTLOCK_ROOM6_PWD_ID`

## Desired-state logic

The service derives a desired access state from the reservation lifecycle:

- `accepted` and `active` -> access should exist
- `cancelled`, `completed`, and `unknown` -> access should be removed or disabled
- a moved reservation should generate both a revoke record for the old room and a create/update record for the new room
- old-room revoke records remain queued across reconciliation attempts and are cleared only after provider read-back confirms the desired state

## Sync-state meanings

The reservation table tracks:

- `source_status` — PMS-provided status from Hostify
- `lifecycle_status` — internal middleware lifecycle classification
- `desired_access_state` — the latest desired access snapshot
- `sync_state` — whether the latest reconcile phase was `unknown`, `pending`, `succeeded`, or `failed`
- `sync_provider` — which provider owns the last action record
- `sync_last_attempted_at` and `sync_last_success_at` — telemetry for retries and repairs

The `access_state` table stores the target credential state per reservation, room, provider, and credential name.
The `actual_state` table stores provider read-back values. TESA values are read from `commonPins`; TTLock values are read from `listKeyboardPwd` and matched by the configured `keyboardPwdId`. A missing TTLock entry is represented as an empty value after a successful list query.
After a TTLock update or revoke, read-back is queried up to three times with one- and two-second waits between attempts to allow the provider state to catch up. The credential write itself is not repeated by this polling.
The daily maintenance task removes reservations whose checkout was more than 30 days ago together with their corresponding `access_state` and `actual_state` rows, in one database transaction.

Malformed provider read-back responses or a matched TTLock entry without `keyboardPwd` are treated as sync failures. Door-code values are intentionally excluded from application log messages; use the database state and secured provider consoles for troubleshooting rather than logging credential values.

## Discord reporting

When `DISCORD_WEBHOOK_URL` is configured, Discord receives alerts for startup/configuration and scheduled reconciliation failures, provider update/read-back failures (with affected room numbers), database cleanup/checkpoint failures, validated webhook queue failures, and health-check outage/recovery transitions. Delivery failures are logged without the webhook URL or response body.

Invalid requests, unauthorized API reads, unsupported webhook events, and successful reads are not sent to Discord. Alerts omit door codes, guest names, reservation IDs, raw provider responses, and raw exception messages. Keep the Discord channel restricted to operational staff.

## Failure / recovery guidance

If the service restarts or a sync fails:

1. Run reconciliation again through the scheduler or by re-triggering the service startup path.
2. Check `access_state` for the reservation to see the desired credentials.
3. Check `actual_state` for the last verified provider values and compare them with `access_state`.
4. Inspect the reservation `sync_error` or the provider logs for the last failure.
5. Confirm the room mapping and credential IDs are still valid in the environment.

## Common troubleshooting checks

- Confirm `TESA_BASE_URL` and `TTLOCK_BASE_URL` are reachable.
- Confirm credentials and room lock IDs are defined in the environment.
- Confirm TESA TLS settings are set intentionally via `TESA_VERIFY_SSL`.
- Confirm TTLock TLS settings are set intentionally via `TTLOCK_VERIFY_SSL`.
- Confirm the reservation dates are valid and timezone-safe.
- Check for duplicate webhook deliveries if the same reservation appears to be processed repeatedly.

## Android read-only API

- `GET /api/locks` returns current TESA and TTLock room codes; rooms 2 and 6 have entries for both providers.
- `GET /api/reservations` returns reservation ID, room, dates, lifecycle status, and door code for reservations checking out today or later.
- Both endpoints require `Authorization: Bearer <READ_API_TOKEN>`. This is one shared secret, independent of sender identity; generate a random token of at least 32 characters and store it in the backend environment or secret manager.
- Serve the API through HTTPS only. Never put the token in a URL or log it.
- In the Android app, enter the backend HTTPS base URL and the same `READ_API_TOKEN` value, then save the connection. The app stores the token encrypted with Android Keystore; share it with intended users through a secure channel, not in this repository.

## Recommended operational discipline

- Keep all credentials in environment variables or secret management; never commit them.
- Treat room moves as revoke-plus-create transitions rather than a blind overwrite.
- Validate every webhook before background processing enters the domain layer.
- Prefer reconcile-based repair over ad hoc direct updates.
