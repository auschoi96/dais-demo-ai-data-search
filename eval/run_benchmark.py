#!/usr/bin/env python3
"""Run Hit@4 and MRR benchmark across search tiers for the Yape demo."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from databricks.sdk import WorkspaceClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "setup"))
from _config import INDEXES, TABLES  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = Path(__file__).resolve().parent / "benchmark_results.json"


@dataclass
class EvalRow:
    query: str
    expected: list[str]
    tier: str


def load_eval() -> list[EvalRow]:
    rows = []
    for line in (DATA_DIR / "search_eval.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows.append(
            EvalRow(
                query=payload["query"],
                expected=payload["expected_service_ids"],
                tier=payload["tier"],
            )
        )
    return rows


def hit_at_k(results: list[str], expected: list[str], k: int = 4) -> float:
    top = results[:k]
    return 1.0 if any(item in top for item in expected) else 0.0


def reciprocal_rank(results: list[str], expected: list[str]) -> float:
    for idx, item in enumerate(results, start=1):
        if item in expected:
            return 1.0 / idx
    return 0.0


def keyword_search(w: WorkspaceClient, query: str, limit: int = 4) -> list[str]:
    warehouse_id = w.config.warehouse_id
    if not warehouse_id:
        raise RuntimeError("Set DATABRICKS_WAREHOUSE_ID")
    q = query.replace("'", "''").lower()
    sql = f"""
      SELECT service_id
      FROM {TABLES['raw']}
      WHERE lower(search_text) LIKE '%{q}%'
         OR lower(name) LIKE '%{q}%'
      LIMIT {limit}
    """
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s",
    )
    rows = resp.result.data_array if resp.result else []
    return [str(row[0]) for row in rows]


def vector_search(w: WorkspaceClient, query: str, index_name: str, limit: int = 4) -> list[str]:
    result = w.vector_search_indexes.query_index(
        index_name=index_name,
        query_text=query,
        columns=["service_id"],
        num_results=limit,
    )
    rows = result.result.data_array if result.result else []
    return [str(row[0]) for row in rows]


def run_tier(
    w: WorkspaceClient,
    eval_rows: list[EvalRow],
    *,
    name: str,
    search_fn,
) -> dict:
    hits: list[float] = []
    mrrs: list[float] = []
    latencies: list[float] = []

    for row in eval_rows:
        started = time.time()
        results = search_fn(row.query)
        latencies.append((time.time() - started) * 1000)
        hits.append(hit_at_k(results, row.expected))
        mrrs.append(reciprocal_rank(results, row.expected))

    summary = {
        "tier": name,
        "hit_at_4": round(sum(hits) / len(hits), 3) if hits else 0.0,
        "mrr": round(sum(mrrs) / len(mrrs), 3) if mrrs else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "queries": len(eval_rows),
    }
    return summary


def main() -> int:
    w = WorkspaceClient()
    eval_rows = load_eval()

    summaries = [
        run_tier(w, eval_rows, name="tier0", search_fn=lambda q: keyword_search(w, q)),
        run_tier(
            w,
            eval_rows,
            name="tier1",
            search_fn=lambda q: vector_search(w, q, INDEXES["raw"]),
        ),
        run_tier(
            w,
            eval_rows,
            name="tier2",
            search_fn=lambda q: vector_search(w, q, INDEXES["enriched"]),
        ),
    ]

    OUTPUT_PATH.write_text(json.dumps(summaries, indent=2))
    print(json.dumps(summaries, indent=2))
    print(f"\nWrote {OUTPUT_PATH}")
    print("Tier 3 (Supervisor) is excluded from batch eval — run manually in the Search UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
