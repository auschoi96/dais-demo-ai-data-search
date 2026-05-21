# Implementation Notes — DAIS AI-Ready Data Search Demo

Reference document for what was built, how it was deployed, and known gotchas. Written after the initial implementation and first successful deployment to `e2-demo-field-eng`.

**GitHub:** https://github.com/auschoi96/dais-demo-ai-data-search  
**Live app:** https://dais-demo-ai-data-search-1444828305810485.aws.databricksapps.com  
**Workspace UI:** https://e2-demo-field-eng.cloud.databricks.com/apps-v2/app/dais-demo-ai-data-search/overview?o=1444828305810485

---

## Goal

Build a **Yape search demo** for a presentation on **Vibe Coding vs AI-Ready Data**, proving that search improves when structured data is semantic, governed, and vectorized — not just when you add a better agent.

The demo compares four search tiers with measurable Hit@4/MRR on labeled queries. Hero queries: `I want to save money` (EN) and `quiero ahorrar` (ES) — fail on raw data, succeed on enriched.

---

## What Was Built

### 1. Sample data (`data/`)

Generated from `setup/generate_data.py` (hand-authored enrichments, not LLM-generated at runtime):

| File | Contents |
|------|----------|
| `services_raw.jsonl` | 20 Yape services — thin catalog copy |
| `services_enriched.jsonl` | Same 20 rows + `semantic_description`, `intent_tags`, `user_intent_phrases`, `embedding_text` |
| `users.jsonl` | 6 Peruvian user personas |
| `search_eval.jsonl` | 15 labeled queries (EN + ES hard queries) |

### 2. Python setup scripts (`setup/`)

| Script | Purpose |
|--------|---------|
| `0_validate_previews.py` | Checklist for Unity AI Gateway, Supervisor API, UC trace storage previews |
| `1_create_uc_tables.py` | Create/load Delta tables in `ac_demo.agents` |
| `2_create_vector_indexes.py` | Create VS endpoint + two Delta Sync indexes (qwen3 embeddings) |
| `3_register_uc_functions.py` | Register `search_yape_services()` UC function for Tier 3 |
| `_config.py` | Shared constants (catalog, schema, index names, models) |
| `generate_data.py` | Regenerate seed JSONL from Python source |
| `requirements.txt` | `databricks-sdk>=0.40.0` |

**UC objects created:**

| Object | Full name |
|--------|-----------|
| Raw table | `ac_demo.agents.yape_services_raw` |
| Enriched table | `ac_demo.agents.yape_services_enriched` |
| Users table | `ac_demo.agents.yape_users` |
| Eval table | `ac_demo.agents.yape_search_eval` |
| VS endpoint | `yape-search-demo-endpoint` (STORAGE_OPTIMIZED) |
| VS index (raw) | `ac_demo.agents.yape_services_raw_idx` — embeds `search_text` |
| VS index (enriched) | `ac_demo.agents.yape_services_enriched_idx` — embeds `embedding_text` |
| UC function | `ac_demo.agents.search_yape_services(query STRING)` |

**Models:**

- LLM: `databricks-claude-opus-4-7` (Supervisor API / Unity AI Gateway)
- Embeddings: `databricks-qwen3-embedding-0-6b` (Vector Search managed)

### 3. AppKit app (Node.js + React)

Scaffolded with:

```bash
databricks apps init --name yape-search-demo --output-dir yape_demo \
  --features analytics --set analytics.sql-warehouse.id=01370556fad60fda --run none
```

Later renamed to **`dais-demo-ai-data-search`** for deployment.

**Backend:**

- `server/server.ts` — plugins: `analytics()`, `searchPlugin()`, `server()`
- `server/plugins/search.ts` — custom AppKit plugin with `POST /api/search/query`. All calls run on-behalf-of-user via `this.asUser(req)` + `getExecutionContext().client`.
  - **Tier 0:** SQL `LIKE` on `yape_services_raw.search_text` (SQL warehouse)
  - **Tier 1:** `client.vectorSearchIndexes.queryIndex` on raw index
  - **Tier 2:** `client.vectorSearchIndexes.queryIndex` on enriched index
  - **Tier 3:** `client.apiClient.request` to `/ai-gateway/mlflow/v1/responses` with `uc_function` tool
