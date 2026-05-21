"""Resolve Anthropic-compatible env vars for the Databricks AI Gateway.

The app's service principal credentials (DATABRICKS_CLIENT_ID / SECRET, injected
by Databricks Apps) are exchanged for a short-lived OAuth bearer via the SDK.
That bearer becomes ANTHROPIC_AUTH_TOKEN, and the SDK is pointed at the
workspace's /ai-gateway/anthropic endpoint with `coding-agent-mode` on.
"""

from __future__ import annotations

import os

from databricks.sdk import WorkspaceClient


GATEWAY_PATH = "/ai-gateway/anthropic"

# The SDK has an internal alias table (DEFAULT_OPUS_MODEL etc.) it uses to pick
# a model when the agent asks for "opus" or "sonnet" generically. We pin all
# three so the Databricks gateway returns a model it actually serves.
GATEWAY_MODELS = {
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "databricks-claude-opus-4-7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "databricks-claude-sonnet-4-6",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "databricks-claude-haiku-4-5",
}


def _bearer_from_sdk() -> tuple[str, str]:
    """Return (host, bearer_token) from the SDK's auth chain (SP in Apps)."""
    w = WorkspaceClient()
    host = (w.config.host or "").rstrip("/")
    headers = w.config.authenticate()
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise RuntimeError(
            "Could not resolve a Bearer token from the Databricks SDK. "
            "Set DATABRICKS_CLIENT_ID/SECRET or DATABRICKS_TOKEN."
        )
    return host, auth[len("Bearer ") :]


def gateway_env(model: str = "databricks-claude-opus-4-6") -> dict[str, str]:
    """Build the env block claude-agent-sdk needs to talk to the AI Gateway."""
    host, bearer = _bearer_from_sdk()
    env = {
        **os.environ,
        "ANTHROPIC_BASE_URL": f"{host}{GATEWAY_PATH}",
        "ANTHROPIC_AUTH_TOKEN": bearer,
        "ANTHROPIC_MODEL": model,
        "ANTHROPIC_CUSTOM_HEADERS": "x-databricks-use-coding-agent-mode: true",
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
        **GATEWAY_MODELS,
    }
    # Strip internal Claude Code env that leaks from the running process and
    # confuses a subprocess. Mirrors skillforge sdk_runner._SKIP_KEYS.
    for k in (
        "CLAUDE_CODE_SSE_PORT",
        "CLAUDE_CODE_ENTRYPOINT",
        "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY",
        "ANTHROPIC_API_KEY",
    ):
        env.pop(k, None)
    return env
