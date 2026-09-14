# Todo list

The project has been advanced from a simple reservation-sync prototype into a reconciliation-oriented access-management workflow. The list below reflects the work completed during this pass and the current target baseline.

## Completed

- [x] Added environment-driven TLS configuration for TESA and TTLock.
- [x] Added Pydantic-based validation for Hostify webhook payloads.
- [x] Added idempotency protections using persisted event hashes.
- [x] Added lifecycle normalization for accepted, active, completed, cancelled, and unknown states.
- [x] Added SQLite sync-state tracking to reservation records.
- [x] Added `access_state` persistence for per-room/provider/credential desired state.
- [x] Added `actual_state` persistence for provider-known state tracking.
- [x] Added mismatch detection helpers for desired-vs-actual comparison.
- [x] Added room-move revoke semantics for previous-room access removal.
- [x] Added startup and scheduler reconciliation triggers.
- [x] Added regression tests for lifecycle transitions, duplicates, room moves, and malformed payload handling.
- [x] Added operational runbook documentation for room mappings and credential lifecycle troubleshooting.

## Final status

The repository now has a mature baseline for:

- webhook validation and normalization,
- reservation lifecycle computation,
- desired access-state generation,
- access-state and actual-state persistence,
- reconciliation-oriented sync steps,
- provider-level credential revoke/update semantics,
- test coverage for the most important edge cases.

This is a strong foundation for continued production hardening, but the remaining operational work is now mostly environment-specific and vendor-contract validation rather than foundational architecture changes.

## References

- `README.md` — runtime configuration and setup
- `docs/project-structure.md` — repository map
- `docs/current-implementation-status.md` — findings and architecture assessment
- `docs/credential-and-room-runbook.md` — room mapping and credential operations guide
