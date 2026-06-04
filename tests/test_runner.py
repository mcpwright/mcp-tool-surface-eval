"""End-to-end runner test with a scripted client (no API, no network)."""

from __future__ import annotations

from mcp_tool_surface_eval.fragmentation import fragment_surface
from mcp_tool_surface_eval.model_client import MockClient, ToolChoice
from mcp_tool_surface_eval.models import ToolSpec
from mcp_tool_surface_eval.report import render_report
from mcp_tool_surface_eval.runner import run_experiment
from mcp_tool_surface_eval.surfaces import load_base_surface
from mcp_tool_surface_eval.tasks import build_tasks


def test_oracle_client_scores_perfectly_on_both_surfaces() -> None:
    """A client that always picks the expected tool should score 100% everywhere.

    This proves the wiring (expected-answer plumbing, scoring) is correct,
    independent of any model's actual ability.
    """
    base = load_base_surface()
    fragmented, selector_map = fragment_surface(base)
    tasks = build_tasks(selector_map)

    # surface-aware oracle: pick the first expected tool for whichever surface's
    # tool list it was handed (identify the surface by its tool names).
    frag_names = fragmented.names()

    def oracle(prompt: str, tools: list[ToolSpec]) -> ToolChoice:
        sid = "fragmented" if {t.name for t in tools} == frag_names else "control"
        task = next(t for t in tasks if t.prompt == prompt)
        return ToolChoice(name=task.expected[sid][0])

    trials = run_experiment([base, fragmented], tasks, MockClient(policy=oracle))
    assert all(t.correct for t in trials)
    assert len(trials) == 2 * len(tasks)


def test_report_renders_summary_and_breakdown() -> None:
    base = load_base_surface()
    fragmented, selector_map = fragment_surface(base)
    tasks = build_tasks(selector_map)
    trials = run_experiment([base, fragmented], tasks, MockClient())
    report = render_report(
        [base, fragmented],
        tasks,
        trials,
        client_label="mock",
        trials_per_task=1,
        hypothesis="test",
    )
    assert "Tool-surface eval" in report
    assert "Per-task breakdown" in report
    assert "Control" in report
