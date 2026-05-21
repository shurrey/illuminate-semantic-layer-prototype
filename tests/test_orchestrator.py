"""Tests for the Claude orchestrator. Uses unittest.mock to avoid live API calls."""

from unittest.mock import MagicMock

import pytest

from semantic_layer.engine import load_canonical
from semantic_layer.orchestrator import Orchestrator, PlannerError


def _mock_planner_response(metric_id: str, filters=None, dimensions=None):
    """Build a fake Anthropic response object whose first text block is JSON."""
    import json

    payload = {
        "metric_id": metric_id,
        "filters": filters or [],
        "dimensions": dimensions or [],
    }
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


def _mock_narrator_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_planner_returns_validated_query_plan():
    cat = load_canonical()
    client = MagicMock()
    client.messages.create.return_value = _mock_planner_response(
        "metric.retention_rate.term_to_term.v1"
    )
    orch = Orchestrator(client=client)
    plan = orch.plan("what's our retention rate?", cat, tenant=None)
    assert plan.metric_id == "metric.retention_rate.term_to_term.v1"
    assert plan.filters == []
    assert plan.dimensions == []


def test_planner_rejects_unknown_metric():
    cat = load_canonical()
    client = MagicMock()
    client.messages.create.return_value = _mock_planner_response("metric.nonsense.v1")
    orch = Orchestrator(client=client)
    with pytest.raises(PlannerError, match="unknown metric"):
        orch.plan("what?", cat, tenant=None)


def test_planner_rejects_invalid_dimension():
    cat = load_canonical()
    client = MagicMock()
    client.messages.create.return_value = _mock_planner_response(
        "metric.retention_rate.term_to_term.v1",
        dimensions=["not_a_real_dim"],
    )
    orch = Orchestrator(client=client)
    with pytest.raises(PlannerError, match="dimension"):
        orch.plan("retention by mystery", cat, tenant=None)


def test_narrator_blocks_non_aggregate():
    cat = load_canonical()
    from semantic_layer.engine import resolve

    merged = resolve(cat, None, "metric.fte.v1")
    client = MagicMock()
    client.messages.create.return_value = _mock_narrator_response("ok")
    orch = Orchestrator(client=client)
    huge = [{"x": i} for i in range(1001)]
    with pytest.raises(AssertionError, match="aggregate"):
        orch.narrate("q", merged, huge)


def test_narrator_returns_string_for_aggregated_rows():
    cat = load_canonical()
    from semantic_layer.engine import resolve

    merged = resolve(cat, None, "metric.fte.v1")
    client = MagicMock()
    client.messages.create.return_value = _mock_narrator_response(
        "Canonical FTE for Spring 2026 was approximately 3,335."
    )
    orch = Orchestrator(client=client)
    out = orch.narrate("q", merged, [{"term_id": "term_2026S", "fte": 3334.9}])
    assert "FTE" in out or "fte" in out.lower()
