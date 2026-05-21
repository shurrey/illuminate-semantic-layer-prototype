from semantic_layer.engine import load_canonical, load_tenant, resolve


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
