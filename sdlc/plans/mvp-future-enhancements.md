# MVP Future Enhancements

This document tracks code and features that are designed but not yet implemented in the MVP. They represent logical extensions to the current architecture.

## Conflict Detection and Resolution

**Status**: Code scaffolding exists, not implemented

**Purpose**: Track and expose data conflicts when events from different sources (Medicare, Hospital, Labs) disagree on the same patient attribute (e.g., different dates of birth, different medication lists).

**Current Code**:
- `ConflictsResponse` model (patient-api/models.py) — Response envelope for conflict data
- `get_patient_conflicts()` endpoints:
  - patient-api/internal_router.py — HTTP endpoint
  - patient_coordinator_service.py — Coordinator method (returns empty stub)
  - patient-event-reconciliation/internal_router.py — Data provider method
- Patient Event Reconciliation Data Provider methods:
  - `get_reconciliation_conflicts()` — TODO: Query conflicts from database
  - `insert_reconciliation_conflict()` — TODO: Store detected conflicts

**Rationale for Deferral**: MVP focuses on reconciliation (merging) rather than conflict exposure. In production, operators need visibility into what the system chose during conflicts for audit and debugging. Can be added post-MVP.

**Implementation Plan**:
1. Define conflict detection rules in `PatientEventReconciliationRules`
2. When reconciliation rule chooses a value, log the rejected alternatives as conflicts
3. Store in `patient_event_reconciliation.reconciliation_conflicts` table
4. Expose via `GET /patient/{id}/conflicts?page=1&page_size=20` endpoint
5. Display in Patient API for operator review

---

## Batch Risk Assessment (Cron Job)

**Status**: Method signatures exist, bodies are TODOs

**Purpose**: Nightly batch job to backfill risk assessments for patients whose timelines haven't been assessed recently (e.g., patients with no recent updates but changing risk profiles).

**Current Code**:
- `_assess_patient(canonical_patient_id)` — patient_summary_service.py — Stub method with 9 TODOs
- `run_batch_for_patient(canonical_patient_id)` — Calls `_assess_patient()`, used by HTTP endpoint
- `run_batch()` — Empty async method, meant as cron entry point

**Rationale for Deferral**: MVP uses event-driven risk assessment (triggered by `timeline.updated`). Batch processing adds complexity and is only needed if:
- Patient timelines stop updating but risk changes
- Need to catch up after service downtime
- Want periodic re-assessment with latest LLM model

Can be added after validating event-driven approach works.

**Implementation Plan**:
1. Create scheduled task (APScheduler or Kubernetes CronJob)
2. Query patients with stale recommendations: `WHERE generated_at < NOW() - INTERVAL '24 hours'`
3. Paginate through candidates
4. For each patient, call `_assess_patient()` (fetch timeline, call LLM, store result)
5. On failure, enqueue to dead-letter queue for manual review

---

## Notification Service (Alert Routing)

**Status**: Service skeleton exists, unimplemented

**Purpose**: Consume `risk.computed` events and route alerts for high/critical risk patients to operators via console, email, webhook, or SMS.

**Current Code**:
- services/notification/main.py — FastAPI app scaffold
- notification_service.py — Handler with 3 TODOs:
  - Parse `risk_tier` from message payload
  - Route alerts based on tier
  - Send to WEBHOOK_URL or console

**Rationale for Deferral**: MVP stops at storing recommendations in the database. Notification is an integration point that depends on:
- Alerting policy (who gets notified, on which tiers)
- Delivery mechanism (email provider, Slack integration, PagerDuty)
- On-call rotation management

Can be added once risk scores are validated by operators.

**Implementation Plan**:
1. Subscribe to `risk.computed` topic (published by patient-summary)
2. Parse payload: `{canonical_patient_id, risk_tier, recommendation_summary}`
3. Route based on tier:
   - `critical` → Immediate page (PagerDuty/phone)
   - `high` → Email to care coordinator
   - `medium/low` → Log to audit trail
4. Webhook delivery: POST to configurable endpoint
5. Include audit trail: who was notified, when, via which channel

---

## RecommendationsResponse Pagination (Partial)

**Status**: Stub model exists, not fully wired

**Purpose**: Paginate historical recommendations for a patient to understand how risk assessment has evolved over time.

