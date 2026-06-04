"""Render an experiment's trials into a Markdown report."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from .score import aggregate, wilson_interval

if TYPE_CHECKING:
    from .models import ArmResult, Surface, Task, Trial


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
