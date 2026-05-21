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
    "transactions": f"{FULL_SCHEMA}.yape_transactions",
}

INDEXES = {
    "raw": f"{FULL_SCHEMA}.yape_services_raw_idx",
    "enriched": f"{FULL_SCHEMA}.yape_services_enriched_idx",
}

METRIC_VIEWS = {
    "adoption": f"{FULL_SCHEMA}.yape_service_adoption",
    "avg_ticket": f"{FULL_SCHEMA}.yape_avg_ticket",
}

UC_FUNCTIONS = {
    "search_raw": f"{FULL_SCHEMA}.search_yape_services",
    "search_enriched": f"{FULL_SCHEMA}.search_yape_services_enriched",
    "top_services_by_region": f"{FULL_SCHEMA}.top_services_by_region",
    "avg_ticket_by_cohort": f"{FULL_SCHEMA}.avg_ticket_by_cohort",
    "list_services_by_category": f"{FULL_SCHEMA}.list_services_by_category",
    "services_for_segment": f"{FULL_SCHEMA}.services_for_segment",
}

METRIC_VIEWS["segment_behavior"] = f"{FULL_SCHEMA}.yape_segment_behavior"

USER_SEGMENTS_VIEW = f"{FULL_SCHEMA}.yape_user_segments"

VS_ENDPOINT = "yape-search-demo-endpoint"
EMBEDDING_MODEL = "databricks-qwen3-embedding-0-6b"
LLM_MODEL = "databricks-claude-opus-4-6"
UC_FUNCTION = UC_FUNCTIONS["search_raw"]  # backcompat for existing scripts

TRACE_DESTINATION = {
    "catalog_name": CATALOG,
    "schema_name": SCHEMA,
    "table_prefix": "yape_search",
}
