"""DuckDB connection and schema management. Knows nothing about metrics."""

from pathlib import Path

import duckdb

REQUIRED_TABLES = {
    "terms",
    "programs",
    "students",
    "courses",
    "sections",
    "enrollments",
    "activity",
    "degrees_conferred",
}

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS terms (
    term_id        VARCHAR PRIMARY KEY,
    name           VARCHAR NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    ordinal        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS programs (
    program_id     VARCHAR PRIMARY KEY,
    name           VARCHAR NOT NULL,
    level          VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id              VARCHAR PRIMARY KEY,
    first_enroll_term_id    VARCHAR REFERENCES terms(term_id),
    program_id              VARCHAR REFERENCES programs(program_id),
    is_degree_seeking       BOOLEAN NOT NULL,
    classification          VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    course_id      VARCHAR PRIMARY KEY,
    subject        VARCHAR NOT NULL,
    number         VARCHAR NOT NULL,
    title          VARCHAR NOT NULL,
    credit_hours   DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    section_id     VARCHAR PRIMARY KEY,
    course_id      VARCHAR REFERENCES courses(course_id),
    term_id        VARCHAR REFERENCES terms(term_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id    VARCHAR PRIMARY KEY,
    student_id       VARCHAR REFERENCES students(student_id),
    section_id       VARCHAR REFERENCES sections(section_id),
    term_id          VARCHAR REFERENCES terms(term_id),
    enrollment_type  VARCHAR NOT NULL,
    final_grade      VARCHAR,
    credit_hours     DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
    activity_id    VARCHAR PRIMARY KEY,
    student_id     VARCHAR REFERENCES students(student_id),
    term_id        VARCHAR REFERENCES terms(term_id),
    activity_date  DATE NOT NULL,
    kind           VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS degrees_conferred (
    student_id     VARCHAR REFERENCES students(student_id),
    program_id     VARCHAR REFERENCES programs(program_id),
    term_id        VARCHAR REFERENCES terms(term_id)
);
"""


def connect(db_path: Path | str = "data/seed.duckdb") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA_DDL)
    return con
