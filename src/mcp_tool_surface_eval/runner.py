"""Run an experiment: every task against every surface, recording the choice.

No network here beyond whatever the ModelClient does — the few-tools experiment
elicits a *selection* and scores it by exact match against the task's expected
tool for that surface. It never executes the chosen tool, so it's cheap, fast, and
fully reproducible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import Trial

if TYPE_CHECKING:
    from collections.abc import Callable

    from .model_client import ModelClient
    from .models import Surface, Task


def run_experiment(
    surfaces: list[Surface],
    tasks: list[Task],
    client: ModelClient,
    trials_per_task: int = 1,
    on_trial: Callable[[Trial], None] | None = None,
) -> list[Trial]:
    """Run each (surface, task) `trials_per_task` times and score each choice.

    `trials_per_task` > 1 only varies the outcome for a stochastic client (e.g. a
    nonzero-temperature model); a deterministic client repeats itself. `on_trial`
    is an optional progress hook.
    """
    trials: list[Trial] = []
    for surface in surfaces:
        for task in tasks:
            expected = set(task.expected.get(surface.id, []))
            for _ in range(trials_per_task):
                choice = client.choose_tool(task.prompt, surface.tools)
                trial = Trial(
                    task_id=task.id,
                    surface_id=surface.id,
                    chosen_tool=choice.name,
                    correct=choice.name in expected,
                )
                trials.append(trial)
                if on_trial:
                    on_trial(trial)
    return trials