- `shared/search-types.ts` — shared TypeScript types for client + server

**No static tokens.** The earlier implementation used `process.env.DATABRICKS_TOKEN` for the VS REST and Supervisor calls — that fails in Databricks Apps, which only expose service-principal OAuth (`DATABRICKS_CLIENT_ID`/`SECRET`) and the user OBO token in `x-forwarded-access-token`. The plugin now goes through the WorkspaceClient so auth headers are added by the SDK in whichever context (user or SP) is active.

**SQL queries (`config/queries/`):**

- `services_raw.sql`, `services_enriched.sql`, `eval_queries.sql` — catalog/eval reads
- `keyword_search.sql` — parameterized keyword search (optional)
- `benchmark_summary.sql` — placeholder tier metrics for Benchmark page

**Frontend (`client/src/`):**

| Page | Route | Purpose |
|------|-------|---------|
| Search | `/` | Multi-tier comparison with side-by-side results |
| Data Compare | `/compare` | Raw vs enriched side-by-side |
| Benchmark | `/benchmark` | Hit@4 / MRR cards |

`SearchPage` mirrors the MAS demo layout:

- Navy header (`#1B3139`) with white Yape wordmark and Lava-red (`#FF3621`) active nav
- Header-right **Tiers picker** (`TierPicker.tsx`) — `DropdownMenu` with checkbox items, `All`/`None` quick links
- Main panel: hero-query buttons → multi-line `Textarea` + circular red send button
- N side-by-side `TierResultColumn` cards (one per selected tier) render on Send
- Right sidebar (`RunDetailsSidebar.tsx`, ~320px) shows per-tier latency, top hit, score, and MLflow trace link (T3)
- ⌘/Ctrl+Enter sends; default selection is T0+T2 (the before/after pair)

Theme is locked to light mode via `<html class="light" style="color-scheme: light">` so the appkit-ui dark-mode media query (`:root:not(.light)`) doesn't fire.

**Eval:**

- `eval/run_benchmark.py` — batch Hit@4/MRR for tiers 0–2 (Tier 3 excluded; run manually in UI)

### 4. DABs bundle (`databricks.yml`)

```yaml
bundle:
  name: dais-demo-ai-data-search

variables:
  catalog, schema, sql_warehouse_id, budget_policy_id

resources:
  apps:
    app:
      name: dais-demo-ai-data-search
      user_api_scopes:
        - sql                                   # warehouse keyword search
        - serving.serving-endpoints             # supervisor + opus invocation
        - vectorsearch.vector-search-indexes    # queryIndex via SDK
        - ai-gateway                            # /ai-gateway/mlflow/v1/responses (Tier 3)
      resources:
        - sql-warehouse (CAN_USE)
        - services-raw-table (SELECT)
        - services-enriched-table (SELECT)
        - search-eval-table (SELECT)
        - search-function (EXECUTE)
        - opus-endpoint → databricks-claude-opus-4-7 (CAN_QUERY)

targets:
  dev:   # default, mode: development
  prod:  # mode: production
```

Both targets point at `e2-demo-field-eng` with warehouse `01370556fad60fda` (TPCDS_L).

---

## Four Search Tiers

| Tier | Label | Implementation | Expected on hero queries |
|------|-------|----------------|--------------------------|
| 0 | Keyword (vibe-coded) | SQL substring on `search_text` | Fail |
| 1 | VS on raw data | Vector Search on `yape_services_raw_idx` | Fail |
| 2 | VS on AI-ready data | Vector Search on `yape_services_enriched_idx` | **Succeed (~90% Hit@4)** |
| 3 | Supervisor + Opus 4.7 | Unity AI Gateway + `search_yape_services` UC function on raw index | Fail (proves data is the bottleneck) |

---

## Deployment Steps Performed

### One-time data setup

```bash
pip install -r setup/requirements.txt
export DATABRICKS_WAREHOUSE_ID=01370556fad60fda

python setup/1_create_uc_tables.py      # succeeded
python setup/3_register_uc_functions.py   # succeeded after fixes (see below)
python setup/2_create_vector_indexes.py  # requires 5–15 min; see gotchas
```

