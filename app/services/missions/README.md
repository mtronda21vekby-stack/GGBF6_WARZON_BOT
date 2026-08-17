# Adaptive Mission Control

`AdaptiveMissionService` converts trusted Player Intelligence into one bounded mission. The service is deterministic, storage-backed and independent from presentation.

Public lifecycle:

```text
snapshot(chat_id)
accept(chat_id, mission_id)
complete(chat_id, mission_id, outcome, metrics, note)
```

Presentation layers must treat mission identifiers as optimistic-concurrency tokens and surface `MissionConflict` as a stale-state refresh, not as a generic server failure.
