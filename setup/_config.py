"""Shared constants for Yape search demo setup scripts."""

from __future__ import annotations

CATALOG = "ac_demo"
SCHEMA = "agents"
FULL_SCHEMA = f"{CATALOG}.{SCHEMA}"

TABLES = {
    "raw": f"{FULL_SCHEMA}.yape_services_raw",
    "enriched": f"{FULL_SCHEMA}.yape_services_enriched",
    "users": f"{FULL_SCHEMA}.yape_users",
    "eval": f"{FULL_SCHEMA}.yape_search_eval",
}

INDEXES = {
    "raw": f"{FULL_SCHEMA}.yape_services_raw_idx",
    "enriched": f"{FULL_SCHEMA}.yape_services_enriched_idx",
}

VS_ENDPOINT = "yape-search-demo-endpoint"
EMBEDDING_MODEL = "databricks-qwen3-embedding-0-6b"
LLM_MODEL = "databricks-claude-opus-4-7"
UC_FUNCTION = f"{FULL_SCHEMA}.search_yape_services"

TRACE_DESTINATION = {
    "catalog_name": CATALOG,
    "schema_name": SCHEMA,
    "table_prefix": "yape_search",
}
