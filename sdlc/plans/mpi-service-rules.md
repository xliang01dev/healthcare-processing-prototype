# MPI & Reconciliation Rules

Assumptions agreed during planning. These govern how the Reconciliation Service processes
incoming events after MPI has resolved `canonical_patient_id`.

---

## Reconciliation Field-Level Rules

The Reconciliation Service evaluates every inbound event against these rules in order. Late
arrival (R8) is checked first — it is a timing gate that applies before any field-level logic.

| # | Trigger | Action | Downstream impact |
|---|---|---|---|
| R-F1 | Same field, different sources, same value | Suppress lower-authority source (`duplicate_suppressed`) | None — not published to `reconciled.events` |
| R-F2 | Same field, different sources, conflicting values | Apply authority rules → auto-resolve; if high-stakes field exceeds conflict threshold → manual review queue | Winning value published; conflict logged |
| R-F3 | Same field, same source, same value (re-delivery) | Idempotency check on `message-id` → drop | None |
| R-F4 | Same field, same source, changed value (correction) | New version row; prior version → `superseded` | Timeline updates, LLM re-runs |
| R-F5 | New field from any source (not previously seen for this patient) | Append / enrich existing record | Timeline updated with new detail |
| R-F6 | Void from same source that created the record | Tombstone written; prior version(s) → `voided` | Timeline removes event, LLM re-runs |
| R-F7 | Void from a different source than the creator | Treat as conflict → flag for manual review | Held pending review; not applied automatically |
| R-F8 / R5 | Any of the above, outside late-arrival window | Reprocessing path applied before field logic — **out of scope for POC** | Full or partial timeline re-materialization |

**Note:** R-F8 is a timing gate, not a field-level rule. It wraps any of R-F1 through R-F7 when
the event's `event_date` falls outside the configured late-arrival window.

---

## Rules

### R1 — MPI resolves identity; Reconciliation resolves events

MPI answers: *"Is this the same patient?"*
Reconciliation answers: *"Is this a valid, non-duplicate, correctly versioned event for that patient?"*
These are strictly separate concerns. Reconciliation never modifies MPI state.

### R2 — Never delete; always version

Corrections (R-F4) write a new version row and mark the prior version `superseded`. Voids (R-F6)
write an explicit tombstone and mark prior version(s) `voided`. No row is ever deleted from the
Reconciliation event store. Replay from the event log must reproduce the same final state.

### R3 — Cross-source deduplication before publishing

If two sources report the same real-world event (matched on `canonical_patient_id` + `event_date`
+ `event_type` within a fuzzy window), the lower-priority source is written as
`duplicate_suppressed` and not published to `reconciled.events`.

Source priority is determined by **event type + origin**, not by source label (A, B, C) alone.
The authoritative source for a given event type is whichever source was present at the moment
the event actually occurred. The three in-scope event types and their authority rules:

Source assignments for this project:

| Source | Origin type | Authoritative for |
|---|---|---|
| Source A | Labs / LIS | Lab result value |
| Source B | Pharmacy / NCPDP | Medication dispensed |
| Source C | Health System / EHR | Procedure performed; ADT timing |

Authority rules per event type:

| Event Type | Authoritative source | Lower-confidence source | Rationale |
|---|---|---|---|
| Lab result value | Source A (LIS direct feed) | Source C (EHR re-transmitting the result) | LIS has LOINC codes, reference ranges, result status; EHR copy may be incomplete |
| Medication dispensed | Source B (Pharmacy / NCPDP) | Source C (EHR medication list) | Pharmacy claim fires at point of dispensing; EHR list is prescribed/self-reported |
| Procedure performed | Source C (Facility claim / 837I) | — | Source C is the only source for procedures in this model |

**Key principle:** authority is determined by event type + origin, not by source label. If a
future source is added, its authority for a given event type must be explicitly assigned — it
does not inherit from its label.

### R4 — Chronological position is set by `event_date`, not ingestion time

All downstream materialization (timeline, LLM lookback window) uses `event_date` — when the
clinical event occurred — not the timestamp the message was received.

### R5 — Late-arrival window governs reprocessing

Events arriving within N days of their `event_date` are reconciled normally. Events arriving
outside the window would trigger a reprocessing path that re-materializes the affected portion
of the timeline from the event log.

**Out of scope for this POC.** Late-arrival reprocessing is noted but not implemented.
The reprocessing strategy (full re-materialization vs. targeted patch) remains an open design
question for a future phase.

### R6 — Tombstones propagate downstream

A void event must be published to `reconciled.events` so the Timeline Service removes the entry
and the LLM Summary Service re-runs risk assessment without the voided event. Silent deletion at
the Reconciliation layer would leave derived views permanently stale.

---

## Open Questions

- **Source priority order** for cross-source deduplication (R3) — resolved; see R3 table above.
  Specific confidence score values per origin type to be defined during implementation.
- **Late-arrival reprocessing strategy** (R5) — out of scope for POC. Future decision: full
  re-materialization from event log vs. targeted patch per patient.
- **Enrichment policy (R-F5)** — when a lower-authority source carries a field not present in the
  authoritative record, R-F5 says append it. The open question is whether there is a confidence
  threshold below which enrichment is rejected rather than appended.
- **Conflict threshold (R-F2)** — what constitutes a "high-stakes field" that routes to manual
  review vs. auto-resolving by authority? To be defined before Phase 2.
