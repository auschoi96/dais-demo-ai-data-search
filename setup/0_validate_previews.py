#!/usr/bin/env python3
"""Validate required Databricks previews before the Yape search demo."""

from __future__ import annotations

import sys

from databricks.sdk import WorkspaceClient

PREVIEW_CHECKS = [
    ("Unity AI Gateway", "unity_ai_gateway"),
    ("Supervisor API", "supervisor_api"),
    ("Store OpenTelemetry traces in Unity Catalog", "uc_trace_storage"),
]


def main() -> int:
    w = WorkspaceClient()
    host = w.config.host
    print(f"Workspace: {host}")
    print("\nRequired previews for this demo:")
    for label, _ in PREVIEW_CHECKS:
        print(f"  - {label}")

    print(
        "\nManual verification required in Admin Console → Previews:"
        "\n  1. Unity AI Gateway (Beta)"
        "\n  2. Supervisor API (Beta)"
        "\n  3. Store OpenTelemetry traces in Unity Catalog"
    )

    try:
        me = w.current_user.me()
        print(f"\nAuthenticated as: {me.user_name}")
    except Exception as exc:  # noqa: BLE001
        print(f"\nAuth check failed: {exc}", file=sys.stderr)
        return 1

    try:
        w.vector_search_endpoints.list_endpoints(max_results=1)
        print("Vector Search API: accessible")
    except Exception as exc:  # noqa: BLE001
        print(f"Vector Search API check failed: {exc}", file=sys.stderr)
        return 1

    print("\nPreview flags cannot be verified programmatically.")
    print("Confirm all three previews are enabled before rehearsal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