### Build

```bash
npm install
npm run build
```

**Build change:** Removed `typegen` from `postinstall` and `prebuild` so fresh clones build without live UC tables. Committed `client/src/appKitTypes.d.ts` instead. Run `npm run typegen` manually after tables exist (also runs on `npm run dev`).

### DABs deploy

```bash
databricks bundle validate --target dev

# App already existed — bind before first deploy:
databricks bundle deployment bind app dais-demo-ai-data-search --target dev --auto-approve

databricks bundle deploy --target dev --auto-approve
databricks apps deploy --target dev
```

**Result:** App state `RUNNING`, deployment `SUCCEEDED`.

---

## GitHub

Pushed to **auschoi96** as a new public repo:

- **URL:** https://github.com/auschoi96/dais-demo-ai-data-search
- **Branch:** `main`
- **Commit:** Initial commit with full app, setup scripts, data, README

`.gitignore` excludes: `node_modules/`, `dist/`, `client/dist/`, `.env`, `.databricks/`, `__pycache__/`.

---

## Issues Encountered and Fixes

### 1. Vector index: pending deletion race

**Error:** `Index ... is currently pending deletion`

**Fix:** Added `wait_until_index_deleted()` in `2_create_vector_indexes.py` after `delete_index()`. Also skip drop/recreate if index is already `ready` (sync only).

### 2. Vector index: wrong SDK enum for endpoint type

**Error:** `'str' object has no attribute 'value'` on `endpoint_type="STORAGE_OPTIMIZED"`

**Fix:** Use `EndpointType.STORAGE_OPTIMIZED` from `databricks.sdk.service.vectorsearch`.

### 3. Vector index: wrong wait API

**Error:** `'VectorIndexStatus' object has no attribute 'detailed_state'`

**Fix:** Poll `idx.status.ready` instead.

### 4. Vector index: multiple embedding columns rejected

**Error:** `At least one valid embedding_source_column ... must be specified` with 3 columns (name, category, description)

**Fix:** Use single `search_text` column on raw table for the raw index (concat of name + category + description, populated in `1_create_uc_tables.py`).

### 5. UC function: CASE in index parameter

**Error:** `vector_search` requires foldable index expression when using `CASE WHEN index_variant ...`

**Fix:** Simplified to single-argument function `search_yape_services(query STRING)` targeting raw index only. Tier 3 demo uses raw index by design.

### 6. UC function: wrong score column name

**Error:** `score` cannot be resolved; actual column is `search_score`

**Fix:** `SELECT ... search_score AS score FROM vector_search(...)`.

### 7. Users table schema mismatch

**Error:** `KeyError: 'income'` when loading `users.jsonl`

**Fix:** Updated table schema to match JSONL fields (`monthly_income`, `tx_count_30d`, `avatar`, `age`, `yape_since`).

### 8. DABs: app already exists

**Error:** `An app with the same name already exists`

**Fix:** `databricks bundle deployment bind app dais-demo-ai-data-search --target dev --auto-approve` before deploy.

### 9. DABs: Terraform provider budget_policy_id glitch

**Error:** `Provider produced inconsistent result after apply ... budget_policy_id: was null, but now ...`

**Fix:** Set `budget_policy_id` in `databricks.yml` (per-target variable). Required for updating the pre-existing app on `e2-demo-field-eng`; optional for new apps on other workspaces.

### 10. DABs: UC function missing at deploy time

**Error:** `Routine or Model 'ac_demo.agents.search_yape_services' does not exist`

**Fix:** Run `setup/3_register_uc_functions.py` before `bundle deploy` (bundle declares EXECUTE permission on that function).

### 11. Typegen fails without UC tables

**Error:** `TABLE_OR_VIEW_NOT_FOUND` during `npm run typegen`

**Fix:** Commit generated `appKitTypes.d.ts`; decouple typegen from `postinstall`/`prebuild`. Tables must exist before regenerating types.

### 12. AppKit `--features serving` not available

The AppKit v0.23.0 template only supports: `analytics`, `files`, `genie`, `lakebase`, `server`. Search routes were implemented as a **custom plugin** instead of tRPC/serving plugin.

