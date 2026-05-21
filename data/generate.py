"""Deterministic synthetic higher-ed warehouse generator. Seed = 42."""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from semantic_layer.warehouse import connect

SEED = 42
N_STUDENTS = 5_000
N_COURSES = 200
N_SECTIONS_PER_TERM = 250

TERMS = [
    ("term_2024F", "Fall 2024", date(2024, 8, 26), date(2024, 12, 13), 1),
    ("term_2025S", "Spring 2025", date(2025, 1, 13), date(2025, 5, 9), 2),
    ("term_2025F", "Fall 2025", date(2025, 8, 25), date(2025, 12, 12), 3),
    ("term_2026S", "Spring 2026", date(2026, 1, 12), date(2026, 5, 8), 4),
]

PROGRAMS = [
    ("prog_ba_cs", "BA Computer Science", "undergrad"),
    ("prog_ba_bus", "BA Business", "undergrad"),
    ("prog_aa_lib", "AA Liberal Arts", "undergrad"),
    ("prog_cert_it", "IT Certificate", "certificate"),
    ("prog_ms_cs", "MS Computer Science", "grad"),
]

CLASSIFICATIONS = ["first_year", "sophomore", "junior", "senior", "grad", "non_degree"]

SUBJECTS = ["CS", "MATH", "ENGL", "BUS", "BIO", "PSYC", "HIST", "ART"]


def main(db_path: str = "data/seed.duckdb") -> None:
    rng = random.Random(SEED)
    Path("data").mkdir(exist_ok=True)
    Path(db_path).unlink(missing_ok=True)
    con = connect(db_path)

    # terms
    con.executemany("INSERT INTO terms VALUES (?,?,?,?,?)", TERMS)

    # programs
    con.executemany("INSERT INTO programs VALUES (?,?,?)", PROGRAMS)

    # students — 5000 with biased credit-hour patterns to make FTE interesting
    students = []
    for i in range(N_STUDENTS):
        sid = f"stu_{i:05d}"
        first_term = rng.choice(TERMS)[0]
        program = rng.choices(
            [p[0] for p in PROGRAMS],
            weights=[3, 3, 2, 1, 1],
        )[0]
        is_ds = rng.random() < 0.85
        classif = rng.choices(
            CLASSIFICATIONS,
            weights=[25, 20, 15, 10, 10, 20],
        )[0]
        students.append((sid, first_term, program, is_ds, classif))
    con.executemany("INSERT INTO students VALUES (?,?,?,?,?)", students)

    # courses
    courses = []
    for i in range(N_COURSES):
        cid = f"crs_{i:04d}"
        subj = rng.choice(SUBJECTS)
        num = f"{rng.randint(100, 499)}"
        title = f"{subj} {num}"
        # bimodal credit-hour distribution so 12 vs 15 credit FTE formulas diverge meaningfully
        credit = rng.choice([3.0, 3.0, 3.0, 4.0, 1.5])
        courses.append((cid, subj, num, title, credit))
    con.executemany("INSERT INTO courses VALUES (?,?,?,?,?)", courses)

    # sections — N_SECTIONS_PER_TERM per term
    sections = []
    for term_id, *_ in TERMS:
        for s in range(N_SECTIONS_PER_TERM):
            sec_id = f"sec_{term_id}_{s:04d}"
            course = rng.choice(courses)[0]
            sections.append((sec_id, course, term_id))
    con.executemany("INSERT INTO sections VALUES (?,?,?)", sections)

    # enrollments — each active student takes 3-5 sections per term they're active in.
    # Deliberate 75% term-to-term retention baseline; ~25% of students in term N
    # do NOT enroll in N+1.
    enrollments = []
    activity_rows = []
    eid = 0
    aid = 0
    students_by_id = {s[0]: s for s in students}
    course_credits = {c[0]: c[4] for c in courses}
    section_by_id = {s[0]: s for s in sections}
    sections_by_term: dict[str, list[str]] = {}
    for sec_id, _course, term_id in sections:
        sections_by_term.setdefault(term_id, []).append(sec_id)

    for sid, first_term, *_ in students:
        first_idx = next(i for i, t in enumerate(TERMS) if t[0] == first_term)
        enrolled_terms = [TERMS[first_idx][0]]
        for next_idx in range(first_idx + 1, len(TERMS)):
            stay = rng.random() < 0.75
            if not stay:
                break
            enrolled_terms.append(TERMS[next_idx][0])

        for term_id in enrolled_terms:
            n_sections = rng.randint(3, 5)
            picks = rng.sample(sections_by_term[term_id], n_sections)
            for sec_id in picks:
                course_id = section_by_id[sec_id][1]
                credit = course_credits[course_id]
                enr_type = "audit" if rng.random() < 0.05 else "credit"
                grade = rng.choices(
                    ["A", "B", "C", "D", "F", "W", None],
                    weights=[25, 30, 20, 8, 5, 7, 5],
                )[0]
                enrollments.append(
                    (f"enr_{eid:07d}", sid, sec_id, term_id, enr_type, grade, credit)
                )
                eid += 1

            t = next(t for t in TERMS if t[0] == term_id)
            term_start, term_end = t[2], t[3]
            n_events = rng.randint(1, 60)
            for _ in range(n_events):
                day = term_start + timedelta(days=rng.randint(0, (term_end - term_start).days))
                activity_rows.append(
                    (
                        f"act_{aid:08d}",
                        sid,
                        term_id,
                        day,
                        rng.choice(["login", "assignment_submit", "discussion_post", "page_view"]),
                    )
                )
                aid += 1

    con.executemany("INSERT INTO enrollments VALUES (?,?,?,?,?,?,?)", enrollments)
    con.executemany("INSERT INTO activity VALUES (?,?,?,?,?)", activity_rows)

    # degrees_conferred — small number of students complete in 2026S
    seniors = [s[0] for s in students if s[4] == "senior"]
    completers = rng.sample(seniors, k=min(200, len(seniors)))
    degrees = [(sid, students_by_id[sid][2], "term_2026S") for sid in completers]
    con.executemany("INSERT INTO degrees_conferred VALUES (?,?,?)", degrees)

    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in [
            "terms",
            "programs",
            "students",
            "courses",
            "sections",
            "enrollments",
            "activity",
            "degrees_conferred",
        ]
    }
    print("Seeded:", counts)


if __name__ == "__main__":
    main()
