"""Run vibe and AI-ready agents in parallel and stream SSE events.

Each agent runs as a `ClaudeSDKClient` session against the Databricks AI Gateway
via `auth.gateway_env()`. The vibe agent gets one tool (`execute_sql`); the
AI-ready agent gets three governed UC-function tools.

`ClaudeSDKClient` (not the top-level `query()` helper) is required for MLflow
autolog — see `tracing.py` and the Databricks Claude Code docs. Don't switch
back to `query()` without re-adding manual span instrumentation.

The runner emits these event types per agent:
  - session_start  {agent}
  - text_delta     {agent, text}
  - tool_call      {agent, tool, args, call_id}
  - tool_result    {agent, call_id, output, is_error}
  - done           {agent, tokens, cost_usd, latency_ms, num_tool_calls}
  - error          {agent, message}

Events are interleaved by arrival time — both agents' progress streams together.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    UserMessage,
)

from .auth import gateway_env
from .tools import (
    READY_ALLOWED,
    READY_TOOLS,
    VIBE_ALLOWED,
    VIBE_TOOLS,
)


AgentKind = Literal["vibe", "ready"]


def _extract_tool_result_text(payload: Any) -> str:
    """ToolResultBlock.content can be a string, a list of MCP dict parts, or a
    list of SDK TextBlock objects. Flatten to a single string for the UI."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts: list[str] = []
        for p in payload:
            if isinstance(p, dict):
                parts.append(str(p.get("text") or p.get("content") or ""))
            else:
                parts.append(str(getattr(p, "text", "") or ""))
        return "".join(parts)
    return str(payload)


VIBE_SYSTEM = (
    "You are a Yape fintech data analyst. You have ONE tool: `execute_sql` against "
    "a Databricks SQL warehouse. The data lives in `ac_demo.agents`. You don't know "
    "the schema — start by listing tables (e.g. `SHOW TABLES IN ac_demo.agents LIKE 'yape_%'`) "
    "and describing the ones that look relevant (`DESCRIBE TABLE ac_demo.agents.yape_transactions`). "
    "Then write the SQL you need to answer the question. If a query fails or returns "
    "nothing useful, try a different one. Show your work — narrate each query briefly. "
    "Answer in the user's language. Be honest if the data doesn't support a clean answer."
)

READY_SYSTEM = (
    "You are a Yape fintech assistant with access to governed AI-ready data on the "
    "Databricks platform. You have these tools:\n"
    "- search_yape_services_enriched(query): semantic catalog search via enriched "
    "embeddings (intent tags + bilingual EN/ES phrases). USE FIRST for ambiguous "
    "wording or non-English — 'plata', 'alquiler', 'ahorrar', 'streaming'. Returns "
    "service_ids.\n"
    "- list_services_by_category(category): fast catalog lookup for named categories "
    "(Insurance, Streaming, Utilities, Transfers, etc.).\n"
    "- top_services_by_region(region, months_back): top-5 services by distinct-user "
    "adoption in a region.\n"
    "- compare_regions_adoption(region_a, region_b, months_back): ONE call side-by-side "
    "region comparison.\n"
    "- avg_ticket_by_cohort(service_id): avg/median ticket per age cohort.\n"
    "- services_for_segment(usage_tier, value_tier): top services for a behavioral "
    "segment. usage_tier ∈ {heavy, medium, light}, value_tier ∈ {high_value, mid_value, "
    "low_value}. Either may be empty.\n"
    "- query_metric_view(view_name, dimensions, measures, filters): generic introspector "
    "for cross-cuts the named tools above don't cover (channel breakdowns, multi-dim "
    "splits). See the tool's own description for view dim/measure catalog.\n"
    "- execute_sql(query): raw SQL fallback. LAST resort — joins, raw transaction "
    "counts, anything no metric view covers.\n\n"
    "Decision tree (try in order):\n"
    "1. Ambiguous / non-English wording → search_yape_services_enriched.\n"
    "2. Named category → list_services_by_category.\n"
    "3. Most popular in <region> → top_services_by_region.\n"
    "4. Compare <region A> vs <region B> → compare_regions_adoption.\n"
    "5. Avg ticket per age cohort → avg_ticket_by_cohort (resolve service first).\n"
    "6. What do <tier> users use → services_for_segment.\n"
    "7. Cross-cut against metric views → query_metric_view.\n"
    "8. Anything else → execute_sql.\n\n"
    "Quote numbers verbatim. Answer in the user's language. Be concise."
)


SUPPORTED_MODELS = {
    "opus": "databricks-claude-opus-4-6",
    "sonnet": "databricks-claude-sonnet-4-6",
    "haiku": "databricks-claude-haiku-4-5",
}


def resolve_model(name: str | None) -> str:
    """Accept short alias ('opus'), full id ('databricks-claude-opus-4-6'), or None."""
    if not name:
        return SUPPORTED_MODELS["opus"]
    return SUPPORTED_MODELS.get(name, name)


