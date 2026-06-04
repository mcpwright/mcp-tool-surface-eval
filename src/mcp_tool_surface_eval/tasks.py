"""The few-tools task set.

Each task names a capability and (where the fragmented surface splits it) the
discriminating parameter value. `build_tasks` fills in the correct tool per
surface from the fragment selector map, so scoring is exact-match, not judged.

Scoring fairness: scored tasks target only splits that return *genuinely distinct
data* — Reg form, report type, financial metric, trade side — where picking the
wrong fragment is unambiguously wrong. The fragmented surface also contains softer
'intent' splits (lookup-by-ticker/name, search scope) to model realistic distractor
load, but no scored task targets those, so cosmetic fragmentation can't bias the
result.
"""

from __future__ import annotations

from .fragmentation import EDGAR_FRAGMENTS
from .models import Task

# (id, prompt, capability, discriminator)
_TASK_DEFS: list[tuple[str, str, str, dict[str, str]]] = [
    # get_recent_offerings, split by Reg form
    (
        "off_cf",
        "Show me the newest Reg CF crowdfunding raises filed recently.",
        "get_recent_offerings",
        {"form": "C"},
    ),
    (
        "off_d",
        "List the most recent Reg D private placements.",
        "get_recent_offerings",
        {"form": "D"},
    ),
    (
        "off_a",
        "What are the latest Reg A+ offerings?",
        "get_recent_offerings",
        {"form": "A"},
    ),
    # list_filings, split by form type
    (
        "list_10k",
        "Pull Apple's most recent annual reports (10-K).",
        "list_filings",
        {"form_type": "10-K"},
    ),
    (
        "list_10q",
        "Show Microsoft's latest quarterly reports (10-Q).",
        "list_filings",
        {"form_type": "10-Q"},
    ),
    (
        "list_8k",
        "What 8-K current reports has Tesla filed lately?",
        "list_filings",
        {"form_type": "8-K"},
    ),
    (
        "list_s1",
        "List the S-1 registration statements filed by Reddit.",
        "list_filings",
        {"form_type": "S-1"},
    ),
    (
        "list_proxy",
        "Show me Amazon's recent proxy statements (DEF 14A).",
        "list_filings",
        {"form_type": "DEF 14A"},
    ),
    # get_company_facts, split by metric
    (
        "fact_rev",
        "What was Apple's reported revenue?",
        "get_company_facts",
        {"metric": "revenue"},
    ),
    (
        "fact_ni",
        "How much net income did Microsoft report?",
        "get_company_facts",
        {"metric": "net_income"},
    ),
    (
        "fact_assets",
        "What are Tesla's total assets?",
        "get_company_facts",
        {"metric": "total_assets"},
    ),
    (
        "fact_eps",
        "What's Nvidia's earnings per share?",
        "get_company_facts",
        {"metric": "eps"},
    ),
    # get_insider_trades, split by side
    (
        "ins_buy",
        "Show recent insider buying at Meta.",
        "get_insider_trades",
        {"side": "buy"},
    ),
    (
        "ins_sell",
        "List recent insider stock sales at Netflix.",
        "get_insider_trades",
        {"side": "sell"},
    ),
    # carried-through (not fragmented) — sanity arm: should score equally on both surfaces
    ("insiders", "Who are the officers and directors of Apple?", "get_insiders", {}),
    (
        "formd",
        "Parse the structured offering details from Form D accession 0001234567-24-000123.",
        "get_form_d_details",
        {},
    ),
    (
        "filing",
        "Open the filing at https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/x.htm and show its documents.",
        "get_filing",
        {},
    ),
]


def build_tasks(
    selector_map: dict[tuple[str, frozenset[tuple[str, str]]], str],
    control_id: str = "control",
    fragmented_id: str = "fragmented",
) -> list[Task]:
    """Construct the task set with per-surface expected answers filled in."""
    tasks: list[Task] = []
    for tid, prompt, capability, disc in _TASK_DEFS:
        expected: dict[str, list[str]] = {control_id: [capability]}
        if capability in EDGAR_FRAGMENTS:
            key = (capability, frozenset(disc.items()))
            if key not in selector_map:
                raise ValueError(
                    f"task {tid!r}: no fragment for {capability} / {disc} — check the rules"
                )
            expected[fragmented_id] = [selector_map[key]]
        else:
            expected[fragmented_id] = [capability]
        tasks.append(
            Task(
                id=tid,
                prompt=prompt,
                capability=capability,
                discriminator=disc,
                expected=expected,
            )
        )
    return tasks
