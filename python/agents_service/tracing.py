"""MLflow tracing for the two-agent demo.

Per https://docs.databricks.com/aws/en/mlflow3/genai/tracing/integrations/claude-code,
`mlflow.anthropic.autolog()` traces `claude-agent-sdk` runs end-to-end —
prompts, assistant responses, tool calls, timing, and token usage — but ONLY
when the SDK is driven via `ClaudeSDKClient`. The top-level `query()` helper is
explicitly NOT traced. Don't switch back to `query()` without also replacing
this with manual instrumentation.

Configuration:
- `MLFLOW_EXPERIMENT_ID` env var (injected by Databricks Apps via valueFrom).
  If unset, tracing silently disables — the runner still works.
- `MLFLOW_TRACKING_URI` defaults to "databricks".
"""

from __future__ import annotations

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

    _MLFLOW = mlflow
    _ENABLED = True
    logger.info("MLflow tracing active. experiment_id=%s tracking_uri=%s", exp_id, tracking_uri)


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
