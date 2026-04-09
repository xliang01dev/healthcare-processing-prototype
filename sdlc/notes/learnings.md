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

## 2026-04-09

### 18. OpenTelemetry & Jaeger Version Mismatch Cascades
**Mistake:** Added OpenTelemetry instrumentation without checking version compatibility. Used `opentelemetry-exporter-jaeger` with modern instrumentation packages.

**What went wrong:**
- OpenTelemetry SDK v0.42b0 (instrumentation) incompatible with exporter-jaeger v1.21
- Exporter tried to import constants (`OTEL_EXPORTER_JAEGER_AGENT_HOST`) that don't exist in that SDK version
- Error: `ModuleNotFoundError: No module named 'deprecated'` (transitive dependency missing)
- Then switched to OTLP exporter, which worked but required Jaeger v2

**Lesson:** When adding observability frameworks, verify version alignment first:
- OpenTelemetry SDK, exporters, and instrumentation must be compatible
- Modern approach: Use OTLP (OpenTelemetry Protocol) with Jaeger v2 instead of Jaeger-specific exporters
- Always lock transitive dependencies explicitly if they're critical (e.g., `deprecated` package)

**Key takeaway:** OTLP is the modern standard. Old Jaeger-specific exporters and APIs are becoming deprecated. New projects should target OTLP + modern Jaeger v2.

---

### 19. Container Image Versions: `latest` ≠ Up-to-Date
**Mistake:** Assumed `jaegertracing/all-in-one:latest` would pull Jaeger v2.

**Reality:**
- `jaegertracing/all-in-one` image is Jaeger v1 only (end-of-life Dec 2025)
- Jaeger v2 is in `jaegertracing/jaeger` image (different image, not a tag)
- Docker's `latest` tag can be stale if not pulled recently
- Cached image stayed on disk even after updating compose file

**Solution:**
```bash
docker-compose down
docker image rm jaegertracing/all-in-one
docker-compose pull jaeger  # explicit pull
docker-compose up
```

**Lesson:** Always verify which image tag actually corresponds to which version. `latest` is not a guarantee of being current. For critical infrastructure (Jaeger, Prometheus, Loki), pin to explicit versions after testing. For observability, accept one minor version lag behind latest for stability.

---

### 20. Loki Configuration Complexity: v2 → v3 Schema Breaking Change
**Mistake:** Started with Loki v2 config syntax, pulled Loki v3 container without updating config.

**What broke:**
- v3 removed fields: `enforce_metric_name`, `retention_deletes_enabled`, `shared_store` (boltdb-shipper)
- v3 changed `schema_config.store` to only accept `tsdb` or `boltdb-shipper` (not `filesystem`)
- v3 moved storage config structure: `tsdb_shipper` moved to `storage_config.tsdb_shipper`
- Every config change spawned 3-4 validation errors at startup, hard to debug incrementally

**Time spent:** ~45 minutes on syntax errors before finding working config.

**Correct v3 config minimal structure:**
```yaml
common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      schema: v13

storage_config:
  filesystem:
    directory: /loki/chunks

limits_config:
  retention_period: 24h
  allow_structured_metadata: false

server:
  http_listen_port: 3010
  log_level: error
```

**Lesson:** For each major version of infrastructure software, read the migration guide before upgrading. Loki v2→v3 is a breaking change. When pulling container updates, update config documentation at the same time. Version mismatches between containers and config cause cascading cryptic errors.

---

### 21. Jaeger v2 Configuration: No Flags, YAML Required
**Mistake:** Tried to configure Jaeger v2 via environment variables and command-line flags like v1.

