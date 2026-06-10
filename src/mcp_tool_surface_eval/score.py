"""Scoring: aggregate trials into per-surface accuracy with a confidence interval."""

from __future__ import annotations

import math

from .models import AnswerArmResult, AnswerTrial, ArmResult, Surface, Trial


def wilson_interval(correct: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion (no scipy needed).

    Better than the normal approximation at small n and near 0/1, which is exactly
    where small eval runs live.
    """
    if n == 0:
        return (0.0, 0.0)
    phat = correct / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def aggregate(trials: list[Trial], surfaces: list[Surface]) -> list[ArmResult]:
    """Roll trials up to one ArmResult per surface, preserving surface order."""
    by_surface = {s.id: s for s in surfaces}
    results: list[ArmResult] = []
    for s in surfaces:
        s_trials = [t for t in trials if t.surface_id == s.id]
        results.append(
            ArmResult(
                surface_id=s.id,
                label=s.label,
                tool_count=by_surface[s.id].tool_count,
                trials=len(s_trials),
                correct=sum(1 for t in s_trials if t.correct),
            )
        )
    return results


def aggregate_answers(
    trials: list[AnswerTrial],
    surfaces: list[Surface],
    topcoded_ids: set[str],
) -> list[AnswerArmResult]:
    """Roll answer trials up per surface, split by top-coded vs ordinary tasks."""
    results: list[AnswerArmResult] = []
    for s in surfaces:
        st = [t for t in trials if t.surface_id == s.id]
        tc = [t for t in st if t.task_id in topcoded_ids]
        nm = [t for t in st if t.task_id not in topcoded_ids]
        results.append(
            AnswerArmResult(
                surface_id=s.id,
                label=s.label,
                trials=len(st),
                correct=sum(1 for t in st if t.correct),
                topcoded_trials=len(tc),
                topcoded_acknowledged=sum(1 for t in tc if t.acknowledged_cap),
                normal_trials=len(nm),
                normal_false_alarms=sum(1 for t in nm if t.acknowledged_cap),
                no_tool_trials=sum(1 for t in st if not t.tool_calls),
            )
        )
    return results
