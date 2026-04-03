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

## Takeaways for Future Decisions

1. **Document scalability ceilings** — Know the bottlenecks (debounce lock is per-patient, acceptable)
2. **Durability before effects** — If state triggers side effects, persist first
3. **Distinguish identity from group** — durable_name ≠ deliver_group
4. **Understand broker semantics** — Know what "pub/sub", "queue", "consumer group" mean in your specific broker
5. **Validate against standards** — Healthcare → event streams, compliance → audit trails required
6. **Test horizontal scaling early** — Catch threading/sharding issues before they're baked in
7. **Automate quality gates** — Use compilation/type-check hooks on every code edit to catch errors before they surface in testing
