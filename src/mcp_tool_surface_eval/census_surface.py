"""Build the two arms of the descriptions experiment from the census surface.

`load_census_surface` loads census exactly as shipped — its descriptions carry
the ACS top-code caveat ("median household income caps at $250,001 … read it as
'$250k or more', not an exact figure"). `without_topcode_caveat` removes *only*
that caveat sentence, leaving every other word identical, so the two arms differ
by exactly the thing under test. (We can't sentence-split — the caveat contains
"e.g." — so we cut from the literal "Note: ACS top-codes" to the end, which is
where it sits in every description that has it.)
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Surface, ToolSpec

# repo-root/data/census_tools.json  (src/mcp_tool_surface_eval/ -> up 2)
_DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "data" / "census_tools.json"

# The caveat sentence always begins here and runs to the end of the description.
_CAVEAT_MARKER = "Note: ACS top-codes"


def load_census_surface(
    fixture: Path = _DEFAULT_FIXTURE,
    surface_id: str = "control",
    label: str = "Census as shipped (with top-code caveat)",
) -> Surface:
    """Load the real captured census tool surface from its fixture."""
    data = json.loads(fixture.read_text())
    tools = [
        ToolSpec(
            name=t["name"],
            description=t["description"],
            input_schema=t.get("input_schema", {}),
        )
        for t in data["tools"]
    ]
    return Surface(id=surface_id, label=label, tools=tools)


def _strip_caveat(description: str) -> str:
    """Remove the top-code caveat sentence, keeping the rest verbatim."""
    idx = description.find(_CAVEAT_MARKER)
    if idx == -1:
        return description
    return description[:idx].rstrip()


def without_topcode_caveat(
    base: Surface,
    surface_id: str = "stripped",
    label: str = "Census, top-code caveat removed",
) -> Surface:
    """The control-arm surface: identical to `base` minus the top-code caveat."""
    return Surface(
        id=surface_id,
        label=label,
        tools=[
            ToolSpec(
                name=t.name,
                description=_strip_caveat(t.description),
                input_schema=t.input_schema,
            )
            for t in base.tools
        ],
    )


def caveat_tool_count(surface: Surface) -> int:
    """How many of a surface's tools carry the top-code caveat (sanity check)."""
    return sum(1 for t in surface.tools if _CAVEAT_MARKER in t.description)
