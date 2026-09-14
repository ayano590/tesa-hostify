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

- Discord notifications are supported through `DiscordNotifier`.
- Healthchecks can be pinged via `Heartbeat`.
- Daily maintenance clears old reservations and truncates the SQLite WAL file.

## Gaps and risk areas

### 1. Architecture is still event-driven, not reconciliation-driven

The current flow is close to: webhook -> upsert -> active reservation list -> sync. This makes it difficult to explicitly model:

- desired access state
- synchronization state
- failed retries
- credential revocation
- room moves and cancellations as separate desired-state transitions

### 2. Request validation is minimal

The webhook endpoint accepts arbitrary JSON and only checks for a raw `action` value. There is no formal validation of required fields or data types, which means malformed payloads can fail deep in the service layer.

### 3. Lifecycle state is derived, but not fully distinguished from PMS state

Reservation status is recalculated based on dates, but external `status` values and internal lifecycle state are kept in the same field. That makes it harder to test deterministic transitions and to distinguish external PMS changes from middleware-derived transitions.

### 4. TESA sync has a partial-update risk

The current code fetches the complete TESA pin set, merges in a partial map, and posts it back. This is workable for the current case but is not a robust desired-state reconciliation model and can accidentally overwrite unrelated slots if the mapping is not treated as a per-credential diff.

### 5. TTLock and TESA do not have explicit sync-state persistence

The project tracks whether a reservation is active, but not whether a door code was successfully synchronized, is pending, or failed. This makes recovery after restarts or failed vendor calls less deterministic.

### 6. No explicit credential removal flow

When a reservation becomes cancelled, completed, or moves to another room, the current code does not model an explicit `desired state` that can be reconciled to external systems. There is no clear removal or revocation path for stale credentials.

### 7. Security and configuration posture could be stricter

- TESA HTTP client uses `verify=False` unconditionally.
- There is no centralized validation for TLS settings or certificate pinning.
- Secrets remain environment-based, which is good, but stronger configuration validation would reduce operational surprises.

## Current readiness

The service is suitable for a controlled local or staging deployment with a small number of rooms and clear vendor API behavior, but it is not yet a fully robust access-control reconciliation engine. The repo already contains the foundation for a production-grade design, but the remaining architectural work is concentrated around:

- typed webhook models and payload validation
- lifecycle/state separation
- desired access state generation
- explicit reconciliation and sync-state persistence
- credential removal and idempotent recovery
- tests and deterministic status transitions

## Recommended follow-up tasks

1. Add Pydantic request models for each Hostify action.
2. Introduce explicit reservation lifecycle and desired-access state records.
3. Build a central `reconcile()` operation that reads reservations and computes changes.
4. Persist last sync attempts, successes, and errors in SQLite.
5. Handle credential removal when a reservation expires or moves.
6. Add tests for edge cases: reservation move, cancellation, overlaps, and duplicate webhook deliveries.
7. Make certificate verification configurable for TESA clients.
