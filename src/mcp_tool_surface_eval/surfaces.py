"""Build the surfaces an experiment compares.

`control` is edgar exactly as shipped, loaded from the captured fixture. The other
surfaces are transforms of it: `fragment_surface` (in fragmentation.py) for the
few-tools experiment, and `strip_caveats` here for the descriptions experiment.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Surface, ToolSpec

# repo-root/data/edgar_tools.json  (src/mcp_tool_surface_eval/surfaces.py -> up 3)
_DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "data" / "edgar_tools.json"


def load_base_surface(
    fixture: Path = _DEFAULT_FIXTURE,
    surface_id: str = "control",
    label: str = "Control (edgar as shipped, 11 tools)",
) -> Surface:
    """Load the real captured edgar tool surface from its fixture."""
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


def _first_sentence(text: str) -> str:
    """The headline 'what it does' sentence, dropping the caveat-bearing remainder.

    edgar's descriptions lead with the core action and follow with the behavioral
    caveats (form windows, ZCTA gaps, top-coding, private-vs-public). Keeping only
    the first sentence is a faithful 'strip the caveats' operation.
    """
    text = text.strip()
    for end in (". ", ".\n", "\n"):
        idx = text.find(end)
        if idx != -1:
            return text[: idx + 1].strip()
    return text


def strip_caveats(
    base: Surface,
    surface_id: str = "stripped",
    label: str = "Caveats stripped (headline description only)",
) -> Surface:
    """Build a surface whose descriptions keep only the headline, no caveats.

    Used as the control arm of the descriptions experiment: does telling the model
    the caveats (the as-shipped surface) reduce confident-wrong answers versus this
    stripped surface? That comparison needs tool execution + judging — see the
    runner's notes; this builder supplies the arm.
    """
    return Surface(
        id=surface_id,
        label=label,
        tools=[
            ToolSpec(
                name=t.name,
                description=_first_sentence(t.description),
                input_schema=t.input_schema,
            )
            for t in base.tools
        ],
    )
