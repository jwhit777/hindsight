"""Replay engine — re-derive a TraceRun from a chosen step onward.

The v0.2 marquee feature. Three operations the spike's diff/show/stats cannot
do: substitute a different model at step N, re-run with the same model to test
non-determinism, and produce a *new* TraceRun that itself diffs against the
original ("what would have happened with Sonnet instead of Haiku?").

Design choices worth defending:
  * `Provider` is a Protocol, not an ABC. Replay is plug-in friendly — pass
    any object with `.simulate(step, *, model=None) -> TraceStep` and the
    right `.name`. The two built-ins are the deterministic identity provider
    (MockProvider, default) and the live API provider (AnthropicProvider).
  * MockProvider returns `step.response` verbatim. That's the *record-
    substitution dry-run* path the PLAN names as the v0.2 default. No
    network, no SDK dependency.
  * AnthropicProvider lazy-imports `anthropic` inside `__init__`. Importing
    `hindsight.replay` on a stdlib-only install must not raise. Live calls
    are opt-in behind `live=True` or by passing an instance explicitly.
  * Only `StepKind.LLM` steps are routed through the provider. AGENT
    boundaries, TOOL calls, and DECISION nodes are copied verbatim — re-
    executing a tool may be destructive (`get_current_time`, DB writes),
    and the PLAN explicitly puts `--live-tools` behind a separate, scarier
    flag we don't ship in v0.2.
  * Model override applied *before* the provider sees the step, so the
    provider can decide how to honor it (or not). MockProvider stamps the
    override onto the returned step so the diff against the original
    surfaces the model swap as a structural change.
"""

from __future__ import annotations

import copy
import os
from dataclasses import replace
from typing import Protocol, runtime_checkable

from .canonical import StepKind, TraceRun, TraceStep


@runtime_checkable
class Provider(Protocol):
    """The replay provider contract.

    `simulate` receives the recorded step (possibly with `model` already
    overridden by the caller) and returns the step that should appear in
    the replayed run. Returning the same dataclass instance is fine —
    callers treat the result as immutable.
    """

    name: str

    def simulate(self, step: TraceStep, *, model: str | None = None) -> TraceStep: ...


class MockProvider:
    """Deterministic identity replay — returns `step.response` unchanged.

    This is the record-substitution dry-run path. It exists so `replay()`
    is usable with zero network, zero SDK, zero API key — the default in
    CI, the default in the demo, and the only path the spike tests need.

    If a `model` override was applied by `replay()` before we were called,
    we preserve it on the returned step so the structural diff against the
    original shows the model swap.
    """

    name = "mock"

    def simulate(self, step: TraceStep, *, model: str | None = None) -> TraceStep:
        # `model` here is informational — the caller has already stamped any
        # override onto `step.model`. We return a deep copy to keep the
        # input run unmutated even if a downstream caller edits the result.
        return replace(
            step,
            request=copy.deepcopy(step.request),
            response=copy.deepcopy(step.response),
            extra=copy.deepcopy(step.extra),
        )


class AnthropicProvider:
    """Live replay against the Anthropic API.

    Lazy import — the `anthropic` SDK is in the `[live]` extra, not a
    required dependency. Importing `hindsight.replay` on a stdlib-only
    install must succeed; the SDK is only resolved when this class is
    instantiated.

    Reads `ANTHROPIC_API_KEY` from env. Honors the `model` override at call
    time. Re-issues the recorded `request.messages` (if present) and writes
    the resulting completion into the returned step's `response`.
    """

    name = "anthropic"

    def __init__(self, *, api_key: str | None = None) -> None:
        # Lazy import so module load doesn't require the SDK.
        try:
            from anthropic import Anthropic  # noqa: F401  (deferred resolution)
        except ImportError as exc:  # pragma: no cover — exercised only with [live]
            raise ImportError(
                "AnthropicProvider requires the `anthropic` SDK. "
                "Install with: pip install 'hindsight-trace[live]'"
            ) from exc
        from anthropic import Anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "AnthropicProvider needs ANTHROPIC_API_KEY in env "
                "(or pass api_key=...)"
            )
        self._client = Anthropic(api_key=key)

    def simulate(self, step: TraceStep, *, model: str | None = None) -> TraceStep:
        # The recorded request shape is whatever the originating adapter
        # captured. We expect at minimum `messages: [...]`. If it's absent
        # we fall back to MockProvider behavior — we have nothing to send.
        req = step.request or {}
        messages = req.get("messages")
        target_model = model or step.model
        if messages is None or not target_model:
            return MockProvider().simulate(step, model=model)

        # Anthropic SDK requires max_tokens; pick the recorded out budget
        # if we have one, else a safe default.
        max_tokens = max(step.tokens_out, 1024) if step.tokens_out else 1024
        # System prompt: Anthropic separates it from messages. If the
        # recorded messages contain a leading `role=system`, pull it out.
        system: str | None = None
        chat_messages = list(messages)
        if chat_messages and chat_messages[0].get("role") == "system":
            system = chat_messages[0].get("content")
            chat_messages = chat_messages[1:]

        kwargs: dict = {
            "model": target_model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
        }
        if system is not None:
            kwargs["system"] = system

        completion = self._client.messages.create(**kwargs)
        # The SDK returns content as a list of blocks; collapse to text.
        text_parts = [
            getattr(b, "text", "") for b in getattr(completion, "content", [])
        ]
        return replace(
            step,
            model=target_model,
            request=copy.deepcopy(step.request),
            response={"text": "".join(text_parts)},
            tokens_in=getattr(completion.usage, "input_tokens", step.tokens_in),
            tokens_out=getattr(completion.usage, "output_tokens", step.tokens_out),
            extra=copy.deepcopy(step.extra),
        )


