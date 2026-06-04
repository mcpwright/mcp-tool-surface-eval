"""Fragmentation rules: turn edgar's collapsed surface into a 'many specific
tools' variant.

The essay's first principle is that few orthogonal tools beat many specific ones.
To test it we need the *same capability* presented two ways. The control surface
is edgar as shipped (11 tools). The fragmented surface un-collapses the tools edgar
deliberately parameterized — one tool per form, per metric, per intent — which is
exactly the design a less disciplined author might have shipped.

Each fragment records its `parent` (the base tool it came from) and a `selector`
(the parameter value it specializes), so the task set can be scored objectively:
a task that needs Reg CF offerings is correct only if the model picks the Reg CF
fragment, not the Reg D one.

Fragments are *faithful*: collectively they cover the parent's capability, with the
specialized parameter removed from the schema and folded into the description. We do
not invent capabilities to pad the count — the resulting size is whatever the honest
rules produce (reported by the harness), not a round number.
"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, Field

from .models import Surface, ToolSpec


class FragmentDef(BaseModel):
    """One specialized tool derived from a base tool."""

    name: str = Field(description="Name of the derived, specialized tool.")
    description: str = Field(description="Narrowed description for the fragment.")
    selector: dict[str, str] = Field(
        description="The (key,value) this fragment specializes, e.g. {'form': 'C'}."
    )
    drop_param: str | None = Field(
        default=None,
        description="Param removed from the schema (now implied by the tool).",
    )


# base tool name -> the fragments it explodes into.
# A base tool absent here is carried through unchanged on the fragmented surface.
EDGAR_FRAGMENTS: dict[str, list[FragmentDef]] = {
    "lookup_issuer": [
        FragmentDef(
            name="lookup_issuer_by_ticker",
            description="Resolve a stock ticker symbol (e.g. 'AAPL') to its SEC CIK and identity.",
            selector={"by": "ticker"},
        ),
        FragmentDef(
            name="lookup_issuer_by_name",
            description="Resolve a company name (e.g. 'Apple Inc.') to its SEC CIK and identity.",
            selector={"by": "name"},
        ),
    ],
    "list_filings": [
        FragmentDef(
            name="list_annual_reports",
            description="List an issuer's most recent annual reports (Form 10-K), newest first.",
            selector={"form_type": "10-K"},
            drop_param="form_type",
        ),
        FragmentDef(
            name="list_quarterly_reports",
            description="List an issuer's most recent quarterly reports (Form 10-Q), newest first.",
            selector={"form_type": "10-Q"},
            drop_param="form_type",
        ),
        FragmentDef(
            name="list_current_reports",
            description="List an issuer's most recent current reports (Form 8-K), newest first.",
            selector={"form_type": "8-K"},
            drop_param="form_type",
        ),
        FragmentDef(
            name="list_registration_statements",
            description="List an issuer's most recent registration statements (Form S-1), newest first.",
            selector={"form_type": "S-1"},
            drop_param="form_type",
        ),
        FragmentDef(
            name="list_proxy_statements",
            description="List an issuer's most recent proxy statements (DEF 14A), newest first.",
            selector={"form_type": "DEF 14A"},
            drop_param="form_type",
        ),
    ],
    "get_recent_offerings": [
        FragmentDef(
            name="get_recent_reg_cf_offerings",
            description="List recent Reg CF crowdfunding offerings (Form C), newest first.",
            selector={"form": "C"},
            drop_param="form",
        ),
        FragmentDef(
            name="get_recent_reg_d_offerings",
            description="List recent Reg D private offerings (Form D), newest first.",
            selector={"form": "D"},
            drop_param="form",
        ),
        FragmentDef(
            name="get_recent_reg_a_offerings",
            description="List recent Reg A+ offerings (Form 1-A), newest first.",
            selector={"form": "A"},
            drop_param="form",
        ),
    ],
    "get_company_facts": [
        FragmentDef(
            name="get_company_revenue",
            description="Get a public company's reported revenue from its XBRL facts.",
            selector={"metric": "revenue"},
        ),
        FragmentDef(
            name="get_company_net_income",
            description="Get a public company's reported net income from its XBRL facts.",
            selector={"metric": "net_income"},
        ),
        FragmentDef(
            name="get_company_total_assets",
            description="Get a public company's reported total assets from its XBRL facts.",
            selector={"metric": "total_assets"},
        ),
        FragmentDef(
            name="get_company_eps",
            description="Get a public company's reported earnings per share from its XBRL facts.",
            selector={"metric": "eps"},
        ),
        FragmentDef(
            name="get_company_cash",
            description="Get a public company's reported cash and equivalents from its XBRL facts.",
            selector={"metric": "cash"},
        ),
        FragmentDef(
            name="get_company_liabilities",
            description="Get a public company's reported total liabilities from its XBRL facts.",
            selector={"metric": "liabilities"},
        ),
    ],
    "get_insider_trades": [
        FragmentDef(
            name="get_insider_buys",
            description="Recent insider purchase transactions (Section 16) for a company, newest first.",
            selector={"side": "buy"},
        ),
        FragmentDef(
            name="get_insider_sells",
            description="Recent insider sale transactions (Section 16) for a company, newest first.",
            selector={"side": "sell"},
        ),
    ],
    "search_filings": [
        FragmentDef(
            name="search_filings_all",
            description="Full-text search across all SEC filing documents.",
            selector={"scope": "all"},
        ),
        FragmentDef(
            name="search_filings_by_company",
            description="Full-text search across SEC filings, scoped to one company.",
            selector={"scope": "company"},
        ),
        FragmentDef(
            name="search_filings_in_daterange",
            description="Full-text search across SEC filings filed within a date range.",
            selector={"scope": "daterange"},
        ),
    ],
}


def _without_param(schema: dict, param: str | None) -> dict:
    """Return a copy of an input schema with `param` removed (if present)."""
    if not param:
        return deepcopy(schema)
    out = deepcopy(schema)
    props = out.get("properties")
    if isinstance(props, dict):
        props.pop(param, None)
    req = out.get("required")
    if isinstance(req, list) and param in req:
        out["required"] = [r for r in req if r != param]
    return out


def fragment_surface(
    base: Surface,
    rules: dict[str, list[FragmentDef]] = EDGAR_FRAGMENTS,
    surface_id: str = "fragmented",
    label: str = "Fragmented (one tool per form / metric / intent)",
) -> tuple[Surface, dict[tuple[str, frozenset[tuple[str, str]]], str]]:
    """Build the fragmented surface from a base surface.

    Returns the new Surface and a `(parent, frozenset(selector.items())) -> fragment
    name` map the task set uses to fill in the correct fragmented-surface answer.
    A base tool with no rule is carried through unchanged.
    """
    by_name = {t.name: t for t in base.tools}
    tools: list[ToolSpec] = []
    selector_map: dict[tuple[str, frozenset[tuple[str, str]]], str] = {}

    for tool in base.tools:
        frags = rules.get(tool.name)
        if not frags:
            tools.append(tool)
            continue
        for f in frags:
            tools.append(
                ToolSpec(
                    name=f.name,
                    description=f.description,
                    input_schema=_without_param(
                        by_name[tool.name].input_schema, f.drop_param
                    ),
                )
            )
            selector_map[(tool.name, frozenset(f.selector.items()))] = f.name

    return (
        Surface(id=surface_id, label=label, tools=tools),
        selector_map,
    )
