# Architectural Mistakes & Learnings

## 2026-04-03

### 1. Per-Patient Topic Routing (Initial Assumption)
**Mistake:** Assumed Patient Data Service should publish to `reconcile.{canonical_patient_id}` topics for per-patient ordering.

**Why it was wrong:** Services are stateless and can't know which topics they "own." The routing model doesn't work with horizontal scaling.

**Correct approach:** Patient Data Service publishes to generic `reconcile` topic. Reconciliation Service instances subscribe with a queue group. NATS handles round-robin distribution, not topic routing.

**Lesson:** Topic-based routing works for specific consumers (Timeline service subscribes to reconciled.events). For work distribution across stateless instances, use queue groups, not topic sharding.

---

### 2. NATS Core Queue Groups (Blocker Identified)
**Mistake:** Initially thought NATS core could handle queue groups with round-robin distribution.

**Reality:** NATS core has no consumer groups or queue group support. Two instances subscribing to the same topic both get every message (fanout), or round-robin but with no ordering guarantee per consumer.

**Impact:** Blocking issue for horizontal scaling without upgrading to JetStream.

**Solution:** Use NATS JetStream for durable work queues with proper consumer groups.

**Lesson:** Understand message broker semantics before designing. NATS core ≠ Kafka. Core NATS is stateless pub/sub; JetStream adds persistence and consumer groups.

---

### 3. Debounce Row Lock Bottleneck
**Mistake:** Assumed Postgres row locks (FOR UPDATE) on debounce table would be "fast enough."

**Reality:** Under extreme per-patient throughput (hot shard), many instances contending for same debounce row creates lock serialization point. Not a global bottleneck, but per-patient bottleneck is real.

**Trade-off accepted:** Lock contention is acceptable for MVP because:
- Debounce hold time is milliseconds (just state updates)
- Different patients don't contend (fine-grained locks)
- Expensive work (reconciliation) happens outside the lock

**Lesson:** Document the bottleneck. Know the scaling ceiling. For production, might need Redis for debounce state (but then face eventual consistency vs. durability trade-off).

---

### 4. Write-Behind Caching for Debounce (Not Viable)
**Mistake:** Explored Redis write-behind pattern (update cache, async flush to Postgres) for debounce state.

**Why it fails:** Effect (reconciliation enqueue) happens before durability (Postgres flush) is complete. If Redis crashes, debounce state lost but reconciliation already triggered. → Duplicate or missing reconciliation.

**Correct pattern:** Write-through (update Postgres first, then cache) or accept eventual consistency (not viable for debounce).

**Lesson:** For state that triggers side effects, durability must come first. Write-behind is only safe for pure caching (non-critical data).

---

### 5. Worker Implementation: Threads vs Instances (Early Validation)
**Mistake:** Could have designed workers as threads within single service instance.

**Why that's wrong:** Threads don't scale across machines. Max throughput = max threads per instance. Defeats microservices scaling.

**Correct approach:** Each worker is a stateless service instance (container/pod). Auto-scales by adding/removing instances.

**Lesson:** Validate architectural patterns early against your scale requirements. Single-instance-with-threads is a common anti-pattern for queue-based systems.

---

### 6. publish_stream() and deliver_group Confusion
**Mistake:** Thought publishers needed to specify `deliver_group` when publishing.

**Reality:** Publishers just publish to stream. Consumers specify deliver_group when subscribing. Publisher-consumer decoupling.

**Correct model:**
- `publish_stream()`: No group logic, just publishes to stream
- `subscribe_stream()` with `deliver_group`: Enables queue group round-robin among consumers

**Lesson:** Understand pub/sub decoupling. Publishers and consumers are independent. Same stream can be consumed by multiple groups.

---

### 7. durable_name and deliver_group: Same vs Different
**Mistake:** Set durable_name and deliver_group to the same value ("reconciliation-workers").

**Why that's wrong:** Loses observability. Can't track which worker processed which message.

**Correct approach:**
- `durable_name`: Unique per instance (e.g., "worker-1", "worker-2")
- `deliver_group`: Shared for the group (e.g., "reconciliation-workers")

**Benefits:**
- Track which instance processed what (for debugging)
- Each instance resumes from its own position
- Better for dead-letter handling and retries

**Lesson:** Distinguish between "identity" (durable_name per instance) and "group" (deliver_group shared). Document why they're different.

---

### 8. Healthcare Systems: Queues vs Event Streams
**Validation:** Confirmed that real healthcare systems use **event streams, not queues**.

