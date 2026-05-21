"""Type vocabulary for the semantic layer. Nothing else defines pydantic models."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AppliedDefinition = Literal["canonical", "tenant-override"]


class Dimension(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    display_name: str
    sql: str  # column expression usable in GROUP BY


class Filter(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    sql: str  # WHERE-clause fragment


class Metric(BaseModel):
    """A canonical metric definition. Immutable."""

    model_config = ConfigDict(frozen=True)
    id: str
    version: str
    display_name: str
    description: str
    owner: str
    authority: str  # e.g. "vendor-canonical" or "tenant:lone-star"
    last_reviewed: date
    entity: str  # primary entity, e.g. "Student"
    measure_sql: str  # Jinja template producing a SQL SELECT
    default_filters: list[Filter] = Field(default_factory=list)
    valid_dimensions: list[Dimension] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    example_questions: list[str] = Field(default_factory=list)


class OverlayMetric(BaseModel):
    """A tenant override that references a canonical metric by ID."""

    model_config = ConfigDict(frozen=True)
    canonical_id: str
    owner: str  # tenant owner (e.g. "Lone Star Registrar's Office")
    last_reviewed: date
    diff_description: str  # human-readable summary of the override
    measure_sql: str | None = None
    extra_filters: list[Filter] = Field(default_factory=list)
    override_default_filters: list[Filter] | None = None


class MergedMetric(BaseModel):
    """The resolved metric used for a tenant request. Records provenance."""

    model_config = ConfigDict(frozen=True)
    id: str
    version: str
    applied_definition: AppliedDefinition
    canonical: Metric
    overlay: OverlayMetric | None = None
    effective_measure_sql: str
    effective_filters: list[Filter] = Field(default_factory=list)
    valid_dimensions: list[Dimension] = Field(default_factory=list)


class Glossary(BaseModel):
    model_config = ConfigDict(frozen=True)
    synonyms: dict[str, str]  # phrase -> metric_id


class CanonicalCatalog(BaseModel):
    metrics: dict[str, Metric]
    glossary: Glossary


class Tenant(BaseModel):
    id: str
    display_name: str
    overlays: dict[str, OverlayMetric]
    glossary: Glossary


class QueryPlan(BaseModel):
    metric_id: str
    filters: list[str] = Field(default_factory=list)  # filter IDs to apply
    dimensions: list[str] = Field(default_factory=list)  # dimension IDs to group by


class QueryResult(BaseModel):
    narrative: str
    value: float | None = None
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    metric_used: MergedMetric
    sql_executed: str
    data_rows: int
    tenant_id: str