**Current Code**:
- `RecommendationsResponse` model — Has stub: bool = True
- `get_patient_recommendations()` endpoint — Calls coordinator method
- Coordinator calls `data_provider.fetch_recommendations(page, page_size)`

**Rationale for Deferral**: MVP prioritizes latest recommendation (O(1) lookup). Historical recommendations are valuable for trend analysis but not critical for initial MVP.

**Status**: Partially working — database query exists, just needs response model update.

**Implementation Plan**:
1. Update `RecommendationsResponse` to include:
   - `recommendations: list[RecommendationResponse]`
   - `page: int`, `page_size: int`, `total_count: int`
2. Wire endpoint to return actual paginated data
3. Add UI for operators to review recommendation history

---

## Explicit Conflict Type Tracking

**Status**: Not started

**Purpose**: Beyond storing conflicts, categorize them by type (demographic mismatch, clinical mismatch, coverage mismatch) and severity (ignored, logged, escalated).

**Examples**:
- Date of birth differs by 1 year (likely typo vs. data quality issue)
- Medication list differs (lab result vs. actual prescription)
- Gender mismatch (data quality issue)

**Rationale for Deferral**: Requires conflict classification rules. Can be added once operators understand what conflicts occur in practice.

---

## Dead-Letter Queue for Failures

**Status**: Referenced in code, not implemented

**Purpose**: When batch assessment fails for a patient (LLM timeout, database error), enqueue to DLQ for manual review instead of silently dropping.

**Current Code**:
- patient_summary_service.py:run_batch() mentions DLQ in TODO comment
- No DLQ service exists

**Rationale for Deferral**: Event-driven path (handle_timeline_updated) has error handling. Batch path (run_batch) is not yet implemented. DLQ is needed once batch processing is added.

**Implementation Plan**:
1. Create `dead-letter-queue` NATS subject
2. On failure in `run_batch()`, publish with original context (patient ID, error reason)
3. Create DLQ consumer to alert operators
4. Manual re-run endpoint to retry from DLQ

---

# Production-Grade Requirements

The following rules, services, and features are essential for a production healthcare system but deferred from the MVP.

## Reconciliation Rules (from mpi-service-rules.md)

### R-F4: Event Versioning & Corrections
**Current state**: MVP writes immutable snapshots. No versioning or correction handling.

**Production requirement**:
- Each event gets a version number (`version` field in reconciliation_events)
- When a source sends a correction (same event_id, incremented version), mark the prior version `superseded`
- Store both versions in event log for audit trail
- When an event is superseded, automatically re-materialize the affected portion of the timeline
- Trigger LLM re-assessment for the patient

**Data model changes**:
- Add `version`, `upstream_event_id`, `status` (active | superseded | voided) columns to reconciliation_events
- Partition timeline_events by (canonical_patient_id, created_at) for efficient targeted refresh

### R-F6 & R-F7: Void/Tombstone Operations
**Current state**: MVP ignores void events (no-op).

**Production requirement**:
- Support explicit voids: source marks an event as "this never happened"
- Write explicit tombstone rows (status = 'voided') in event log for audit
- Distinguish voids by source:
  - **R-F6**: Void from source that created the event → auto-apply (trusted to know their own data)
  - **R-F7**: Void from different source → flag for manual review (cross-source conflict)
- Re-materialize timeline when void is applied

**Data model changes**:
- Event log supports `void_reason`, `voided_by_source_system_id` fields

### R-F1 & R-F2: Cross-Source Deduplication & Conflict Resolution
**Current state**: MVP accumulates all events; no dedup or conflict detection.

**Production requirement**:
- **R-F1 (Duplicate suppression)**: When two sources report the same clinical event (same event_type, event_date within fuzzy window), suppress the lower-authority source as `duplicate_suppressed`
  - Requires authority matrix per event type (e.g., "Lab results are authoritative from Labs source, less so from Hospital EHR re-transmissions")
- **R-F2 (Conflict flagging)**: When sources disagree on facts (e.g., different DOB, conflicting medication lists), apply authority rules to auto-resolve, or escalate high-stakes conflicts to manual review queue
  - Define high-stakes fields: DOB, gender, primary diagnosis, allergies
  - Store conflict with both values + which source won + confidence score