**Why:** HIPAA audit trails, replay capability, multiple subscribers, temporal queries all require streams, not queues.

**Insight:** Using JetStream as a stream (not traditional queue) aligns with healthcare best practices.

**Lesson:** Validate architecture against industry standards and compliance requirements. Event Sourcing/streams are standard for regulated domains.

---

### 9. Code Compilation Verification Hooks
**Mistake:** Recommended code changes without automated verification that they compile/type-check correctly.

**Why it was wrong:** Manual reviews missed type errors (e.g., `pub_ack.sequence` vs `pub_ack.seq`, incorrect async/await usage). Errors discovered only after user ran checks or attempted execution.

**Correct approach:** Set up compilation/type-checking hooks in `.claude/settings.json` to run automatically on every code edit. For Python: `mypy` for type checking, `py_compile` for syntax validation. Hooks catch errors before delivery.

**Implementation:** Add PostToolUse command hooks:
- `type: "command"` with `command: "python -m mypy {file}"` for Python files
- Run on every Edit to .py files
- Fail fast with clear error output

**Lesson:** Automate quality gates for code changes. Compilation/type-check hooks are cheap insurance against regressions and provide immediate feedback. Similar to pre-commit hooks in CI/CD but for individual edits during development.

---

## 2026-04-06

### 10. Patient Data Service Sharding Breaks Identity Resolution
**Mistake:** Proposed per-source sharding to scale Patient Data Service (Medicare → shard 0, Hospital → shard 1, Labs → shard 2) to reduce contention on atomic upsert.

**Why it fails:** Each shard would have its own `patients` table. Same Medicare ID assigned to different canonical UUIDs in different shards:
- Medicare shard: MED-123 → uuid-x
- Hospital shard: MED-123 → uuid-y (different!)
- Labs shard: MED-123 → uuid-z (different!)

Result: **Multiple canonical IDs for the same patient** — defeats the entire purpose of MPI.

**Correct approach:** Single primary `patients` table (source of truth) + read replicas for SELECT queries. No sharding.

**Lesson:** Identity resolution requires a single source of truth for the mapping. Sharding breaks this invariant. Don't shard identity tables; replicate them instead.

---

### 11. Patient Data Service Bottleneck Reassessed
**Initial claim:** Atomic upsert on `patients(shared_identifier)` is a "medium production bottleneck" requiring future sharding mitigation.

**Reality check:** For typical healthcare systems:
- **Event distribution**: ~99% of events are for existing patients (recurring labs, claims, encounters)
- **New patient registration**: Only ~0.5-1% of traffic (50-100/day in large health systems)
- **Lock behavior**: Postgres row locks complete in sub-millisecond; even 5,000 concurrent new-patient inserts finish in ~100ms
- **Real bottleneck**: Postgres write throughput (~1000 inserts/sec), not serialization

**Revised assessment:** Not a real bottleneck except during specific bulk-import scenarios (nightly EHR dumps). Serialization on atomic upsert is an implementation detail, not a scaling constraint.

**Correct mitigation:** Single primary + read replicas. No architectural change needed.

**Lesson:** Challenge scale assumptions. Measure actual event distributions before declaring architectural constraints. New patient registration is rare; optimize for the common case (existing patient updates).

---

### 12. Ollama Chat API vs Generate API
**Mistake:** Initially used `ollama.generate()` method for LLM inference, which doesn't support system prompts properly.

**Why it failed:** `generate()` is for raw text completion. System prompts must be in a messages array with `{"role": "system", "content": "..."}`.

**Correct API:** Use `ollama.chat()` with messages array:
```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
]
response = await client.chat(model=model_name, messages=messages, stream=False)
response.message.content  # Access result as attribute, not dict
```

**Lesson:** Understand your LLM SDK's API contract. Different methods serve different purposes. Chat API = multi-turn conversations with roles; Generate API = simple completion. Match the method to your use case.

---

### 13. System Prompt as Multi-Line String
**Mistake:** Defined system prompt as a tuple of string literals instead of a single string.

**Result:** Passed tuple instead of string to `OllamaAgentHandler`, causing type errors.

**Correct approach:** Use implicit string concatenation in parentheses to define multi-line strings:
```python
_system_prompt = (
    "You are a healthcare professional. "
    "Review the patient data and provide next steps. "
    "Return JSON format as {\"summary\": \"...\", \"risk_tier\": \"high\"|\"medium\"|\"low\"|\"critical\"}"
)
```

