# v19 security invariants

- Candidate retrieval is read-only.
- Accept and complete require verified Telegram identity.
- Client profile, chat ID and mission evidence are never authoritative.
- Every lifecycle mutation carries the current deterministic mission ID.
- Unknown or stale IDs raise a conflict.
- Only allow-listed finite metrics are stored.
- Notes, evidence and public response fields are bounded.
- Completion is idempotent.
- One player cannot mutate another player's mission.
- Existing replay, rate-limit and resilient-storage controls remain in force.
