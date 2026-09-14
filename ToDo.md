You are working on the GitHub repository `ayano590/tesa-hostify`.

This is a production-oriented PMS → door-lock middleware. Hostify sends webhook payloads for reservations. The application stores reservation data in SQLite, determines reservation lifecycle/status, and synchronizes door PINs with TESA and TTLock. APScheduler periodically evaluates reservations and performs synchronization.

Your task is to **improve the existing system's architecture, correctness, reliability, and maintainability without unnecessarily rewriting the project or introducing excessive infrastructure**.

Do not blindly implement changes. First inspect the complete repository and understand the existing behavior and integrations.

## Primary architectural goal

Change the system conceptually from:

Hostify reservation → active reservation → push PIN to locks

to:

Hostify events → reservation state → desired access state → reconciliation → actual lock state

The middleware must be able to recover from failures, restarts, missed webhooks, reservation changes, cancellations, moves, and expired reservations.

The system should have a clear distinction between:

1. PMS/reservation state
2. Middleware-derived reservation lifecycle state
3. Desired access-control state
4. Actual synchronization state

SQLite should remain the primary persistence mechanism. Do not introduce PostgreSQL, Redis, Kafka, Celery, or microservices unless there is a compelling repository-specific reason.

---

## Phase 1 — Full repository analysis

Before changing code:

- Inspect every source file.
- Inspect README, requirements, configuration, tests, deployment-related files, and database schema.
- Trace the complete flow:
  - Hostify webhook
  - payload parsing
  - SQLite persistence
  - status calculation
  - scheduler
  - desired PIN calculation
  - TESA synchronization
  - TTLock synchronization
  - error handling
  - monitoring
- Identify assumptions about Hostify payload formats.
- Identify assumptions about rooms, TESA PIN slots, and TTLock credentials.
- Identify all failure cases where SQLite state and lock state can diverge.

Do not assume that the current implementation's behavior is correct merely because it already exists.

Produce a concise internal assessment before implementing the changes.

---

# Phase 2 — Fix the reservation/webhook architecture

The webhook endpoint currently treats several event types similarly even though their payload structures may differ.

Explicitly support the relevant Hostify event types independently:

- `new_reservation`
- `update_reservation`
- `move_reservation`

Create appropriate parsing/handling paths for each event.

The API boundary should validate incoming payloads instead of allowing malformed payloads to fail deep inside the service layer.

Use Pydantic models or another clean validation mechanism appropriate for the existing FastAPI architecture.

Do not make assumptions that fields exist in every event type.

Webhook processing must be idempotent.

If Hostify can send the same event more than once, processing it repeatedly must not create inconsistent reservation state or repeatedly perform unnecessary lock changes.

---

# Phase 3 — Introduce explicit reservation lifecycle state

Separate Hostify/PMS status from middleware-derived lifecycle state.

For example, distinguish concepts such as:

- PMS status
- accepted
- active
- completed
- cancelled

Do not overwrite external/PMS status with internally calculated state unless that is explicitly intended.

The state transition logic should be deterministic and testable.

Make timezone handling explicit. Avoid mixing naive local datetimes with timezone-aware values.

The following situations must be correctly represented:

- future reservation
- active reservation
- completed reservation
- cancelled reservation
- reservation moved to another room
- reservation dates/times changed
- reservation status changed
- malformed or incomplete reservation data

---

# Phase 4 — Introduce desired access state

This is the most important architectural change.

The reservation itself should not directly determine what is sent to TESA/TTLock.

Introduce an access-control/domain layer that derives the desired access state from reservations.

Conceptually:

Reservation(s)
    ↓
Access Policy
    ↓
Desired Access State
    ↓
Reconciliation
    ↓
TESA / TTLock

For each room/lock, the application must be able to determine:

- whether access should currently exist
- which credential/PIN should exist
- which provider manages it
- which credential identifier is used
- whether the desired state differs from the last known synchronized state

The design must support removal/revocation of credentials.

A reservation becoming `completed` or `cancelled` must not merely stop being included in the active-reservation list.

It must produce an explicit desired state such as:

room 2 → credential disabled/removed

Likewise, moving a reservation from room 2 to room 5 must result in:

room 2 → credential removed
room 5 → credential assigned

---

# Phase 5 — Reconciliation engine

Implement a proper reconciliation operation.

