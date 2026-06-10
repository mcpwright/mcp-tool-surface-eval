"""Model clients: how a surface's tools are put to a model to elicit a choice.

`ModelClient` is the seam. `AnthropicClient` is the real one — it forces a single
tool call and reports which tool the model picked. `MockClient` is deterministic
(a keyword-overlap heuristic) so the harness runs end-to-end and is unit-testable
without an API key or spend. Mock results are a pipeline smoke test, NOT findings.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field

from .execution import result_to_text

if TYPE_CHECKING:
    from collections.abc import Callable

    from .models import ToolSpec

_SELECT_SYSTEM = (
    "You are an agent with the tools below. The user makes a request. Choose the "
    "single most appropriate tool and call it. Do not ask questions; make your best "
    "choice. You must call exactly one tool."
)

# The descriptions experiment runs a short agent loop. The system prompt is kept
# deliberately NEUTRAL — it never mentions precision, caps, or caveats — so the
# only thing that differs between the two arms is the tool descriptions.
_AGENT_SYSTEM = (
    "You are a helpful assistant with the tools below, backed by U.S. Census "
    "data. Use them to answer the user's question, then call submit_answer with "
    "your final answer to the user."
)

# A neutral capture tool. The schema gives nothing away: just an answer string.
_SUBMIT_TOOL: dict[str, Any] = {
    "name": "submit_answer",
    "description": "Call this once you can answer the user, with your final answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "Your final answer to the user.",
            }
        },
        "required": ["answer"],
    },
}


class AgentOutcome(BaseModel):
    """The result of one agent run: its final answer and the tools it called."""

    answer: str = Field(description="The model's final natural-language answer.")
    tool_calls: list[str] = Field(
        default_factory=list, description="Data tools called, in order."
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


class AgentClient(Protocol):
    def answer_with_tools(
        self,
        prompt: str,
        tools: list[ToolSpec],
        executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        max_rounds: int = 4,
    ) -> AgentOutcome: ...


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

    def answer_with_tools(
        self,
        prompt: str,
        tools: list[ToolSpec],
        executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        max_rounds: int = 4,
    ) -> AgentOutcome:
        """Deterministic smoke run: call the best-overlap tool, echo the figure.

        Calls no language model and never adds caveat language, so its answers
        are a pipeline check, NOT a finding.
        """
        choice = self._policy(prompt, tools)
        if not choice.name:
            return AgentOutcome(answer="No tool available.", tool_calls=[])
        args: dict[str, Any] = {}
        zip_match = re.search(r"\b(\d{5})\b", prompt)
        if zip_match:
            args["zip_code"] = zip_match.group(1)
        result = executor(choice.name, args)
        figure = next((v for v in result.values() if isinstance(v, int | float)), None)
        return AgentOutcome(
            answer=f"Based on Census data, the value is {figure}.",
            tool_calls=[choice.name],
        )


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

    def answer_with_tools(
        self,
        prompt: str,
        tools: list[ToolSpec],
        executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        max_rounds: int = 4,
    ) -> AgentOutcome:
        """Run a short agent loop: call data tools, then submit a final answer.

        Each round forces a single tool call; the last round forces `submit_answer`
        so the loop always terminates with an answer. Data-tool results come from
        `executor` (the fixture), fed back as tool_result blocks. Parallel tool use
        is disabled — we feed back one tool_result per turn, and a turn with an
        unmatched tool_use block would make the next request 400.
        """
        if max_rounds < 2:
            raise ValueError("max_rounds must be >= 2 (one to gather, one to submit).")
        api_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema or {"type": "object", "properties": {}},
            }
            for t in tools
        ] + [_SUBMIT_TOOL]
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        calls: list[str] = []

        for round_i in range(max_rounds):
            force_submit = round_i == max_rounds - 1
            tool_choice: dict[str, Any] = (
                {"type": "tool", "name": "submit_answer"}
                if force_submit
                else {"type": "any"}
            )
            tool_choice["disable_parallel_tool_use"] = True
            msg = self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=self._max_tokens,
                system=_AGENT_SYSTEM,
                tools=api_tools,
                tool_choice=tool_choice,
                messages=messages,
            )
            use = next(
                (b for b in msg.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if use is None:
                return AgentOutcome(answer="", tool_calls=calls)
            if use.name == "submit_answer":
                answer = str((use.input or {}).get("answer", ""))
                return AgentOutcome(answer=answer, tool_calls=calls)
            calls.append(use.name)
            result = executor(use.name, dict(use.input or {}))
            messages.append({"role": "assistant", "content": msg.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": use.id,
                            "content": result_to_text(result),
                        }
                    ],
                }
            )
        return AgentOutcome(answer="", tool_calls=calls)
