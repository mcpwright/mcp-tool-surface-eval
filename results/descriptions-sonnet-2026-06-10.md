# Descriptions eval — results

**Hypothesis.** A behavioral caveat in a tool description changes behavior: telling the model that ACS top-codes income/home-value makes it flag a capped value as "at least" instead of reporting it as an exact figure.

- Model / client: `claude-sonnet-4-6`
- Tasks: 8 (4 top-coded, 4 ordinary) · trials per (task, surface): 5
- Grading: deterministic regex for cap-acknowledging language (no LLM judge).

## Summary

| Surface | Cap-ack rate (top-coded) | 95% CI | False-alarm rate (ordinary) | Overall correct |
|---|--:|--:|--:|--:|
| Census as shipped (with top-code caveat) | **100%** (20/20) | 84%–100% | 0% (0/20) | 100% |
| Census, top-code caveat removed | **80%** (16/20) | 58%–92% | 0% (0/20) | 90% |

**Result.** With the caveat in the description, the model flagged the top-coded value as a cap 100% of the time, vs 80% without it — the caveat added 20%.

## Per-task breakdown

| Task | Kind | Prompt | control ack? | stripped ack? |
|---|---|---|---|---|
| tc_income_1 | top-coded | What is the median household income in Atherto… | ✓ 5/5 | ✗ 2/5 |
| tc_income_2 | top-coded | How much does a typical household in ZIP 94027… | ✓ 5/5 | ✓ 5/5 |
| tc_home_1 | top-coded | What's the median home value in ZIP 94027 (Ath… | ✓ 5/5 | ✗ 4/5 |
| tc_home_2 | top-coded | What does a typical home cost in Atherton, 940… | ✓ 5/5 | ✓ 5/5 |
| nm_income_1 | ordinary | What is the median household income in ZIP 432… | ✓ 0/5 | ✓ 0/5 |
| nm_income_2 | ordinary | What's the median household income in ZIP 7852… | ✓ 0/5 | ✓ 0/5 |
| nm_home_1 | ordinary | What's the median home value in ZIP 43215? | ✓ 0/5 | ✓ 0/5 |
| nm_home_2 | ordinary | What does a typical home cost in ZIP 78521? | ✓ 0/5 | ✓ 0/5 |

_✓ = correct (top-coded → acknowledged the cap; ordinary → did not). `n/m` = answers that acknowledged a cap, of trials._
