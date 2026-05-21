"""Typer CLI for the semantic layer prototype.

Phase 1 uses a glossary substring stub to resolve NL questions to metric IDs.
Phase 2 (Task 6) replaces this with a Claude planner.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .engine import compile_sql, load_canonical, load_tenant, resolve
from .models import CanonicalCatalog, Tenant
from .warehouse import connect

app = typer.Typer(
    help="Illuminate semantic-layer prototype",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


@app.callback()
def _main(ctx: typer.Context) -> None:
    """Illuminate semantic-layer prototype CLI."""


def _resolve_metric_id(
    question: str,
    canonical: CanonicalCatalog,
    tenant: Tenant | None,
) -> str | None:
    """Pick a metric_id by substring-matching tenant glossary then canonical glossary.

    Phase 1 stub — Phase 2 replaces with a Claude planner.
    """
    q = question.lower()
    if tenant is not None:
        for phrase, mid in tenant.glossary.synonyms.items():
            if phrase.lower() in q:
                return mid
    for phrase, mid in canonical.glossary.synonyms.items():
        if phrase.lower() in q:
            return mid
    return None


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural-language question."),
    tenant: str | None = typer.Option(None, help="Tenant id (subdir of tenants/)."),
    db: Path = typer.Option(Path("data/seed.duckdb"), help="DuckDB path."),  # noqa: B008
) -> None:
    """Answer a question against canonical (+ overlay if tenant given).

    Phase 1: glossary-only resolution. Phase 2 swaps in the Claude planner.
    """
    canonical = load_canonical()
    tenant_obj = load_tenant(tenant) if tenant else None

    metric_id = _resolve_metric_id(question, canonical, tenant_obj)
    if metric_id is None:
        console.print(
            "[yellow]No matching metric in glossary. "
            "Phase 2 will replace this with the Claude planner.[/yellow]"
        )
        raise typer.Exit(code=1)

    merged = resolve(canonical, tenant_obj, metric_id)
    sql = compile_sql(merged, filters=merged.effective_filters, dimensions=[])

    con = connect(db)
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]

    console.rule(f"[bold]{merged.canonical.display_name}[/bold]")
    console.print(f"applied_definition: [cyan]{merged.applied_definition}[/cyan]")
    owner = merged.overlay.owner if merged.overlay else merged.canonical.owner
    console.print(f"owner: {owner}")
    if merged.overlay:
        console.print(f"overlay diff: [magenta]{merged.overlay.diff_description}[/magenta]")
    console.print(f"\n[dim]sql:[/dim]\n{sql}\n")

    table = Table(show_header=True, header_style="bold")
    for c in cols:
        table.add_column(c)
    for r in rows:
        table.add_row(*[str(v) for v in r])
    console.print(table)


if __name__ == "__main__":
    app()
