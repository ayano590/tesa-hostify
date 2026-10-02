# Current implementation status

## Status summary

The repository is in a working proof-of-concept / operational prototype stage. The service can receive Hostify webhook events, persist reservation rows to SQLite, recompute lifecycle status, and call vendor APIs for synchronized door-code updates.

## Implemented

### Webhook intake

- FastAPI receives `POST /webhook/hostify` requests.
- Hostify action types `new_reservation`, `update_reservation`, and `move_reservation` are recognized.
- Reservation payloads are written to SQLite with a basic upsert flow.

### Reservation persistence

- SQLite database with `reservations` table is created automatically.
- Reservation fields include guest name, room number, door code, dates, and external status.
- A scheduler job periodically recalculates whether a reservation is `accepted`, `active`, `completed`, or `cancelled`.

### Access synchronization

- `sync_to_tesa()` builds a room-to-pin map and updates the TESA common pin set.
- `sync_to_ttlock()` requests an access token and updates a room-specific keypad credential.
- Retries are implemented for transient sync failures via `tenacity`.

### Monitoring and housekeeping

- Discord notifications report configuration/startup and scheduled reconciliation failures, provider sync/read-back failures, database maintenance failures, validated webhook queue failures, and health-check outage/recovery transitions.
- Discord reports contain controlled summaries and affected room numbers only; they exclude door codes, guest names, reservation IDs, raw provider responses, raw exception messages, and webhook URLs. Discord delivery failures log only exception types or HTTP status codes.
- Invalid/authentication-rejected requests, unsupported webhooks, successful reads, and ordinary success events are not sent to Discord, avoiding alert noise.
- Healthchecks can be pinged via `Heartbeat`; Discord is notified on outage/recovery transitions rather than on each repeated failure.
- Daily maintenance clears old reservations and truncates the SQLite WAL file.

## Gaps and risk areas

### 1. Reconciliation is operationally useful, but still not fully provider-agnostic

The service now computes desired access from reservations, stores it in `access_state`, and reads provider state into `actual_state`. TESA read-back uses `commonPins`; TTLock read-back queries paginated `listKeyboardPwd` results and matches the configured `keyboardPwdId`. Provider behaviour is still tuned to the current TTLock/TESA room mappings and room-specific credential patterns rather than a generalized credential catalog.

### 2. Request validation is much better, but not exhaustive

The webhook endpoint now validates incoming payloads through Pydantic models, which closes the most obvious malformed-data failure modes. There is still no exhaustive schema validation for every Hostify vendor variant, so edge-case payloads can still fail in boundary conditions.

### 3. Lifecycle state and source-status are still partially coupled

Reservation rows keep both the upstream Hostify `source_status` and the middleware-derived `lifecycle_status`. This is intentional and useful for debugging, but it still means the persistence layer carries both vendor semantics and internal logic together in one table.

### 4. TESA sync is still a full-map merge pattern

`sync_to_tesa()` still reads the current `commonPins` payload, merges the desired room mapping, and writes the merged map back. That is workable for this service, but it is still not a complete provider-agnostic reconciliation engine and should be treated as a room-specific sync layer rather than a universal access-state diff.

### 5. Sync state is implemented, but recovery semantics are still relatively simple

The repo now persists `sync_state`, `desired_access_state`, and provider-read `actual_state` metadata, reports missing/stale/value mismatches, and treats per-room TTLock failures and read-back mismatches as reconciliation failures. Further recovery behavior after vendor outages and broader provider verification still need hardening.

### 6. Revocation flow exists for room moves and stale entries, but it is still narrowly scoped

The service now revokes or clears credentials when a reservation moves rooms and when a current desired access record becomes empty. Old-room revoke records remain persisted until provider sync and read-back succeed, so transient failures can be retried on later reconciliations. This is still a room-driven credential lifecycle rather than a full policy engine for every credential type.

### 7. Security and configuration posture remains an operational concern

- TESA and TTLock HTTP clients still allow TLS verification to be disabled by configuration.
- There is no central certificate pinning or mutual-TLS policy layer.
- Required credentials, room IDs, endpoint URL syntax, and TLS boolean values are checked at startup. Secrets remain environment-based; stronger secret-management and certificate controls are still operational concerns.

## Current readiness

The service is now a working operational prototype with reconciliation-oriented state tracking. It is suitable for a controlled local or staging deployment with a narrow, well-understood room map and clear vendor API behavior. It is substantially stronger than the original event-driven prototype, but it is still not a full multi-tenant or fully generalized property-access reconciliation engine.

The remaining work is concentrated around:

- hardening provider-specific reconciliation behavior
- broadening payload validation for vendor edge cases
- reducing reliance on room-specific assumptions
- improving deterministic recovery after failed sync attempts
- increasing operational safeguards around TLS and configuration

## Recommended follow-up tasks

1. Expand webhook validation for all Hostify action variants and edge-case payloads.
2. Add explicit retry and recovery tests for provider outages and delayed vendor consistency.
3. Review TTLock response status semantics and TESA/TTLock room mapping assumptions against live vendor behaviour.
4. Make TLS verification defaults and certificate controls explicit in operational runbooks.
