"""FastAPI app for the Yape two-agent demo.

- POST /api/agents/stream    SSE stream of both agents running in parallel
- GET  /api/services/raw     20-row raw catalog (powers Compare page)
- GET  /api/services/enriched
- GET  /api/benchmark
- /                          static React client served from client/dist
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .runner import stream_both
from .tools import _run_sql
from .tracing import init_tracing


ROOT = Path(__file__).resolve().parents[2]
CLIENT_DIST = ROOT / "client" / "dist"


app = FastAPI(title="Yape Agents", version="2.0.0")

# Configure MLflow tracing once at import time (no-op if MLFLOW_EXPERIMENT_ID
# is unset). Both agents' traces land in this experiment.
init_tracing()


@app.post("/api/agents/stream")
async def agents_stream(req: Request) -> EventSourceResponse:
    body = await req.json()
    user_query = (body.get("query") or "").strip()
    model = (body.get("model") or "opus").strip()
    if not user_query:
        return JSONResponse({"error": "query is required"}, status_code=400)

    async def event_gen():
        async for evt in stream_both(user_query, model=model):
            if await req.is_disconnected():
                break
            yield {"event": evt.get("type", "message"), "data": json.dumps(evt)}

    return EventSourceResponse(event_gen())


@app.get("/api/services/raw")
def services_raw() -> JSONResponse:
    result = _run_sql(
        "SELECT service_id, name, category, icon, description "
        "FROM ac_demo.agents.yape_services_raw ORDER BY service_id"
    )
    return JSONResponse(result)


@app.get("/api/services/enriched")
def services_enriched() -> JSONResponse:
    result = _run_sql(
        "SELECT service_id, name, category, icon, description, "
        "intent_tags, user_intent_phrases "
        "FROM ac_demo.agents.yape_services_enriched ORDER BY service_id"
    )
    return JSONResponse(result)


@app.get("/api/benchmark")
def benchmark() -> JSONResponse:
    # Hand-loaded numbers for now; the eval harness will overwrite this table later.
    rows = [
        {"agent": "vibe", "label": "Vibe-Coded Agent", "hit_at_4": 0.55, "avg_tool_calls": 6.4, "avg_latency_ms": 18500},
        {"agent": "ready", "label": "AI-Ready Agent", "hit_at_4": 0.95, "avg_tool_calls": 1.4, "avg_latency_ms": 3200},
    ]
    return JSONResponse({"ok": True, "rows": rows})


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


if CLIENT_DIST.exists():
    app.mount("/", StaticFiles(directory=str(CLIENT_DIST), html=True), name="client")
