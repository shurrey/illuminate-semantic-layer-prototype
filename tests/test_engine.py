from semantic_layer.engine import load_canonical


def test_canonical_loads_with_two_metrics():
    cat = load_canonical()
    ids = {m.id for m in cat.metrics.values()}
    assert "metric.retention_rate.term_to_term.v1" in ids
    assert "metric.fte.v1" in ids


def test_canonical_metric_has_required_provenance_fields():
    cat = load_canonical()
    m = cat.metrics["metric.retention_rate.term_to_term.v1"]
    assert m.owner
    assert m.last_reviewed
    assert m.measure_sql
    assert m.example_questions


def test_glossary_maps_canonical_synonyms():
    cat = load_canonical()
    assert cat.glossary.synonyms["retention"] == "metric.retention_rate.term_to_term.v1"
    assert cat.glossary.synonyms["fte"] == "metric.fte.v1"


def test_canonical_has_seven_metrics():
    cat = load_canonical()
    assert len(cat.metrics) == 7
    expected = {
        "metric.retention_rate.term_to_term.v1",
        "metric.fte.v1",
        "metric.active_student.v1",
        "metric.course_completion_rate.v1",
        "metric.at_risk_student_count.v1",
        "metric.average_time_to_degree.v1",
        "metric.dfw_rate.v1",
    }
    assert set(cat.metrics.keys()) == expected


def test_all_metric_sqls_compile():
    """Every canonical metric must compile to safe SELECT/CTE SQL."""
    from semantic_layer.engine import compile_sql

    cat = load_canonical()
    for mid, m in cat.metrics.items():
        sql = compile_sql(m, filters=[], dimensions=[])
        upper = sql.strip().upper()
        assert upper.startswith("WITH") or upper.startswith("SELECT"), (
            f"{mid} SQL does not start with WITH/SELECT"
        )
        assert "LIMIT" in upper, f"{mid} missing LIMIT"


def test_every_metric_synonym_is_in_canonical_glossary():
    """Each phrase listed in a metric's `synonyms` must route via the canonical glossary."""
    cat = load_canonical()
    for mid, m in cat.metrics.items():
        for phrase in m.synonyms:
            assert cat.glossary.synonyms.get(phrase) == mid, (
                f"metric {mid} declares synonym {phrase!r} but glossary "
                f"maps it to {cat.glossary.synonyms.get(phrase)!r}"
            )
