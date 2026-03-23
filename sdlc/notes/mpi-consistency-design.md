# MPI Consistency and Scaling — Design Conclusions

## Context

The Master Patient Index (MPI) resolves patient identities across three independent data sources (Source A, B, C) into a single `canonical_patient_id`. This document captures design decisions around consistency, availability, caching, and throughput for the MPI layer.

---

## Why MBI Cannot Be Used as the Canonical Patient ID

The Medicare Beneficiary Identifier (MBI) is how you **find** a patient. The `canonical_patient_id` (UUID) is how you **refer** to a patient everywhere else. They are not interchangeable for three reasons:

### 1. MBI is not always present

MBI is present on Medicare claims and CMS-sourced data, but Source C (EHR) may not include it — clinic systems that predate MBI adoption or don't expose it in exports will send records with only a name, DOB, and internal medical record number. If `canonical_patient_id` = MBI, Source C records have no join key until MBI is resolved. A generated internal UUID lets the patient be registered immediately and the MBI association backfilled later.

### 2. MBI can change

CMS issues MBI corrections and replacements when a card is compromised, an identity error is found, or a patient transitions between programs. If MBI is the primary key, a correction requires updating every downstream record across Reconciliation, Timeline, and LLM summary tables.

A UUID `canonical_patient_id` never changes. The MBI is stored as an attribute on the MPI record. When CMS corrects an MBI, one field in one row is updated — all downstream services are unaffected.

### 3. MBI is PHI

The MBI is Protected Health Information. Embedding it as a foreign key across every service schema, every NATS message, and every log line propagates PHI throughout the system. A generated internal UUID is meaningless outside the MPI — only the MPI maps UUID → MBI. Every other service operates on a non-PHI key, limiting PHI exposure to one service.

---

## Core Insight: Immutability Makes Caching Safe

Once a `canonical_patient_id` is written to the primary, it never changes. This immutability is what makes the entire caching and eventual consistency strategy sound. A cached ID can be trusted indefinitely — cache invalidation is only needed when a merge corrects a split identity.

---

## Read Routing — Full Table

| Query | Target | Reason |
|---|---|---|
| `canonical_patient_id` lookup by source ID | Redis cache → primary fallback | Hot path — called on every inbound event from every source |
| Patient demographics (name, DOB) | Read replica | Low frequency — UI display and name+DOB fallback matching only |
| Patient timeline events | Read replica | Reporting query — not identity-critical |
| Risk tier / LLM summary | Read replica | Reporting query — not identity-critical |
| Identity-critical reads (Reconciliation → MPI) | Primary or cache | Must be consistent — replica lag is not acceptable |
| New patient registration (upsert) | Primary only | ACID required |

Redis cache is scoped exclusively to the MPI identity layer — it caches the result of `(source_system, source_patient_id) → canonical_patient_id`. It does not cache demographics, timeline data, or summaries. Those are served directly from Postgres read replicas.

---

## Read/Write Split

| Path | Target | Consistency | Rationale |
|---|---|---|---|
| New patient registration | Primary (ACID upsert) | Strong | Race condition must be resolved exactly once |
| Existing patient lookup | Redis cache → primary fallback | Cache-consistent | ID is immutable once written; safe to cache |
| UI / aggregate reporting reads | Read replica | Eventual | No identity consistency required |

UI clients read from replicas. Downstream batch processors (Reconciliation Service) resolve `canonical_patient_id` from the cache, falling back to the primary — never replicas — for identity-critical lookups.

---

## Does Writing to the Primary Lock Reads?

No. Postgres uses **MVCC (Multi-Version Concurrency Control)**:

- Readers never block writers
- Writers never block readers
- Each read sees the last committed snapshot with no wait or lock
- The only serialization is write-write on the same row (two concurrent inserts for the same patient), handled by `INSERT ... ON CONFLICT DO NOTHING`

Reconciliation reading `canonical_patient_id` from the primary while MPI writes a new patient row causes no table-level throttling — they operate on different rows.

---

## Where Throttling Actually Occurs

