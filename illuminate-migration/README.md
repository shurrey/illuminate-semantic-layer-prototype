# Illuminate Migration — Step 1 artifact

This directory holds the **canonical metric catalog targeting the real Illuminate Snowflake CDM schema**, derived from `verified_queries.json` in `illuminate-conversational-intelligence`. It is a staging area — the YAML files are the deliverable of migration Step 1; subsequent steps lift them into the CI repo and wire the engine into the Lambda.

## What's in here

| File | Purpose |
|------|---------|
| `canonical/metrics.yaml` | 12 canonical metrics, Snowflake-native SQL, full provenance fields |
| `canonical/glossary.yaml` | Synonym → metric_id mappings derived from each metric's `synonyms` list |

Nothing here is loaded by the prototype's engine. The prototype's own catalog (synthetic DuckDB warehouse) lives at `../canonical/`. The two are intentionally separate — this one targets a different schema and runtime.

## Mapping back to `verified_queries.json`

Every metric records an `originally:` field naming the verified-query intent it replaces. 12 of the 14 verified queries became canonical metrics; the 2 catalog-browse entries (`list schemas`, `list tables in CDM_LMS`) are tool actions, not metrics — they'll be handled by a `describe_schema` tool when the engine is ported, not by the metric catalog.

| Verified query intent | Canonical metric |
|---|---|
| total student count | `metric.student_count.v1` |
| instructor count | `metric.instructor_count.v1` |
| total course count | `metric.course_count.v1` |
| active courses by term | `metric.active_courses.by_term.v1` |
| enrollment by term | `metric.enrollment_count.by_term.v1` |
| course enrollment counts | `metric.enrollment_count.by_course.v1` |
| enrollment summary statistics | `metric.enrollment_summary.v1` |
| average GPA | `metric.average_gpa.v1` |
| GPA by term | `metric.average_gpa.by_term.v1` |
| GPA for a specific term | `metric.average_gpa.for_term.v1` |
| grade distribution | `metric.grade_distribution.v1` |
| course completion rates | `metric.course_completion_rate.v1` |

Dimensional variants (e.g. `enrollment_count.by_term` vs `enrollment_count.by_course`) are kept as separate canonical metrics because their SQL output shapes genuinely differ (per-term rows vs per-course rows). A future engine enhancement could consolidate these as one metric with multiple `valid_dimensions`, but for now the 1:1 mapping is simpler and preserves the existing verified-query semantics.

## What's intentionally deferred to later steps

- **Engine port:** the prototype's `engine.py` is hardcoded to `sqlglot.read="duckdb"` and renders Jinja templates with only `where` and `dimensions` variables. To consume this YAML it needs (a) Snowflake dialect, (b) `database` as a Jinja variable, (c) safe handling of `{{ database }}` substitution before the SELECT-only check fires.
- **Tenant overlays:** there are no overlay YAMLs in this directory yet because the production Illuminate stack does not have tenant identity wired through to SQL today (the database name is resolved from Secrets Manager, single-tenant per deployment per current code). Adding overlays requires a Cognito JWT claim + per-request tenant resolution — that's Step 4.
- **Parameter binding:** `metric.average_gpa.for_term.v1` needs a `term_name` parameter. The verified query uses Snowflake bind variable syntax (`:term_name`); the prototype's engine doesn't bind. This needs a small engine enhancement during Step 2.

## Verifying the YAML loads cleanly

```bash
uv run python -c "
import yaml
m = yaml.safe_load(open('illuminate-migration/canonical/metrics.yaml'))
g = yaml.safe_load(open('illuminate-migration/canonical/glossary.yaml'))
print(f'metrics: {len(m[\"metrics\"])}, glossary entries: {len(g[\"synonyms\"])}')
print('metric ids:')
for entry in m['metrics']:
    print(f'  - {entry[\"id\"]}')
# Glossary parity check (the prototype's pattern)
missing = []
for entry in m['metrics']:
    for syn in entry.get('synonyms', []):
        if g['synonyms'].get(syn) != entry['id']:
            missing.append((entry['id'], syn))
if missing:
    print('SYNONYM GAPS:')
    for mid, syn in missing:
        print(f'  {mid}: missing or wrong route for {syn!r}')
else:
    print('synonym parity: OK')
"
```

## Next step

Step 2 is wiring the prototype's `engine.py` into the CI repo as a Python module the Lambda imports, then adding `plan` and `compile_sql` as Bedrock Converse tools alongside the existing `execute_sql`. That's where the architectural work begins. This Step 1 artifact is the input.
