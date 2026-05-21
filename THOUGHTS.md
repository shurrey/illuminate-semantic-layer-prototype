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
- Test coverage scoped to overlay merge + metric resolution + SQL safety.
- Web UI is one HTML file. Default styling.
- No Bedrock; direct Anthropic API.
