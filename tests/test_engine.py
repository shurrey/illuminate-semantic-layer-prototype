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
