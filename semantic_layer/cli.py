"""Typer CLI for the semantic layer prototype.

Phase 1 uses a glossary substring stub to resolve NL questions to metric IDs.
Phase 2 (Task 6) branches on ANTHROPIC_API_KEY: uses the Claude orchestrator when
available, falls back to the glossary stub otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .engine import compile_sql, load_canonical, load_tenant, resolve
from .models import CanonicalCatalog, Tenant
from .orchestrator import Orchestrator
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

    Phase 1 stub — Phase 2 replaces with a Claude planner when ANTHROPIC_API_KEY is set.
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


def _print_query_result_glossary(rows, cols, merged) -> None:
    """Print result table for the glossary fallback path."""
    table = Table(show_header=True, header_style="bold")
    for c in cols:
        table.add_column(c)
    for r in rows:
        table.add_row(*[str(v) for v in r])
    console.print(table)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural-language question."),
    tenant: str | None = typer.Option(None, help="Tenant id (subdir of tenants/)."),
    db: Path = typer.Option(Path("data/seed.duckdb"), help="DuckDB path."),  # noqa: B008
) -> None:
    """Answer a question against canonical (+ overlay if tenant given).

    Uses the Claude orchestrator when ANTHROPIC_API_KEY is set; otherwise falls
    back to the Phase 1 glossary stub.
    """
    canonical = load_canonical()
    tenant_obj = load_tenant(tenant) if tenant else None
    con = connect(db)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if api_key:
        # -------------------------------------------------------------------
        # Phase 2: Claude orchestrator path
        # -------------------------------------------------------------------
        orch = Orchestrator()
        result = orch.ask(question, canonical, tenant_obj, con)
        merged = result.metric_used

        # Narrative heading
        console.rule(f"[bold]{merged.canonical.display_name}[/bold]")
        console.print()
        console.print(result.narrative)
        console.print()

        # Provenance panel
        owner = merged.overlay.owner if merged.overlay else merged.canonical.owner
        prov_lines = [
            f"metric_id:          {merged.id}",
            f"applied_definition: {merged.applied_definition}",
            f"owner:              {owner}",
        ]
        if merged.overlay:
            prov_lines.append(f"overlay_diff:       {merged.overlay.diff_description}")
        console.print(
            Panel(
                "\n".join(prov_lines),
                title="Provenance",
                expand=False,
                border_style="dim",
            )
        )
        console.print()

        # SQL block
        console.print("[dim]SQL executed:[/dim]")
        console.print(Syntax(result.sql_executed, "sql", theme="monokai", word_wrap=True))
        console.print()

        # Result table
        if result.breakdown:
            table = Table(show_header=True, header_style="bold cyan")
            for col in result.breakdown[0].keys():
                table.add_column(col)
            for row in result.breakdown:
                table.add_row(*[str(v) for v in row.values()])
            console.print(table)
        else:
            console.print("[yellow]No rows returned.[/yellow]")

    else:
        # -------------------------------------------------------------------
        # Phase 1: Glossary fallback path
        # -------------------------------------------------------------------
        console.print(
            "[yellow]Note: narrative requires ANTHROPIC_API_KEY — using glossary fallback.[/yellow]"
        )

        metric_id = _resolve_metric_id(question, canonical, tenant_obj)
        if metric_id is None:
            console.print(
                "[yellow]No matching metric in glossary. "
                "Phase 2 will replace this with the Claude planner.[/yellow]"
            )
            raise typer.Exit(code=1)

        merged = resolve(canonical, tenant_obj, metric_id)
        sql = compile_sql(merged, filters=merged.effective_filters, dimensions=[])

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
