"""A fixtured stand-in for the census MCP tools.

The descriptions experiment runs a real agent loop: the model calls a census
tool, gets a result, and answers. We serve that result from a small seeded
fixture instead of the live store so the run is deterministic, offline, and
reproducible — the same discipline the few-tools experiment uses.

The point of the experiment lives in one detail: for a top-coded ZIP the
executor returns the **raw capped integer** (median income `250001`, home value
`2000001`) with no annotation. Nothing in the result says "this is a cap." So
the only place that signal can come from is the tool *description* — which is
exactly the variable the two surfaces differ on. (Atherton's figures are the
real ACS 2024 values; the ordinary ZIPs are representative, clearly sub-cap.)
"""

from __future__ import annotations

import json
from typing import Any

VINTAGE = 2024

# ACS top-code caps (the value the API reports for the richest areas).
INCOME_CAP = 250_001
HOME_VALUE_CAP = 2_000_001

# Seeded per-ZIP records. Field names mirror census-mcp's pydantic return models.
_RECORDS: dict[str, dict[str, Any]] = {
    # Atherton, CA — hits BOTH top-codes (verified real ACS 2024 figures).
    "94027": {
        "name": "ZCTA5 94027",
        "population": 7253,
        "median_age": 47.8,
        "median_household_income": INCOME_CAP,
        "per_capita_income": 188_761,
        "total_households": 2_435,
        "households_200k_plus_pct": 65.6,
        "median_home_value": HOME_VALUE_CAP,
        "median_gross_rent": 3_501,
        "occupied_units": 2_435,
        "owner_occupied_pct": 87.6,
        "population_25_plus": 5_120,
        "bachelors_plus_pct": 83.2,
        "graduate_or_professional_pct": 52.2,
    },
    # Columbus, OH (downtown) — ordinary values, plainly below both caps.
    "43215": {
        "name": "ZCTA5 43215",
        "population": 9_812,
        "median_age": 32.4,
        "median_household_income": 71_640,
        "per_capita_income": 58_220,
        "total_households": 5_870,
        "households_200k_plus_pct": 9.1,
        "median_home_value": 318_400,
        "median_gross_rent": 1_412,
        "occupied_units": 5_870,
        "owner_occupied_pct": 38.2,
        "population_25_plus": 7_010,
        "bachelors_plus_pct": 61.4,
        "graduate_or_professional_pct": 24.7,
    },
    # Brownsville, TX — ordinary low-income values, well below both caps.
    "78521": {
        "name": "ZCTA5 78521",
        "population": 79_330,
        "median_age": 31.1,
        "median_household_income": 41_205,
        "per_capita_income": 18_940,
        "total_households": 24_110,
        "households_200k_plus_pct": 2.3,
        "median_home_value": 96_700,
        "median_gross_rent": 821,
        "occupied_units": 24_110,
        "owner_occupied_pct": 64.9,
        "population_25_plus": 49_880,
        "bachelors_plus_pct": 17.8,
        "graduate_or_professional_pct": 5.6,
    },
}

# Which record fields each tool surfaces (plus the always-present zcta/vintage).
# get_income intentionally OMITS households_200k_plus_pct here: the real tool
# returns it, but in this experiment it would (a) leak a cap-correlated hint into
# the result payload — muddying "the description is the only differing signal" —
# and (b) tempt the model to write "…earn $200k or more," which the grader could
# misread as acknowledging the $250k cap. Dropping it keeps the cap signal
# attributable to the description and the grading clean.
_TOOL_FIELDS: dict[str, list[str]] = {
    "lookup_zip": ["name", "population"],
    "get_income": [
        "name",
        "median_household_income",
        "per_capita_income",
        "total_households",
    ],
    "get_demographics": ["name", "population", "median_age"],
    "get_housing": [
        "name",
        "median_home_value",
        "median_gross_rent",
        "occupied_units",
        "owner_occupied_pct",
    ],
    "get_education": [
        "name",
        "population_25_plus",
        "bachelors_plus_pct",
        "graduate_or_professional_pct",
    ],
}

# Friendly column names get_acs_variable / compare_zips accept.
_METRIC_ALIASES = {
    "b19013_001e": "median_household_income",
    "b25077_001e": "median_home_value",
}


def _normalize_zip(raw: object) -> str | None:
    digits = "".join(c for c in str(raw) if c.isdigit())
    return digits[:5] if len(digits) in (5, 9) else None


def _no_data(zcta: str) -> dict[str, Any]:
    return {
        "error": (
            f"No Census ZCTA data for ZIP {zcta} — it may be a PO-box-only or "
            "non-residential ZIP with no ZIP Code Tabulation Area."
        )
    }


def execute(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run a census tool against the fixture; return the structured result.

    Returns the same shape census-mcp would (minus nothing the model needs).
    Unknown ZIPs return census's real error string; unknown tools return an
    error the agent can read.
    """
    if tool_name == "compare_zips":
        return _compare(args)

    zcta = _normalize_zip(args.get("zip_code"))
    if zcta is None:
        return {"error": f"Not a 5-digit US ZIP code: {args.get('zip_code')!r}"}
    rec = _RECORDS.get(zcta)
    if rec is None:
        return _no_data(zcta)

    if tool_name in _TOOL_FIELDS:
        out: dict[str, Any] = {"zcta": zcta, "vintage": VINTAGE}
        for field in _TOOL_FIELDS[tool_name]:
            out[field] = rec.get(field)
        return out

    if tool_name == "get_acs_variable":
        variable = str(args.get("variable", "")).strip().lower()
        column = _METRIC_ALIASES.get(variable, variable)
        if column not in rec:
            return {"error": f"Unknown ACS variable {args.get('variable')!r}."}
        return {
            "zcta": zcta,
            "name": rec["name"],
            "variable": args.get("variable"),
            "column": column,
            "value": rec[column],
            "vintage": VINTAGE,
        }

    return {"error": f"Unknown tool {tool_name!r}."}


def _numeric(value: object) -> float:
    """A sortable number for a cell, 0 for missing/non-numeric."""
    return float(value) if isinstance(value, int | float) else 0.0


def _compare(args: dict[str, Any]) -> dict[str, Any]:
    metric = str(args.get("metric", "")).strip().lower()
    column = _METRIC_ALIASES.get(metric, metric)
    results = []
    for raw in args.get("zips", []) or []:
        zcta = _normalize_zip(raw)
        rec = _RECORDS.get(zcta) if zcta else None
        results.append(
            {
                "zcta": zcta,
                "name": rec.get("name") if rec else None,
                "value": rec.get(column) if rec else None,
            }
        )
    results.sort(key=lambda r: (r["value"] is None, -_numeric(r["value"])))
    return {"metric": column, "vintage": VINTAGE, "results": results}


def result_to_text(result: dict[str, Any]) -> str:
    """Serialize a tool result for a tool_result message block."""
    return json.dumps(result)
