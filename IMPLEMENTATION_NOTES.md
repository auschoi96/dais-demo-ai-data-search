# Implementation Notes — DAIS AI-Ready Data Demo

Reference for what's built, how it's wired, and the non-obvious gotchas we hit. Read this after the [README](./README.md) when you need to extend the demo or debug a deploy.

**Repo:** https://github.com/auschoi96/dais-demo-ai-data-search
**Live app:** https://dais-demo-ai-data-search-1444828305810485.aws.databricksapps.com
**Workspace UI:** https://e2-demo-field-eng.cloud.databricks.com/apps-v2/app/dais-demo-ai-data-search/overview?o=1444828305810485

---

## Goal

Make a stage audience feel that **"AI-ready data" is the leverage**, not the agent. Same Claude model. Same prompt scaffolding. Two agents, two tool surfaces. The one with governed metric views and enriched Vector Search consistently outperforms raw-SQL on wall time, tool calls, and tokens — for the analytical Yape fintech questions the demo asks.

Specifically the demo measures three signals per agent run, side-by-side in the UI:

- **wall time** — agent run latency
- **tool calls** — how many round trips the agent made
- **tokens** — total LLM context burned

On the demo's hero queries, the AI-ready agent is 2–5× faster and burns ~3–6× fewer tokens. The vibe-coded agent's overhead is real: it has to discover the schema, learn MEASURE() syntax, resolve service ids, and iterate when its SQL is wrong.

---

## Architecture overview

### Runtime

Databricks Apps container running **Python 3.11** under `uvicorn`. Single FastAPI app at `agents_service.main:app`.

```
uvicorn  ──>  FastAPI
              ├─ POST /api/agents/stream    (SSE)
              ├─ GET  /api/services/raw     (JSON)
              ├─ GET  /api/services/enriched (JSON)
              ├─ GET  /api/benchmark        (JSON)
              ├─ GET  /api/health
              └─ /     (StaticFiles → client/dist/)
```

Per request, FastAPI spawns **two `claude-agent-sdk.query()` sessions in parallel** (one per agent) via `asyncio`. Messages from both sessions are interleaved by arrival time onto a single SSE stream, tagged with `agent: 'vibe' | 'ready'`. The client splits them into two columns in real time.

### LLM path

Both agents target the **Databricks AI Gateway**:

```
ANTHROPIC_BASE_URL  = https://<workspace>/ai-gateway/anthropic
ANTHROPIC_AUTH_TOKEN = <SP bearer from WorkspaceClient.config.authenticate()>
ANTHROPIC_MODEL      = databricks-claude-opus-4-6  (or sonnet-4-6 / haiku-4-5)
ANTHROPIC_CUSTOM_HEADERS = x-databricks-use-coding-agent-mode: true
```

The bundled `claude` CLI inside `claude-agent-sdk` handles the actual API calls. The SDK ships its CLI as a Python package resource — no external binary, no `npm install`, no Docker work for Databricks Apps.

### Tools / MCP

Each agent gets a **separate in-process MCP server** named `yape`:

| Agent | MCP-registered tools |
|---|---|
| `VIBE_TOOLS` | `execute_sql` |
| `READY_TOOLS` | `execute_sql`, `search_yape_services_enriched`, `list_services_by_category`, `top_services_by_region`, `compare_regions_adoption`, `avg_ticket_by_cohort`, `services_for_segment`, `query_metric_view` |

The MCP tools are Python functions decorated with `@tool(name, description, schema)`. The descriptions are deliberately rich — they're how the LLM picks which tool to call. The system prompt then adds a numbered decision tree to bias selection further.

---

## Data layer (Unity Catalog)

All in `ac_demo.agents` on `e2-demo-field-eng`.

### Tables

| Object | Rows | Provisioned by |
|---|---|---|
| `yape_services_raw` | 20 | `setup/1_create_uc_tables.py` ← `data/services_raw.jsonl` |
| `yape_services_enriched` | 20 | same; adds `intent_tags`, `user_intent_phrases`, `embedding_text` |
| `yape_users` | 6 | persona table for the demo narrative |
| `yape_search_eval` | 15 | labeled queries (EN/ES) |
| `yape_transactions` | 8000 | `setup/generate_transactions.py` then `1_create_uc_tables.py` |

