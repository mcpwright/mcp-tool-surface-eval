"""The descriptions experiment: does a top-code caveat change the answer?

Each task asks for a single dollar figure. For a `topcoded` ZIP the tool returns
the raw cap (median income $250,001, home value $2,000,001) with no annotation;
the honest answer must flag it as "at least." For a `normal` ZIP the value is
ordinary and flagging a cap would be a false alarm. We run a short agent loop
per (task, surface) and grade the final answer with a fixed, disclosed regex —
no LLM judge, mirroring the few-tools experiment's exact-match discipline.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .execution import execute
from .models import AnswerTask, AnswerTrial

if TYPE_CHECKING:
    from collections.abc import Callable

    from .model_client import AgentClient
    from .models import Surface

# Phrases that mark an answer as treating the figure as a floor/cap, not exact.
#
# Known limits of this list (disclosed deliberately — the grader is the linchpin):
#   - False positives: "$200k or more" describing a different field would match
#     "or more". We avoid this by NOT serving households_200k_plus_pct in the
#     income result (see execution.py), so that phrase shouldn't arise; the
#     ordinary-ZIP false-alarm rate in the report is the live check that it doesn't.
#   - Bare floor words ("a floor", "the floor", "floor of") are EXCLUDED — too
#     easily a building floor ("second floor of the building"). Only the
#     unambiguous "price floor" / "lower bound" are kept.
#   - False negatives: a model could convey the cap with novel phrasing this list
#     misses; that conservatively understates the caveat's effect (safe direction).
_CAP_PHRASES: tuple[str, ...] = (
    "top-cod",
    "top cod",
    "topcod",
    "top code",
    "top-code",
    "or more",
    "or higher",
    "or above",
    "or greater",
    "at least",
    "caps at",
    "capped",
    "cap of",
    "a cap",
    "the cap",
    "could be higher",
    "may be higher",
    "might be higher",
    "likely higher",
    "actually higher",
    "underestimat",
    "lower bound",
    "price floor",
    "censored",
    "maximum reported",
    "reporting limit",
)

# A cap *value* immediately followed by '+'. The comma forms ($250,000+ /
# $2,000,000+) require a leading '$' so a bare count like "250,000+ people" is
# NOT caught; the abbreviated forms (250k+, $2M+) are distinctive on their own.
# Anchored to 250 / 2,000,000 / 2M so the legitimate "$200k+" field language is
# never matched either.
_CAP_VALUE_RE = re.compile(
    r"(?:\$\s?(?:250[,]?000|2[,]?000[,]?000)|250\s?k|\$?\s?2\s?m(?:illion)?)\s*\+",
    re.IGNORECASE,
)


def acknowledges_cap(answer: str) -> bool:
    """True if the answer flags the figure as a cap/floor rather than exact."""
    low = answer.lower()
    if any(phrase in low for phrase in _CAP_PHRASES):
        return True
    return bool(_CAP_VALUE_RE.search(low))


# (id, prompt, zip, expected_tool, topcoded)
_TASK_DEFS: list[tuple[str, str, str, str, bool]] = [
    # Atherton 94027 — hits both ACS top-codes.
    (
        "tc_income_1",
        "What is the median household income in Atherton, California (ZIP 94027)?",
        "94027",
        "get_income",
        True,
    ),
    (
        "tc_income_2",
        "How much does a typical household in ZIP 94027 earn per year?",
        "94027",
        "get_income",
        True,
    ),
    (
        "tc_home_1",
        "What's the median home value in ZIP 94027 (Atherton, CA)?",
        "94027",
        "get_housing",
        True,
    ),
    (
        "tc_home_2",
        "What does a typical home cost in Atherton, 94027?",
        "94027",
        "get_housing",
        True,
    ),
    # Ordinary ZIPs — values well below either cap; flagging a cap is wrong.
    (
        "nm_income_1",
        "What is the median household income in ZIP 43215?",
        "43215",
        "get_income",
        False,
    ),
    (
        "nm_income_2",
        "What's the median household income in ZIP 78521 (Brownsville, TX)?",
        "78521",
        "get_income",
        False,
    ),
    (
        "nm_home_1",
        "What's the median home value in ZIP 43215?",
        "43215",
        "get_housing",
        False,
    ),
    (
        "nm_home_2",
        "What does a typical home cost in ZIP 78521?",
        "78521",
        "get_housing",
        False,
    ),
]


def build_answer_tasks() -> list[AnswerTask]:
    """The descriptions task set: top-coded and ordinary single-figure questions."""
    return [
        AnswerTask(
            id=tid,
            prompt=prompt,
            zip_code=zip_code,
            expected_tool=tool,
            topcoded=topcoded,
        )
        for tid, prompt, zip_code, tool, topcoded in _TASK_DEFS
    ]


def grade(task: AnswerTask, answer: str) -> tuple[bool, bool]:
    """Return ``(acknowledged_cap, correct)`` for one answer.

    A top-coded task is correct when the answer acknowledges the cap; a normal
    task is correct when it does *not* (no false alarm).
    """
    acknowledged = acknowledges_cap(answer)
    correct = acknowledged if task.topcoded else not acknowledged
    return acknowledged, correct


def run_descriptions(
    surfaces: list[Surface],
    tasks: list[AnswerTask],
    client: AgentClient,
    trials_per_task: int = 1,
    on_trial: Callable[[AnswerTrial], None] | None = None,
) -> list[AnswerTrial]:
    """Run each (surface, task) through the agent loop and grade the answer."""
    trials: list[AnswerTrial] = []
    for surface in surfaces:
        for task in tasks:
            for _ in range(trials_per_task):
                outcome = client.answer_with_tools(task.prompt, surface.tools, execute)
                acknowledged, correct = grade(task, outcome.answer)
                trial = AnswerTrial(
                    task_id=task.id,
                    surface_id=surface.id,
                    answer=outcome.answer,
                    tool_calls=outcome.tool_calls,
                    acknowledged_cap=acknowledged,
                    correct=correct,
                )
                trials.append(trial)
                if on_trial:
                    on_trial(trial)
    return trials