**v1 approach (doesn't work on v2):**
- `LOGLEVEL=error` environment variable — ignored in v2
- `--log-level=error` command flag — unknown flag error
- `--query.http.server.host-port=:3030` — v1 syntax, not recognized in v2

**v2 approach:** Must use OpenTelemetry Collector YAML config syntax:
```yaml
service:
  telemetry:
    logs:
      level: error

receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
  jaeger:
    protocols:
      grpc:
        endpoint: 0.0.0.0:14250
      thrift_http:
        endpoint: 0.0.0.0:14268

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024

exporters:
  debug:

service:
  pipelines:
    traces:
      receivers: [otlp, jaeger]
      processors: [batch]
      exporters: [debug]
```

**Lesson:** Jaeger v2 is a complete architectural rewrite on top of OpenTelemetry Collector. It's not "Jaeger with new flags" — it's a different system. When migrating from v1 to v2, expect to rewrite all configuration. Document this heavily: no backward compatibility on config syntax.

---

### 22. Logging Suppression: `logging: driver: "none"` vs Log Level Config
**Mistake:** Initially tried to suppress Loki/Prometheus/Jaeger logs with `logging: driver: "none"` in docker-compose.

**Why wrong:** Suppressing all logs means losing error information for debugging. Better to configure the service to only show errors.

**Correct approach per service:**

**Prometheus:**
```yaml
command:
  - "--log.level=error"
```

**Loki:**
```yaml
server:
  log_level: error
```

**Jaeger:**
```yaml
service:
  telemetry:
    logs:
      level: error
```

**Lesson:** Each service has its own logging configuration API. Configure them individually rather than suppressing all logs. This preserves observability while reducing noise.

---

### 23. Premature Simplification: Removed Config Only to Re-Add It
**Mistake:** When Jaeger config was complex (extensions validation errors), removed the config file entirely to "use defaults" and simplify troubleshooting.

**What happened:**
1. Removed `jaeger-config.yaml` volume mount and `--config` command flag
2. Jaeger started successfully with defaults
3. **But:** Default OTLP HTTP receiver listened on `127.0.0.1:4318` (localhost only), not `0.0.0.0:4318`
4. Services inside Docker couldn't connect (Connection refused)
5. Had to re-add the config file to explicitly bind to `0.0.0.0:4318`

**Lesson:** Don't strip away configuration thinking "defaults will work." The defaults for Jaeger v2 bind to localhost for security (restricts exposure). You don't need *less* config; you need *working* config. 

**Better approach:** Instead of removing config when stuck, analyze what's actually failing:
- Config has syntax errors → Fix syntax incrementally (test each section)
- Services can't reach it → Check network binding (localhost vs 0.0.0.0), not absence of config
- Unknown field errors → Read docs for that version's field names

**Time cost:** ~15 minutes of false troubleshooting (removed config, restarted, saw "working" but broken behavior, then had to re-add and fix properly).

---

## How to Avoid These Issues in the Future

### Observability Stack (Issues 18-22)

**Preventative measures that would have saved 2+ hours:**

1. **Start with explicit version pinning (before first docker-compose up)**
   - Don't use `latest` for any infrastructure service
   - Pin: `jaegertracing/jaeger:2.0.0`, `grafana/loki:3.0.0`, `prom/prometheus:v2.45.0`
   - Reason: Discover breaking changes during planning, not after container boots
   - **Action:** Create a spreadsheet of service versions and their release dates before adding to compose

2. **Read release notes for major versions before upgrading**
   - Jaeger v1→v2: Major architectural change (required)
   - Loki v2→v3: Breaking config syntax changes (required)
   - Prometheus: Generally more stable, but still check if upgrading past v2
   - **Action:** Spend 10 minutes reading "Breaking Changes" section on GitHub releases page

3. **Test configuration locally first (docker-compose up on your laptop)**
   - Push to remote only after confirming all services pass health checks
   - Watch the logs for 30 seconds to spot initialization errors
   - **Action:** Add pre-commit hook: `docker-compose config > /dev/null` to validate syntax

4. **Verify OpenTelemetry compatibility matrix upfront**
   - Don't mix arbitrary versions of SDK, exporter, instrumentation
   - Check compatibility table: https://github.com/open-telemetry/opentelemetry-python/blob/main/CONTRIBUTING.md
   - For modern stacks: Use OTLP from the start (not Jaeger-specific exporters)
   - **Action:** Pin all OTel packages to same minor version (e.g., all `>=0.44b0, <0.45`)

5. **Read the service's logging configuration API**
   - Don't try `logging: driver: "none"` — it suppresses visibility, not noise
   - Check service docs for log level config before first run
   - **Action:** Add to docker-compose as comment: `# Logging: see https://docs.service.io/logging`

6. **Create a "infrastructure versions.md" document**
   - List each service, pinned version, and known config syntax
   - Add "breaking changes from previous major" section
   - Include minimal working config for each
   - **Action:** Update this doc every time you upgrade a service version

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
15. **OTLP is the modern standard** — Use OTLP exporter + Jaeger v2, not Jaeger-specific exporters. Version mismatches cascade quickly.
16. **Version mismatches are costly** — When adding observability, verify SDK/exporter/instrumentation compatibility upfront. Transitive dependencies matter.
17. **Pin infrastructure versions** — Don't rely on `latest` tags for critical services. Verify which image/tag actually corresponds to which version. Cache invalidation is real.
18. **Read migration guides for major versions** — v2→v3 breaking changes require config rewrites. Check docs before pulling new container versions.
19. **Jaeger v1→v2 is architectural, not incremental** — v2 is OpenTelemetry Collector-based. No backward compat on config or CLI flags. Plan for complete rewrite.
20. **Configure logging per-service** — Don't suppress all logs. Use service-specific log level config (Prometheus: `--log.level`, Loki: `server.log_level`, Jaeger: YAML) to reduce noise while preserving visibility.
21. **Don't strip config to "simplify" troubleshooting** — Default configurations often have security constraints (localhost-only binding). When config is complex, fix it incrementally; don't remove it. Removing config to debug often hides the actual problem (network binding, not config syntax).
