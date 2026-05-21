from semantic_layer.warehouse import REQUIRED_TABLES, connect


def test_schema_creates_required_tables(tmp_path):
    db = tmp_path / "test.duckdb"
    con = connect(db)
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert REQUIRED_TABLES <= names, f"missing tables: {REQUIRED_TABLES - names}"
