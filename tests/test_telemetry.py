import sqlite3

from semantic_layer.telemetry import Telemetry


def test_log_query_creates_row(tmp_path):
    db = tmp_path / "tel.db"
    tel = Telemetry(db_path=db)
    tel.log_query(
        tenant_id="lone-star",
        question="hello?",
        metric_id="metric.retention_rate.term_to_term.v1",
        applied_definition="tenant-override",
        sql="SELECT 1",
        execution_ms=12.5,
        success=True,
        error=None,
        narrative="ok",
    )
    con = sqlite3.connect(db)
    rows = con.execute("SELECT tenant_id, metric_id, success, narrative FROM queries").fetchall()
    assert rows == [("lone-star", "metric.retention_rate.term_to_term.v1", 1, "ok")]


def test_log_query_swallows_errors(tmp_path, capsys):
    # An unwritable parent (no permission, no exist) should not raise
    bad_path = tmp_path / "does-not-exist" / "tel.db"
    tel = Telemetry(db_path=bad_path)  # init should not raise
    tel.log_query(
        tenant_id=None,
        question="x",
        metric_id=None,
        applied_definition=None,
        sql=None,
        execution_ms=None,
        success=False,
        error="boom",
        narrative=None,
    )
    captured = capsys.readouterr()
    assert "telemetry" in captured.err
