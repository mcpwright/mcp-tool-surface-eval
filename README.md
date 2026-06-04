# mcp-tool-surface-eval

An eval harness that measures the tool-surface design claims from the essay
[**What Makes a Good MCP Tool Surface for an LLM**](https://devender.me/2026/06/04/good-mcp-tool-surface/).

The essay argues for specific design principles (few orthogonal tools, lean returns,
descriptions-as-API, honest read-only, zero-config). Most of those were stated as
arguments, not measured. This harness exists to turn the *behavioral* ones into
numbers — and to publish those numbers honestly, including the ones that don't
flatter the principle.

## The few-tools experiment (implemented)

> **Hypothesis.** Few orthogonal tools beat many specific ones: presenting the same
> EDGAR capability as a small parameterized surface yields higher *tool-selection
> accuracy* than an equivalent surface split one-tool-per-form/metric.

- **Control** — `edgar-mcp` exactly as shipped (11 tools), loaded from a captured
  fixture of the real tool schemas (`data/edgar_tools.json`).
- **Fragmented** — the same capability, un-collapsed: `get_recent_offerings(form=…)`
  becomes one tool per Reg form, `list_filings(form_type=…)` one per report type,
  `get_company_facts` one per metric, and so on. These are *faithful* splits — they
  cover the same ground, just spread across many narrow tools, which is the design a
  less disciplined author might ship. The count is whatever the honest rules produce
  (reported in the output), not padded to a round number.

For each task the model is shown one surface's tools and forced to call exactly one.
We score whether it picked the tool in the expected set for that surface — **exact
match, no LLM judge**. Selection is never executed, so the run is cheap and fully
reproducible.

**Scoring fairness.** Scored tasks target only splits that return *genuinely distinct
data* (Reg form, report type, financial metric, trade side), where the wrong fragment
is unambiguously wrong. The fragmented surface also carries softer "intent" splits
(lookup-by-ticker/name, search scope) to model realistic distractor load, but **no
scored task targets those**, so cosmetic fragmentation can't bias the result. A
carried-through arm (tools that aren't fragmented) acts as a sanity check — it should
score equally on both surfaces.

## Run it

```bash
uv sync

# Pipeline smoke test — deterministic keyword heuristic, NO API key, NOT a result:
uv run mcp-tool-surface-eval few-tools --client mock

# Real run — needs a key; --trials repeats each (task, surface) to average over sampling:
ANTHROPIC_API_KEY=sk-... uv run mcp-tool-surface-eval few-tools \
    --client anthropic --model claude-sonnet-4-6 --trials 5 --out report.md
```

The `mock` client is a keyword-overlap heuristic, not a language model — it exists
only to exercise the pipeline end-to-end without spend. **Its accuracy is not a
finding.** Only `--client anthropic` produces results worth citing.

## Layout

```
data/edgar_tools.json      real captured edgar tool schemas (the control surface)
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
tests/             oracle/scoring/fragmentation tests (no network)
```

## Roadmap — the next experiment

**Descriptions: do honest caveats reduce confident-wrong answers?** (Principle 3 of the
essay.) This is the planned second experiment, and it needs the opposite of the few-tools
path: few-tools scores tool *selection* and never executes anything, whereas this one has
to run the chosen tool against real data — a ZIP with no ZCTA, a top-coded income value, a
filing outside the recent window — with and without the caveat in the tool's description,
then grade whether the model reports the limitation or fabricates a confident answer.

The control arm already exists (`surfaces.strip_caveats` builds the no-caveat surface); the
execution-and-grading layer is the build. Designed but not yet implemented — tracked here so
the scope is explicit rather than implied.

## Honesty notes

- The control surface is the **real** edgar schema, not a flattering paraphrase.
- Fragments are faithful; the variant size is reported, not engineered.
- `mock` results are never findings; only live-model runs are.
- Results will be published as-is — including any that fail to support the essay.

Part of the **mcpwright** project · built by Devender Gollapally
