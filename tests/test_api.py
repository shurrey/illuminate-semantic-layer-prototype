"""Smoke tests for the FastAPI service.

Uses TestClient (no live server). The /ask endpoint is exercised with the
ANTHROPIC_API_KEY env var explicitly unset so it returns 503 without
attempting a live Claude call. We do not cover the orchestrator-happy path
here — that's exercised by tests/test_orchestrator.py with a mocked client.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from semantic_layer.api import app


@pytest.fixture
def client(monkeypatch) -> TestClient:
    # Ensure the /ask endpoint takes the no-key branch deterministically.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return TestClient(app)


def test_get_tenants_returns_both_tenants(client):
    r = client.get("/tenants")
    assert r.status_code == 200
    body = r.json()
    assert "tenants" in body
    assert set(body["tenants"]) == {"lone-star", "midwest-state"}


def test_get_metrics_returns_seven_with_required_fields(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "metrics" in body
    assert len(body["metrics"]) == 7
    for m in body["metrics"]:
        assert {"id", "display_name", "description", "synonyms"} <= m.keys()


def test_root_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "html" in r.headers.get("content-type", "").lower()
    assert "Illuminate Semantic Layer Demo" in r.text


def test_post_ask_without_api_key_returns_503(client):
    # The fixture has already cleared ANTHROPIC_API_KEY.
    assert not os.environ.get("ANTHROPIC_API_KEY", "")
    r = client.post("/ask", json={"tenant_id": "lone-star", "question": "retention"})
    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_post_ask_rejects_missing_question(client):
    r = client.post("/ask", json={"tenant_id": "lone-star"})
    assert r.status_code == 422  # pydantic validation