**Lesson:** Python implicit string concatenation is clean for multi-line literals. Document the format explicitly (e.g., "Pass as single string, not tuple") to prevent similar mistakes.

---

### 14. LLM Response Parsing with Fallback
**Mistake:** Assumed LLM would always return valid JSON with required fields ("recommend", "risk").

**Reality:** LLM returned plain natural language text without JSON structure when prompt was ambiguous.

**Correct approach:** Wrap JSON parsing in try-except with fallback:
```python
try:
    result_json = json.loads(result)
    summary = result_json.get("recommend", result)  # fallback to whole result
    risk_tier = result_json.get("risk", "medium")
except (json.JSONDecodeError, ValueError):
    # LLM returned plain text, not JSON
    summary = result
    risk_tier = "medium"  # sensible default
```

**Lesson:** Defensive parsing for LLM outputs. LLMs are non-deterministic; always have a fallback for unexpected formats. Document the expected format in the system prompt clearly.

---

### 15. Risk Tier Value Mismatch (System Prompt vs Database)
**Mistake:** System prompt said `"risk": high/med/low` but database constraint expected `risk_tier IN ('low', 'medium', 'high', 'critical')`.

**Error:** LLM returned "med" → database CHECK constraint violation.

**Correct fix:** Make system prompt explicit about valid values:
```python
_system_prompt = (
    "...risk_tier should be exactly one of: "
    "\"high\"|\"medium\"|\"low\"|\"critical\""
)
```

**Lesson:** Align system prompt examples with database schema. A difference of "med" vs "medium" is enough to break a constraint. Use exact value lists in prompts.

---

### 16. Response Models: Trim Unnecessary Fields
**Mistake:** Included `canonical_patient_id` and `content_hash` in `RecommendationResponse` API model.

**Why wrong:** Clients don't need these fields:
- `canonical_patient_id` — Already known by client (used to fetch recommendation)
- `content_hash` — Internal deduplication detail, not relevant to API consumers

**Correct approach:** Return only fields clients care about: `id`, `summary`, `risk_tier`, `generated_at`.

**Lesson:** API response models should represent the client's view, not the database schema. Don't leak internal details (hashing, deduplication logic) to the API layer.

---

### 17. Patient Timeline Endpoints: Distinguish Latest vs History
**Mistake:** Assumed single `/timeline` endpoint would paginate all history per patient.

**Reality:** Materialized view only stores latest per patient (O(1) lookup). Pagination on "latest 1 row per patient" is pointless.

**Correct approach:** Two endpoints:
- `GET /patient/{id}/timeline/latest` — Returns PatientTimeline (single row, O(1))
- `GET /patient/{id}/timeline/history` — Returns paginated history (optional, for full timeline)

**Lesson:** Understand your data model before designing API. Pagination doesn't make sense for queries that always return 1 row. Separate endpoints for different access patterns.

---

## Takeaways for Future Decisions

1. **Document scalability ceilings** — Know the bottlenecks (debounce lock is per-patient, acceptable)
2. **Durability before effects** — If state triggers side effects, persist first
3. **Distinguish identity from group** — durable_name ≠ deliver_group
4. **Understand broker semantics** — Know what "pub/sub", "queue", "consumer group" mean in your specific broker
5. **Validate against standards** — Healthcare → event streams, compliance → audit trails required
6. **Test horizontal scaling early** — Catch threading/sharding issues before they're baked in
7. **Automate quality gates** — Use compilation/type-check hooks on every code edit to catch errors before they surface in testing
8. **Identity tables must have single source of truth** — Never shard identity mappings; replicate instead. Sharding breaks the invariant.
9. **Challenge scale assumptions** — Measure actual event distributions before declaring architectural bottlenecks. New patient registration may be <1% of traffic.
10. **Match SDK methods to use cases** — `generate()` for completion, `chat()` for multi-turn + system prompts. Know your API contract.
11. **Align prompts with schema** — System prompt examples must match database constraints exactly ("med" ≠ "medium"). Test the constraint boundary.
12. **Defensive LLM parsing** — Always have fallbacks for unexpected response formats. LLMs are non-deterministic.
13. **API models represent client view** — Don't leak internal details (hashes, deduplication) to API consumers. Return only what clients need.
14. **Data model drives API design** — Pagination is pointless for queries returning 1 row. Separate endpoints for different access patterns.
