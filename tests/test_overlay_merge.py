from semantic_layer.engine import compile_sql, load_canonical, load_tenant, resolve


def test_lone_star_overlay_resolves_with_provenance():
    cat = load_canonical()
    tenant = load_tenant("lone-star")
    merged = resolve(cat, tenant, "metric.retention_rate.term_to_term.v1")

    assert merged.applied_definition == "tenant-override"
    assert merged.overlay is not None
    assert merged.overlay.owner == "Lone Star Registrar's Office"
    assert "degree-seeking" in merged.overlay.diff_description.lower()
    assert merged.effective_measure_sql != merged.canonical.measure_sql


def test_canonical_metric_object_is_not_mutated_by_overlay():
    cat = load_canonical()
    canonical_sql_before = cat.metrics["metric.retention_rate.term_to_term.v1"].measure_sql
    tenant = load_tenant("lone-star")
    _ = resolve(cat, tenant, "metric.retention_rate.term_to_term.v1")
    canonical_sql_after = cat.metrics["metric.retention_rate.term_to_term.v1"].measure_sql
    assert canonical_sql_before == canonical_sql_after


def test_metric_with_no_overlay_resolves_canonical():
    cat = load_canonical()
    tenant = load_tenant("lone-star")
    merged = resolve(cat, tenant, "metric.fte.v1")
    assert merged.applied_definition == "canonical"
    assert merged.overlay is None


def test_lone_star_glossary_persistence_synonym():
    tenant = load_tenant("lone-star")
    assert tenant.glossary.synonyms["persistence"] == "metric.retention_rate.term_to_term.v1"


def test_overlay_sql_compiles_to_safe_select():
    cat = load_canonical()
    tenant = load_tenant("lone-star")
    merged = resolve(cat, tenant, "metric.retention_rate.term_to_term.v1")
    sql = compile_sql(merged, filters=[], dimensions=[])
    upper = sql.strip().upper()
    assert upper.startswith("WITH")
    assert "LIMIT" in upper


def test_midwest_state_fte_overrides_divisor():
    cat = load_canonical()
    tenant = load_tenant("midwest-state")
    merged = resolve(cat, tenant, "metric.fte.v1")
    assert merged.applied_definition == "tenant-override"
    assert "/ 15" in merged.effective_measure_sql or "/15" in merged.effective_measure_sql
    assert "/ 12" not in merged.effective_measure_sql


def test_midwest_state_completion_excludes_audits():
    cat = load_canonical()
    tenant = load_tenant("midwest-state")
    merged = resolve(cat, tenant, "metric.course_completion_rate.v1")
    assert merged.applied_definition == "tenant-override"
    # Canonical is inclusive of all enrollment types — no type filter at all.
    assert "enrollment_type" not in merged.canonical.measure_sql
    # Overlay restricts the denominator to credit enrollments.
    assert "enrollment_type = 'credit'" in merged.effective_measure_sql


def test_midwest_state_no_retention_override_falls_back_canonical():
    cat = load_canonical()
    tenant = load_tenant("midwest-state")
    merged = resolve(cat, tenant, "metric.retention_rate.term_to_term.v1")
    assert merged.applied_definition == "canonical"
    assert merged.overlay is None


def test_midwest_state_first_year_retention_synonym():
    tenant = load_tenant("midwest-state")
    assert (
        tenant.glossary.synonyms["first-year retention"] == "metric.retention_rate.term_to_term.v1"
    )
