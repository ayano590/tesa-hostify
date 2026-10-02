# Todo list

The project has been advanced from a simple reservation-sync prototype into a reconciliation-oriented access-management workflow. The list below reflects the work completed during this pass and the current target baseline.

## Completed

- [x] Added environment-driven TLS configuration for TESA and TTLock.
- [x] Added Pydantic-based validation for Hostify webhook payloads.
- [x] Added idempotency protections using persisted event hashes.
- [x] Added lifecycle normalization for accepted, active, completed, cancelled, and unknown states.
- [x] Added SQLite sync-state tracking to reservation records.
- [x] Added `access_state` persistence for per-room/provider/credential desired state.
- [x] Added `actual_state` persistence for TESA and TTLock read-back values.
- [x] Added mismatch detection helpers for desired-vs-actual comparison.
- [x] Added room-move revoke semantics for previous-room access removal.
- [x] Added startup and scheduler reconciliation triggers.
- [x] Added regression tests for lifecycle transitions, duplicates, room moves, and malformed payload handling.
- [x] Added provider-backed reconciliation tests for code updates, revokes, mismatch categories, unrelated TESA pins, and partial TTLock failures.
- [x] Added TTLock `listKeyboardPwd` read-back by configured keyboard password ID.
- [x] Added bounded, spaced TTLock read-back polling after updates and revokes without repeating writes.
- [x] Added startup validation for required vendor credentials, room IDs, endpoint URLs, and TLS boolean settings.
- [x] Return appropriate HTTP status codes for malformed webhook JSON, invalid payloads, and enqueue failures.
- [x] Delete expired reservations and their desired/actual credential state in one transaction.
- [x] Add shared-bearer-authenticated GET endpoints for current lock codes and upcoming reservations.
- [x] Add a native Android client with two query buttons and encrypted local token storage.
- [x] Added operational runbook documentation for room mappings and credential lifecycle troubleshooting.

## Final status

- [x] Added value-redacted Discord alerts for operational failures and health-check transitions.
- [x] Documented notification scope, read API token setup/use, and Android client configuration.

The repository now has a tested operational prototype baseline for:

- webhook validation and normalization,
- reservation lifecycle computation,
- desired access-state generation,
- access-state and actual-state persistence,
- reconciliation-oriented sync steps,
- provider-level credential revoke/update semantics,
- test coverage for the most important edge cases.

The stored `actual_state` now records provider read-back values. Production hardening still includes live vendor-contract validation, secure TLS defaults, and deterministic recovery from outages.

## References

- `README.md` — runtime configuration and setup
- `docs/project-structure.md` — repository map
- `docs/current-implementation-status.md` — findings and architecture assessment
- `docs/credential-and-room-runbook.md` — room mapping and credential operations guide
