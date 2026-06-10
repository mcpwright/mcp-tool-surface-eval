"""Fixtured census execution tests."""

from __future__ import annotations

from mcp_tool_surface_eval.execution import (
    HOME_VALUE_CAP,
    INCOME_CAP,
    execute,
)


def test_topcoded_zip_returns_the_raw_caps() -> None:
    income = execute("get_income", {"zip_code": "94027"})
    assert income["median_household_income"] == INCOME_CAP
    housing = execute("get_housing", {"zip_code": "94027"})
    assert housing["median_home_value"] == HOME_VALUE_CAP
    # the result is just the raw fields — no annotation flags it as a cap, and the
    # cap-correlated households_200k_plus_pct field is deliberately not served here
    assert set(income) == {
        "zcta",
        "vintage",
        "name",
        "median_household_income",
        "per_capita_income",
        "total_households",
    }
    assert "households_200k_plus_pct" not in income


def test_ordinary_zip_is_below_both_caps() -> None:
    income = execute("get_income", {"zip_code": "43215"})
    assert income["median_household_income"] < INCOME_CAP
    housing = execute("get_housing", {"zip_code": "43215"})
    assert housing["median_home_value"] < HOME_VALUE_CAP


def test_zip_plus_four_is_normalized() -> None:
    assert execute("get_income", {"zip_code": "94027-1234"})["zcta"] == "94027"


def test_unknown_zip_returns_census_error_shape() -> None:
    out = execute("get_income", {"zip_code": "00000"})
    assert "error" in out and "zip code tabulation area" in out["error"].lower()


def test_bad_zip_errors() -> None:
    assert "error" in execute("get_income", {"zip_code": "nope"})


def test_get_acs_variable_resolves_code_alias() -> None:
    out = execute("get_acs_variable", {"zip_code": "94027", "variable": "B19013_001E"})
    assert out["value"] == INCOME_CAP
    assert out["column"] == "median_household_income"


def test_compare_zips_sorts_desc_and_top_codes_tie_high() -> None:
    out = execute(
        "compare_zips",
        {"zips": ["43215", "94027", "78521"], "metric": "median_household_income"},
    )
    values = [r["value"] for r in out["results"]]
    assert values == sorted(values, reverse=True)
    assert out["results"][0]["zcta"] == "94027"  # the top-coded ZIP leads


def test_unknown_tool_errors() -> None:
    assert "error" in execute("get_nonsense", {"zip_code": "94027"})
