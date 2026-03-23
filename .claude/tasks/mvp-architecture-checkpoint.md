# Checkpoint: MVP Architecture Plan

## Status
Approved and ready for implementation delegation.

## Plan File
`/Volumes/Files/Development/Service/Health/learning-healthcare-processing/sdlc/plans/mvp-architecture.md`

## Summary of Decisions

1. **Canonical model**: FHIR R4 is used internally. All raw formats (HL7v2 ADT, X12 837 claims, CCDA EHR) are normalized at the ingestion boundary.
2. **Architecture style**: Event-driven, Kappa-style (streaming as source of truth). Kafka or NATS JetStream as message broker.
3. **Reconciliation is a first-class service**: Handles versioning, voiding, deduplication, and late-arrival logic. Publishes a clean `reconciled.events` stream.
4. **Timeline is a derived materialized view**: Built by the Timeline Service from reconciled events. Stored in Postgres JSONB. Invalidated and rebuilt on upstream changes.
5. **Risk engine is rule-based for MVP**: ICD-10 to HCC mapping, RAF scoring, risk tier assignment (Low/Medium/High/Critical), post-discharge readmission flag.
6. **LLM is inserted post-reconciliation**: Sees the cleanest available timeline. Produces structured JSON output (summary, key_risks, recommended_actions). Stores provenance (model version, prompt version).
7. **Dashboard is a BFF + UI pattern**: A read-only API aggregates the timeline, risk, and summary stores. A browser UI shows patient list, timeline, risk breakdown, and AI summary.

## Services Defined

- Ingestion Gateway
- Master Patient Index (MPI)
- Reconciliation Service
- Timeline Service
- Risk Engine
- LLM Summary Service
- Notification Service
- Dashboard API (BFF)
- Dashboard UI

## Open Questions (for user to decide before implementation)

- Message broker choice: NATS JetStream (lightweight) vs. Kafka (realistic)?
- LLM provider: OpenAI GPT-4o vs. Anthropic Claude?
- Dashboard: React SPA vs. server-rendered (Next.js)?

## Implementation Phases

1. Foundation — schemas, event bus, ingestion, MPI
2. Reconciliation and Timeline
3. Risk Stratification
4. LLM Integration
5. Delivery — dashboard API and UI, notifications
6. Observability — logging, synthetic data generators, documentation

## Risks Noted

- Reconciliation rules require explicit business rule decisions before implementation.
- LLM summarization quality depends on prompt design — prompt templates should be versioned.
- Post-discharge risk scoring requires defining what "risk" means (readmission rate proxy rules).
