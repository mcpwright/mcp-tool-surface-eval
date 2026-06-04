"""Scoring + Wilson-interval tests."""

from __future__ import annotations

from mcp_tool_surface_eval.models import Surface, ToolSpec, Trial
from mcp_tool_surface_eval.score import aggregate, wilson_interval


def test_wilson_bounds_and_ordering() -> None:
    lo, hi = wilson_interval(8, 10)
    assert 0.0 <= lo < 0.8 < hi <= 1.0
    # all-correct still has a finite lower bound below 1
    lo2, hi2 = wilson_interval(10, 10)
    assert lo2 < 1.0 and hi2 == 1.0
    # empty
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_aggregate_counts_per_surface() -> None:
    surfaces = [
        Surface(id="control", label="c", tools=[ToolSpec(name="a", description="d")]),
        Surface(
            id="fragmented", label="f", tools=[ToolSpec(name="a", description="d")]
        ),
    ]
    trials = [
        Trial(task_id="t1", surface_id="control", chosen_tool="a", correct=True),
        Trial(task_id="t1", surface_id="fragmented", chosen_tool="b", correct=False),
    ]
    results = aggregate(trials, surfaces)
    assert [r.surface_id for r in results] == ["control", "fragmented"]
    assert results[0].correct == 1 and results[0].accuracy == 1.0
    assert results[1].correct == 0 and results[1].accuracy == 0.0