### 13. Search plugin used `process.env.DATABRICKS_TOKEN` (apps have no PAT)

**Symptom:** All non-Tier-0 calls returned 502 in production. App logs showed `DATABRICKS_TOKEN is not configured`.

**Root cause:** Databricks Apps only expose service-principal OAuth env vars (`DATABRICKS_CLIENT_ID`/`SECRET`) plus the user OBO token in the `x-forwarded-access-token` header. There is no static PAT.

**Fix:** Replaced raw `fetch(..., Authorization: Bearer ${env.TOKEN})` with `getExecutionContext().client` — `vectorSearchIndexes.queryIndex` for Tiers 1/2 and `apiClient.request` for Tier 3. Wrapped the route handler with `this.asUser(req)` so calls go OBO. Added the matching `user_api_scopes`.

### 14. Tier 3 needs `ai-gateway` scope (and a fresh session)

After adding `serving.serving-endpoints`, T3 still returned 502 with `Provided OAuth token does not have required scopes: ai-gateway`. The `/ai-gateway/mlflow/v1/responses` endpoint is its own scope.

**Fix:** Add `ai-gateway` to `user_api_scopes`. **Note:** existing browser sessions cache the OBO token — after editing scopes, sign out + back in (or use a fresh incognito window) so the token is reminted with the new scopes.

### 15. App theme locked to dark mode

`@databricks/appkit-ui/styles.css` has a `@media (prefers-color-scheme: dark) :root:not(.light) { ... }` block that flipped the whole app dark on systems set to dark mode.

**Fix:** `<html class="light" style="color-scheme: light">` in `client/index.html` so the dark-mode rule doesn't match.

---

## Directory Layout (final)

```
dais-demo-ai-data-search/
├── client/src/           # React UI (Search, Benchmark, Compare, Home)
├── server/               # AppKit server + search plugin
├── shared/               # Shared TypeScript types
├── config/queries/       # Typed SQL for analytics plugin
├── data/                 # Seed JSONL
├── setup/                # Python UC/VS provisioning
├── eval/                 # Benchmark harness
├── reference/            # yape_recsys.py (Streamlit baseline, not deployed)
├── databricks.yml        # DABs bundle
├── app.yaml              # App runtime (npm start, warehouse env)
├── README.md             # User-facing deploy guide
└── IMPLEMENTATION_NOTES.md  # This file
```

---

## Redeploy Checklist

1. `python setup/1_create_uc_tables.py` (if data changed)
2. `python setup/2_create_vector_indexes.py` + wait for indexes ready
3. `python setup/3_register_uc_functions.py`
4. `npm run build`
5. `databricks bundle deploy --target dev --auto-approve`
6. `databricks apps deploy --target dev`
7. Verify: https://dais-demo-ai-data-search-1444828305810485.aws.databricksapps.com

---

## Presenter Flow (summary)

1. **Vibe-coded baseline** — show `reference/yape_recsys.py` (Streamlit, hardcoded dicts)
2. **Platform, raw data** — Tier 0 → Tier 1, hero query fails
3. **AI-ready data** — Data Compare page, then Tier 2, hero queries succeed
4. **Supervisor contrast** — Tier 3 runs agent loop but hard intents still miss
5. **Benchmark close** — Hit@4 jump on Tier 2; narrative: Semantic · Governed · Vectorized · Measured

---

## Environment

| Setting | Value |
|---------|-------|
| Workspace | `e2-demo-field-eng` |
| CLI profile | Default (`e2-demo-field-eng`) |
| SQL warehouse | `01370556fad60fda` (TPCDS_L) |
| UC location | `ac_demo.agents` |
| App name | `dais-demo-ai-data-search` |
| Budget policy (e2-demo only) | `5b62fa02-8671-46d3-96ac-64c1725dc9d9` |

---

## Out of Scope (v1)

- Recommendation system / CF scores from `yape_recsys.py`
- Tier 3 batch eval in `run_benchmark.py`
- Automated enrichment via `ai_query()` at runtime (pre-built JSONL shipped instead)
- Flattening nested `yape_demo/yape-search-demo/` path (repo root is the app)
