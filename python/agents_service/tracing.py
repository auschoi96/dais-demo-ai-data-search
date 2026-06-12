"""MLflow tracing for the two-agent demo.

Per https://docs.databricks.com/aws/en/mlflow3/genai/tracing/integrations/claude-code,
`mlflow.anthropic.autolog()` traces `claude-agent-sdk` runs end-to-end —
prompts, assistant responses, tool calls, timing, and token usage — but ONLY
when the SDK is driven via `ClaudeSDKClient`. The top-level `query()` helper is
explicitly NOT traced. Don't switch back to `query()` without also replacing
this with manual instrumentation.

Cost / model workaround: MLflow's claude_code autolog never sets `mlflow.llm.cost`
on the trace — it relies on LiteLLM's pricing table, which doesn't recognize
the Databricks gateway model names (e.g. `databricks-claude-opus-4-6`). The
autolog also sets a plain `"model"` attribute, not the canonical
`mlflow.llm.model` / `mlflow.llm.provider`, so the experiment Overview's Cost
Breakdown chart has no model to group by (it renders `NULL_VALUE`).

claude-agent-sdk already computes the actual USD spend on each run
(`ResultMessage.total_cost_usd`, filled in by the bundled `claude` CLI). We
splice that value plus the canonical model/provider attributes into the trace
by monkey-patching three internals of `mlflow.claude_code.tracing`:
  - `process_sdk_messages` — extract cost + model from the SDK messages into a
    contextvar before the original runs.
  - `_create_sdk_child_spans` — add `mlflow.llm.model` / `mlflow.llm.provider`
    to each LLM child span the autolog creates.
  - `_finalize_trace` — add `mlflow.llm.cost`, `mlflow.llm.model`, and
    `mlflow.llm.provider` to the AGENT root span before its span ends.

Configuration:
- `MLFLOW_EXPERIMENT_ID` env var (injected by Databricks Apps via valueFrom).
  If unset, tracing silently disables — the runner still works.
- `MLFLOW_TRACKING_URI` defaults to "databricks".
"""

from __future__ import annotations

import contextvars
import logging
import os
from typing import Any

logger = logging.getLogger("agents_service.tracing")

_INITIALIZED = False
_ENABLED = False
_MLFLOW: Any = None  # lazily imported so missing mlflow at import time doesn't break the app


def init_tracing() -> None:
    """Call once at app startup. Idempotent."""
    global _INITIALIZED, _ENABLED, _MLFLOW
    if _INITIALIZED:
        return
    _INITIALIZED = True

    exp_id = (os.environ.get("MLFLOW_EXPERIMENT_ID") or "").strip()
    if not exp_id:
        logger.info("MLFLOW_EXPERIMENT_ID not set — tracing disabled.")
        return

    try:
        import mlflow  # type: ignore
        import mlflow.anthropic  # type: ignore  # noqa: F401
    except ImportError:
        logger.warning("mlflow not installed — tracing disabled.")
        return

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI") or "databricks"
    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_id=exp_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MLflow tracking init failed (%s) — tracing disabled.", exc)
        return

    # autolog() does `from anthropic.resources import ...` at the top — if the
    # `anthropic` PyPI package isn't installed it raises ImportError and the
    # ClaudeSDKClient patch never registers. Log loudly so a missing dep
    # doesn't silently disable tracing the way it did pre-3.12.
    try:
        mlflow.anthropic.autolog()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "mlflow.anthropic.autolog() failed (%s) — traces will not be captured. "
            "Most likely cause: `anthropic` package not in requirements.txt.",
            exc,
        )
        return

    _install_cost_patch()

    _MLFLOW = mlflow
    _ENABLED = True
    logger.info("MLflow tracing active. experiment_id=%s tracking_uri=%s", exp_id, tracking_uri)


# Per-run cost + model name, threaded from our `process_sdk_messages` wrapper
# down to `_create_sdk_child_spans` and `_finalize_trace`. All three run on
# the same task inside the autolog's `wrapped_receive_response` post-loop.
_PENDING_COST: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "agents_service_pending_cost", default=None
)
_PENDING_MODEL: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agents_service_pending_model", default=None
)