**Data model changes**:
- reconciliation_conflicts table populated with detailed conflict information
- Add `authority_source_system_id`, `losing_source_system_id`, `winning_value`, `losing_value`, `confidence_score` fields
- Store conflict metadata: timestamp, conflict type, whether resolved manually or auto-resolved

### R-F8: Late-Arrival Reprocessing
**Current state**: MVP assumes all events arrive in chronological order within debounce window. No reprocessing for late events.

**Production requirement**:
- Define late-arrival window (e.g., events must arrive within 30 days of event_date)
- Events outside window trigger reprocessing path:
  - Option A (Full): Re-materialize entire patient timeline from event log
  - Option B (Targeted): Re-materialize only the affected time range
- Reprocessing must trigger LLM re-assessment (risk may change if clinical timeline changes)

**Implementation challenge**: Targeted refresh requires per-patient transaction management; full refresh is simpler but more expensive.

### Authority Rules Per Event Type
**Current state**: MVP uses single source priority (Medicare > Hospital > Labs) for all fields.

**Production requirement**:
- Define authority matrix: which source is definitive for each event type?
  - Lab results: authoritative from Labs source, less so from Hospital copy
  - Medications: authoritative from Pharmacy claims, less so from EHR list
  - Procedures: authoritative from Hospital claims
  - Demographics: shared across sources, Medicare highest priority

**Data model changes**:
- Authority mapping table: `event_type × field_name → authoritative_source_system_id`
- Conflicts only flagged when authoritative source disagrees; non-authoritative source disagreement is logged but not escalated

---

## Data Quality & Compliance

### Confidence Scoring & Deduplication
**Current state**: Content hash only (SHA256). No semantic deduplication or confidence metrics.

**Production requirement**:
- Compute confidence score for merged fields based on:
  - Agreement across sources (all 3 sources agree → high confidence)
  - Authority of source (Medicare enrollment is high-confidence for coverage)
  - Staleness of data (recent data > old data)
- Semantic deduplication: cosine similarity on recommendation text (not just hash match)
- Store confidence scores in recommendations table

### Audit Trail & Compliance
**Current state**: Minimal logging. No audit trail for operator decisions.

**Production requirement**:
- Every reconciliation decision logged: which source won, which lost, why
- Manual conflict resolutions tracked: which operator resolved it, when, reasoning
- Data provenance: every field in ReconciledEvent tagged with its source(s) and timestamp
- Immutable audit log for regulatory review (HIPAA, state healthcare regulations)

**New tables**:
- `reconciliation_audit_log`: (patient_id, field, old_value, new_value, source, timestamp, resolved_by)
- `conflict_resolution_log`: (conflict_id, resolved_by_operator, resolution, reasoning, timestamp)

### Data Quality Metrics
**Current state**: No metrics on conflict rates, data freshness, or source reliability.

