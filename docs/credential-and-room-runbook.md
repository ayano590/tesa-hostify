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

## Sync-state meanings

The reservation table tracks:

- `source_status` — PMS-provided status from Hostify
- `lifecycle_status` — internal middleware lifecycle classification
- `desired_access_state` — the latest desired access snapshot
- `sync_state` — whether the latest reconcile phase was `unknown`, `pending`, `succeeded`, or `failed`
- `sync_provider` — which provider owns the last action record
- `sync_last_attempted_at` and `sync_last_success_at` — telemetry for retries and repairs

The `access_state` table stores the target credential state per reservation, room, provider, and credential name.
The `actual_state` table stores the last provider-known state for comparison.

## Failure / recovery guidance

If the service restarts or a sync fails:

1. Run reconciliation again through the scheduler or by re-triggering the service startup path.
2. Check `access_state` for the reservation to see the desired credentials.
3. Check `actual_state` for the provider-known values.
4. Inspect the reservation `sync_error` or the provider logs for the last failure.
5. Confirm the room mapping and credential IDs are still valid in the environment.

## Common troubleshooting checks

- Confirm `TESA_BASE_URL` and `TTLOCK_BASE_URL` are reachable.
- Confirm credentials and room lock IDs are defined in the environment.
- Confirm TESA TLS settings are set intentionally via `TESA_VERIFY_SSL`.
- Confirm TTLock TLS settings are set intentionally via `TTLOCK_VERIFY_SSL`.
- Confirm the reservation dates are valid and timezone-safe.
- Check for duplicate webhook deliveries if the same reservation appears to be processed repeatedly.

## Recommended operational discipline

- Keep all credentials in environment variables or secret management; never commit them.
- Treat room moves as revoke-plus-create transitions rather than a blind overwrite.
- Validate every webhook before background processing enters the domain layer.
- Prefer reconcile-based repair over ad hoc direct updates.