Write throttling on the primary is not caused by concurrent reads. It comes from **write volume** — specifically, WAL throughput and index updates during mass new patient registration.

This is only a real concern during the monthly CMS attribution file seed load. During normal ingestion, most MPI operations resolve to existing rows (cache hits or primary `SELECT`) — not new `INSERT` operations.

---

## Achieving Eventual Consistency

Eventual consistency is achieved via Redis cache, not replica routing.

```
New patient (first arrival):
  → ACID upsert on primary → returns canonical_patient_id
  → Write-through to Redis

Existing patient (all subsequent events):
  → Check Redis → hit → return canonical_patient_id (no DB touch)
  → Cache miss → read from primary → populate Redis → return

UI / reporting:
  → Read replica (no identity requirement)
```

Once a patient's ID is in cache, the primary is never touched again for that patient. The system becomes effectively read-free at the DB level for established patients.

---

## Where Eventual Consistency Lives in the Pipeline

Identity resolution (MPI) must be strongly consistent. Everything downstream is eventually consistent:

- **Timeline Service** — rebuilds on each `reconciled.events` message; a slightly lagged rebuild is acceptable
- **LLM Summary Service** — regenerates asynchronously on `timeline.updated`; a stale summary does not block ingestion
- **Notification Service** — tolerates seconds of lag before alerting

The MPI is the consistency anchor. Everything after it flows eventually.

---

## Evaluated Scaling Strategies

### 1. Redis Cache (adopted)
Optimizes the READ-heavy steady state. Most events are for already-registered patients — cache hits eliminate primary round-trips entirely.

**Required:** cache invalidation on patient merge. Stale entries after a merge route to ghost identities. Use write-through on new registration, explicit eviction on merge.

### 2. Bloom Filter (optional, low priority)
Does not increase cache hit rate. Reduces cache IOPS by skipping lookups for IDs definitely not in cache. Low value on a pre-seeded MPI. Adds complexity for narrow benefit during bootstrap only.

### 3. Eventual Consistency via Read Replicas (partially adopted)
Replicas are safe for UI/reporting. They are **not safe** for identity-critical reads — async replication lag means the replica may not have the MPI write when Reconciliation reads milliseconds later. Identity-critical reads go to the primary (or cache).

### 4. Reconciliation Batch Job Ordering (required)
If split identities occur (two canonical IDs for one patient), a batch reconciliation job must merge them before downstream processing builds corrupted timelines. NATS does not gate this automatically — an explicit mechanism is required:
- Staging topic with an identity-clean gate consumer, or
- Lock flag in Postgres checked before publishing `reconciled.events`, or
- Scheduled blackout window during batch job execution

### 5. Prefetch / Seed from Attribution File (adopted)
CMS sends a monthly beneficiary attribution file for ACO REACH. Pre-loading all assigned patient IDs into MPI before ingestion begins converts most write races into read hits. Highest-leverage single optimization.

**Edge cases to handle:**
- New patients not on the attribution file (mid-month admissions) — the `INSERT ... ON CONFLICT` path handles this but the race condition risk remains for these patients
- Disenrolled patients — historical record preserved; downstream business rules suppress alerts
- MBI corrections — must update the existing `shared_anchor`, not insert a duplicate row

### 6. Hash Ring + Virtual Node Partitioning (future, if needed)
Partition `mpi_patients` by hash of `shared_anchor` (MBI). MBI hash produces near-uniform distribution.

Use `PARTITION BY HASH (shared_anchor)` in Postgres natively before introducing a custom ring. Virtual nodes average arc lengths but do not solve hot keys — a single very active patient still saturates one shard.

### 7. Write-Behind Cache (future, high write spikes)
MPI writes go to Redis first; Redis flushes to Postgres asynchronously in batches. Absorbs write spikes during monthly seed loads or large re-ingestions. Requires Redis persistence (AOF) to prevent identity data loss on Redis failure.

### 8. Probabilistic Identity Graph (future, correctness)
The fallback path (name + DOB exact match) fails silently on nicknames, hyphenated names, and data entry errors. A weighted fuzzy matching layer (Jaro-Winkler on name, exact on DOB) with confidence scoring closes this gap. Auto-merge above threshold, queue for human review in the confidence band, register as new below threshold. Commercial equivalents: Verato, Rhapsody.

