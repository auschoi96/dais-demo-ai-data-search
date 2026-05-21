#!/usr/bin/env python3
"""Register search_yape_services UC function for Supervisor API tool calls."""

from __future__ import annotations

from databricks.sdk import WorkspaceClient

from _config import INDEXES, UC_FUNCTION

# Raw-index function for Tier 3 Supervisor demo. Enriched search uses Vector Search API directly.
FUNCTION_BODY = f"""
CREATE OR REPLACE FUNCTION {UC_FUNCTION}(query STRING)
RETURNS TABLE (
  service_id STRING,
  name STRING,
  category STRING,
  description STRING,
  score DOUBLE
)
RETURN
  SELECT
    service_id,
    name,
    category,
    description,
    search_score AS score
  FROM vector_search(
    index => '{INDEXES["raw"]}',
    query_text => query,
    num_results => 4
  )
"""


def main() -> None:
    w = WorkspaceClient()
    if not w.config.warehouse_id:
        raise RuntimeError("Set DATABRICKS_WAREHOUSE_ID before registering UC functions.")

    print(f"Registering UC function: {UC_FUNCTION}")
    resp = w.statement_execution.execute_statement(
        warehouse_id=w.config.warehouse_id,
        statement=FUNCTION_BODY,
        wait_timeout="50s",
    )
    if resp.status and resp.status.state and resp.status.state.value != "SUCCEEDED":
        raise RuntimeError(resp.status.error.message if resp.status.error else resp.status.state)
    print("UC function registered.")


if __name__ == "__main__":
    main()
