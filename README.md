# DAIS Demo: AI-Ready Data vs Vibe-Coded Agent

A Databricks app that runs **two Claude Code agents in parallel** against the same Yape fintech catalog. They share the same model, the same prompt scaffolding, the same query — they differ only in their **tool surface**:

- **Vibe-Coded Agent** has one tool: raw SQL. It must discover the schema and write queries from scratch.
- **AI-Ready Agent** has governed Unity Catalog metric-view tools, semantic Vector Search, and SQL as a fallback.

The demo's point: with the same LLM, the AI-ready agent finishes hero queries in **2–5× less wall time, fewer tool calls, and ~3–6× less token cost.** That gap is the leverage of doing the data work upfront in UC.

**Live app:** [dais-demo-ai-data-search](https://dais-demo-ai-data-search-1444828305810485.aws.databricksapps.com) on `e2-demo-field-eng`.

---

## Architecture

```
┌─ Browser ──────────────────────────────────┐
│  AgentsPage (React + Vite)                 │
│  ─ two-column streaming UI                 │
│  ─ model dropdown (Opus / Sonnet / Haiku)  │
│  ─ live tool-call rendering, running timer │
└────────────┬───────────────────────────────┘
             │ SSE (text/event-stream)
┌────────────▼───────────────────────────────┐
│  Python FastAPI (python/agents_service/)   │
│  ─ /api/agents/stream POST → SSE           │
│  ─ /api/services/{raw,enriched}            │
│  ─ /api/benchmark                          │
│  ─ Static files from client/dist           │
└────────────┬───────────────────────────────┘
             │ asyncio.gather of two agents
   ┌─────────▼──────────┐    ┌─────────▼──────────┐
   │  Vibe-Coded        │    │  AI-Ready          │
   │  claude-agent-sdk  │    │  claude-agent-sdk  │
   │  MCP server: yape  │    │  MCP server: yape  │
   │   tools:           │    │   tools:           │
   │   - execute_sql    │    │   - search_*       │
   │                    │    │   - list_*         │
   │                    │    │   - top_services_* │
   │                    │    │   - avg_ticket_*   │
   │                    │    │   - services_*     │
   │                    │    │   - compare_*      │
   │                    │    │   - query_metric_* │
   │                    │    │   - execute_sql    │
   └─────────┬──────────┘    └─────────┬──────────┘
             │  HTTPS (Anthropic API)        │
             ▼                               ▼
   https://e2-demo-field-eng.cloud.databricks.com
      /ai-gateway/anthropic/v1/messages
      (Databricks AI Gateway, coding-agent-mode)
                       │
                       ▼
        ┌─ Unity Catalog (ac_demo.agents) ─────────┐
        │  yape_transactions  (8000 synth rows)   │
        │  yape_services_raw  /  ..._enriched     │
        │  yape_users  /  yape_search_eval        │
        │                                          │
        │  Metric views (yape_*):                  │
        │   - service_adoption                     │
        │   - avg_ticket                           │
        │   - segment_behavior                     │
        │  Supporting view: user_segments          │
        │                                          │
        │  UC functions (6) wrap the views with    │
        │  named, typed args and LLM docstrings.   │
        │                                          │
        │  Vector Search: yape-search-demo-endpoint│
        │   - yape_services_raw_idx                │
        │   - yape_services_enriched_idx           │
        └──────────────────────────────────────────┘
```

The MCP servers are **per-agent** — Vibe's server only registers `execute_sql`, so the governed tools are literally not in its context. `allowed_tools` on top is a belt-and-suspenders permission allowlist, but the structural isolation is the load-bearing piece (see [`IMPLEMENTATION_NOTES.md`](./IMPLEMENTATION_NOTES.md#tool-isolation-allowed_tools-isnt-enough)).

---

## Quick start

### Prerequisites

Workspace previews to enable (Admin Console → Previews — verify with `python setup/0_validate_previews.py`):

1. Unity AI Gateway
2. Vector Search
3. Metric Views (DBR 17.2+ for YAML v1.1)

`user_api_scopes` your app needs (the DABs bundle declares them):

- `sql`
- `serving.serving-endpoints`
- `vectorsearch.vector-search-indexes`
- `ai-gateway`
- `mcp.functions` *(the scope `uc_function` tool calls actually require — see notes for the `unity-catalog` red-herring)*

### 1. Authenticate

```bash
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
export DATABRICKS_WAREHOUSE_ID=YOUR_WAREHOUSE_ID
```

### 2. Provision data + governance (one-time, ~10 min)

```bash
pip install -r setup/requirements.txt

python setup/1_create_uc_tables.py        # services + users + eval + 8k transactions
python setup/2_create_vector_indexes.py   # VS endpoint + 2 indexes (~5–15 min)
python setup/3_register_uc_functions.py   # 6 UC functions (agent tools)
python setup/4_create_metric_views.py     # 3 metric views + user_segments
```

Optional: regenerate the synthetic transactions before step 1:

```bash
python setup/generate_transactions.py     # writes data/transactions.jsonl
```

### 3. Build + deploy

```bash
npm install && npm run build:client       # produces client/dist/

databricks bundle validate --target dev

# If the app already exists in the workspace, bind first:
databricks bundle deployment bind app dais-demo-ai-data-search --target dev --auto-approve

databricks bundle deploy --target dev --auto-approve
databricks apps deploy dais-demo-ai-data-search \
  --source-code-path /Workspace/Users/$(whoami)@YOUR.com/.bundle/dais-demo-ai-data-search/dev/files
```

The Apps runtime detects `requirements.txt` + the `uvicorn` command in `app.yaml` and runs the Python service. The npm build still runs during the build phase because `package.json` is present; that's harmless — only the Vite client build matters at runtime.

### 4. Local dev (Python backend)

```bash
# Terminal 1 — Python service against the deployed warehouse
export DATABRICKS_WAREHOUSE_ID=YOUR_WAREHOUSE_ID
uvicorn agents_service.main:app --reload --app-dir python --port 8000

# Terminal 2 — Vite dev server with /api proxy to localhost:8000
npm run dev:client     # if configured; otherwise just npm run build:client and reload
```

---

## Bundle variables

| Variable | Default | Description |
|---|---|---|
| `catalog` | `ac_demo` | UC catalog for demo tables |
| `schema` | `agents` | UC schema |
| `sql_warehouse_id` | *(required per target)* | Warehouse the app uses for `execute_sql` and the UC functions |
| `budget_policy_id` | *(per-target)* | Required for some workspaces' app updates |

---

## What lives in Unity Catalog

| Object | Purpose |
|---|---|
| `yape_services_raw` | Thin 20-row catalog — what a vibe-coded chatbot would see |
| `yape_services_enriched` | Same 20 rows + `intent_tags`, `user_intent_phrases` (EN/ES), `embedding_text` |
| `yape_users`, `yape_search_eval` | 6 persona users + 15 labeled eval queries |
| `yape_transactions` | 8000 synthetic transactions over 90 days. Persona-biased by region + cohort. |
| `yape_user_segments` | Plain SQL view — buckets users into usage_tier (heavy/medium/light) and value_tier (high/mid/low) by transaction percentile |
| `yape_service_adoption` (metric view) | dims: service_id, region, age_cohort, month, channel · measures: distinct_users, total_transactions, total_volume_pen |
| `yape_avg_ticket` (metric view) | dims: service_id, age_cohort, region · measures: avg_ticket_pen, median_ticket_pen, transaction_count |
| `yape_segment_behavior` (metric view) | dims: service_id, usage_tier, value_tier, region, age_cohort, channel · measures: distinct_users, total_transactions, total_volume_pen, avg_ticket_pen |
| `search_yape_services` *(raw VS)* | UC function — vector search on raw index |
| `search_yape_services_enriched` | UC function — vector search on AI-ready enriched index |
| `top_services_by_region(region, months_back)` | Adoption-metric wrapper |
| `compare_regions_adoption(region_a, region_b, months_back)` | Side-by-side adoption |
| `avg_ticket_by_cohort(service_id)` | Avg/median ticket per age cohort |
| `services_for_segment(usage_tier, value_tier)` | Top services by behavioral segment |
| `list_services_by_category(category_filter)` | Fast catalog lookup |
| VS endpoint `yape-search-demo-endpoint` | `STORAGE_OPTIMIZED`, hosts both indexes |

---

## Models

| Role | Endpoint |
|---|---|
| Vibe + AI-Ready agents (default Opus) | `databricks-claude-opus-4-6` |
| Sonnet option | `databricks-claude-sonnet-4-6` |
| Haiku option | `databricks-claude-haiku-4-5` |
| Embeddings (Vector Search managed) | `databricks-qwen3-embedding-0-6b` |

All routed through `https://<workspace>/ai-gateway/anthropic` with the `x-databricks-use-coding-agent-mode: true` header. The app's service principal exchanges its OAuth credentials for a Bearer token via the Databricks SDK at request time and passes that as `ANTHROPIC_AUTH_TOKEN` to the bundled `claude` CLI inside `claude-agent-sdk`.

---

## Demo flow

See [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md) for the full keynote walkthrough (10–15 min, 7 beats). Hero queries on the live app:

| Query | Why it lands |
|---|---|
| `What is the average ticket size for Yape Loans by age cohort?` | VS resolves "Yape Loans" → `s01`, then `avg_ticket_by_cohort` returns governed numbers in one call. Vibe takes 5–8 SQL calls to discover the schema + learn MEASURE() syntax. |
| `Compare savings adoption in Lima vs Trujillo` | `compare_regions_adoption` returns both regions side-by-side in one call. |
| `¿Qué servicios usan los usuarios para pagar el alquiler?` | Spanish + slang. Yape has no rent product — enriched intent phrases map "alquiler" to Transfer to BCP. Vibe gets nothing on raw SQL. |
| `What do heavy users use Yape for the most?` | `services_for_segment("heavy", "")` — one call against the `yape_segment_behavior` metric view. |
| `Which insurance product has the highest average ticket?` | `list_services_by_category("Insurance")` → 2 insurance products → `avg_ticket_by_cohort` × 2 → compare. ~3 calls. |

---

## Project layout

```
yape-search-demo/
├── app.yaml                    # uvicorn entry for Databricks Apps runtime
├── databricks.yml              # DABs bundle (app + UC resources + scopes)
├── requirements.txt            # Python deps for the runtime
├── python/agents_service/      # FastAPI app
│   ├── main.py                 # routes + SSE
│   ├── runner.py               # two-agent orchestration
│   ├── tools.py                # MCP tools (Vibe + Ready surfaces)
│   └── auth.py                 # SP → AI Gateway bearer
├── client/src/                 # React UI
│   ├── pages/agents/           # AgentsPage + columns + sidebar
│   ├── pages/compare/          # Raw vs Enriched data tour
│   ├── pages/benchmark/        # static benchmark numbers
│   └── lib/search-api.ts       # SSE client + tool metadata
├── shared/                     # TS types shared by client (no longer by server)
├── setup/                      # idempotent Python provisioning scripts
│   ├── 1_create_uc_tables.py
│   ├── 2_create_vector_indexes.py
│   ├── 3_register_uc_functions.py
│   ├── 4_create_metric_views.py
│   ├── generate_data.py        # services, users, eval
│   └── generate_transactions.py
├── data/                       # seed JSONL (committed)
├── DEMO_SCRIPT.md              # keynote walkthrough
└── IMPLEMENTATION_NOTES.md     # deeper architecture + gotchas
```

`server/` (Node/AppKit) is dead but still tracked — leftover from the pre-Python era. Removing it is a follow-up.

---

## Reference

- [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md) — stage-ready beats with the cost/ambiguity/data-tour narrative
- [`IMPLEMENTATION_NOTES.md`](./IMPLEMENTATION_NOTES.md) — full architecture, deployment history, gotchas
- `reference/yape_recsys.py` — original Streamlit baseline (not deployed; useful as the "what people actually ship" before slide)
