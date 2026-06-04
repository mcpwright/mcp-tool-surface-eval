# mcp-tool-surface-eval — working agreement

An offline eval harness that measures the tool-surface design claims from the essay
[**What Makes a Good MCP Tool Surface for an LLM**](https://devender.me/2026/06/04/good-mcp-tool-surface/).
It is part of the **mcpwright** project (`github.com/mcpwright`) but is **not** an MCP
server — it has no tools, no Registry entry, and no MCPB bundle. Its product is
*evidence*: accuracy numbers and a report that back a public, falsifiable claim.

## Non-negotiable policies

- **Evidential integrity comes first.** A change must never make one surface easier to
  score than the other, cripple a fragmented split so the comparison stops being
  faithful, or let a result look stronger than the data supports. Fragments stay
  faithful; `expected` answers match what the prompt asks; scoring is apples-to-apples;
  small-N results are reported with their (overlapping) confidence intervals, not as
  wins.
- **No secrets, ever.** The only credential is `ANTHROPIC_API_KEY`, read from the
  environment. It must never be written to a committed file, a report, a log, an error,
  or a test fixture. `report*.md` and `.env` are gitignored; keep them that way.
- **Mock results are not findings.** `MockClient` (a keyword heuristic) exists to run
  and test the pipeline without a key. Only `--client anthropic` runs produce numbers
  worth citing, and the harness labels mock output accordingly.
- **Lots of unit tests, no network in them.** Every scoring/fragmentation/wiring
  invariant has a test (including the oracle check that proves scoring is correct
  independent of any model). New behavior ships with its tests in the same PR. Tests
  must not require a key or a network. `pytest -v` green before a PR opens.
- **PR per change, CI-gated.** Standard flow:
  **feature branch → code → code-review subagent → fold in findings → PR → CI green → squash-merge.**
  - *Code-review subagent:* before opening the PR, review the diff with the
    **`code-reviewer`** subagent (`.claude/agents/code-reviewer.md`) — or run
    **`/review-pr`**. It runs in a **fresh context** and returns severity-tagged findings
    (**Blocker / High / Medium / Low**); address Blocker/High before the PR opens.
  - *Merge:* `Code Quality & Tests` green and branch up to date → squash-merge with a
    `(#N)` suffix. `main` is branch-protected; **no direct pushes**.
  - *Commits:* imperative subject + short body, ending with the dual trailer
    (`Co-authored-by: Devender …` + `Co-authored-by: Claude …`).
- **Green locally before pushing:**
  ```bash
  uv run ruff check src/ && uv run ruff format --check src/ && uv run mypy && uv run pytest -v
  ```
  `uv run pre-commit run --all-files` mirrors CI (ruff, ruff-format, mypy, detect-secrets, hygiene).

## Layout

```
data/edgar_tools.json      captured real edgar tool schemas (the control surface)
src/mcp_tool_surface_eval/
  models.py        ToolSpec / Surface / Task / Trial / ArmResult
  surfaces.py      load the control surface; strip_caveats transform
  fragmentation.py the explicit edgar fragmentation rules + applier
  tasks.py         the task set, with per-surface expected answers
  model_client.py  ModelClient protocol; AnthropicClient (real) + MockClient
  runner.py        run every (surface, task); score each choice
  score.py         aggregate + Wilson confidence interval
  report.py        Markdown report (summary table + per-task breakdown)
  cli.py           `few-tools` subcommand
results/           committed run results (the published evidence)
tests/             oracle / scoring / fragmentation tests (no network)
```

## Experiments

- **few-tools** — implemented and wired. Few orthogonal tools vs. the same capability
  fragmented one-tool-per-form/metric, scored on tool-selection accuracy.
- **descriptions** — scaffolded only (`surfaces.strip_caveats` builds the no-caveat
  arm). Wiring it needs tool *execution* + answer grading, which the few-tools path
  deliberately avoids. This is the next build.
