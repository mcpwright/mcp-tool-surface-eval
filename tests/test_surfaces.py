"""Surface construction + fragmentation tests."""

from __future__ import annotations

from mcp_tool_surface_eval.fragmentation import EDGAR_FRAGMENTS, fragment_surface
from mcp_tool_surface_eval.surfaces import load_base_surface, strip_caveats


def test_base_surface_is_the_real_eleven() -> None:
    base = load_base_surface()
    assert base.id == "control"
    assert base.tool_count == 11
    assert "get_recent_offerings" in base.names()


def test_fragmentation_grows_and_replaces_bases() -> None:
    base = load_base_surface()
    fragmented, selector_map = fragment_surface(base)

    # every fragmented base is gone, replaced by its fragments
    for parent in EDGAR_FRAGMENTS:
        assert parent not in fragmented.names()
    # non-fragmented tools carry through unchanged
    assert "get_insiders" in fragmented.names()
    assert "get_form_d_details" in fragmented.names()

    # the variant is strictly larger
    assert fragmented.tool_count > base.tool_count
    # selector map resolves a known split
    assert selector_map[("get_recent_offerings", frozenset({("form", "C")}))] == (
        "get_recent_reg_cf_offerings"
    )


def test_fragments_drop_the_specialized_param() -> None:
    base = load_base_surface()
    fragmented, _ = fragment_surface(base)
    cf = next(t for t in fragmented.tools if t.name == "get_recent_reg_cf_offerings")
    assert "form" not in cf.input_schema.get("properties", {})


def test_strip_caveats_shortens_descriptions() -> None:
    base = load_base_surface()
    stripped = strip_caveats(base)
    assert stripped.tool_count == base.tool_count
    # at least one description got materially shorter (caveats removed)
    assert any(
        len(s.description) < len(b.description)
        for s, b in zip(stripped.tools, base.tools, strict=True)
    )
