"""FastAPI service exposing the semantic-layer orchestrator.

Endpoints:
- POST /ask  body {"tenant_id": "...", "question": "..."} -> QueryResult JSON
- GET  /tenants -> list of available tenant ids
- GET  /metrics -> list of canonical metric metadata
- GET  /        -> serves ui/index.html
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .engine import TENANTS_DIR, SqlSafetyError, load_canonical, load_tenant
from .models import QueryResult
from .orchestrator import Orchestrator, PlannerError
from .telemetry import Telemetry
from .warehouse import connect

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_UI_INDEX = _PROJECT_ROOT / "ui" / "index.html"
_DB_PATH = _PROJECT_ROOT / "data" / "seed.duckdb"


class AskRequest(BaseModel):
    tenant_id: str | None = None
    question: str


app = FastAPI(title="Illuminate Semantic Layer Demo")
_tel = Telemetry()
_orchestrator: Orchestrator | None = None


def _get_orchestrator() -> Orchestrator:
    """Lazy-construct the orchestrator only on first /ask hit so the server
    starts even without ANTHROPIC_API_KEY (UI for /tenants, /metrics still works)."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(telemetry=_tel)
    return _orchestrator


@app.get("/")
def root() -> FileResponse:
    if not _UI_INDEX.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(_UI_INDEX)


@app.get("/tenants")
def list_tenants() -> dict:
    if not TENANTS_DIR.exists():
        return {"tenants": []}
    ids = [
        d.name for d in sorted(TENANTS_DIR.iterdir()) if d.is_dir() and (d / "tenant.yaml").exists()
    ]
    return {"tenants": ids}


@app.get("/metrics")
def list_metrics() -> dict:
    cat = load_canonical()
    return {
        "metrics": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "description": m.description.strip(),
                "synonyms": m.synonyms,
            }
            for m in cat.metrics.values()
        ]
    }


@app.post("/ask")
def ask(req: AskRequest) -> QueryResult:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not set; this endpoint requires the Claude orchestrator.",
        )
    canonical = load_canonical()
    tenant_obj = load_tenant(req.tenant_id) if req.tenant_id else None
    con = connect(_DB_PATH)
    orch = _get_orchestrator()
    try:
        return orch.ask(req.question, canonical, tenant_obj, con)
    except PlannerError as e:
        raise HTTPException(status_code=400, detail=f"planner error: {e}") from e
    except SqlSafetyError as e:
        raise HTTPException(status_code=422, detail=f"unsafe SQL in metric definition: {e}") from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"tenant not found: {e}") from e
    finally:
        con.close()
