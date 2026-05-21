import pytest

from semantic_layer.engine import SqlSafetyError, compile_sql, load_canonical


def test_compile_retention_produces_select():
    cat = load_canonical()
    sql = compile_sql(
        cat.metrics["metric.retention_rate.term_to_term.v1"],
        filters=[],
        dimensions=[],
    )
    upper = sql.strip().upper()
    assert upper.startswith("WITH") or upper.startswith("SELECT")
    assert "LIMIT" in upper


def test_compile_rejects_non_select():
    cat = load_canonical()
    m = cat.metrics["metric.retention_rate.term_to_term.v1"]
    bad = m.model_copy(update={"measure_sql": "DELETE FROM students"})
    with pytest.raises(SqlSafetyError):
        compile_sql(bad, filters=[], dimensions=[])


def test_compile_rejects_unknown_table():
    cat = load_canonical()
    m = cat.metrics["metric.fte.v1"]
    bad = m.model_copy(update={"measure_sql": "SELECT * FROM secret_table"})
    with pytest.raises(SqlSafetyError):
        compile_sql(bad, filters=[], dimensions=[])
