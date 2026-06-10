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

## The descriptions experiment (implemented)

> **Hypothesis.** A behavioral caveat in a tool description changes behavior:
> telling the model that the ACS *top-codes* income and home value makes it report
> a capped figure as "at least that" instead of as an exact number.

This is principle 3 of the essay ("descriptions are the API"), and it needs the
opposite of the few-tools path: few-tools scores tool *selection* and never executes
anything; this one runs a short **agent loop** and grades the *answer*.

- **Control** — `census-mcp` exactly as shipped (`data/census_tools.json`). Its
  `get_income` / `get_housing` descriptions carry the caveat that ACS top-codes
  median household income at \$250,001 and median home value at \$2,000,001.
  *(The caveat wasn't there originally — building this eval surfaced that gap, so it
  was added to census-mcp first; the fixture is the real, improved surface.)*
- **Stripped** — the identical surface with **only** the `Note: ACS top-codes…`
  sentence removed. Every other word is byte-for-byte the same, so the two arms
  differ by exactly the variable under test.

For each task the model is given one surface's tools plus a neutral `submit_answer`
tool, under a neutral system prompt (it never mentions caps or precision). It calls
a census tool, gets a **fixtured** result, and answers. The fixture returns the
**raw capped integer** (`250001` / `2000001`) with *no annotation* — so the only
place the "this is a cap" signal can come from is the description (or the model's
own priors, which is itself a fair finding).

**Grading is deterministic — no LLM judge.** A fixed, disclosed regex
(`descriptions.py`, `_CAP_PHRASES` + `_CAP_VALUE_RE`) decides whether an answer
flagged the value as a cap/floor ("at least", "or more", "top-coded", "capped",
"$250,000+"…). Two task kinds keep it honest: **top-coded** tasks are correct only
if the cap is acknowledged; **ordinary** ZIPs (values well below either cap) are
correct only if it is *not* — a guard against an arm that simply always hedges.

## Run it

```bash
uv sync

# Pipeline smoke test — deterministic keyword heuristic, NO API key, NOT a result:
uv run mcp-tool-surface-eval few-tools --client mock
uv run mcp-tool-surface-eval descriptions --client mock

# Real runs — need a key; --trials repeats each (task, surface) to average over sampling:
ANTHROPIC_API_KEY=sk-... uv run mcp-tool-surface-eval few-tools \
    --client anthropic --model claude-sonnet-4-6 --trials 5 --out report.md
ANTHROPIC_API_KEY=sk-... uv run mcp-tool-surface-eval descriptions \
    --client anthropic --model claude-sonnet-4-6 --trials 5 --out report.md
```

The `mock` client is a keyword-overlap heuristic, not a language model — it exists
only to exercise the pipeline end-to-end without spend. **Its accuracy is not a
finding.** Only `--client anthropic` produces results worth citing.

## Layout

```
data/edgar_tools.json      real captured edgar tool schemas (few-tools control)
data/census_tools.json     real captured census tool schemas (descriptions control)
src/mcp_tool_surface_eval/
  models.py        ToolSpec / Surface / Task / Trial / ArmResult; Answer* types
  surfaces.py      load the edgar control surface; strip_caveats transform
  fragmentation.py the explicit edgar fragmentation rules + applier
  tasks.py         the few-tools task set, with per-surface expected answers
  census_surface.py  load census; without_topcode_caveat (surgical strip)
  execution.py     fixtured census tool execution (seeded ZIPs, raw caps)
  descriptions.py  the descriptions task set, the regex grader, the run loop
  model_client.py  ModelClient/AgentClient; AnthropicClient (real) + MockClient
  runner.py        few-tools: run every (surface, task); score each choice
  score.py         aggregate (+ aggregate_answers) + Wilson confidence interval
  report.py        Markdown reports (few-tools + descriptions)
  cli.py           `few-tools` and `descriptions` subcommands
tests/             oracle/scoring/fragmentation/execution/grading tests (no network)
```

## Results so far

Full writeups in [`results/`](results/). Headlines:

**Few-tools** ([`results/few-tools-2026-06-04.md`](results/few-tools-2026-06-04.md)) — the
predicted advantage of a small surface over a fragmented one **did not hold** on tool
*selection*: Sonnet 100% vs 94%, Haiku 93% vs 92%, CIs overlapping. A capable model picks
the right tool whether you hand it 11 tools or 26.

**Descriptions** ([`results/descriptions-2026-06-10.md`](results/descriptions-2026-06-10.md))
— a top-code caveat in the description sharply changes how the model *interprets* a result:

| Model | With caveat | Caveat removed |
|---|--:|--:|
| claude-haiku-4-5 | **100%** flag the cap | **0%** — reports it as exact every time |
| claude-sonnet-4-6 | **100%** | **80%** (already knows the ACS sentinels) |

Together they sharpen the essay's claim: tool *selection* is robust to surface shape, but
tool-result *interpretation* leans heavily on the description's caveats — most of all where
the model lacks priors (smaller models, obscure datasets). That's the regime where a server
most needs to carry its own warnings.

## Honesty notes

- Both control surfaces are the **real** shipped schemas (edgar, census), not
  flattering paraphrases. The descriptions arms differ by one removed sentence.
- The census top-code caveat was added to the **real server** before capture — the
  eval improves the thing it measures rather than testing a mock-up.
- Fragments are faithful; the variant size is reported, not engineered.
- Descriptions grading is a fixed, disclosed regex — no LLM judge in the loop.
- `mock` results are never findings; only live-model runs are.
- Results will be published as-is — including any that fail to support the essay.

Part of the **mcpwright** project · built by Devender Gollapally
