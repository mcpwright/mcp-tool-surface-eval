"""Command-line entry point.

uv run mcp-tool-surface-eval few-tools --client mock
ANTHROPIC_API_KEY=… uv run mcp-tool-surface-eval few-tools --client anthropic --trials 5 --out report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .census_surface import (
    caveat_tool_count,
    load_census_surface,
    without_topcode_caveat,
)
from .descriptions import build_answer_tasks, run_descriptions
from .fragmentation import fragment_surface
from .model_client import AnthropicClient, MockClient
from .report import render_descriptions_report, render_report
from .runner import run_experiment
from .surfaces import load_base_surface
from .tasks import build_tasks

_FEW_TOOLS_HYPOTHESIS = (
    "Few orthogonal tools beat many specific ones: presenting the same EDGAR "
    "capability as a small parameterized surface yields higher tool-selection "
    "accuracy than an equivalent surface split one-tool-per-form/metric."
)

_DESCRIPTIONS_HYPOTHESIS = (
    "A behavioral caveat in a tool description changes behavior: telling the "
    "model that ACS top-codes income/home-value makes it flag a capped value as "
    '"at least" instead of reporting it as an exact figure.'
)


def _make_client(name: str, model: str) -> tuple[MockClient | AnthropicClient, str]:
    if name == "mock":
        return MockClient(), "mock (keyword heuristic — NOT a language model)"
    if name == "anthropic":
        return AnthropicClient(model=model), model
    raise SystemExit(f"unknown client {name!r}")


def _run_few_tools(args: argparse.Namespace) -> str:
    base = load_base_surface()
    fragmented, selector_map = fragment_surface(base)
    tasks = build_tasks(selector_map)
    client, client_label = _make_client(args.client, args.model)

    done = [0]
    total = 2 * len(tasks) * args.trials

    def progress(_trial: object) -> None:
        done[0] += 1
        print(f"\r  {done[0]}/{total} trials", end="", file=sys.stderr, flush=True)

    trials = run_experiment(
        [base, fragmented],
        tasks,
        client,
        trials_per_task=args.trials,
        on_trial=progress,
    )
    print("", file=sys.stderr)
    return render_report(
        [base, fragmented],
        tasks,
        trials,
        client_label=client_label,
        trials_per_task=args.trials,
        hypothesis=_FEW_TOOLS_HYPOTHESIS,
    )


def _run_descriptions(args: argparse.Namespace) -> str:
    control = load_census_surface()
    stripped = without_topcode_caveat(control)
    if caveat_tool_count(control) == 0:
        raise SystemExit(
            "census fixture carries no top-code caveat — re-capture data/census_tools.json "
            "from a census-mcp that documents the ACS top-code."
        )
    tasks = build_answer_tasks()
    client, client_label = _make_client(args.client, args.model)

    done = [0]
    total = 2 * len(tasks) * args.trials

    def progress(_trial: object) -> None:
        done[0] += 1
        print(f"\r  {done[0]}/{total} runs", end="", file=sys.stderr, flush=True)

    trials = run_descriptions(
        [control, stripped],
        tasks,
        client,
        trials_per_task=args.trials,
        on_trial=progress,
    )
    print("", file=sys.stderr)
    return render_descriptions_report(
        [control, stripped],
        tasks,
        trials,
        client_label=client_label,
        trials_per_task=args.trials,
        hypothesis=_DESCRIPTIONS_HYPOTHESIS,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mcp-tool-surface-eval")
    sub = parser.add_subparsers(dest="experiment", required=True)

    ft = sub.add_parser("few-tools", help="few orthogonal tools vs many specific ones")
    ft.add_argument("--client", choices=["mock", "anthropic"], default="mock")
    ft.add_argument("--model", default="claude-sonnet-4-6")
    ft.add_argument("--trials", type=int, default=1, help="trials per (task, surface)")
    ft.add_argument("--out", help="write the report here (default: stdout)")

    de = sub.add_parser(
        "descriptions", help="does a top-code caveat in a description change the answer"
    )
    de.add_argument("--client", choices=["mock", "anthropic"], default="mock")
    de.add_argument("--model", default="claude-sonnet-4-6")
    de.add_argument("--trials", type=int, default=1, help="trials per (task, surface)")
    de.add_argument("--out", help="write the report here (default: stdout)")

    args = parser.parse_args(argv)

    if args.experiment == "few-tools":
        report = _run_few_tools(args)
    elif args.experiment == "descriptions":
        report = _run_descriptions(args)
    else:  # pragma: no cover - argparse guards this
        parser.error(f"unknown experiment {args.experiment!r}")

    if getattr(args, "out", None):
        with Path(args.out).open("w") as fh:
            fh.write(report)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
