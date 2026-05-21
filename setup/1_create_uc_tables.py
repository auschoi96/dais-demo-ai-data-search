#!/usr/bin/env python3
"""Create UC Delta tables and load seed JSONL for the Yape search demo."""

from __future__ import annotations

import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import catalog

from _config import FULL_SCHEMA, TABLES

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


def array_literal(values: list[str]) -> str:
    if not values:
        return "array()"
    inner = ", ".join(f"'{sql_escape(v)}'" for v in values)
    return f"array({inner})"


def exec_sql(w: WorkspaceClient, statement: str) -> None:
    print(statement.split("\n", maxsplit=1)[0][:120] + "...")
    resp = w.statement_execution.execute_statement(
        warehouse_id=w.config.warehouse_id,
        statement=statement,
        wait_timeout="50s",
    )
    if resp.status and resp.status.state and resp.status.state.value != "SUCCEEDED":
        raise RuntimeError(f"SQL failed: {resp.status.error}")


def main() -> None:
    w = WorkspaceClient()
    if not w.config.warehouse_id:
        raise RuntimeError("Set DATABRICKS_WAREHOUSE_ID or configure a default warehouse.")

    exec_sql(w, f"CREATE SCHEMA IF NOT EXISTS {FULL_SCHEMA}")

    exec_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {TABLES['raw']} (
          service_id STRING COMMENT 'Primary key',
          name STRING,
          category STRING,
          icon STRING,
          description STRING,
          search_text STRING COMMENT 'Concatenated name + category + description for keyword search'
        ) USING DELTA
        COMMENT 'Raw Yape service catalog — vibe-coded baseline data'
        """,
    )

    exec_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {TABLES['enriched']} (
          service_id STRING,
          name STRING,
          category STRING,
          icon STRING,
          description STRING,
          semantic_description STRING COMMENT 'Intent-rich description for embeddings',
          intent_tags ARRAY<STRING>,
          user_intent_phrases ARRAY<STRING>,
          synonyms ARRAY<STRING>,
          target_segments ARRAY<STRING>,
          embedding_text STRING COMMENT 'Combined text for Vector Search index'
        ) USING DELTA
        COMMENT 'AI-ready enriched Yape service catalog'
        """,
    )

    exec_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {TABLES['users']} (
          user_id STRING,
          name STRING,
          avatar STRING,
          segment STRING,
          age INT,
          city STRING,
          monthly_income INT,
          yape_since STRING,
          tx_count_30d INT,
          top_categories ARRAY<STRING>,
          bio STRING
        ) USING DELTA
        """,
    )

    exec_sql(
        w,
        f"""
        CREATE OR REPLACE TABLE {TABLES['eval']} (
          query STRING,
          language STRING,
          expected_service_ids ARRAY<STRING>,
          tier STRING
        ) USING DELTA
        COMMENT 'Labeled search eval queries for Hit@4 / MRR'
        """,
    )

    raw_rows = load_jsonl(DATA_DIR / "services_raw.jsonl")
    raw_values = []
    for row in raw_rows:
        search_text = f"{row['name']} {row['category']} {row['description']}"
        raw_values.append(
            "('{sid}', '{name}', '{cat}', '{icon}', '{desc}', '{search}')".format(
                sid=sql_escape(row["service_id"]),
                name=sql_escape(row["name"]),
                cat=sql_escape(row["category"]),
                icon=sql_escape(row["icon"]),
                desc=sql_escape(row["description"]),
                search=sql_escape(search_text),
            )
        )
    exec_sql(w, f"INSERT OVERWRITE {TABLES['raw']} VALUES\n  " + ",\n  ".join(raw_values))

    enriched_rows = load_jsonl(DATA_DIR / "services_enriched.jsonl")
    enriched_values = []
    for row in enriched_rows:
        enriched_values.append(
            "('{sid}', '{name}', '{cat}', '{icon}', '{desc}', '{sem}', "
            "{tags}, {phrases}, {syn}, {seg}, '{emb}')".format(
                sid=sql_escape(row["service_id"]),
                name=sql_escape(row["name"]),
                cat=sql_escape(row["category"]),
                icon=sql_escape(row["icon"]),
                desc=sql_escape(row["description"]),
                sem=sql_escape(row.get("semantic_description", "")),
                tags=array_literal(row.get("intent_tags", [])),
                phrases=array_literal(row.get("user_intent_phrases", [])),
                syn=array_literal(row.get("synonyms", [])),
                seg=array_literal(row.get("target_segments", [])),
                emb=sql_escape(row.get("embedding_text", "")),
            )
        )
    exec_sql(
        w,
        f"INSERT OVERWRITE {TABLES['enriched']} VALUES\n  " + ",\n  ".join(enriched_values),
    )

    user_rows = load_jsonl(DATA_DIR / "users.jsonl")
    user_values = []
    for row in user_rows:
        user_values.append(
            "('{uid}', '{name}', '{avatar}', '{seg}', {age}, '{city}', {income}, '{since}', {tx}, {cats}, '{bio}')".format(
                uid=sql_escape(row["user_id"]),
                name=sql_escape(row["name"]),
                avatar=sql_escape(row.get("avatar", "")),
                seg=sql_escape(row["segment"]),
                age=int(row.get("age", 0)),
                city=sql_escape(row["city"]),
                income=int(row.get("monthly_income", 0)),
                since=sql_escape(row.get("yape_since", "")),
                tx=int(row.get("tx_count_30d", 0)),
                cats=array_literal(row.get("top_categories", [])),
                bio=sql_escape(row.get("bio", "")),
            )
        )
    exec_sql(w, f"INSERT OVERWRITE {TABLES['users']} VALUES\n  " + ",\n  ".join(user_values))

    eval_rows = load_jsonl(DATA_DIR / "search_eval.jsonl")
    eval_values = []
    for row in eval_rows:
        eval_values.append(
            "('{q}', '{lang}', {expected}, '{tier}')".format(
                q=sql_escape(row["query"]),
                lang=sql_escape(row["language"]),
                expected=array_literal(row["expected_service_ids"]),
                tier=sql_escape(row["tier"]),
            )
        )
    exec_sql(w, f"INSERT OVERWRITE {TABLES['eval']} VALUES\n  " + ",\n  ".join(eval_values))

    print("\nUC tables created and loaded:")
    for name in TABLES.values():
        print(f"  - {name}")


if __name__ == "__main__":
    main()