Transactions are persona-biased: Lima skews savings + business, Arequipa skews utilities, 18–24 skews top-ups + streaming, 35+ skews utilities + insurance. Amount distributions are tier-banded so analytical queries return realistic patterns.

### Metric views (YAML v1.1, snake_case)

All three live in `ac_demo.agents`:

| View | Dimensions | Measures |
|---|---|---|
| `yape_service_adoption` | service_id, region, age_cohort, month, channel | distinct_users, total_transactions, total_volume_pen |
| `yape_avg_ticket` | service_id, age_cohort, region | avg_ticket_pen, median_ticket_pen, transaction_count |
| `yape_segment_behavior` | service_id, usage_tier, value_tier, region, age_cohort, channel | distinct_users, total_transactions, total_volume_pen, avg_ticket_pen |

`yape_segment_behavior` joins a supporting **`yape_user_segments`** plain SQL view that classifies users:

- `usage_tier` ∈ {heavy (top 20% by txn count), medium (next 30%), light (rest)}
- `value_tier` ∈ {high_value (top 20% by total volume), mid_value, low_value}

All dim / measure names are snake_case so LLM-generated SQL doesn't need backtick-quoting.

### UC functions (agent-facing)

Each is a `RETURNS TABLE` function with a descriptive `COMMENT` the LLM reads when picking tools.

| Function | Signature | Wraps |
|---|---|---|
| `search_yape_services(query)` | raw VS index | `yape_services_raw_idx` (kept for the Vibe-Coded reference path; not currently MCP-exposed) |
| `search_yape_services_enriched(query)` | enriched VS index | `yape_services_enriched_idx` |
| `top_services_by_region(region_filter, months_back)` | adoption metric | `yape_service_adoption` |
| `compare_regions_adoption(region_a, region_b, months_back)` | one-call comparison | `yape_service_adoption` ×2 |
| `avg_ticket_by_cohort(service_id_filter)` | ticket-size metric | `yape_avg_ticket` |
| `services_for_segment(usage_tier_filter, value_tier_filter)` | segment behavior | `yape_segment_behavior` |
| `list_services_by_category(category_filter)` | catalog lookup | `yape_services_enriched` |

