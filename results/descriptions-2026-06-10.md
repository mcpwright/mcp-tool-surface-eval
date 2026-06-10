# Descriptions experiment — results (2026-06-10)

**Question.** Principle 3 of the essay says a tool *description* is the real API the
model programs against. So: does a behavioral caveat in the description change
behavior? Concretely — telling the model that the ACS *top-codes* median household
income at \$250,001 and median home value at \$2,000,001, does it then report a
capped value as "at least that" instead of as an exact figure?

**Setup.** Control = `census-mcp` exactly as shipped, whose `get_income` /
`get_housing` descriptions carry the top-code caveat. Stripped = the identical
surface with *only* the `Note: ACS top-codes…` sentence removed. A short agent loop
answers each question under a neutral system prompt; the tool result is fixtured and
returns the **raw capped integer with no annotation**, so the only signal that differs
between arms is the description. Grading is a fixed, disclosed regex for
cap-acknowledging language — **no LLM judge**. Top-coded tasks are correct iff the cap
is acknowledged; ordinary ZIPs are correct iff it is *not* (a false-alarm guard).
5 trials × 8 tasks × 2 surfaces per model. Every trial called a data tool (no
answers from priors alone slipped through ungrounded).

## Headline

| Model | With caveat (cap-ack) | Caveat removed (cap-ack) | Effect |
|---|--:|--:|--:|
| **claude-haiku-4-5** | **100%** (20/20) | **0%** (0/20) | **+100 pts** — CIs disjoint |
| **claude-sonnet-4-6** | **100%** (20/20) | **80%** (16/20) | +20 pts |

Neither arm ever raised a false alarm on an ordinary ZIP (0/20 both models, both
arms) — the effect is real signal, not a model that simply always hedges.

## What it means

The result splits cleanly by how much the model already knows:

- **Haiku has no useful prior** about ACS top-coding. Without the caveat it reports
  \$250,001 / \$2,000,001 as the exact answer **every single time** — confidently
  wrong. With the caveat it flags the cap every time. The description *is* the
  difference between right and wrong; nothing else changed.
- **Sonnet already recognizes the sentinels** (it hedges 80% of the time with no
  caveat, inferring the cap from the suspiciously exact figure). The caveat closes
  the remaining 20%, and the per-task breakdown shows *where*: the gap is entirely
  on the formally-phrased queries ("What is the **median household income**…",
  stripped 2/5) — exactly the framing that most invites reporting the cap as a
  precise statistic. On the casual phrasings ("what does a typical home cost")
  Sonnet hedges anyway.

## The honest contrast with the few-tools experiment

The few-tools experiment predicted weaker models would show a bigger gap, and that
prediction **did not hold** for tool *selection* (Sonnet 100% vs 94%, Haiku 93% vs
92% — no significant difference). It holds emphatically here. The reconciliation is
the actual insight:

> Tool **selection** is robust to surface shape — a capable model picks the right
> tool whether you give it 11 or 26. But tool-result **interpretation** is highly
> sensitive to what the description says, and most sensitive exactly where the model
> can't fall back on priors. The caveat earns its place not by helping the model
> *choose*, but by stopping it from confidently misreading what it gets back.

So "descriptions are the API" is too coarse. Sharper: **a description's behavioral
caveats are load-bearing in proportion to how little the model already knows about
the data's quirks** — and that's precisely the regime (smaller models, obscure
datasets) where an MCP server most needs to carry its own warnings.

## Caveats on these numbers

- n = 20 per cell (4 top-coded tasks × 5 trials). Haiku's 0%/100% split is
  unambiguous; Sonnet's 80%→100% has overlapping Wilson intervals (58–92% vs
  84–100%) — directionally clear, not a tight estimate.
- The fixture's capped integers (250001 / 2000001) are themselves recognizable
  sentinels, which is *why* Sonnet does well unaided. A less telegraphing value
  would likely widen Sonnet's gap too — untested.
- One dataset, one caveat kind (top-coding). Generalization to other caveats
  (stale windows, suppressed cells, unit ambiguity) is unmeasured.

Raw per-model reports: `descriptions-sonnet-2026-06-10.md`,
`descriptions-haiku-2026-06-10.md`.
