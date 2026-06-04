"""Model clients: how a surface's tools are put to a model to elicit a choice.

`ModelClient` is the seam. `AnthropicClient` is the real one — it forces a single
tool call and reports which tool the model picked. `MockClient` is deterministic
(a keyword-overlap heuristic) so the harness runs end-to-end and is unit-testable
without an API key or spend. Mock results are a pipeline smoke test, NOT findings.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Callable

    from .models import ToolSpec

_SELECT_SYSTEM = (
    "You are an agent with the tools below. The user makes a request. Choose the "
    "single most appropriate tool and call it. Do not ask questions; make your best "
    "choice. You must call exactly one tool."
)


class ToolChoice(BaseModel):
    """The tool a model picked for one request."""

    name: str | None = Field(
        default=None, description="Chosen tool, or None if none called."
    )
    arguments: dict = Field(
        default_factory=dict, description="Arguments the model supplied."
    )


class ModelClient(Protocol):
    def choose_tool(self, prompt: str, tools: list[ToolSpec]) -> ToolChoice: ...


# --- mock --------------------------------------------------------------------

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "for",
        "to",
        "and",
        "or",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "show",
        "me",
        "list",
        "get",
        "find",
        "what",
        "are",
        "is",
        "has",
        "have",
        "recent",
        "most",
        "newest",
        "filed",
        "lately",
        "latest",
    }
)


def _tokens(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z0-9]+", text.lower())
        if w not in _STOP and len(w) > 1
    }


def keyword_policy(prompt: str, tools: list[ToolSpec]) -> ToolChoice:
    """Deterministic baseline: pick the tool with the most prompt-word overlap.

    A crude stand-in for a model — enough to exercise the whole pipeline. It is
    *not* a language model and its accuracy is not a result worth reporting.
    """
    p = _tokens(prompt)
    best: tuple[int, int] | None = None  # (-overlap, index) for stable argmin
    choice = tools[0].name if tools else None
    for i, t in enumerate(tools):
        overlap = len(p & _tokens(f"{t.name} {t.description}"))
        key = (-overlap, i)
        if best is None or key < best:
            best, choice = key, t.name
    return ToolChoice(name=choice)


class MockClient:
    """A deterministic ModelClient driven by a policy function."""

    def __init__(
        self,
        policy: Callable[[str, list[ToolSpec]], ToolChoice] = keyword_policy,
    ) -> None:
        self._policy = policy

    def choose_tool(self, prompt: str, tools: list[ToolSpec]) -> ToolChoice:
        return self._policy(prompt, tools)


# --- real --------------------------------------------------------------------


class AnthropicClient:
    """Real ModelClient. Forces one tool call and reports the model's pick."""

    def __init__(
        self, model: str = "claude-sonnet-4-6", max_tokens: int = 1024
    ) -> None:
        # Imported lazily so the package imports without the SDK / a key installed.
        from anthropic import Anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set — export it to run the live eval."
            )
        self._client = Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def choose_tool(self, prompt: str, tools: list[ToolSpec]) -> ToolChoice:
        api_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema or {"type": "object", "properties": {}},
            }
            for t in tools
        ]
        msg = self._client.messages.create(  # type: ignore[call-overload]
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SELECT_SYSTEM,
            tools=api_tools,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                return ToolChoice(name=block.name, arguments=dict(block.input or {}))
        return ToolChoice(name=None)