The application should have a central operation conceptually equivalent to:

    reconcile()

It should:

1. Read relevant reservation state from SQLite.
2. Calculate the desired access state.
3. Determine what needs to change.
4. Synchronize the required changes with TESA and TTLock.
5. Persist the synchronization result.
6. Record failures in a way that allows a later reconciliation to retry them.

Reconciliation must be safe to run repeatedly.

If there is nothing to change, it should perform no unnecessary external updates.

If the application restarts, a reconciliation should be capable of restoring the external systems to the desired state.

The scheduler should primarily be responsible for triggering reconciliation rather than containing the entire business process itself.

Run a reconciliation on application startup before relying exclusively on periodic scheduling.

---

# Phase 6 — Synchronization state

Add persistence for synchronization state where appropriate.

The system must be able to distinguish:

- desired state matches actual/last-known state
- synchronization pending
- synchronization succeeded
- synchronization failed
- actual state is unknown

At minimum, store enough information to answer:

- What credential should exist?
- Which room does it belong to?
- Which provider manages it?
- When was synchronization last attempted?
- When did synchronization last succeed?
- What was the last synchronization error?

Do not make SQLite pretend that an external API operation succeeded when the operation actually failed.

A reservation can remain active while its access synchronization is failed/pending.

This must be represented explicitly.

---

# Phase 7 — TESA integration

Review the current TESA synchronization carefully.

Fix the current logical comparison between the complete TESA PIN configuration and the partial set of desired PIN updates.

The implementation should compare individual relevant PIN slots/credentials.

The synchronizer must support both:

- assigning/updating a PIN
- clearing/removing/disabling a PIN when the reservation no longer requires access

Do not accidentally overwrite unrelated TESA PIN configuration.

The synchronizer should be idempotent.

Handle TESA authentication and API failures explicitly.

Avoid hard-coded TLS behavior such as unconditional `verify=False`.

Make certificate verification configurable if the TESA installation genuinely requires a self-signed/local certificate.

---

# Phase 8 — TTLock integration

Review the TTLock integration with the same desired-state/reconciliation model.

Do not assume that every synchronization operation is an update.

Support the actual lifecycle required by the existing TTLock API:

- create/update credential if necessary
- disable/delete/revoke credential when necessary
- recover from failed operations
- avoid unnecessary updates

Preserve the existing room/lock mappings unless repository analysis shows they are incorrect, but move hard-coded mapping/configuration toward a clear configuration/data structure.

Do not silently treat an unsupported room as room 6 merely because the current implementation's `else` branch happens to do so.

Validate room/lock configuration explicitly.

---

# Phase 9 — Room configuration

Remove scattered hard-coded mappings such as:

room → TESA PIN

and:

room → TTLock

where practical.

Create one clear room/access configuration model.

It should be possible to understand from one place:

- room ID
- TESA PIN/slot
- lock provider
- TTLock lock ID
- TTLock credential ID
- whether the room is managed by TESA, TTLock, or both

Do not duplicate this information across multiple modules.

Environment variables may still be used for secrets and deployment-specific IDs.

---

# Phase 10 — Webhook durability

Do not acknowledge a webhook as successfully processed merely because a FastAPI background task was scheduled.

A process crash immediately after returning HTTP 200 must not silently lose the reservation event.

Design the webhook flow so that important inbound state is persisted before successful acknowledgement, or otherwise make event processing durable.

Consider adding a `webhook_events` table containing appropriate information such as:

- event ID/idempotency key if available
- event type
- reservation ID
- received timestamp
- processing timestamp
- processing status
- error information
- optionally the original payload if appropriate

Avoid storing sensitive data unnecessarily.

The exact implementation should follow the actual Hostify webhook semantics discovered during repository analysis.

---

# Phase 11 — Database design

Keep SQLite.

Improve the schema only where necessary to support:

- reservation state
- access state
- synchronization state
- webhook idempotency/durability

Maintain appropriate indexes and uniqueness constraints.

Explicitly consider concurrent webhook processing and scheduler access.

Transactions should protect multi-step state changes where necessary.

Avoid holding SQLite transactions open while making external HTTP requests.

External API calls should happen outside database transactions, with synchronization state updated appropriately before/after the call.

Do not store old door PINs indefinitely if they are no longer operationally necessary.

Implement a sensible retention policy for sensitive access credentials.

