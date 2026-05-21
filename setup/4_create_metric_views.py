#!/usr/bin/env python3
"""Create Unity Catalog metric views over yape_transactions.

Two metric views power the AI-ready agent's analytical tools:

- yape_service_adoption — distinct users / total volume per service per region per month
- yape_avg_ticket — avg / median ticket size per service per age cohort
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient

from _config import FULL_SCHEMA, METRIC_VIEWS, TABLES, USER_SEGMENTS_VIEW


def exec_sql(w: WorkspaceClient, statement: str) -> None:
    print(statement.split("\n", maxsplit=1)[0][:120] + "...")
    resp = w.statement_execution.execute_statement(
        warehouse_id=w.config.warehouse_id,
        statement=statement,
        wait_timeout="50s",
    )
    if resp.status and resp.status.state and resp.status.state.value != "SUCCEEDED":
        raise RuntimeError(f"SQL failed: {resp.status.error}")


ADOPTION_YAML = f"""
version: 1.1
source: {TABLES['transactions']}
comment: "Yape service adoption — distinct users, transactions, volume per service / region / month"
dimensions:
  - name: service_id
    expr: service_id
  - name: region
    expr: region
  - name: age_cohort
    expr: age_cohort
  - name: month
    expr: DATE_TRUNC('MONTH', txn_ts)
  - name: channel
    expr: channel
measures:
  - name: distinct_users
    expr: COUNT(DISTINCT user_id)
    comment: "Unique users who transacted this service in the window"
  - name: total_transactions
    expr: COUNT(1)
  - name: total_volume_pen
    expr: SUM(amount_pen)
    comment: "Sum of transaction amounts in Peruvian sol"
"""

AVG_TICKET_YAML = f"""
version: 1.1
source: {TABLES['transactions']}
comment: "Yape ticket-size metrics — avg / median amount per service per cohort"
dimensions:
  - name: service_id
    expr: service_id
  - name: age_cohort
    expr: age_cohort
  - name: region
    expr: region
measures:
  - name: avg_ticket_pen
    expr: AVG(amount_pen)
  - name: median_ticket_pen
    expr: PERCENTILE(amount_pen, 0.5)
  - name: transaction_count
    expr: COUNT(1)
"""

# Behavioral user segments derived from the last 90 days of transactions.
# Usage tier (txn count percentiles): top 20% = heavy, next 30% = medium, rest = light.
# Value tier (total volume percentiles): same split on amount_pen.
USER_SEGMENTS_SQL = f"""
CREATE OR REPLACE VIEW {USER_SEGMENTS_VIEW} AS
WITH per_user AS (
  SELECT
    user_id,
    COUNT(*)                    AS txn_count,
    SUM(amount_pen)             AS total_volume_pen,
    COUNT(DISTINCT service_id)  AS distinct_services,
    MAX(region)                 AS region,
    MAX(age_cohort)             AS age_cohort
  FROM {TABLES['transactions']}
  GROUP BY user_id
),
ranked AS (
  SELECT
    user_id,
    txn_count,
    total_volume_pen,
    distinct_services,
    region,
    age_cohort,
    PERCENT_RANK() OVER (ORDER BY txn_count)        AS txn_pct,
    PERCENT_RANK() OVER (ORDER BY total_volume_pen) AS volume_pct
  FROM per_user
)
SELECT
  user_id,
  txn_count,
  total_volume_pen,
  distinct_services,
  region,
  age_cohort,
  CASE
    WHEN txn_pct >= 0.80 THEN 'heavy'
    WHEN txn_pct >= 0.50 THEN 'medium'
    ELSE 'light'
  END AS usage_tier,
  CASE
    WHEN volume_pct >= 0.80 THEN 'high_value'
    WHEN volume_pct >= 0.50 THEN 'mid_value'
    ELSE 'low_value'
  END AS value_tier
FROM ranked
"""

SEGMENT_BEHAVIOR_YAML = f"""
version: 1.1
source: {TABLES['transactions']}
comment: "Yape behavior by user segment — service usage broken out by usage tier + value tier"
joins:
  - name: segments
    source: {USER_SEGMENTS_VIEW}
    on: source.user_id = segments.user_id
dimensions:
  - name: service_id
    expr: source.service_id
  - name: usage_tier
    expr: segments.usage_tier
  - name: value_tier
    expr: segments.value_tier
  - name: region
    expr: source.region
  - name: age_cohort
    expr: source.age_cohort
  - name: channel
    expr: source.channel
measures:
  - name: distinct_users
    expr: COUNT(DISTINCT source.user_id)
  - name: total_transactions
    expr: COUNT(1)
  - name: total_volume_pen
    expr: SUM(source.amount_pen)
  - name: avg_ticket_pen
    expr: AVG(source.amount_pen)
"""


def main() -> None:
    w = WorkspaceClient()
    if not w.config.warehouse_id:
        raise RuntimeError("Set DATABRICKS_WAREHOUSE_ID or configure a default warehouse.")

    exec_sql(
        w,
        f"CREATE OR REPLACE VIEW {METRIC_VIEWS['adoption']} WITH METRICS LANGUAGE YAML AS $$\n{ADOPTION_YAML}\n$$",
    )
    exec_sql(
        w,
        f"CREATE OR REPLACE VIEW {METRIC_VIEWS['avg_ticket']} WITH METRICS LANGUAGE YAML AS $$\n{AVG_TICKET_YAML}\n$$",
    )

    # User segments view must exist before the segment-behavior metric view joins it.
    exec_sql(w, USER_SEGMENTS_SQL)
    exec_sql(
        w,
        f"CREATE OR REPLACE VIEW {METRIC_VIEWS['segment_behavior']} WITH METRICS LANGUAGE YAML AS $$\n{SEGMENT_BEHAVIOR_YAML}\n$$",
    )

    print("\nMetric views + supporting view created:")
    for name in [*METRIC_VIEWS.values(), USER_SEGMENTS_VIEW]:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