All parameters are suffixed `_filter` to avoid collisions with column names (SQL UC functions silently prefer columns over parameters when names overlap — see [gotcha #9](#9-uc-function-parameter--column-collision)).

### Vector Search

Endpoint `yape-search-demo-endpoint`, `STORAGE_OPTIMIZED`, two indexes:

- `yape_services_raw_idx` — embeds `search_text` (`name + category + description` concatenated)
- `yape_services_enriched_idx` — embeds `embedding_text` (catalog + intent tags + bilingual phrases)

Embedding model: `databricks-qwen3-embedding-0-6b` (managed). Pipeline: `TRIGGERED` (manual `sync_index` after `INSERT OVERWRITE`).

---

## Python backend (`python/agents_service/`)

| File | What it does |
|---|---|
| `auth.py` | Reads the app's SP credentials via the Databricks SDK, exchanges them for a workspace OAuth bearer, returns the env dict that `claude-agent-sdk` needs (base URL, auth token, model, custom header, model defaults). |
| `tools.py` | All MCP tool definitions. Two `create_sdk_mcp_server()` calls produce `VIBE_TOOLS` and `READY_TOOLS`. The whitelist `METRIC_VIEW_CATALOG` is the source of truth for `query_metric_view`'s allowed dim/measure names. |
| `runner.py` | `stream_both(query, model)` → `AsyncIterator[event]`. Spawns two `_run_one` tasks, one per agent, and merges events through a shared `asyncio.Queue`. Each task forwards `AssistantMessage` / `UserMessage` / `ResultMessage` into typed SSE events, buffers a copy of the events, and emits an MLflow trace when the run reaches `ResultMessage` (or errors). |
| `tracing.py` | Manual MLflow span emission. `init_tracing()` runs at app startup (reads `MLFLOW_EXPERIMENT_ID`, sets tracking URI). `emit_agent_trace(...)` walks buffered events and builds a root agent span + child tool spans with truncated inputs/outputs. No-op if `MLFLOW_EXPERIMENT_ID` is unset. |
| `main.py` | FastAPI app — routes + SSE wrapper via `sse_starlette.EventSourceResponse`. Calls `init_tracing()` at import time. Mounts `client/dist/` as static. |

### Event types emitted to the client

```
session_start   { agent, ts }
text_delta      { agent, text }
tool_call       { agent, call_id, tool, args }
tool_result     { agent, call_id, output, is_error }
done            { agent, tokens, cost_usd, latency_ms, num_tool_calls }
error           { agent, message, latency_ms? }
```

The client (`client/src/lib/search-api.ts`) reduces these into a per-agent `AgentRunState` using a small switch over the discriminated union.

### Agent options

```python
ClaudeAgentOptions(
    model=model,                            # databricks-claude-{opus,sonnet,haiku}-...
    tools=[],                               # strip Bash/Read/Edit/Write
    mcp_servers={"yape": VIBE_TOOLS | READY_TOOLS},
    allowed_tools=[...],                    # belt-and-suspenders allowlist
    permission_mode="bypassPermissions",
    system_prompt=VIBE_SYSTEM | READY_SYSTEM,
    env=gateway_env(model),                 # AI Gateway URL + bearer
    setting_sources=[],                     # don't read ~/.claude/settings.json
)
```

---

## Frontend (`client/src/`)

| Page | Route | Purpose |
|---|---|---|
| `AgentsPage` | `/` | Two-agent split-screen with live tool-call streaming, model dropdown, hero query buttons, comparison sidebar. |
| `DataComparePage` | `/compare` | Raw vs enriched catalog side-by-side. Reads `/api/services/{raw,enriched}`. |
| `BenchmarkPage` | `/benchmark` | Static hit@4 / tool-call / latency benchmarks per agent. Reads `/api/benchmark`. |

Header is Databricks Navy `#1B3139`; active nav uses Lava red `#FF3621`. Light mode is **forced** via `<html class="light" style="color-scheme: light">` in `client/index.html` so the appkit-ui dark-mode media query (`:root:not(.light)`) doesn't fire — see [gotcha #5](#5-app-theme-locked-to-dark-mode).

The SSE parser at `streamAgents()` normalizes CRLF → LF before splitting frames on `\n\n` — see [gotcha #6](#6-sse-frame-separator).

---

## DABs bundle (`databricks.yml`)

```yaml
resources:
  apps:
    app:
      name: dais-demo-ai-data-search
      source_code_path: ./
      user_api_scopes:
        - sql
        - serving.serving-endpoints
        - vectorsearch.vector-search-indexes
        - ai-gateway
        - mcp.functions

      resources:
        - sql-warehouse (CAN_USE)
        - services-raw-table (SELECT)
        - services-enriched-table (SELECT)
        - search-eval-table (SELECT)
        - transactions-table (SELECT)
        - fn-search-raw (EXECUTE)
        - fn-search-enriched (EXECUTE)
        - fn-top-services-by-region (EXECUTE)
        - fn-avg-ticket-by-cohort (EXECUTE)
        - fn-list-services-by-category (EXECUTE)
        - fn-services-for-segment (EXECUTE)
        - opus-endpoint → databricks-claude-opus-4-6 (CAN_QUERY)
        - mlflow-experiment → ${var.mlflow_experiment_id} (CAN_EDIT)
```

The MLflow experiment is referenced **by ID** (variable `mlflow_experiment_id`, default `2177684156462207`) rather than created via a top-level `experiments:` resource. Reason: in `mode: development`, DABs auto-prefixes resource names with `[dev <user>]`, which forks the experiment path and creates a new ID instead of binding to the existing one. Referencing by ID sidesteps that. Trade-off: the experiment must exist before deploy — bundle deploy fails fast with a 404 if not.

Both targets also set `presets.name_prefix: ""` to keep other resources (tables, schemas) at their canonical names in dev — this demo lives on a single workspace where the dev/prod distinction is cosmetic.

Both targets (`dev`, `prod`) point at `e2-demo-field-eng` with warehouse `01370556fad60fda` (TPCDS_L).

---

## Deployment

```bash
# Data + governance (idempotent — safe to rerun)
python setup/1_create_uc_tables.py         # tables incl. 8k transactions
python setup/2_create_vector_indexes.py    # 5–15 min
python setup/3_register_uc_functions.py    # 6 UC functions
python setup/4_create_metric_views.py      # 3 metric views + user_segments

# Build + deploy
npm run build:client                       # writes client/dist
databricks bundle deploy --target dev --auto-approve
databricks apps deploy dais-demo-ai-data-search \
  --source-code-path /Workspace/Users/<user>/.bundle/dais-demo-ai-data-search/dev/files
```

The Apps runtime detects Python via `requirements.txt`, runs `npm run build:server && npm run build:client` (legacy package.json scripts — harmless; only the client build matters), then runs the `command:` from `app.yaml` (`uvicorn agents_service.main:app …`).

---

## Gotchas + lessons learned

### 1. Databricks Apps have no static PAT

**Symptom:** Earlier Node implementation used `process.env.DATABRICKS_TOKEN` and got `DATABRICKS_TOKEN is not configured` in production.

**Reality:** Databricks Apps expose service-principal OAuth (`DATABRICKS_CLIENT_ID` / `_SECRET`) and the user's OBO token in the `x-forwarded-access-token` header. No PAT.

**Fix:** Use `WorkspaceClient` from the Databricks SDK and let it pick up the SP credentials automatically. For the AI Gateway path specifically: `WorkspaceClient().config.authenticate()` returns the Bearer headers; pull the token out and pass it as `ANTHROPIC_AUTH_TOKEN`.

### 2. The `unity-catalog` scope is a misleading error

**Symptom:** Calling Supervisor API / AI Gateway with a `uc_function` tool: `Insufficient OAuth scopes for requested tools: 'uc_function' (requires 'unity-catalog')`. But adding `unity-catalog` to `user_api_scopes` is rejected by the DABs Terraform provider: *"is not a valid scope."*

**Reality:** The receiving gateway's error message references a legacy scope name. The actual scope the Apps OAuth issuer mints (and the gateway accepts) is **`mcp.functions`**. The Apps UI scope picker also doesn't surface `mcp.functions` — it has to be added via DABs / API. Tracked in JIRA ES-1855028 and ML-63358; fix landed in app-templates PR #215 around May 2026.

**Fix:** `user_api_scopes: [..., mcp.functions]`. Users with an existing browser session must sign out + back in (or open incognito) so the new scope makes it into their OBO token.

### 3. Apps UI scope picker hides many valid scopes

The picker is a curated list — `sql`, `dashboards.genie`, `files.files`, the `catalog.*` family. Less-common scopes like `ai-gateway`, `mcp.functions`, `vectorsearch.vector-search-indexes`, `serving.serving-endpoints` aren't shown there, but they're valid and can be added via DABs / REST API. The workspace's "Restrict OAuth scopes for apps to selected values" setting can further narrow what's accepted.

Truth source for "what does this app actually have":

```bash
databricks apps get dais-demo-ai-data-search | jq '.effective_user_api_scopes'
```

### 4. `allowed_tools` is not enough for tool isolation

**Symptom:** Even with `allowed_tools=[TOOL_EXECUTE_SQL]`, the Vibe agent could see and call `search_yape_services_enriched`, `avg_ticket_by_cohort`, etc.

**Reality:** `claude-agent-sdk`'s `allowed_tools` is a **permission** layer. Combined with `permission_mode="bypassPermissions"` (which auto-approves all tool calls), the allowlist is effectively bypassed. The MCP tools registered on a *shared* server are still visible to the agent's context and still callable.

**Fix:** Register a **separate MCP server per agent**. Vibe's server only includes `execute_sql`; the governed tools simply don't exist in its tool list. `allowed_tools` stays as belt-and-suspenders.

```python
# tools.py
VIBE_TOOLS  = create_sdk_mcp_server(name="yape", version="1.0.0",
                                    tools=[execute_sql])
READY_TOOLS = create_sdk_mcp_server(name="yape", version="1.0.0",
                                    tools=[execute_sql, search_enriched,
                                           top_services_by_region, ...])
```

### 5. App theme locked to dark mode

**Symptom:** Audience laptops in dark mode → entire app rendered dark, ruining the Databricks-brand light theme.

**Cause:** `@databricks/appkit-ui/styles.css` has a `@media (prefers-color-scheme: dark) :root:not(.light) { ... }` block that flips all CSS variables.

**Fix:** `<html class="light" style="color-scheme: light">` in `client/index.html`. The `:not(.light)` selector now fails, the dark-mode block doesn't apply.

### 6. SSE frame separator

**Symptom:** Tool-call events were streamed by the backend (confirmed via curl) but the React UI showed both agents stuck on "Thinking…".

**Cause:** `sse_starlette` emits frames separated by `\r\n\r\n`. The frontend's manual SSE parser only split on `\n\n`. `'\r\n\r\n'` doesn't contain `'\n\n'` (the \n chars aren't adjacent — \r sits between them), so frames never flushed.

**Fix:** Normalize `\r\n` → `\n` on each chunk before splitting:

```ts
buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
```

### 7. Named tools beat the generic introspector empirically

After building `query_metric_view(view_name, dimensions[], measures[], filters{})` as a single tool to cover all three metric views, we tested dropping the four named wrappers (`top_services_by_region`, `compare_regions_adoption`, `avg_ticket_by_cohort`, `services_for_segment`). Result: AI-Ready agent regressed on every demo query — calling `query_metric_view` 3–4 times before falling back to `execute_sql`. On some queries, Vibe (raw SQL) was burning *fewer* tokens than Ready.

**Reason:** The generic API exposes 4 degrees of freedom (view, dims, measures, filters). LLMs struggle to construct the multi-field arg blob correctly on the first try — every wrong call adds ~3-4k tokens of context to retry.

**Fix:** Keep both. Named tools encode "the right defaults" (months_back=1, LIMIT 5, ORDER BY distinct_users DESC, JOIN to enriched catalog for service names) as a single typed parameter; LLMs use them in 1 call. The generic introspector stays as a fallback for cross-cuts the named tools don't cover.

Snake_case for dim/measure names + fuzzy matching at the tool layer (`_canonicalize`) were also added. Helpful, but didn't close the gap on their own.

### 8. Metric view dim names need snake_case for LLM-generated SQL

**Original:** `Service ID`, `Age Cohort`, `Total Volume PEN` — required backtick-quoting in every query.

**Now:** `service_id`, `age_cohort`, `total_volume_pen` — no quoting needed, matches column-name conventions LLMs and SQL editors expect.

### 9. UC function parameter / column collision

**Symptom:** `SELECT * FROM list_services_by_category('Insurance')` returned all 20 services, not just the 2 Insurance ones.

**Cause:** The function had a parameter named `category` and the source view also has a `category` column. In Databricks UC SQL functions, when a parameter name collides with a column name, the column wins. The `WHERE category = category` clause became "column = column" — trivially true.

**Fix:** Rename parameters to non-colliding names (e.g. `category_filter`, `region_filter`, `service_id_filter`).

### 10. claude-agent-sdk's bundled CLI

The SDK ships its own `claude` CLI as a package resource — no separate npm install, no static binary download, no Dockerfile work. On Databricks Apps, `pip install claude-agent-sdk` is the entire install. Setting `cli_path=None` (the default) lets the SDK use the bundled CLI; setting `setting_sources=[]` ensures it doesn't try to read `~/.claude/settings.json` which doesn't exist in the container.

### 11. Apps' dual Node + Python build

The Databricks Apps build phase auto-detects both `requirements.txt` and `package.json` and runs `npm install && npm run build` regardless of the `command:` in `app.yaml`. For us, the Node build produces an unused `dist/` output (the old AppKit server lives in `server/` — leftover dead code) plus the `client/dist/` Vite bundle that *is* used.

Net effect: every deploy spends ~20s on a build that produces some artifacts we throw away. Removing `server/`, `package.json`'s `build:server` script, and tightening `package.json` to client-only would clean this up — follow-up cleanup task.

### 12. MLflow tracing must be manual for `claude-agent-sdk`

**Symptom:** Wanted both agents to emit traces into a specific experiment. Calling `mlflow.anthropic.autolog()` and `mlflow.openai.autolog()` in our FastAPI process produced no traces.

**Cause:** Both autolog functions patch in-process SDK clients. `claude-agent-sdk` spawns a `claude` CLI subprocess that makes its own HTTP calls — autolog has no way to instrument that subprocess.

**Fix:** Manual span emission from `python/agents_service/tracing.py`. The runner already buffers SSE events for forwarding to the client; we reuse that buffer at `ResultMessage` time to build a span tree:

```
agent.<vibe|ready>        (AGENT) — root, attrs: model, query, tokens, cost, latency
├── tool.<tool_name>      (TOOL)  — inputs=args, outputs=output (truncated to 4KB)
├── tool.<tool_name>      (TOOL)
└── ...
```

The experiment ID is injected via `app.yaml`'s `valueFrom: mlflow-experiment` resource, which DABs grants the app `CAN_EDIT` on. `mlflow.set_tracking_uri("databricks")` runs at import time. If `MLFLOW_EXPERIMENT_ID` is unset, tracing silently no-ops.

Trace destination is the experiment's UC table. The new MLflow tracing API requires `MLFLOW_TRACING_SQL_WAREHOUSE_ID` to be set on the *reader* side (e.g. when calling `mlflow.search_traces(...)` from a notebook or script) — the app itself doesn't need it because writes happen via the OpenTelemetry exporter that ships with `mlflow-skinny`.

### 13. Cancel-scope warning on agent teardown

When the SSE stream closes mid-run (user disconnects, frontend aborts), `claude-agent-sdk`'s underlying anyio generator may raise `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`. The error is cosmetic — the events already produced are intact, the `done` event has already been forwarded. Future work: a clean shutdown path.

---

## Open items / cleanup

| Item | Why it's open |
|---|---|
| Delete `server/` (old Node/AppKit code) | Dead since the Python rewrite. Build still runs against it for no reason. |
| Trim `package.json` to client-only scripts | Same — Node-server `build:server` script is unused. |
| Suppress / clean up the cancel-scope warning | Cosmetic but noisy in logs. |
| Refresh `eval/run_benchmark.py` against the new two-agent endpoint | Old benchmark harness assumed the tier-search backend; numbers in `/api/benchmark` are hand-loaded for now. |
| Add a `reference/` walkthrough cleanup | `yape_recsys.py` is still around as the "what people actually ship" before-slide. Move or label clearly. |

---

## Models

| Role | Endpoint |
|---|---|
| Agent (default) | `databricks-claude-opus-4-6` |
| Agent (Sonnet option in dropdown) | `databricks-claude-sonnet-4-6` |
| Agent (Haiku option in dropdown) | `databricks-claude-haiku-4-5` |
| VS embedding model | `databricks-qwen3-embedding-0-6b` |

Earlier iterations targeted `claude-opus-4-7`; the Supervisor API rejected it as unsupported when we briefly used `/ai-gateway/mlflow/v1/responses`. The current `/ai-gateway/anthropic` path serves Opus 4.6 cleanly.

---

## Environment

| Setting | Value |
|---|---|
| Workspace | `e2-demo-field-eng` |
| SQL warehouse | `01370556fad60fda` (TPCDS_L) |
| UC location | `ac_demo.agents` |
| App name | `dais-demo-ai-data-search` |
| App runtime | Python 3.11, `uvicorn`, Databricks Apps MEDIUM |
| Budget policy (workspace-required) | `5b62fa02-8671-46d3-96ac-64c1725dc9d9` |
