#!/usr/bin/env python3
"""Register UC functions used as Supervisor agent tools.

Four functions registered:

- search_yape_services            — Vibe-coded agent tool: VS on raw index
- search_yape_services_enriched   — AI-Ready agent tool: VS on enriched index
- top_services_by_region          — AI-Ready agent tool: metric view (adoption)
- avg_ticket_by_cohort            — AI-Ready agent tool: metric view (avg ticket)
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient

from _config import FULL_SCHEMA, INDEXES, METRIC_VIEWS, UC_FUNCTIONS


def function_body(name: str, sql: str) -> str:
    return f"CREATE OR REPLACE FUNCTION {name}\n{sql}"


SEARCH_RAW = function_body(
    UC_FUNCTIONS["search_raw"],
    f"""(query STRING COMMENT 'User query in any language')
RETURNS TABLE (
  service_id STRING,
  name STRING,
  category STRING,
  description STRING,
  score DOUBLE
)
COMMENT 'Search the Yape service catalog by name + category + description. Backed by Vector Search on the RAW catalog only — no intent tags, no enriched phrases. Use this to find services from a user query.'
RETURN
  SELECT service_id, name, category, description, search_score AS score
  FROM vector_search(
    index => '{INDEXES["raw"]}',
    query_text => query,
    num_results => 4
  )""",
)

SEARCH_ENRICHED = function_body(
    UC_FUNCTIONS["search_enriched"],
    f"""(query STRING COMMENT 'User query in any language including Spanish intent phrases')