---

## MPI Lookup Race Condition — Resolution

The Reconciliation Service and MPI Service both consume the same raw NATS topics simultaneously. Reconciliation may call MPI's HTTP endpoint before MPI has finished its upsert — a narrow race condition.

### MVP: Exponential Backoff Retry

Reconciliation retries the MPI HTTP lookup with exponential backoff:

```
attempt 1 → immediate
attempt 2 → wait 100ms
attempt 3 → wait 200ms
attempt 4 → wait 400ms
attempt 5 → wait 800ms → dead-letter queue on failure
```

Exponential backoff avoids hammering MPI under load and respects rate limits. On a local Docker network the race resolves on attempt 1 or 2 in practice — MPI's upsert completes in microseconds.

### Production: identity.resolved topic

MPI publishes an `identity.resolved` event after its upsert. Reconciliation subscribes to `identity.resolved` instead of calling MPI over HTTP. This eliminates the race class entirely and removes the synchronous HTTP dependency between the two services.

---

## MPI vs Reconciliation Service — Responsibility Boundary

> **MPI merges who the patient is. Reconciliation merges what happened to them.**

These two services are often confused. Their responsibilities are strictly separated.

### MPI Service
- Resolves patient identity across Source A, B, C
- Answers: "Is this the same person I've seen before?"
- Output: `canonical_patient_id` (UUID)
- Does NOT touch clinical or event data

### Reconciliation Service
- Receives raw events after `canonical_patient_id` is resolved
- Merges and versions **events** (what happened, when, from which source)
- Does NOT resolve patient identity — that is already done

### What Reconciliation does with data from A, B, C

| Scenario | What Reconciliation does |
|---|---|
| Same event from multiple sources | Deduplicates — keeps the authoritative source, discards the duplicate |
| Corrected record re-sent by a source | Versions — stores as v2, surfaces latest non-voided version downstream |
| Voided / cancelled record | Tombstones — marks prior version inactive, does not delete |
| Record arriving long after the event date | Late-arrival windowing — reconciles into the correct chronological position |

By the time any event reaches Reconciliation, `canonical_patient_id` is already resolved by MPI. Reconciliation operates purely on events — it never touches identity.

---

## Service Data Ownership — No Cross-Service Writes

Each service owns its own database schema and is the only writer to its own tables. Services share data exclusively through NATS topics — never by writing to another service's tables.

| Service | Writes to |
|---|---|
| MPI | `mpi_patients`, `mpi_source_identities` |
| Reconciliation | its own reconciled events table |
| Timeline | timeline table |
| LLM Summary | risk/summary table |

### Reconciliation → Timeline hand-off

Reconciliation does not update the timeline table. It publishes to `reconciled.events` and stops. Timeline Service is the sole writer to the timeline table.

```
Reconciliation Service
  → writes versioned/deduped event to its own schema
  → publishes to reconciled.events
              ↓
        Timeline Service
          → consumes reconciled.events
          → writes to timeline table
          → publishes to timeline.updated
```

This boundary ensures that a bug or redeployment in Reconciliation cannot corrupt the timeline, and Timeline can be rebuilt independently by replaying `reconciled.events` from NATS.

---

## Decision Summary

| Decision | Adopted for MVP | Deferred |
|---|---|---|
| ACID upsert on primary for new patients | Yes | — |
| Redis write-through cache | Yes | — |
| UI/reporting reads to replicas | Yes | — |
| Identity-critical reads to primary (not replica) | Yes | — |
| Prefetch from CMS attribution file | Yes | — |
| Reconciliation batch job with explicit gate | Yes (gate mechanism TBD) | — |
| Bloom filter | — | Low priority |
| Hash ring partitioning | — | When primary write throughput becomes a ceiling |
| Write-behind cache | — | When seed load write spikes are observed |
| Probabilistic identity graph | — | When name+DOB mis-matches are observed in testing |