---

# Phase 12 — Scheduler

Keep APScheduler unless there is a concrete reason not to.

The scheduler should trigger deterministic jobs such as:

- reservation/access reconciliation
- maintenance/cleanup
- health/monitoring tasks if needed

Use the existing single-instance assumptions unless repository deployment indicates otherwise.

Make sure overlapping scheduler runs cannot corrupt state.

The system must behave correctly if:

- a scheduler run fails
- the process restarts
- the process is unavailable for several scheduler intervals
- an external API is temporarily unavailable

A restart must not require manual database manipulation.

---

# Phase 13 — Error handling and retries

Review all broad `except Exception` usage.

Use meaningful exception boundaries where appropriate.

Differentiate between:

- invalid webhook
- database failure
- configuration failure
- TESA failure
- TTLock failure
- monitoring failure

Retry transient external failures with bounded exponential backoff.

Do not retry permanent validation/configuration failures indefinitely.

A failure to send a Discord notification must never cause a reservation or lock synchronization operation to fail.

Monitoring is secondary to the actual business operation.

---

# Phase 14 — Security

Perform a security review specifically for a door-lock middleware.

Pay attention to:

- plaintext PIN storage
- log messages
- webhook authentication/signature validation
- credentials in environment variables
- Discord webhook leakage
- HTTP/TLS verification
- SQLite file permissions
- backup/retention of the SQLite database
- sensitive exception messages
- exposing the webhook endpoint publicly

Never log door PINs, API passwords, client secrets, access tokens, or equivalent credentials.

If Hostify supports webhook signatures/secrets, implement verification based on the actual documented mechanism rather than inventing one.

Do not expose internal exception details to the public webhook caller in production.

---

# Phase 15 — Testing

Add or substantially improve automated tests.

Prioritize tests for the domain logic rather than merely testing HTTP endpoints.

At minimum test:

### Reservation lifecycle

- future → accepted
- check-in → active
- checkout → completed
- cancellation
- changed check-in
- changed checkout
- moved reservation

### Access state

- active reservation produces desired PIN
- completed reservation removes desired PIN
- cancelled reservation removes desired PIN
- moved reservation removes old-room credential and assigns new-room credential
- overlapping reservations are handled deterministically

### Reconciliation

- desired == actual → no external update
- desired != actual → update
- external API failure → sync state records failure
- subsequent reconciliation retries
- restart/reconciliation repairs stale external state

### Webhooks

- each supported webhook type parses correctly
- malformed payloads are rejected safely
- duplicate events are idempotent

### Integrations

Mock TESA and TTLock HTTP calls.

Tests must not contact real lock systems.

---

# Phase 16 — Preserve simplicity

Do not turn this small middleware into an enterprise framework.

Do NOT introduce:

- microservices
- message brokers
- Kubernetes
- Redis
- PostgreSQL
- complex dependency injection frameworks
- unnecessary abstractions

unless the existing repository provides concrete evidence that they are required.

The goal is a **small, reliable, recoverable Python service**.

Prefer clear code over architectural cleverness.

---

# Important implementation principle

Do not perform a massive rewrite if the existing implementation can be incrementally improved.

Preserve working integrations where possible.

Refactor around clear boundaries:

    API/Webhook
        ↓
    Reservation Service
        ↓
    Access/Domain Logic
        ↓
    Reconciliation Service
        ↓
    Integration Adapters
        ├── TESA
        └── TTLock

Persistence should be isolated from business logic as much as reasonably possible.

---

# Deliverables

After implementation, provide:

1. A summary of the existing problems discovered.
2. A summary of the architecture after the changes.
3. A list of changed files.
4. Database/schema migration details.
5. Explanation of the reservation → desired access → reconciliation flow.
6. Explanation of failure/retry behavior.
7. Explanation of credential revocation.
8. Explanation of webhook idempotency/durability.
9. Test coverage added.
10. Any remaining limitations or assumptions.

Before finishing, inspect the final code for:

- race conditions
- inconsistent state transitions
- credentials appearing in logs
- accidental PIN overwrites
- stale credentials remaining after checkout/cancellation
- room-move inconsistencies
- failed external synchronization being incorrectly represented as successful
- startup/restart recovery problems
- timezone bugs
- malformed webhook handling

The final result should be production-oriented but remain small and understandable.