class OpenAIProvider:
    """Live replay against the OpenAI API.

    Lazy import — the `openai` SDK is in the `[live]` extra, not a
    required dependency. Importing `hindsight.replay` on a stdlib-only
    install must succeed; the SDK is only resolved when this class is
    instantiated.

    Reads `OPENAI_API_KEY` from env. Honors the `model` override at call
    time. Re-issues the recorded `request.messages` (if present) and writes
    the resulting completion into the returned step's `response`.

    OpenAI's chat.completions.create accepts messages with role=system
    natively (unlike Anthropic which separates it), so no message
    pre-processing is needed.
    """

    name = "openai"

    def __init__(self, *, model: str = "gpt-4o") -> None:
        # Lazy import so module load doesn't require the SDK.
        try:
            from openai import OpenAI  # noqa: F401  (deferred resolution)
        except ImportError as exc:  # pragma: no cover — exercised only with [live]
            raise ImportError(
                "OpenAIProvider requires the `openai` SDK. "
                "Install with: pip install 'hindsight-trace[live]'"
            ) from exc
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAIProvider needs OPENAI_API_KEY in env"
            )
        self._client = OpenAI(api_key=api_key)
        self._default_model = model

    def simulate(self, step: TraceStep, *, model: str | None = None) -> TraceStep:
        # The recorded request shape is whatever the originating adapter
        # captured. We expect at minimum `messages: [...]`. If it's absent
        # we fall back to MockProvider behavior — we have nothing to send.
        req = step.request or {}
        messages = req.get("messages")
        target_model = model or step.model or self._default_model
        if messages is None:
            return MockProvider().simulate(step, model=model)

        # OpenAI chat.completions accepts role=system messages inline —
        # no need to separate the system prompt as Anthropic requires.
        max_tokens = max(step.tokens_out, 1024) if step.tokens_out else 1024
        resp = self._client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=0,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0].message
        return replace(
            step,
            model=target_model,
            request=copy.deepcopy(step.request),
            response={"text": choice.content or ""},
            tokens_in=getattr(getattr(resp, "usage", None), "prompt_tokens", step.tokens_in),
            tokens_out=getattr(getattr(resp, "usage", None), "completion_tokens", step.tokens_out),
            extra={**(copy.deepcopy(step.extra) or {}), "replayed_by": "openai"},
        )


def _resolve_from_step(run: TraceRun, from_step: str | int) -> int:
    """Resolve `from_step` to a positional index into `run.steps`.

    Accepts either a step `id` (string match) or an int index. Negative
    indices are not supported — silent off-by-one bugs in replay are
    worse than a clear ValueError. Raises ValueError on unknown id or
    out-of-range int. (Documented in test_replay_invalid_step_id_raises.)
    """
    if isinstance(from_step, int):
        if from_step < 0 or from_step >= len(run.steps):
            raise ValueError(
                f"from_step index {from_step} out of range "
                f"for run with {len(run.steps)} steps"
            )
        return from_step
    if isinstance(from_step, str):
        for i, s in enumerate(run.steps):
            if s.id == from_step:
                return i
        raise ValueError(
            f"from_step id {from_step!r} not found among run steps "
            f"(have {[s.id for s in run.steps]})"
        )
    raise TypeError(f"from_step must be str or int, got {type(from_step).__name__}")


def replay(
    run: TraceRun,
    from_step: str | int,
    *,
    provider: Provider | None = None,
    model: str | None = None,
    live: bool = False,
) -> TraceRun:
    """Replay `run` from `from_step` onward, returning a new TraceRun.

    Steps with index < `from_step` are copied verbatim. Steps with index
    >= `from_step` of kind `StepKind.LLM` go through `provider.simulate()`;
    other kinds (AGENT/TOOL/DECISION) are copied verbatim — tool re-
    execution is opt-in behind a separate flag not exposed in v0.2.

    If `model` is provided, the LLM step's `model` field is overridden
    *before* the provider sees it, so the provider can decide how to honor
    the swap.

    Provider defaults to `MockProvider()` (deterministic, no network). If
    `live=True` and no provider is passed, `AnthropicProvider()` is built —
    that's the only code path that touches the network.
    """
    if provider is None:
        provider = AnthropicProvider() if live else MockProvider()

    cutoff = _resolve_from_step(run, from_step)

    new_steps: list[TraceStep] = []
    for i, step in enumerate(run.steps):
        if i < cutoff:
            # Pre-cutoff: byte-identical copy (deep so the original run
            # cannot be mutated through the returned one).
            new_steps.append(
                replace(
                    step,
                    request=copy.deepcopy(step.request),
                    response=copy.deepcopy(step.response),
                    extra=copy.deepcopy(step.extra),
                )
            )
            continue
        if step.kind is not StepKind.LLM:
            # AGENT / TOOL / DECISION — copy verbatim. See module docstring
            # for why tool re-execution is not in v0.2.
            new_steps.append(
                replace(
                    step,
                    request=copy.deepcopy(step.request),
                    response=copy.deepcopy(step.response),
                    extra=copy.deepcopy(step.extra),
                )
            )
            continue
        # LLM step at or after cutoff — apply model override, then provider.
        staged = step
        if model is not None:
            staged = replace(step, model=model)
        new_steps.append(provider.simulate(staged, model=model))

    # Carry run-level metadata; stamp replay provenance into extra. Don't
    # mutate the input's extra dict.
    new_extra = copy.deepcopy(run.extra)
    new_extra["replay"] = {
        "from_step": run.steps[cutoff].id,
        "from_index": cutoff,
        "provider": provider.name,
        "model_override": model,
        "live": live,
    }

    return TraceRun(
        id=run.id,
        source=run.source,
        started_at=run.started_at,
        finished_at=run.finished_at,
        steps=new_steps,
        extra=new_extra,
    )
