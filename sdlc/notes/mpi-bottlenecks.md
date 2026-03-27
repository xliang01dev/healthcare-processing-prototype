# Service Bottlenecks

Potential bottlenecks per service and shared infrastructure. POC impact is assessed against
synthetic single-process workloads. Production impact assumes real patient volumes.

---

## Ingestion Gateway

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| Burst fan-out from Source C | Nightly EHR export delivers N patients simultaneously. All N events hit the bus at once with no backpressure mechanism. | Low — small synthetic dataset | High — N events flood downstream services |
| In-memory bus saturation | Bus has no persistence or flow control. If a downstream subscriber is slow, messages queue in memory with no spillover. | Low — single process, fast consumers | High — process OOM under large bursts |
| `message-id` hash computation | SHA-256 computed per event at ingestion. Trivial per event but multiplied by burst volume. | Negligible | Low — CPU-bound but parallelisable |

---

## Master Patient Index (MPI)

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| Atomic upsert under parallel arrival | All three sources may publish the same patient simultaneously. The `ON CONFLICT` upsert on `shared_identifier` serialises at the DB row level. | Low — asyncio event loop serialises naturally | Medium — high concurrency creates lock contention on the row |
| Name + DOB fallback lookup | When `shared_identifier` is absent (Source C), fallback queries `idx_mpi_name_dob`. Broader scan than a point lookup. | Low — small dataset | Medium — index scan degrades as `mpi_source_identities` grows |
| `mpi_source_identities` growth | One row per (source, patient) pair. Grows with population. Lookup is indexed but table scan risk on cold cache. | Negligible | Low — well-indexed, manageable growth rate |

---

## Reconciliation Service

> **POC topology note:** The POC uses a single Postgres instance with logical table separation per
> service instance. Write contention entries below are not real bottlenecks at this scale. In
> production, each shard would be a separate Postgres instance with its own replicas — write
> pressure, contention, and failover are handled at the infrastructure level, not the application
> level.

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| Cross-source dedup lookup | Resolved by `idx_rec_events_dedup` — a unique partial index on `(canonical_patient_id, event_type, upstream_event_id) WHERE status = 'active'`. When `upstream_event_id` is present, dedup is a point lookup with uniqueness enforced by the index. When `upstream_event_id` is NULL, Postgres allows multiple rows (NULLs are not equal) and fuzzy `event_date` window matching is applied in application logic. | Low | Low — index covers both cases; fuzzy fallback only for sources without stable event IDs |
| Conflict table accumulation | Unresolved rows in `reconciliation_conflicts` are never drained in POC (no downstream workflow). Grows indefinitely. | Low — synthetic conflicts only | Medium — unbounded growth, no archival defined |

---

## Timeline Service

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| Full-view materialized view refresh | `REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline` recomputes all patients every time any patient's data changes. Postgres materialized views cannot be partitioned — so despite the underlying `reconciliation_events` table being hash-partitioned by `canonical_patient_id`, the view is always rebuilt in full. Partition pruning reduces scan cost but does not change refresh granularity. Cost grows linearly with patient population. | Low — small dataset | High — refresh time increases with patient count; frequent triggers compound this |
| Refresh storm during batch burst | A Source C export triggers N `reconciled.events` messages → N refresh calls in quick succession. Refreshes queue up serially; the view may be perpetually refreshing. | Low | High — primary scaling constraint for Timeline Service |
| `llm_pending_assessments` upsert volume | N upserts during batch burst. Single-row PK updates are fast individually but concurrent burst adds up. | Low | Low — PK upserts are lightweight; not a meaningful bottleneck |
| CONCURRENTLY lock during snapshot swap | `CONCURRENTLY` holds a brief lock when swapping the old snapshot for the new one. At high refresh frequency this lock fires repeatedly. | Negligible | Medium — brief but frequent locks under high throughput |

---

## LLM Summary Service

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| LLM inference latency | Even the dictionary demo backend adds simulated delay. Real LLM calls are seconds per patient. Batch worker throughput is bounded by inference concurrency. | Low — dictionary is instant | High — primary throughput ceiling; determines whether 12h window is sufficient |
| Batch queue drain time | After debounce settles, N patients become ready simultaneously. Serial inference drains one patient at a time unless parallelised. | Low | High — N patients × inference latency must fit within 12h cron window |
| DLQ accumulation | Timed-out rows are marked `failed` and enqueued to DLQ. DLQ consumer is not implemented. Failed rows accumulate and are never reassessed. | Low — synthetic timeouts only | High — unprocessed patients grow indefinitely without DLQ consumer |
| Cold cache miss rate | On first population or after restart, `CacheService` has 100% miss rate. All UI reads fall through to Postgres. | Low — small user base | Medium — cold start causes DB read spike |
| Cosine similarity embed call | Only triggered in the borderline dedup case, but requires an embedding API call. If that call is slow or fails, the write pipeline stalls. | Not applicable — hash-only for POC | Low — rare case but adds latency when triggered |
| `llm_recommendations` table growth | Append-only with no archival policy. Grows with every batch run and agent session. | Negligible | Medium — needs archival or partitioning strategy at scale |

---

## Notification Service

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| Webhook endpoint latency | If the external webhook target is slow or unavailable, the service blocks on each `risk.computed` message. No timeout or retry is defined. | Low — console log only in POC | Medium — external dependency introduces latency and failure modes |
| No retry on webhook failure | A failed delivery is silently dropped. High/Critical alerts may be missed with no error surfacing. | Low | High — silent alert loss is a patient safety concern |

---

## Shared Infrastructure

| Bottleneck | Detail | POC impact | Production impact |
|---|---|---|---|
| Single Postgres instance | All services share one instance, schema-isolated. Write contention across schemas during batch bursts. | Low | High — single point of failure and write throughput ceiling |
| In-memory `CacheService` (dict) | Python dict is GIL-protected but not designed for concurrent async writes. Ordering under high concurrency is not guaranteed. | Low — single process | Not applicable — replaced by Redis in production |
| In-memory `MessageBus` | No persistence — messages in flight are lost on process crash. No dead-letter, no replay. | Low — POC accepts this | Not applicable — replaced by NATS/Kafka in production |

---

## Summary — Highest Priority for Production

1. **Timeline Service refresh storm** — full-view refresh at high frequency is the hardest architectural constraint to scale. Mitigation: switch `patient_timeline` to a regular partitioned table (Timeline Service upserts per patient) or use `pg_ivm` for incremental refresh.
2. **LLM batch drain time** — inference latency × patient count must fit within the cron window. Mitigation: parallelise batch worker, tune concurrency.
3. **DLQ consumer** — failed inference rows accumulate silently. Mitigation: implement DLQ consumer before going to production.
4. **Notification retry** — silent alert loss on webhook failure is a patient safety concern. Mitigation: retry with exponential backoff, dead-letter for persistent failures.
5. **Single Postgres instance** — POC simplification only. Production replaces this with separate DB instances per shard, each with read replicas.
