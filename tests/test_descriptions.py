"""Descriptions experiment: surface stripping, grading, and the run loop."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mcp_tool_surface_eval.census_surface import (
    caveat_tool_count,
    load_census_surface,
    without_topcode_caveat,
)
from mcp_tool_surface_eval.descriptions import (
    acknowledges_cap,
    build_answer_tasks,
    grade,
    run_descriptions,
)
from mcp_tool_surface_eval.execution import execute
from mcp_tool_surface_eval.model_client import AgentOutcome, MockClient
from mcp_tool_surface_eval.score import aggregate_answers

# --- surfaces ----------------------------------------------------------------


def test_control_carries_the_topcode_caveat() -> None:
    control = load_census_surface()
    assert control.id == "control"
    assert caveat_tool_count(control) >= 2  # get_income + get_housing


def test_strip_removes_only_the_caveat_sentence() -> None:
    control = load_census_surface()
    stripped = without_topcode_caveat(control)
    assert stripped.tool_count == control.tool_count
    assert caveat_tool_count(stripped) == 0

    by_name = {t.name: t for t in stripped.tools}
    for ct in control.tools:
        st = by_name[ct.name]
        if "Note: ACS top-codes" in ct.description:
            # the kept text is a strict prefix of the original (nothing else changed)
            assert ct.description.startswith(st.description)
            assert len(st.description) < len(ct.description)
            assert "250,001" not in st.description
            assert "2,000,001" not in st.description
        else:
            assert st.description == ct.description  # untouched tools are identical


# --- grading -----------------------------------------------------------------


def test_acknowledges_cap_detects_hedging_language() -> None:
    for s in (
        "The median household income is $250,001 or more.",
        "It's at least $250,000 — the figure is top-coded.",
        "Home values there are capped at $2,000,000 in the data.",
        "The value of $250,001 is the ACS cap, so the true figure could be higher.",
        "Median home value: $2M+ (a reporting maximum).",
    ):
        assert acknowledges_cap(s), s


def test_acknowledges_cap_ignores_ordinary_and_200k_field_language() -> None:
    for s in (
        "The median household income in ZIP 43215 is $71,640.",
        "About 65.6% of households there earn $200k+.",  # legit field, not a cap
        "The median home value is $318,400.",
        "It's a ground-floor unit on the second floor of the building.",  # 'floor'
        "About 250,000+ people live in the surrounding county.",  # count, not $cap
    ):
        assert not acknowledges_cap(s), s


def test_grade_topcoded_vs_normal() -> None:
    tasks = {t.id: t for t in build_answer_tasks()}
    tc, nm = tasks["tc_income_1"], tasks["nm_income_1"]

    assert grade(tc, "It's $250,001 or more.") == (True, True)
    assert grade(tc, "It's exactly $250,001.") == (False, False)
    assert grade(nm, "It's $71,640.") == (False, True)
    assert grade(nm, "It's at least $71,640.") == (True, False)  # false alarm


# --- run loop ----------------------------------------------------------------


class _ScriptedAgent:
    """Returns a fixed answer regardless of input — for deterministic grading tests."""

    def __init__(self, answer: str, tool_calls: list[str] | None = None) -> None:
        self._answer = answer
        self._tool_calls = ["get_income"] if tool_calls is None else tool_calls

    def answer_with_tools(self, prompt, tools, executor, max_rounds=4):  # type: ignore[no-untyped-def]
        return AgentOutcome(answer=self._answer, tool_calls=list(self._tool_calls))


def test_run_descriptions_scores_a_perfect_caveat_aware_agent() -> None:
    control = load_census_surface()
    stripped = without_topcode_caveat(control)
    tasks = build_answer_tasks()
    # an agent that always hedges: right on top-coded tasks, false-alarms on normal
    trials = run_descriptions(
        [control, stripped], tasks, _ScriptedAgent("It's at least that — or more.")
    )
    assert len(trials) == 2 * len(tasks)
    topcoded_ids = {t.id for t in tasks if t.topcoded}
    results = aggregate_answers(trials, [control, stripped], topcoded_ids)
    for r in results:
        assert r.acknowledge_rate == 1.0  # caught every cap
        assert r.false_alarm_rate == 1.0  # but also flagged ordinary ones


def test_run_descriptions_with_mock_client_smoke() -> None:
    control = load_census_surface()
    tasks = build_answer_tasks()
    trials = run_descriptions([control], tasks, MockClient())
    assert len(trials) == len(tasks)
    # the mock never hedges, so it acknowledges no caps
    assert all(not t.acknowledged_cap for t in trials)


def test_no_tool_call_trials_are_recorded() -> None:
    control = load_census_surface()
    tasks = build_answer_tasks()
    # an agent that answers straight from priors, never calling a data tool
    trials = run_descriptions(
        [control], tasks, _ScriptedAgent("It's $250,001.", tool_calls=[])
    )
    assert all(t.tool_calls == [] for t in trials)
    topcoded_ids = {t.id for t in tasks if t.topcoded}
    [result] = aggregate_answers(trials, [control], topcoded_ids)
    assert result.no_tool_trials == len(tasks)


# --- real client loop (fake transport) ---------------------------------------


class _FakeMessages:
    def __init__(self, scripted: list[list[object]]) -> None:
        self._scripted = scripted
        self._i = 0

    def create(self, **_kwargs: object) -> SimpleNamespace:
        blocks = self._scripted[self._i]
        self._i += 1
        return SimpleNamespace(content=blocks)


class _FakeAnthropic:
    def __init__(self, scripted: list[list[object]]) -> None:
        self.messages = _FakeMessages(scripted)


def test_real_loop_feeds_tool_result_then_submits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-construction")
    from mcp_tool_surface_eval.model_client import AnthropicClient

    client = AnthropicClient()
    scripted: list[list[object]] = [
        [
            SimpleNamespace(
                type="tool_use",
                id="t1",
                name="get_income",
                input={"zip_code": "94027"},
            )
        ],
        [
            SimpleNamespace(
                type="tool_use",
                id="t2",
                name="submit_answer",
                input={"answer": "About $250,001 or more — it's top-coded."},
            )
        ],
    ]
    client._client = _FakeAnthropic(scripted)  # type: ignore[assignment]
    surface = load_census_surface()
    out = client.answer_with_tools("What's income in 94027?", surface.tools, execute)
    assert out.tool_calls == ["get_income"]
    assert "or more" in out.answer


def test_real_loop_rejects_max_rounds_below_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-construction")
    from mcp_tool_surface_eval.model_client import AnthropicClient

    client = AnthropicClient()
    client._client = _FakeAnthropic([])  # type: ignore[assignment]
    with pytest.raises(ValueError, match="max_rounds"):
        client.answer_with_tools(
            "q", load_census_surface().tools, execute, max_rounds=1
        )
