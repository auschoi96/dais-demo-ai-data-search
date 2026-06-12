"""Shared constants for Yape search demo setup scripts.

Each value resolves in order:
  1. KEY=VALUE argv overrides — how the bundle's setup job passes per-target
     values (serverless tasks can't set env vars).
  2. DEMO_<KEY> env var — same names the app backend reads (see
     python/agents_service/tools.py).
  3. <KEY> env var.
  4. Default matching the live deployment.
"""

from __future__ import annotations

import os
import sys


def _overrides() -> dict[str, str]:
    out: dict[str, str] = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            out[key.strip().upper()] = value.strip()
    return out


_OV = _overrides()


def _get(key: str, default: str) -> str:
    return _OV.get(key) or os.environ.get(f"DEMO_{key}") or os.environ.get(key) or default


CATALOG = _get("CATALOG", "ac_demo")
SCHEMA = _get("SCHEMA", "agents")
FULL_SCHEMA = f"{CATALOG}.{SCHEMA}"

# Expose the warehouse to WorkspaceClient (scripts read w.config.warehouse_id).
_WAREHOUSE_ID = _get("WAREHOUSE_ID", "")
if _WAREHOUSE_ID:
    os.environ.setdefault("DATABRICKS_WAREHOUSE_ID", _WAREHOUSE_ID)

TABLES = {
    "raw": f"{FULL_SCHEMA}.yape_services_raw",
    "enriched": f"{FULL_SCHEMA}.yape_services_enriched",
    "users": f"{FULL_SCHEMA}.yape_users",
    "eval": f"{FULL_SCHEMA}.yape_search_eval",
    "transactions": f"{FULL_SCHEMA}.yape_transactions",
}

INDEXES = {
    "raw": f"{FULL_SCHEMA}.yape_services_raw_idx",
    "enriched": f"{FULL_SCHEMA}.yape_services_enriched_idx",
}

METRIC_VIEWS = {
    "adoption": f"{FULL_SCHEMA}.yape_service_adoption",
    "avg_ticket": f"{FULL_SCHEMA}.yape_avg_ticket",
    "segment_behavior": f"{FULL_SCHEMA}.yape_segment_behavior",
}

UC_FUNCTIONS = {
    "search_raw": f"{FULL_SCHEMA}.search_yape_services",
    "search_enriched": f"{FULL_SCHEMA}.search_yape_services_enriched",
    "top_services_by_region": f"{FULL_SCHEMA}.top_services_by_region",
    "avg_ticket_by_cohort": f"{FULL_SCHEMA}.avg_ticket_by_cohort",
    "list_services_by_category": f"{FULL_SCHEMA}.list_services_by_category",
    "services_for_segment": f"{FULL_SCHEMA}.services_for_segment",
}

USER_SEGMENTS_VIEW = f"{FULL_SCHEMA}.yape_user_segments"

VS_ENDPOINT = _get("VS_ENDPOINT", "yape-demo-vs-endpoint")
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "databricks-gte-large-en")
LLM_MODEL = _get("LLM_MODEL", "databricks-claude-opus-4-6")
UC_FUNCTION = UC_FUNCTIONS["search_raw"]  # backcompat for existing scripts

TRACE_DESTINATION = {
    "catalog_name": CATALOG,
    "schema_name": SCHEMA,
    "table_prefix": "yape_search",
}