RETURNS TABLE (
  service_id STRING,
  name STRING,
  category STRING,
  description STRING,
  score DOUBLE
)
COMMENT 'Search the Yape service catalog by user intent. Backed by Vector Search on the AI-READY enriched catalog (semantic descriptions, intent tags, bilingual user phrases). Use for intent-style queries like "I want to save money" or "quiero ahorrar".'
RETURN
  SELECT service_id, name, category, description, search_score AS score
  FROM vector_search(
    index => '{INDEXES["enriched"]}',
    query_text => query,
    num_results => 4
  )""",
)

TOP_SERVICES = function_body(
    UC_FUNCTIONS["top_services_by_region"],
    f"""(
  region_filter STRING COMMENT 'Region name: Lima, Arequipa, Cusco, Trujillo, or Chiclayo',
  months_back INT DEFAULT 1 COMMENT 'How many months back to include (1=current month, 3=last 3 months)'
)
RETURNS TABLE (
  service_id STRING,
  service_name STRING,
  category STRING,
  distinct_users BIGINT,
  total_transactions BIGINT,
  total_volume_pen DOUBLE
)
COMMENT 'Rank Yape services by distinct-user adoption in a given region over the trailing N months. Queries the yape_service_adoption metric view and joins to the enriched service catalog for human-readable names. Returns top 5.'
RETURN
  WITH ranked AS (
    SELECT
      service_id,
      MEASURE(distinct_users) AS distinct_users,
      MEASURE(total_transactions) AS total_transactions,
      MEASURE(total_volume_pen) AS total_volume_pen
    FROM {METRIC_VIEWS["adoption"]}
    WHERE region = region_filter
      AND month >= DATE_TRUNC('MONTH', CURRENT_DATE() - make_interval(0, months_back, 0, 0, 0, 0, 0))
    GROUP BY service_id
    ORDER BY distinct_users DESC
    LIMIT 5
  )
  SELECT
    r.service_id,
    s.name AS service_name,
    s.category,
    r.distinct_users,
    r.total_transactions,
    r.total_volume_pen
  FROM ranked r
  LEFT JOIN ac_demo.agents.yape_services_enriched s ON s.service_id = r.service_id
  ORDER BY r.distinct_users DESC""",
)

AVG_TICKET = function_body(
    UC_FUNCTIONS["avg_ticket_by_cohort"],
    f"""(
  service_id_filter STRING COMMENT 'Service id like s01..s20. Use search_yape_services_enriched first to resolve a service name to an id.'
)
RETURNS TABLE (
  age_cohort STRING,
  avg_ticket_pen DOUBLE,
  median_ticket_pen DOUBLE,
  transaction_count BIGINT
)
COMMENT 'Average and median ticket size for a service, broken out by age cohort. Queries the yape_avg_ticket metric view.'
RETURN
  SELECT
    age_cohort,
    MEASURE(avg_ticket_pen) AS avg_ticket_pen,
    MEASURE(median_ticket_pen) AS median_ticket_pen,
    MEASURE(transaction_count) AS transaction_count
  FROM {METRIC_VIEWS["avg_ticket"]}
  WHERE service_id = service_id_filter
  GROUP BY age_cohort
  ORDER BY transaction_count DESC""",
)

LIST_SERVICES_BY_CATEGORY = function_body(
    UC_FUNCTIONS["list_services_by_category"],
    f"""(
  category_filter STRING COMMENT 'Service category. Case-insensitive. Valid values: Credit, Top-ups, Utilities, Delivery, Investments, Insurance, Streaming, Transfers, Education, Business, Health, Supermarkets, Transport.'
)
RETURNS TABLE (
  service_id STRING,
  name STRING,
  category STRING,
  description STRING
)
COMMENT 'List all Yape services in a given category. Faster than search_yape_services_enriched when the user names a known category (e.g. "insurance product", "streaming services"). Returns the enriched catalog rows so the agent can pick by intent_tags or description.'
RETURN
  SELECT service_id, name, category, description
  FROM {FULL_SCHEMA}.yape_services_enriched
  WHERE lower(category) = lower(category_filter)
  ORDER BY service_id""",
)

SERVICES_FOR_SEGMENT = function_body(
    UC_FUNCTIONS["services_for_segment"],
    f"""(
  usage_tier_filter STRING COMMENT 'User behavior tier: heavy | medium | light (or NULL for any)',
  value_tier_filter STRING COMMENT 'User value tier: high_value | mid_value | low_value (or NULL for any)'
)
RETURNS TABLE (
  service_id STRING,
  service_name STRING,
  category STRING,
  distinct_users BIGINT,
  total_transactions BIGINT,
  avg_ticket_pen DOUBLE
)
COMMENT 'Top services adopted by a behavioral user segment. Tiers are derived from transaction count (usage_tier) and total volume (value_tier) over the last 90 days. Backed by the yape_segment_behavior metric view.'
RETURN
  SELECT
    s.service_id,
    e.name AS service_name,
    e.category,
    s.distinct_users,
    s.total_transactions,
    s.avg_ticket_pen
  FROM (
    SELECT
      service_id,
      MEASURE(distinct_users) AS distinct_users,
      MEASURE(total_transactions) AS total_transactions,
      ROUND(MEASURE(avg_ticket_pen), 2) AS avg_ticket_pen
    FROM {METRIC_VIEWS["segment_behavior"]}
    WHERE (usage_tier_filter IS NULL OR usage_tier = usage_tier_filter)
      AND (value_tier_filter IS NULL OR value_tier = value_tier_filter)
    GROUP BY service_id
    ORDER BY distinct_users DESC
    LIMIT 10
  ) s
  LEFT JOIN {FULL_SCHEMA}.yape_services_enriched e ON e.service_id = s.service_id
  ORDER BY s.distinct_users DESC""",
)


def main() -> None:
    w = WorkspaceClient()
    if not w.config.warehouse_id:
        raise RuntimeError("Set DATABRICKS_WAREHOUSE_ID before registering UC functions.")

    for label, body in [
        ("search_yape_services (raw)", SEARCH_RAW),
        ("search_yape_services_enriched", SEARCH_ENRICHED),
        ("top_services_by_region", TOP_SERVICES),
        ("avg_ticket_by_cohort", AVG_TICKET),
        ("list_services_by_category", LIST_SERVICES_BY_CATEGORY),
        ("services_for_segment", SERVICES_FOR_SEGMENT),
    ]:
        print(f"Registering: {label}")
        resp = w.statement_execution.execute_statement(
            warehouse_id=w.config.warehouse_id,
            statement=body,
            wait_timeout="50s",
        )
        if resp.status and resp.status.state and resp.status.state.value != "SUCCEEDED":
            err = resp.status.error.message if resp.status.error else resp.status.state
            raise RuntimeError(f"{label}: {err}")

    print("\nAll UC functions registered.")


if __name__ == "__main__":
    main()