# All Databricks gateway Claude endpoints route to Anthropic models — fix the
# provider string so the Cost Breakdown chart's "by Provider" view has a
# stable, non-null bucket.
_PROVIDER = "anthropic"


def _install_cost_patch() -> None:
    """Monkey-patch claude_code autolog to attach cost, model, provider to traces.

    Three patches, all on `mlflow.claude_code.tracing`:
    1. `process_sdk_messages` — extract cost + model from SDK messages into
       contextvars, then delegate.
    2. `_create_sdk_child_spans` — augment the LLM child spans with the canonical
       `mlflow.llm.*` AND the OpenTelemetry `gen_ai.*` semconv model/provider.
    3. `_finalize_trace` — set cost + model + provider + token usage on the AGENT
       parent span, in BOTH the `mlflow.llm.*` and `gen_ai.*` namespaces.

    Why two namespaces: the experiment Token Usage chart reads the trace-level
    `mlflow.trace.tokenUsage` metadata (always populated), but the Cost
    Breakdown / Cost Over Time charts compute cost from the OTel GenAI semconv
    span attributes (`gen_ai.response.model` + `gen_ai.usage.*`). MLflow's
    server-side `translate_span_when_storing` would normally bridge mlflow.* →
    gen_ai.*, but it does NOT run on Databricks backends — so without setting
    gen_ai.* ourselves the cost chart groups by a NULL model and shows $0.
    """
    try:
        import mlflow  # type: ignore
        import mlflow.claude_code.tracing as cc_tracing  # type: ignore
        from mlflow.entities import SpanType  # type: ignore
        from mlflow.tracing.constant import GenAiSemconvKey, SpanAttributeKey  # type: ignore
        from claude_agent_sdk.types import (  # type: ignore
            AssistantMessage,
            ResultMessage,
            TextBlock,
            ToolUseBlock,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cost patch deps missing (%s) — cost/model fields will be blank.", exc)
        return

    original_process = cc_tracing.process_sdk_messages
    original_finalize = cc_tracing._finalize_trace

    def _first_model(messages: Any) -> str | None:
        """Return the model name from the first AssistantMessage that carries one."""
        for m in messages:
            if isinstance(m, AssistantMessage) and getattr(m, "model", None):
                return str(m.model)
        return None

    def patched_process(messages: Any, session_id: Any = None) -> Any:
        result_msg = next((m for m in messages if isinstance(m, ResultMessage)), None)
        cost = float(getattr(result_msg, "total_cost_usd", 0) or 0) if result_msg else 0.0
        model = _first_model(messages)
        cost_token = _PENDING_COST.set(cost if cost > 0 else None)
        model_token = _PENDING_MODEL.set(model)
        try:
            return original_process(messages, session_id=session_id)
        finally:
            _PENDING_COST.reset(cost_token)
            _PENDING_MODEL.reset(model_token)

    # Replace `_create_sdk_child_spans` with an inline copy that adds the
    # canonical model + provider attributes when it creates each LLM child
    # span. We can't set the attributes after the fact because the autolog
    # ends each span immediately. Re-implementing is cheaper than wrapping
    # `start_span_no_context` globally.
    def patched_create_sdk_child_spans(
        messages: Any, parent_span: Any, tool_result_map: Any
    ) -> str | None:
        final_response = None
        pending_messages: list[dict[str, Any]] = []

        for msg in messages:
            if isinstance(msg, AssistantMessage) and msg.content:
                text_blocks = [b for b in msg.content if isinstance(b, TextBlock)]
                tool_blocks = [b for b in msg.content if isinstance(b, ToolUseBlock)]
                msg_model = getattr(msg, "model", None) or _PENDING_MODEL.get() or "unknown"

                if text_blocks and not tool_blocks:
                    text = "\n".join(b.text for b in text_blocks)
                    if text.strip():
                        final_response = text

                    llm_span = mlflow.start_span_no_context(
                        name="llm",
                        parent_span=parent_span,
                        span_type=SpanType.LLM,
                        inputs={"model": msg_model, "messages": pending_messages},
                        attributes={
                            "model": msg_model,
                            SpanAttributeKey.MODEL: msg_model,
                            SpanAttributeKey.MODEL_PROVIDER: _PROVIDER,
                            SpanAttributeKey.MESSAGE_FORMAT: "anthropic",
                            # gen_ai model/provider for the Cost chart's "by Model"
                            # / "by Provider" grouping. No token counts here — the
                            # authoritative aggregate lives on the parent span to
                            # avoid double-counting across spans.
                            GenAiSemconvKey.RESPONSE_MODEL: msg_model,
                            GenAiSemconvKey.REQUEST_MODEL: msg_model,
                            GenAiSemconvKey.PROVIDER_NAME: _PROVIDER,
                        },
                    )
                    llm_span.set_outputs({
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": b.text} for b in text_blocks],
                    })
                    llm_span.end()
                    pending_messages = []
                    continue

                for tool_block in tool_blocks:
                    tool_span = mlflow.start_span_no_context(
                        name=f"tool_{tool_block.name}",
                        parent_span=parent_span,
                        span_type=SpanType.TOOL,
                        inputs=tool_block.input,
                        attributes={"tool_name": tool_block.name, "tool_id": tool_block.id},
                    )
                    tool_span.set_outputs({"result": tool_result_map.get(tool_block.id, "")})
                    tool_span.end()

            if anthropic_msg := cc_tracing._serialize_sdk_message(msg):
                pending_messages.append(anthropic_msg)

        return final_response

    def patched_finalize(parent_span: Any, *args: Any, **kwargs: Any) -> Any:
        cost = _PENDING_COST.get()
        model = _PENDING_MODEL.get()
        # `usage` is the raw SDK ResultMessage.usage dict, passed as a kwarg by
        # the original process_sdk_messages. Mirror MLflow's own accounting:
        # cache-creation tokens are priced like input, cache-read is excluded.
        usage = kwargs.get("usage") or {}
        in_tokens = int(usage.get("input_tokens", 0)) + int(
            usage.get("cache_creation_input_tokens", 0)
        )
        out_tokens = int(usage.get("output_tokens", 0))
        try:
            if model:
                parent_span.set_attribute(SpanAttributeKey.MODEL, model)
                parent_span.set_attribute(SpanAttributeKey.MODEL_PROVIDER, _PROVIDER)
                # gen_ai semconv: this is what the Cost charts read for the
                # model/provider dimension and token magnitudes.
                parent_span.set_attribute(GenAiSemconvKey.RESPONSE_MODEL, model)
                parent_span.set_attribute(GenAiSemconvKey.REQUEST_MODEL, model)
                parent_span.set_attribute(GenAiSemconvKey.PROVIDER_NAME, _PROVIDER)
            if in_tokens or out_tokens:
                parent_span.set_attribute(GenAiSemconvKey.USAGE_INPUT_TOKENS, in_tokens)
                parent_span.set_attribute(GenAiSemconvKey.USAGE_OUTPUT_TOKENS, out_tokens)
            if cost:
                parent_span.set_attribute(
                    SpanAttributeKey.LLM_COST,
                    {"input_cost": 0.0, "output_cost": 0.0, "total_cost": cost},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to attach cost/model to parent span (%s)", exc)
        return original_finalize(parent_span, *args, **kwargs)

    cc_tracing.process_sdk_messages = patched_process
    cc_tracing._create_sdk_child_spans = patched_create_sdk_child_spans
    cc_tracing._finalize_trace = patched_finalize


def tag_active_trace(**tags: Any) -> None:
    """Attach tags (agent kind, model alias, etc.) to the autologged trace.

    Must be called while a `ClaudeSDKClient` run is in progress so there's a
    live trace to mutate. Safe to call when tracing is disabled.
    """
    if not _ENABLED or _MLFLOW is None:
        return
    try:
        _MLFLOW.update_current_trace(tags={k: str(v) for k, v in tags.items() if v is not None})
    except Exception as exc:  # noqa: BLE001
        logger.warning("tag_active_trace failed (%s)", exc)