def _options(agent: AgentKind, model: str) -> ClaudeAgentOptions:
    # Per-agent MCP server: Vibe's server only registers execute_sql, so the
    # governed tools are literally not in its context. `allowed_tools` adds a
    # belt-and-suspenders permission allowlist on top.
    server = VIBE_TOOLS if agent == "vibe" else READY_TOOLS
    allowed = VIBE_ALLOWED if agent == "vibe" else READY_ALLOWED
    system = VIBE_SYSTEM if agent == "vibe" else READY_SYSTEM
    return ClaudeAgentOptions(
        model=model,
        tools=[],  # strip all built-ins (Bash/Read/Edit/Write)
        mcp_servers={"yape": server},
        allowed_tools=allowed,
        permission_mode="bypassPermissions",
        system_prompt=system,
        env=gateway_env(model),
        setting_sources=[],
    )


async def _run_one(
    user_query: str,
    agent: AgentKind,
    model: str,
    out: asyncio.Queue[dict[str, Any]],
) -> None:
    started = time.monotonic()
    await out.put({"type": "session_start", "agent": agent, "ts": started})
    num_tool_calls = 0
    final_text_parts: list[str] = []

    # ClaudeSDKClient (not query()) is what mlflow.anthropic.autolog patches —
    # tokens, tool calls, timing all land on the autologged trace.
    #
    # CRITICAL: the autolog wraps receive_response() so that `process_sdk_messages`
    # only fires AFTER the wrapped generator's `async for` loop completes
    # naturally. Returning out of this caller-side loop early triggers
    # GeneratorExit and the trace is never created — so we drain the iterator
    # to completion and signal end-of-stream via a flag instead of `return`.
    try:
        async with ClaudeSDKClient(options=_options(agent, model)) as client:
            await client.query(user_query)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        btype = type(block).__name__
                        if btype == "TextBlock" and getattr(block, "text", ""):
                            final_text_parts.append(block.text)
                            await out.put({
                                "type": "text_delta",
                                "agent": agent,
                                "text": block.text,
                            })
                        elif btype == "ToolUseBlock":
                            num_tool_calls += 1
                            full = getattr(block, "name", "")
                            short = full.split("__")[-1] if "__" in full else full
                            await out.put({
                                "type": "tool_call",
                                "agent": agent,
                                "tool": short,
                                "args": getattr(block, "input", {}),
                                "call_id": getattr(block, "id", ""),
                            })
                elif isinstance(msg, UserMessage):
                    # Tool results come back as UserMessage with ToolResultBlock content.
                    content = msg.content if isinstance(msg.content, list) else []
                    for block in content:
                        if type(block).__name__ == "ToolResultBlock":
                            output = _extract_tool_result_text(getattr(block, "content", ""))
                            await out.put({
                                "type": "tool_result",
                                "agent": agent,
                                "call_id": getattr(block, "tool_use_id", ""),
                                "output": output,
                                "is_error": bool(getattr(block, "is_error", False)),
                            })
                elif isinstance(msg, ResultMessage):
                    latency_ms = int((time.monotonic() - started) * 1000)
                    usage = msg.usage or {}
                    tokens = int(
                        usage.get("total_tokens")
                        or (usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
                    )
                    cost = float(msg.total_cost_usd or 0.0)
                    await out.put({
                        "type": "done",
                        "agent": agent,
                        "tokens": tokens,
                        "cost_usd": cost,
                        "latency_ms": latency_ms,
                        "num_tool_calls": num_tool_calls,
                    })
                    # Do NOT `return` here — the autolog's wrapped
                    # receive_response only emits the trace after its own loop
                    # exits naturally. ResultMessage is the last message the
                    # underlying generator yields, so the loop will end on the
                    # next iteration on its own.
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        err_msg = f"{type(exc).__name__}: {exc}"
        await out.put({
            "type": "error",
            "agent": agent,
            "message": err_msg,
            "latency_ms": latency_ms,
        })


async def stream_both(
    user_query: str, model: str | None = None
) -> AsyncIterator[dict[str, Any]]:
    """Run both agents in parallel and yield SSE events as they arrive."""
    resolved = resolve_model(model)
    out: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def _runner(kind: AgentKind) -> None:
        try:
            await _run_one(user_query, kind, resolved, out)
        finally:
            await out.put({"__sentinel__": kind})  # type: ignore[arg-type]

    tasks = [asyncio.create_task(_runner("vibe")), asyncio.create_task(_runner("ready"))]
    finished: set[str] = set()
    try:
        while len(finished) < 2:
            msg = await out.get()
            if isinstance(msg, dict) and msg.get("__sentinel__"):
                finished.add(msg["__sentinel__"])  # type: ignore[arg-type]
                continue
            yield msg
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
