"""Core data types for the tool-surface eval.

The eval pits two *surfaces* (a set of tool specs presented to a model) against
each other on a fixed *task set*, and scores which tool the model reaches for.
Everything here is plain validated data — no I/O, no model calls.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """One tool as the model sees it: a name, a description, an input schema.

    This is exactly the surface area an LLM programs against — there is nothing
    else. Fragmenting or rewording a surface means transforming a list of these.
    """

    name: str = Field(description="Tool name the model calls.")
    description: str = Field(
        description="Natural-language description the model reads."
    )
    input_schema: dict = Field(
        default_factory=dict, description="JSON Schema for the tool's arguments."
    )


class Surface(BaseModel):
    """A named set of tools presented to the model for a single experiment arm."""

    id: str = Field(description="Stable id, e.g. 'control' or 'fragmented'.")
    label: str = Field(description="Human label for reports.")
    tools: list[ToolSpec] = Field(description="The tools, in presentation order.")

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    def names(self) -> set[str]:
        return {t.name for t in self.tools}


class Task(BaseModel):
    """One request with a known-correct tool choice per surface.

    `capability` is the canonical base-tool name the task needs; `discriminator`
    captures the parameter value a fragmented surface splits on (e.g. the Reg
    form). `expected[surface_id]` lists the tool name(s) that count as correct on
    that surface — populated by the surface builders so scoring stays objective.
    """

    id: str = Field(description="Stable task id.")
    prompt: str = Field(description="The user request handed to the model.")
    capability: str = Field(description="Canonical base tool the task requires.")
    discriminator: dict[str, str] = Field(
        default_factory=dict,
        description="Param value a fragmented surface splits on, e.g. {'form': 'C'}.",
    )
    expected: dict[str, list[str]] = Field(
        default_factory=dict,
        description="surface_id -> tool name(s) that count as a correct choice.",
    )


class Trial(BaseModel):
    """One model decision on one (task, surface)."""

    task_id: str
    surface_id: str
    chosen_tool: str | None = Field(
        default=None, description="Tool the model called, or None if it refused."
    )
    correct: bool = Field(
        default=False, description="Was the choice in expected[surface]?"
    )


class ArmResult(BaseModel):
    """Aggregate accuracy for one surface across the task set."""

    surface_id: str
    label: str
    tool_count: int
    trials: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.trials if self.trials else 0.0
