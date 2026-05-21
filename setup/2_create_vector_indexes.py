#!/usr/bin/env python3
"""Create Vector Search endpoint and Delta Sync indexes for the Yape search demo."""

from __future__ import annotations

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    EndpointType,
    PipelineType,
    VectorIndexType,
)

from _config import EMBEDDING_MODEL, INDEXES, TABLES, VS_ENDPOINT


def wait_for_endpoint(w: WorkspaceClient, name: str, timeout_s: int = 600) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ep = w.vector_search_endpoints.get_endpoint(name)
        state = ep.endpoint_status.state if ep.endpoint_status else None
        print(f"  endpoint state: {state}")
        if state and state.value == "ONLINE":
            return
        if state and state.value in {"FAILED", "OFFLINE"}:
            raise RuntimeError(f"Endpoint {name} is {state.value}")
        time.sleep(15)
    raise TimeoutError(f"Endpoint {name} not online after {timeout_s}s")


def wait_for_index(w: WorkspaceClient, name: str, timeout_s: int = 900) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        idx = w.vector_search_indexes.get_index(name)
        status = idx.status
        ready = status.ready if status else False
        message = status.message if status else None
        print(f"  index {name.split('.')[-1]} ready={ready} msg={message}")
        if ready:
            return
        if message and "failed" in message.lower():
            raise RuntimeError(f"Index {name} failed: {message}")
        time.sleep(20)
    raise TimeoutError(f"Index {name} not ready after {timeout_s}s")


def ensure_endpoint(w: WorkspaceClient) -> None:
    existing = {ep.name for ep in w.vector_search_endpoints.list_endpoints()}
    if VS_ENDPOINT in existing:
        print(f"Endpoint exists: {VS_ENDPOINT}")
    else:
        print(f"Creating endpoint: {VS_ENDPOINT}")
        w.vector_search_endpoints.create_endpoint(
            name=VS_ENDPOINT,
            endpoint_type=EndpointType.STORAGE_OPTIMIZED,
        )
    wait_for_endpoint(w, VS_ENDPOINT)


def wait_until_index_deleted(w: WorkspaceClient, name: str, timeout_s: int = 600) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        existing = {idx.name for idx in w.vector_search_indexes.list_indexes(VS_ENDPOINT)}
        if name not in existing:
            print(f"  index deleted: {name.split('.')[-1]}")
            return
        print(f"  waiting for deletion: {name.split('.')[-1]}")
        time.sleep(15)
    raise TimeoutError(f"Index {name} still deleting after {timeout_s}s")


def index_is_ready(w: WorkspaceClient, name: str) -> bool:
    try:
        idx = w.vector_search_indexes.get_index(name)
    except Exception:  # noqa: BLE001
        return False
    return bool(idx.status and idx.status.ready)


def create_or_replace_index(
    w: WorkspaceClient,
    *,
    index_name: str,
    source_table: str,
    columns: list[tuple[str, str]],
) -> None:
    if index_is_ready(w, index_name):
        print(f"Index already ready, syncing: {index_name}")
        w.vector_search_indexes.sync_index(index_name)
        return

    existing = {idx.name for idx in w.vector_search_indexes.list_indexes(VS_ENDPOINT)}
    if index_name in existing:
        print(f"Dropping existing index: {index_name}")
        w.vector_search_indexes.delete_index(index_name)
        wait_until_index_deleted(w, index_name)

    embedding_columns = [
        EmbeddingSourceColumn(name=col, embedding_model_endpoint_name=EMBEDDING_MODEL)
        for col, _ in columns
    ]

    print(f"Creating index: {index_name}")
    w.vector_search_indexes.create_index(
        name=index_name,
        endpoint_name=VS_ENDPOINT,
        primary_key="service_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=source_table,
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=embedding_columns,
        ),
    )
    wait_for_index(w, index_name)
    print(f"Syncing index: {index_name}")
    w.vector_search_indexes.sync_index(index_name)


def main() -> None:
    w = WorkspaceClient()
    ensure_endpoint(w)

    create_or_replace_index(
        w,
        index_name=INDEXES["raw"],
        source_table=TABLES["raw"],
        columns=[("search_text", "Concatenated name, category, description")],
    )

    create_or_replace_index(
        w,
        index_name=INDEXES["enriched"],
        source_table=TABLES["enriched"],
        columns=[("embedding_text", "AI-ready embedding text")],
    )

    print("\nVector Search indexes ready:")
    print(f"  - {INDEXES['raw']}")
    print(f"  - {INDEXES['enriched']}")


if __name__ == "__main__":
    main()
