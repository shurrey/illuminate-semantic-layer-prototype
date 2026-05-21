"""Two-pass Claude orchestrator: plan (NL → QueryPlan) → execute → narrate (rows → prose).

The orchestrator is the only module that imports anthropic. It accepts an injected
client in the constructor so tests can mock it. ANTHROPIC_API_KEY must be set in
the environment for live use.

Model: claude-sonnet-4-6. JSON output via output_config.format for the planner.
No assistant prefills (returns 400 on Sonnet 4.6). Extended thinking is not enabled
(planner returns structured JSON; narrator output is short prose — both fine without).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import anthropic
import duckdb
from pydantic import ValidationError

from .engine import compile_sql, resolve
from .models import (
    CanonicalCatalog,
    MergedMetric,
    QueryPlan,
    QueryResult,
    Tenant,
)
from .telemetry import Telemetry

MODEL = "claude-sonnet-4-6"
MAX_NARRATOR_ROWS = 1000
DEFAULT_MAX_TOKENS = 4096

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class PlannerError(Exception):
    """Raised when the planner returns an invalid or unresolvable plan."""


class Orchestrator:
    """Two-pass NL → SQL → narrative orchestrator.

    Pass 1 (plan): NL question + metric catalog → structured QueryPlan via json_schema.
    Pass 2 (narrate): aggregated result rows → plain-English summary.

    A per-process in-memory cache de-dupes identical (tenant_id, question) calls.
    Cache is keyed on the strings only — not on catalog/tenant state — so reload
    invalidations require restarting the process. Prototype-only.
    """

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        model: str = MODEL,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.client = client if client is not None else anthropic.Anthropic()
        self.model = model
        self.telemetry = telemetry
        self._plan_prompt = (_PROMPTS_DIR / "plan.md").read_text()
        self._narrate_prompt = (_PROMPTS_DIR / "narrate.md").read_text()
        self._cache: dict[tuple[str, str], QueryResult] = {}

    # ------------------------------------------------------------------
    # Pass 1 — planner
    # ------------------------------------------------------------------

    def _catalog_for_planner(
        self,
        canonical: CanonicalCatalog,
        tenant: Tenant | None,
    ) -> list[dict[str, Any]]:
        """Build the merged metric catalog the planner sees as user input.

        For each canonical metric, attach the tenant's overlay info if present.
        Filter and dimension lists are reduced to id-only.
        """
        out = []
        for mid, m in canonical.metrics.items():
            overlay = tenant.overlays.get(mid) if tenant else None
            entry = {
                "id": m.id,
                "display_name": m.display_name,
                "description": m.description,
                "synonyms": m.synonyms,
                "example_questions": m.example_questions,
                "valid_dimensions": [d.id for d in m.valid_dimensions],
                "default_filters": [f.id for f in m.default_filters],
                "applied_definition": "tenant-override" if overlay else "canonical",
                "extra_filters": [f.id for f in overlay.extra_filters] if overlay else [],
            }
            out.append(entry)
        return out

    def plan(
        self,
        question: str,
        canonical: CanonicalCatalog,
        tenant: Tenant | None,
    ) -> QueryPlan:
        catalog = self._catalog_for_planner(canonical, tenant)
        tenant_id = tenant.id if tenant else "canonical"

        user_content = (
            f"Tenant: {tenant_id}\n\n"
            f"Question: {question}\n\n"
            "Available metrics:\n"
            f"{json.dumps(catalog, indent=2)}"
        )

        schema = {
            "type": "object",
            "properties": {
                "metric_id": {"type": "string"},
                "filters": {"type": "array", "items": {"type": "string"}},
                "dimensions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["metric_id", "filters", "dimensions"],
            "additionalProperties": False,
        }

        response = self.client.messages.create(
            model=self.model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=self._plan_prompt,
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise PlannerError(f"planner did not return JSON: {e}") from e
        try:
            plan = QueryPlan(**data)
        except ValidationError as e:
            raise PlannerError(f"planner returned malformed plan: {e}") from e
        self._validate_plan(plan, canonical, tenant)
        return plan

    def _validate_plan(
        self,
        plan: QueryPlan,
        canonical: CanonicalCatalog,
        tenant: Tenant | None,
    ) -> None:
        if plan.metric_id not in canonical.metrics:
            raise PlannerError(f"unknown metric: {plan.metric_id}")
        merged = resolve(canonical, tenant, plan.metric_id)
        valid_dims = {d.id for d in merged.valid_dimensions}
        for d in plan.dimensions:
            if d not in valid_dims:
                raise PlannerError(
                    f"invalid dimension '{d}' for {plan.metric_id}; valid: {sorted(valid_dims)}"
                )
        valid_filters = {f.id for f in merged.effective_filters}
        for f in plan.filters:
            if f not in valid_filters:
                raise PlannerError(
                    f"invalid filter '{f}' for {plan.metric_id}; valid: {sorted(valid_filters)}"
                )

    # ------------------------------------------------------------------
    # Pass 2 — narrator
    # ------------------------------------------------------------------

    def narrate(
        self,
        question: str,
        merged: MergedMetric,
        rows: list[dict[str, Any]],
        tenant_id: str = "canonical",
    ) -> str:
        assert len(rows) <= MAX_NARRATOR_ROWS, (
            f"narrator must only see aggregates; got {len(rows)} rows (max {MAX_NARRATOR_ROWS})"
        )

        provenance = {
            "tenant_id": tenant_id,
            "metric_id": merged.id,
            "display_name": merged.canonical.display_name,
            "applied_definition": merged.applied_definition,
            "owner": (merged.overlay.owner if merged.overlay else merged.canonical.owner),
            "overlay_diff": (merged.overlay.diff_description if merged.overlay else None),
        }
        user_content = (
            f"Question: {question}\n\n"
            f"Metric used:\n{json.dumps(provenance, indent=2)}\n\n"
            f"Aggregated rows ({len(rows)}):\n{json.dumps(rows, indent=2, default=str)}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=self._narrate_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return next((b.text for b in response.content if b.type == "text"), "").strip()

    # ------------------------------------------------------------------
    # End-to-end ask
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        canonical: CanonicalCatalog,
        tenant: Tenant | None,
        con: duckdb.DuckDBPyConnection,
    ) -> QueryResult:
        tenant_id = tenant.id if tenant else "canonical"
        cache_key = (tenant_id, question)
        if cache_key in self._cache:
            return self._cache[cache_key]

        plan: QueryPlan | None = None
        merged: MergedMetric | None = None
        sql: str | None = None
        rows: list[dict[str, Any]] = []
        execution_ms: float | None = None

        try:
            plan = self.plan(question, canonical, tenant)
            merged = resolve(canonical, tenant, plan.metric_id)

            # Filters/dimensions resolution: the engine accepts Filter/Dimension objects, not ids.
            filter_objs = [f for f in merged.effective_filters if f.id in plan.filters]
            dim_objs = [d for d in merged.valid_dimensions if d.id in plan.dimensions]
            sql = compile_sql(merged, filters=filter_objs, dimensions=dim_objs)

            t0 = time.perf_counter()
            cursor = con.execute(sql)
            raw_rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            execution_ms = (time.perf_counter() - t0) * 1000.0

            rows = [dict(zip(cols, r, strict=True)) for r in raw_rows]

            narrative = self.narrate(question, merged, rows, tenant_id=tenant_id)

            value: float | None = None
            if len(rows) == 1 and len(rows[0]) == 1:
                (v,) = rows[0].values()
                try:
                    value = float(v)
                except (TypeError, ValueError):
                    value = None

            result = QueryResult(
                narrative=narrative,
                value=value,
                breakdown=rows,
                metric_used=merged,
                sql_executed=sql,
                data_rows=len(rows),
                execution_ms=execution_ms,
                tenant_id=tenant_id,
            )
        except Exception as e:
            if self.telemetry is not None:
                self.telemetry.log_query(
                    tenant_id=tenant_id,
                    question=question,
                    metric_id=plan.metric_id if plan else None,
                    applied_definition=merged.applied_definition if merged else None,
                    sql=sql,
                    execution_ms=execution_ms,
                    success=False,
                    error=f"{type(e).__name__}: {e}",
                    narrative=None,
                )
            raise

        if self.telemetry is not None:
            self.telemetry.log_query(
                tenant_id=tenant_id,
                question=question,
                metric_id=merged.id,
                applied_definition=merged.applied_definition,
                sql=sql,
                execution_ms=execution_ms,
                success=True,
                error=None,
                narrative=result.narrative,
            )

        self._cache[cache_key] = result
        return result


__all__ = ["Orchestrator", "PlannerError"]
