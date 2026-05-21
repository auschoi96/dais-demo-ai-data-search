"""MLflow tracing for the two-agent demo.

`mlflow.anthropic.autolog()` patches the Python `anthropic` SDK in-process only.
`claude-agent-sdk` spawns a `claude` CLI subprocess that talks to the gateway
directly, so autolog can't see those calls. We emit traces manually from the
events the runner already produces — one trace per agent run, with a root
agent span and one child span per tool call.

Configuration:
- `MLFLOW_EXPERIMENT_ID` env var (injected by Databricks Apps via valueFrom).
  If unset, tracing silently disables — the runner still works.
- `MLFLOW_TRACKING_URI` defaults to "databricks" (the workspace's own tracking
  server). Override only for local dev against a different MLflow server.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("agents_service.tracing")

_INITIALIZED = False
_EXPERIMENT_ID: str | None = None
_MLFLOW: Any = None  # lazily imported so missing mlflow at import time doesn't break the app


def init_tracing() -> None:
    """Call once at app startup. Idempotent."""
    global _INITIALIZED, _EXPERIMENT_ID, _MLFLOW
    if _INITIALIZED:
        return
    _INITIALIZED = True

    exp_id = (os.environ.get("MLFLOW_EXPERIMENT_ID") or "").strip()
    if not exp_id:
        logger.info("MLFLOW_EXPERIMENT_ID not set — tracing disabled.")
        return

    try:
        import mlflow  # type: ignore
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

    _MLFLOW = mlflow
    _EXPERIMENT_ID = exp_id
    logger.info("MLflow tracing active. experiment_id=%s tracking_uri=%s", exp_id, tracking_uri)


def emit_agent_trace(
    *,
    agent: str,
    model: str,
    query: str,
    final_answer: str,
    events: list[dict[str, Any]],
    tokens: int,
    cost_usd: float,
    latency_ms: int,
    error: str | None = None,
) -> None:
    """Synchronously emit a trace for one completed agent run.

    Spans are reconstructed from the buffered SSE events. Tool spans are
    nested inside an agent root span; tool inputs/outputs come from the
    matched tool_call/tool_result pair. Tokens, cost, and latency are
    attached as attributes on the root span.
    """
    if _MLFLOW is None:
        return

    try:
        with _MLFLOW.start_span(
            name=f"agent.{agent}",
            span_type="AGENT",
            attributes={
                "agent.kind": agent,
                "agent.model": model,
                "agent.tokens": tokens,
                "agent.cost_usd": cost_usd,
                "agent.latency_ms": latency_ms,
                "agent.num_tool_calls": sum(1 for e in events if e.get("type") == "tool_call"),
            },
        ) as root:
            root.set_inputs({"query": query, "model": model})

            # Build a quick lookup of tool_result events by call_id.
            results_by_id: dict[str, dict[str, Any]] = {
                e.get("call_id", ""): e for e in events if e.get("type") == "tool_result"
            }

            for evt in events:
                if evt.get("type") != "tool_call":
                    continue
                call_id = evt.get("call_id", "")
                short_name = str(evt.get("tool") or "tool").split(".")[-1]
                result = results_by_id.get(call_id)

                with _MLFLOW.start_span(
                    name=f"tool.{short_name}",
                    span_type="TOOL",
                    attributes={
                        "tool.name": evt.get("tool"),
                        "tool.call_id": call_id,
                    },
                ) as tool_span:
                    tool_span.set_inputs(_safe_args(evt.get("args")))
                    if result is not None:
                        tool_span.set_outputs({"output": _truncate(result.get("output"))})
                        if result.get("is_error"):
                            try:
                                tool_span.set_status("ERROR")
                            except Exception:  # noqa: BLE001
                                pass

            root.set_outputs({"answer": _truncate(final_answer)})
            if error:
                try:
                    root.set_status("ERROR")
                except Exception:  # noqa: BLE001
                    pass
                root.set_attribute("agent.error", error)
    except Exception as exc:  # noqa: BLE001
        # Never let tracing break a demo run.
        logger.warning("emit_agent_trace failed (%s)", exc)


def _safe_args(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return {k: _truncate(v) for k, v in args.items()}
    return {"value": _truncate(args)}


def _truncate(v: Any, limit: int = 4000) -> Any:
    if v is None:
        return None
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s
