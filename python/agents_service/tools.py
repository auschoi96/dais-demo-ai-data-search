"""Custom MCP tools the two Yape agents can call.

One in-process MCP server (`yape_tools`) registers all four functions; per-agent
restrictions are applied via `allowed_tools` in the SDK options. The vibe agent
only sees `execute_sql`; the AI-ready agent only sees the three UC-function
wrappers (no raw SQL).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from databricks.sdk import WorkspaceClient


CATALOG = os.environ.get("DEMO_CATALOG") or "ac_demo"
SCHEMA = os.environ.get("DEMO_SCHEMA") or "agents"
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID") or "01370556fad60fda"

_w: WorkspaceClient | None = None


def _client() -> WorkspaceClient:
    """Lazily-constructed service-principal WorkspaceClient (one per process)."""
    global _w
    if _w is None:
        _w = WorkspaceClient()
    return _w


def _run_sql(statement: str, *, timeout_s: str = "30s") -> dict[str, Any]:
    """Execute SQL against the SP-bound warehouse and shape the result for tools."""
    started = time.monotonic()
    resp = _client().statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        wait_timeout=timeout_s,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)

    state = (resp.status.state.value if resp.status and resp.status.state else "UNKNOWN")
    if state != "SUCCEEDED":
        err = (resp.status.error.message if resp.status and resp.status.error else state)
        return {"ok": False, "error": err, "latency_ms": elapsed_ms}

    columns = [c.name for c in (resp.manifest.schema.columns if resp.manifest and resp.manifest.schema else [])]
    rows = resp.result.data_array if resp.result and resp.result.data_array else []
    return {
        "ok": True,
        "columns": columns,
        "rows": rows[:200],          # truncate so the model isn't drowned
        "row_count": len(rows),
        "latency_ms": elapsed_ms,
    }


def _content(payload: Any) -> dict[str, Any]:
    """Wrap a Python dict as an MCP tool-content response."""
    return {"content": [{"type": "text", "text": json.dumps(payload, default=str)}]}


# ── Vibe agent's one tool ─────────────────────────────────────────────────────


@tool(
    "execute_sql",
    (
        "Execute a SQL query against the Yape Databricks warehouse. The data is in "
        f"catalog `{CATALOG}`, schema `{SCHEMA}`. Useful tables include "
        "`yape_services_raw`, `yape_users`, `yape_transactions`. "
        "Use SHOW TABLES / DESCRIBE TABLE to discover the schema. "
        "Returns up to 200 rows. Read-only — no DDL/DML."
    ),
    {"query": str},
)
async def execute_sql(args: dict[str, Any]) -> dict[str, Any]:
    sql = (args.get("query") or "").strip()
    if not sql:
        return _content({"ok": False, "error": "query is required"})
    # Cheap guardrail — we're a demo, not a sandbox. Just block obvious mutation.
    head = sql.lstrip().split(None, 1)[0].upper() if sql.lstrip() else ""
    if head in {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "MERGE", "CREATE", "TRUNCATE"}:
        return _content({"ok": False, "error": f"Mutation not allowed ({head})"})
    return _content(_run_sql(sql))


# ── AI-ready agent's three tools ──────────────────────────────────────────────


@tool(
    "search_yape_services_enriched",
    (
        "Search the Yape service catalog by user intent. Backed by Vector Search on the "
        "AI-READY enriched catalog (semantic descriptions, intent tags, bilingual user phrases). "
        "Use for intent-style queries like 'I want to save money' or 'quiero ahorrar' — "
        "best way to resolve a user request to a service_id/name."
    ),
    {"query": str},
)
async def search_yape_services_enriched(args: dict[str, Any]) -> dict[str, Any]:
    q = (args.get("query") or "").strip().replace("'", "''")
    if not q:
        return _content({"ok": False, "error": "query is required"})
    sql = f"SELECT * FROM {CATALOG}.{SCHEMA}.search_yape_services_enriched('{q}')"
    return _content(_run_sql(sql))


@tool(
    "top_services_by_region",
    (
        "Rank Yape services by distinct-user adoption in a region over the trailing N months. "
        "Backed by the governed yape_service_adoption metric view. "
        "Valid regions: Lima, Arequipa, Cusco, Trujillo, Chiclayo."
    ),
    {"region": str, "months_back": int},
)
async def top_services_by_region(args: dict[str, Any]) -> dict[str, Any]:
    region = (args.get("region") or "").strip().replace("'", "''")
    months_back = int(args.get("months_back") or 1)
    if not region:
        return _content({"ok": False, "error": "region is required"})
    sql = f"SELECT * FROM {CATALOG}.{SCHEMA}.top_services_by_region('{region}', {months_back})"
    return _content(_run_sql(sql))


@tool(
    "avg_ticket_by_cohort",
    (
        "Get avg / median ticket size for a Yape service broken out by age cohort. "
        "Backed by the governed yape_avg_ticket metric view. "
        "Argument is the service_id (e.g. 's01' for Yape Loans). "
        "Resolve a service name to a service_id via search_yape_services_enriched first."
    ),
    {"service_id": str},
)
async def avg_ticket_by_cohort(args: dict[str, Any]) -> dict[str, Any]:
    sid = (args.get("service_id") or "").strip().replace("'", "''")
    if not sid:
        return _content({"ok": False, "error": "service_id is required"})
    sql = f"SELECT * FROM {CATALOG}.{SCHEMA}.avg_ticket_by_cohort('{sid}')"
    return _content(_run_sql(sql))


# Whitelisted metric views the generic introspector can query. The agent can
# only point this tool at known views, and dimension / filter names are checked
# against this catalog (any unknown name is rejected) — so the tool can't be
# used to exfiltrate arbitrary tables.
METRIC_VIEW_CATALOG: dict[str, dict[str, list[str]]] = {
    f"{CATALOG}.{SCHEMA}.yape_service_adoption": {
        "dimensions": ["service_id", "region", "age_cohort", "month", "channel"],
        "measures": ["distinct_users", "total_transactions", "total_volume_pen"],
    },
    f"{CATALOG}.{SCHEMA}.yape_avg_ticket": {
        "dimensions": ["service_id", "age_cohort", "region"],
        "measures": ["avg_ticket_pen", "median_ticket_pen", "transaction_count"],
    },
    f"{CATALOG}.{SCHEMA}.yape_segment_behavior": {
        "dimensions": [
            "service_id", "usage_tier", "value_tier", "region", "age_cohort", "channel",
        ],
        "measures": [
            "distinct_users", "total_transactions", "total_volume_pen", "avg_ticket_pen",
        ],
    },
}


def _canonicalize(name: str, valid: set[str]) -> str | None:
    """Fuzzy-match an LLM-supplied name to a canonical snake_case name.

    Accepts: snake_case, Title Case With Spaces, camelCase, with trailing 'pen'/'PEN'.
    Returns the canonical name from `valid`, or None if no match.
    """
    if name in valid:
        return name
    normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in valid:
        return normalized
    # camelCase → snake_case
    import re as _re
    camel = _re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    if camel in valid:
        return camel
    return None


@tool(
    "query_metric_view",
    (
        "Generic introspection tool for the governed Yape metric views. Use this for "
        "ANY aggregation / ranking / metric question across services, regions, "
        "age cohorts, channels, or behavioral segments. \n\n"
        "Available views (all dim + measure names are snake_case, no quoting needed):\n"
        f"- {CATALOG}.{SCHEMA}.yape_service_adoption\n"
        "    dims: service_id, region, age_cohort, month, channel\n"
        "    measures: distinct_users, total_transactions, total_volume_pen\n"
        f"- {CATALOG}.{SCHEMA}.yape_avg_ticket\n"
        "    dims: service_id, age_cohort, region\n"
        "    measures: avg_ticket_pen, median_ticket_pen, transaction_count\n"
        f"- {CATALOG}.{SCHEMA}.yape_segment_behavior\n"
        "    dims: service_id, usage_tier, value_tier, region, age_cohort, channel\n"
        "    measures: distinct_users, total_transactions, total_volume_pen, avg_ticket_pen\n\n"
        "Examples:\n"
        "  Top services in Lima:\n"
        f"    view_name='{CATALOG}.{SCHEMA}.yape_service_adoption',\n"
        "    dimensions=['service_id'], measures=['distinct_users'],\n"
        "    filters={'region': 'Lima'}\n"
        "  Avg ticket for s01 by age cohort:\n"
        f"    view_name='{CATALOG}.{SCHEMA}.yape_avg_ticket',\n"
        "    dimensions=['age_cohort'], measures=['avg_ticket_pen'],\n"
        "    filters={'service_id': 's01'}\n"
        "  What heavy users use most:\n"
        f"    view_name='{CATALOG}.{SCHEMA}.yape_segment_behavior',\n"
        "    dimensions=['service_id'], measures=['distinct_users'],\n"
        "    filters={'usage_tier': 'heavy'}\n"
        "  Lima vs Trujillo savings:\n"
        f"    view_name='{CATALOG}.{SCHEMA}.yape_service_adoption',\n"
        "    dimensions=['region', 'service_id'], measures=['distinct_users'],\n"
        "    filters={}   (then read both regions out of the result)\n\n"
        "Returns up to 50 rows sorted by the first measure descending. tier values "
        "for segment_behavior: usage_tier ∈ {heavy, medium, light}, value_tier ∈ "
        "{high_value, mid_value, low_value}."
    ),
    {
        "view_name": str,
        "dimensions": list,
        "measures": list,
        "filters": dict,
    },
)
async def query_metric_view(args: dict[str, Any]) -> dict[str, Any]:
    view = (args.get("view_name") or "").strip()
    # Tolerate unqualified or partially-qualified view names.
    if "." not in view:
        view = f"{CATALOG}.{SCHEMA}.{view}"
    elif view.startswith(f"{SCHEMA}."):
        view = f"{CATALOG}.{view}"
    spec = METRIC_VIEW_CATALOG.get(view)
    if not spec:
        return _content(
            {"ok": False, "error": f"unknown view {view!r}; allowed: {list(METRIC_VIEW_CATALOG)}"}
        )
    valid_dims = set(spec["dimensions"])
    valid_measures = set(spec["measures"])

    raw_dims = [d for d in (args.get("dimensions") or []) if isinstance(d, str)]
    raw_measures = [m for m in (args.get("measures") or []) if isinstance(m, str)]
    raw_filters = args.get("filters") or {}
    if not raw_measures:
        return _content({"ok": False, "error": "at least one measure required"})

    dims: list[str] = []
    for d in raw_dims:
        canon = _canonicalize(d, valid_dims)
        if not canon:
            return _content({"ok": False, "error": f"unknown dimension {d!r}; valid: {sorted(valid_dims)}"})
        dims.append(canon)

    measures: list[str] = []
    for m in raw_measures:
        canon = _canonicalize(m, valid_measures)
        if not canon:
            return _content({"ok": False, "error": f"unknown measure {m!r}; valid: {sorted(valid_measures)}"})
        measures.append(canon)

    filters: dict[str, Any] = {}
    for k, v in raw_filters.items():
        canon = _canonicalize(str(k), valid_dims)
        if not canon:
            return _content({"ok": False, "error": f"unknown filter dim {k!r}; valid: {sorted(valid_dims)}"})
        filters[canon] = v

    dim_cols = ", ".join(dims) if dims else "1"
    measure_cols = ", ".join(f"MEASURE({m}) AS {m}" for m in measures)
    where_parts: list[str] = []
    for k, v in filters.items():
        if isinstance(v, (int, float)):
            where_parts.append(f"{k} = {v}")
        else:
            where_parts.append(f"{k} = '{str(v).replace(chr(39), chr(39)*2)}'")
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    group_clause = f"GROUP BY {dim_cols}" if dims else ""
    order_target = measures[0]
    select_dims = (dim_cols + ", ") if dims else ""

    sql = (
        f"SELECT {select_dims}{measure_cols} "
        f"FROM {view} {where_clause} {group_clause} "
        f"ORDER BY {order_target} DESC LIMIT 50"
    )
    return _content(_run_sql(sql))


@tool(
    "list_services_by_category",
    (
        "List all Yape services in a given category. Fast path for category-known "
        "queries like 'which insurance product...' or 'streaming services'. Valid "
        "categories: Credit, Top-ups, Utilities, Delivery, Investments, Insurance, "
        "Streaming, Transfers, Education, Business, Health, Supermarkets, Transport."
    ),
    {"category": str},
)
async def list_services_by_category(args: dict[str, Any]) -> dict[str, Any]:
    cat = (args.get("category") or "").strip().replace("'", "''")
    if not cat:
        return _content({"ok": False, "error": "category is required"})
    sql = f"SELECT * FROM {CATALOG}.{SCHEMA}.list_services_by_category('{cat}')"
    return _content(_run_sql(sql))


@tool(
    "services_for_segment",
    (
        "Top services adopted by a behavioral user segment. Tiers are derived from "
        "transaction count (usage_tier: heavy | medium | light) and total volume "
        "(value_tier: high_value | mid_value | low_value) over the last 90 days. "
        "Pass null/empty for a dimension to leave it unconstrained. Backed by the "
        "yape_segment_behavior metric view."
    ),
    {"usage_tier": str, "value_tier": str},
)
async def services_for_segment(args: dict[str, Any]) -> dict[str, Any]:
    u = (args.get("usage_tier") or "").strip().replace("'", "''") or None
    v = (args.get("value_tier") or "").strip().replace("'", "''") or None
    u_sql = f"'{u}'" if u else "NULL"
    v_sql = f"'{v}'" if v else "NULL"
    sql = f"SELECT * FROM {CATALOG}.{SCHEMA}.services_for_segment({u_sql}, {v_sql})"
    return _content(_run_sql(sql))


@tool(
    "compare_regions_adoption",
    (
        "Compare service adoption between TWO regions in a single call. Returns each "
        "region's top services side-by-side ranked by distinct users. Backed by the "
        "yape_service_adoption metric view. Use for 'compare X vs Y' / 'X vs Y adoption' "
        "questions instead of calling top_services_by_region twice."
    ),
    {"region_a": str, "region_b": str, "months_back": int},
)
async def compare_regions_adoption(args: dict[str, Any]) -> dict[str, Any]:
    a = (args.get("region_a") or "").strip().replace("'", "''")
    b = (args.get("region_b") or "").strip().replace("'", "''")
    months_back = int(args.get("months_back") or 1)
    if not a or not b:
        return _content({"ok": False, "error": "region_a and region_b are required"})
    sql = f"""
      WITH a AS (SELECT * FROM {CATALOG}.{SCHEMA}.top_services_by_region('{a}', {months_back})),
           b AS (SELECT * FROM {CATALOG}.{SCHEMA}.top_services_by_region('{b}', {months_back}))
      SELECT '{a}' AS region, service_id, service_name, category,
             distinct_users, total_transactions, total_volume_pen
      FROM a
      UNION ALL
      SELECT '{b}' AS region, service_id, service_name, category,
             distinct_users, total_transactions, total_volume_pen
      FROM b
      ORDER BY region, distinct_users DESC
    """
    return _content(_run_sql(sql))


# ── MCP server registration ──────────────────────────────────────────────────
#
# IMPORTANT: each agent gets its OWN MCP server with only the tools it is
# allowed to see. claude-agent-sdk's `allowed_tools` is a *permission* layer,
# and `permission_mode="bypassPermissions"` bypasses it — so the only reliable
# way to keep Vibe out of the governed tools is to not register them on Vibe's
# server in the first place.

VIBE_TOOLS = create_sdk_mcp_server(
    name="yape",
    version="1.0.0",
    tools=[execute_sql],
)

READY_TOOLS = create_sdk_mcp_server(
    name="yape",
    version="1.0.0",
    tools=[
        execute_sql,
        search_yape_services_enriched,
        list_services_by_category,
        top_services_by_region,
        compare_regions_adoption,
        avg_ticket_by_cohort,
        services_for_segment,
        query_metric_view,
    ],
)

# Tool names as the SDK exposes them (mcp__<server>__<tool>).
TOOL_EXECUTE_SQL = "mcp__yape__execute_sql"
TOOL_SEARCH_ENRICHED = "mcp__yape__search_yape_services_enriched"
TOOL_LIST_BY_CATEGORY = "mcp__yape__list_services_by_category"
TOOL_TOP_SERVICES = "mcp__yape__top_services_by_region"
TOOL_AVG_TICKET = "mcp__yape__avg_ticket_by_cohort"
TOOL_COMPARE_REGIONS = "mcp__yape__compare_regions_adoption"
TOOL_SERVICES_FOR_SEGMENT = "mcp__yape__services_for_segment"
TOOL_QUERY_METRIC_VIEW = "mcp__yape__query_metric_view"

VIBE_ALLOWED = [TOOL_EXECUTE_SQL]
READY_ALLOWED = [
    TOOL_EXECUTE_SQL,
    TOOL_SEARCH_ENRICHED,
    TOOL_LIST_BY_CATEGORY,
    TOOL_TOP_SERVICES,
    TOOL_AVG_TICKET,
    TOOL_COMPARE_REGIONS,
    TOOL_SERVICES_FOR_SEGMENT,
    TOOL_QUERY_METRIC_VIEW,
]
