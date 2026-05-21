# Decisions and Intentional Corner-Cuts

Running log of design decisions and the spots where the prototype deliberately departs from what production would require.

## Decisions

- **DuckDB over real warehouse.** Single-file, embedded, no ops. Production would target Snowflake/BigQuery/Databricks via dialect-aware SQL generation in `engine.py`.
- **YAML for canonical + overlay.** Human-editable, diffable in PRs. Production would back this with a registry service + UI, but the file format can stay similar.
- **In-process orchestrator.** Production would expose the engine as an MCP server so multiple agents (and the agentic IDE) can use it. The split point is clean: `engine.py` already returns SQL strings, so wrapping it as MCP tools is mechanical.
- **Two-pass Claude (plan → narrate).** Separating structured planning from prose composition lets us validate the plan before any DB call and lets us assert "no PII to the narrator" structurally.

## Intentional corner-cuts

- No real tenant isolation — `--tenant` flag is trusted.
- In-memory cache only; no Redis.
- Test coverage focuses on overlay merge + metric resolution + SQL safety + telemetry + FastAPI smoke tests. The orchestrator's planner/narrator paths are exercised via mocked Anthropic clients; the live API path is spot-tested via `curl` rather than pytest.
- Web UI is one HTML file. Default styling.
- No Bedrock; direct Anthropic API.

## Overlay merge semantics

- Canonical objects are frozen pydantic models; `merge()` never mutates them. A test enforces this.
- `OverlayMetric.measure_sql` is `Optional[str]`; if `None`, the merger falls back to canonical SQL.
- `OverlayMetric.override_default_filters` is a tri-state sentinel: `None` = keep canonical defaults; `[]` = explicitly clear; non-empty = replace.
- Tenant glossary entries take precedence over canonical synonyms (the CLI resolver checks tenant first).
- The `MergedMetric` carries both the canonical and overlay definitions plus an `applied_definition` discriminator, so provenance is structurally recoverable from any query result.

## Closing reflections

### What worked

- **Two-pass orchestrator (plan → narrate).** The clean separation between structured planning and prose composition meant we could validate the plan before any DB call and assert structurally that no PII reaches the narrator. Mocking `anthropic.Anthropic` at the module level kept tests fast and offline — the mock pattern is worth carrying forward.
- **YAML overlay format.** Turns out flat YAML is a surprisingly good overlay format for a small catalog. Diffable in PRs, readable by non-engineers, and the tri-state sentinel on `override_default_filters` handled the "explicitly clear vs unset" distinction without ceremony.
- **sqlglot SELECT-only guard.** Parsing the rendered SQL through sqlglot before handing it to DuckDB stopped three accidental DDL injections during development. Worth every line.
- **Tenant-local glossary.** The "persistence" scenario demonstrates real value: Lone Star maps the term to retention via its local glossary, while canonical and Midwest State return no-match — the right behavior, derived from data structure rather than prompt engineering.

### What surprised me

- **The planner is more reliable than expected.** Claude with a strict `output_config.format` schema and a small, well-described metric catalog returns valid JSON on the first call nearly every time. Temperature=0 and `max_tokens` tuning mattered more than prompt wording.
- **The glossary stub did meaningful work as a fallback.** I expected it to be a throwaway scaffold, but it handled the demo scenarios cleanly — and the `persistence` no-match case revealed a genuine design insight: the canonical layer should not over-extend its synonym set.
- **Pydantic's `frozen=True` was a useful tripwire.** Two early bugs were caught immediately by the frozen model raising an error on attempted mutation. The discipline of "canonical objects are immutable" paid dividends beyond tests.
- **The `_lead_value` helper needed a smarter column-selection heuristic.** Naively picking the first numeric column chose `from_term_ordinal=1` for retention rows. Adding a preference order (rate > non-skip count > skip/ordinal) fixed the demo output and is a pattern that generalizes.

### What I'd change for production

- **Replace DuckDB with a dialect-aware SQL compiler.** The engine already returns SQL strings; swapping `sqlglot`'s DuckDB dialect for Snowflake/BigQuery/Trino is mechanical once the test suite pins dialect expectations.
- **Expose the engine as an MCP server.** The split point is already clean: `engine.py` returns SQL strings; wrapping it as MCP tools lets other agents and the agentic IDE call it directly without duplicating the merge + compile logic.
- **Replace the YAML overlay format with a registry service + diff UI.** The file format can stay similar, but production needs versioned changesets, approval workflows, and a "patch" notation that records deltas vs full SQL restatement. Full SQL restatement in overlays is hard to review.
- **Real tenant isolation.** The `--tenant` flag is trusted. Production needs RLS (row-level security) or ABAC so a tenant's overlay cannot accidentally (or deliberately) reference another tenant's data.
- **Real observability.** Ship telemetry to a real metric pipeline (Prometheus/OpenTelemetry). Add latency budgets per metric. Log when the planner picks the wrong metric and use that corpus to improve the catalog's `example_questions`.
- **Move LIMIT injection from string-scan to AST-aware.** The current `"LIMIT" not in rendered.upper()` check is fragile; sqlglot can inject a LIMIT node into the AST cleanly.
- **Per-tenant rate limits + cache.** Each tenant's query volume is independent; a shared cache with per-tenant TTL budgets prevents one noisy tenant from blowing the cache for others.
- **Feedback loop.** When the planner picks the wrong metric, that should be a labeled training example. Logging it automatically and surfacing a review queue is how the catalog improves over time.