**Production requirement**:
- Track metrics per source:
  - Conflict rate (how often does this source disagree with others?)
  - Data freshness (how old is this source's data relative to event_date?)
  - Completeness (what % of fields are populated?)
- Alert operators to degradation (e.g., "Labs stopped sending test results")

---

## Operational Services

### Conflict Resolution UI & Workflow
**Current state**: Scaffolding only; no operator UI for reviewing conflicts.

**Production requirement**:
- Web dashboard showing:
  - High-priority conflicts (high-stakes fields, unclear authority)
  - Conflict history (resolved vs. pending)
  - Source reliability scores
- Manual resolution workflow:
  - Operator views both values + source metadata
  - Operator selects winning value + records reasoning
  - Resolution applied retroactively (re-materialize affected timeline)
  - Audit log records operator decision

### DLQ Consumer & Failure Handling
**Current state**: Mentioned in code but not implemented.

**Production requirement**:
- When LLM assessment fails (timeout, OOM), enqueue to DLQ with context
- DLQ consumer:
  - Alerts on-call team (Slack, PagerDuty)
  - Stores failed assessment for manual review
  - Provides retry button for operators
- Separate DLQ for different failure modes (LLM errors vs. database errors)

### Metrics & Monitoring
**Current state**: Basic logging only.

**Production requirement**:
- Performance metrics:
  - Reconciliation latency (p50, p95, p99)
  - Timeline materialization time
  - LLM inference latency
  - Queue depth (reconciliation.tasks backlog)
- Business metrics:
  - High-risk patients detected per day
  - Conflict resolution time (how long pending?)
  - LLM model accuracy (assessed by human review sample)
  - Data freshness (age of latest event per patient)

---

## Infrastructure & Scaling

### Horizontal Scaling for Reconciliation
**Current state**: Reconciliation happens inline in Patient Event Reconciliation service. No independent worker scaling.

**Production requirement**:
- Reconciliation worker pool should scale based on queue depth
- Kubernetes KEDA auto-scaler: min=2, max=50 replicas (vs. max=20 in MVP)
- SQS/JetStream monitoring: alert if queue depth exceeds threshold

### Database Optimizations
**Current state**: Single Postgres instance, per-service schemas.

**Production requirement**:
- Partition reconciliation_events table by hash(canonical_patient_id) to distribute write load
- Read replicas for timeline queries (O(1) lookups don't need writer locks)
- Connection pooling per service (already in MVP, but tune pool sizes based on load)
- Vacuum strategies for append-only event log (grows unbounded)

### Message Bus High Availability
**Current state**: Single NATS broker (Docker Compose only).

**Production requirement**:
- NATS cluster: 3+ nodes for quorum (StatefulSet on Kubernetes)
- JetStream replication factor: 3 (durability across node failures)
- Persistent storage: S3-backed or local persistent volumes
- Consumer group checkpointing: ensure no message loss on broker restart

---

## LLM Improvements

### Model Selection & Benchmarking
**Current state**: Ollama with biomistral-7b (local, free).

**Production requirement**:
- Benchmark LLM accuracy against ground truth (human expert assessments)
- Compare models: Ollama + local open-source vs. Claude API vs. fine-tuned models
- Tradeoff: cost vs. accuracy vs. latency
- Model versioning: track which model generated each recommendation (audit trail)

### Prompt Engineering & Customization
**Current state**: Single system prompt for all patients.

**Production requirement**:
- Specialized prompts for high-risk patients (oncology, cardiac, etc.)
- Per-patient context injection: past recommendations, outcomes, provider notes
- Prompt versioning & A/B testing: compare prompt variations on historical data
- Fallback logic: if LLM returns empty/error, graceful degradation (return last recommendation or alert)

### Recommendation Freshness
**Current state**: Event-driven (triggered by timeline updates).

**Production requirement**:
- Configurable re-assessment frequency (e.g., re-assess every 7 days even if no timeline update)
- Semantic change detection: re-assess only if timeline materially changed (not just formatting)
- Automatic model retraining: periodically re-assess historical patients with latest model

---

## Regulatory & Security

### HIPAA Compliance
**Current state**: No encryption, no access controls, no audit logging.

**Production requirement**:
- Encrypt data at rest (TDE for Postgres, encryption for object storage)
- Encrypt data in transit (TLS for all services)
- Role-based access control (RBAC): operators, data admins, auditors with different permissions
- Audit logging: all access to PII logged and immutable
- Data retention: implement right-to-be-forgotten (GDPR) and deletion workflows

### Authorization & Secrets Management
**Current state**: Environment variables for DB credentials (Docker Compose).

**Production requirement**:
- Vault/AWS Secrets Manager for credential rotation
- Service-to-service authentication (mTLS or service tokens)
- Operator authentication (OAuth2 / SAML for web UI)

---

## Summary: Phased Rollout to Production

**Phase 1 (MVP → Early Production)**:
- Conflict detection & logging (R-F2)
- Event versioning (R-F4)
- Audit trail for operator decisions
- Basic monitoring & alerting

**Phase 2 (Scaling)**:
- Late-arrival reprocessing (R-F8)
- Per-event-type authority rules
- LLM model selection & benchmarking
- Database partitioning & read replicas

**Phase 3 (Hardening)**:
- Void/tombstone support (R-F6, R-F7)
- HIPAA compliance (encryption, RBAC, audit)
- Advanced conflict resolution UI
- Confidence scoring & semantic deduplication

**Phase 4 (Optimization)**:
- Model retraining & A/B testing
- Prompt specialization per condition
- Cost optimization (batch processing vs. real-time)
- Auto-scaling tuning & capacity planning

