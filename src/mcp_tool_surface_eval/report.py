"""Render an experiment's trials into a Markdown report."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from .score import aggregate, aggregate_answers, wilson_interval

if TYPE_CHECKING:
    from .models import AnswerTask, AnswerTrial, ArmResult, Surface, Task, Trial


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _summary_table(results: list[ArmResult]) -> str:
    rows = [
        "| Surface | Tools | Trials | Correct | Tool-selection accuracy | 95% CI |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for r in results:
        lo, hi = wilson_interval(r.correct, r.trials)
        rows.append(
            f"| {r.label} | {r.tool_count} | {r.trials} | {r.correct} | "
            f"**{_pct(r.accuracy)}** | {_pct(lo)}–{_pct(hi)} |"
        )
    return "\n".join(rows)


def _majority_choice(trials: list[Trial]) -> str | None:
    names = [t.chosen_tool for t in trials if t.chosen_tool is not None]
    if not names:
        return None
    return Counter(names).most_common(1)[0][0]


def _per_task_table(
    tasks: list[Task], trials: list[Trial], surfaces: list[Surface]
) -> str:
    sids = [s.id for s in surfaces]
    head = ["Task", "Prompt"] + [f"{s.id} ✓/chose" for s in surfaces]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for task in tasks:
        cells = [task.id, task.prompt[:54] + ("…" if len(task.prompt) > 54 else "")]
        for sid in sids:
            t = [tr for tr in trials if tr.task_id == task.id and tr.surface_id == sid]
            ok = all(tr.correct for tr in t) if t else False
            chose = _majority_choice(t) or "—"
            mark = "✓" if ok else "✗"
            cells.append(f"{mark} `{chose}`")
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def render_report(
    surfaces: list[Surface],
    tasks: list[Task],
    trials: list[Trial],
    *,
    client_label: str,
    trials_per_task: int,
    hypothesis: str,
) -> str:
    results = aggregate(trials, surfaces)
    control = next((r for r in results if r.surface_id == "control"), None)
    other = next((r for r in results if r.surface_id != "control"), None)

    parts = [
        "# Tool-surface eval — results",
        "",
        f"**Hypothesis.** {hypothesis}",
        "",
        f"- Model / client: `{client_label}`",
        f"- Tasks: {len(tasks)} · trials per (task, surface): {trials_per_task}",
        "",
        "## Summary",
        "",
        _summary_table(results),
        "",
    ]
    if control and other:
        delta = control.accuracy - other.accuracy
        verb = "higher" if delta > 0 else ("lower" if delta < 0 else "equal")
        parts += [
            f"**Result.** The control ({control.tool_count} tools) scored "
            f"{_pct(control.accuracy)} vs {_pct(other.accuracy)} for the "
            f"{other.tool_count}-tool variant — {_pct(abs(delta))} {verb}.",
            "",
        ]
    parts += [
        "## Per-task breakdown",
        "",
        _per_task_table(tasks, trials, surfaces),
        "",
        "_✓ = model chose a tool in the expected set for that surface._",
    ]
    return "\n".join(parts)


def _answer_summary_table(results: list) -> str:
    rows = [
        "| Surface | Cap-ack rate (top-coded) | 95% CI | False-alarm rate (ordinary) "
        "| Overall correct |",
        "|---|--:|--:|--:|--:|",
    ]
    for r in results:
        lo, hi = wilson_interval(r.topcoded_acknowledged, r.topcoded_trials)
        rows.append(
            f"| {r.label} | **{_pct(r.acknowledge_rate)}** "
            f"({r.topcoded_acknowledged}/{r.topcoded_trials}) | {_pct(lo)}–{_pct(hi)} "
            f"| {_pct(r.false_alarm_rate)} ({r.normal_false_alarms}/{r.normal_trials}) "
            f"| {_pct(r.accuracy)} |"
        )
    return "\n".join(rows)


def _answer_per_task_table(
    tasks: list[AnswerTask], trials: list[AnswerTrial], surfaces: list[Surface]
) -> str:
    sids = [s.id for s in surfaces]
    head = ["Task", "Kind", "Prompt"] + [f"{s.id} ack?" for s in surfaces]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for task in tasks:
        kind = "top-coded" if task.topcoded else "ordinary"
        cells = [
            task.id,
            kind,
            task.prompt[:46] + ("…" if len(task.prompt) > 46 else ""),
        ]
        for sid in sids:
            t = [tr for tr in trials if tr.task_id == task.id and tr.surface_id == sid]
            acked = sum(1 for tr in t if tr.acknowledged_cap)
            ok = all(tr.correct for tr in t) if t else False
            mark = "✓" if ok else "✗"
            cells.append(f"{mark} {acked}/{len(t)}")
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def render_descriptions_report(
    surfaces: list[Surface],
    tasks: list[AnswerTask],
    trials: list[AnswerTrial],
    *,
    client_label: str,
    trials_per_task: int,
    hypothesis: str,
) -> str:
    """Render the descriptions experiment's answer trials into Markdown."""
    topcoded_ids = {t.id for t in tasks if t.topcoded}
    results = aggregate_answers(trials, surfaces, topcoded_ids)
    control = next((r for r in results if r.surface_id == "control"), None)
    stripped = next((r for r in results if r.surface_id != "control"), None)

    parts = [
        "# Descriptions eval — results",
        "",
        f"**Hypothesis.** {hypothesis}",
        "",
        f"- Model / client: `{client_label}`",
        f"- Tasks: {len(tasks)} "
        f"({len(topcoded_ids)} top-coded, {len(tasks) - len(topcoded_ids)} ordinary) "
        f"· trials per (task, surface): {trials_per_task}",
        "- Grading: deterministic regex for cap-acknowledging language (no LLM judge).",
        "",
        "## Summary",
        "",
        _answer_summary_table(results),
        "",
    ]
    if control and stripped:
        delta = control.acknowledge_rate - stripped.acknowledge_rate
        if delta > 0:
            tail = f"the caveat added {_pct(delta)}."
        elif delta < 0:
            tail = (
                f"*higher without* the caveat by {_pct(-delta)} — an inverted result."
            )
        else:
            tail = "identical — the caveat made no difference."
        parts += [
            f"**Result.** With the caveat in the description, the model flagged the "
            f"top-coded value as a cap {_pct(control.acknowledge_rate)} of the time, "
            f"vs {_pct(stripped.acknowledge_rate)} without it — {tail}",
            "",
        ]
    no_tool = sum(r.no_tool_trials for r in results)
    if no_tool:
        parts += [
            f"_Note: {no_tool} trial(s) answered without calling any data tool "
            "(answered from the model's priors, not the tool result)._",
            "",
        ]
    parts += [
        "## Per-task breakdown",
        "",
        _answer_per_task_table(tasks, trials, surfaces),
        "",
        "_✓ = correct (top-coded → acknowledged the cap; ordinary → did not). "
        "`n/m` = answers that acknowledged a cap, of trials._",
    ]
    return "\n".join(parts)
