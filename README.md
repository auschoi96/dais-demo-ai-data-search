# DAIS Demo: AI-Ready Data Search

Node.js AppKit app demonstrating measurable search lift from **AI-ready structured data** on Databricks — not just better agents.

**Live app:** [dais-demo-ai-data-search](https://e2-demo-field-eng.cloud.databricks.com/apps-v2/app/dais-demo-ai-data-search/overview?o=1444828305810485) on `e2-demo-field-eng`

## Quick start (any workspace)

### 1. Clone and configure

```bash
git clone https://github.com/auschoi96/dais-demo-ai-data-search.git
cd dais-demo-ai-data-search

# Authenticate to your workspace
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com

# Copy and edit bundle variables (or pass --var flags)
cp .env.example .env
```

### 2. Provision data (one-time)

```bash
pip install -r setup/requirements.txt

export DATABRICKS_WAREHOUSE_ID=YOUR_WAREHOUSE_ID

python setup/generate_data.py          # optional — seed JSONL included
python setup/1_create_uc_tables.py       # creates ac_demo.agents.* tables
python setup/2_create_vector_indexes.py  # VS endpoint + indexes (~5–15 min)
python setup/3_register_uc_functions.py
```

Default UC location: `ac_demo.agents`. Override in `setup/_config.py` if needed.

### 3. Deploy with DABs

```bash
npm install
npm run build

databricks bundle validate --target dev

# If the app already exists in your workspace, bind it first:
databricks bundle deployment bind app YOUR_APP_NAME --target dev --auto-approve

databricks bundle deploy --target dev --auto-approve
databricks apps deploy --target dev
```

Override warehouse/catalog per workspace:

```bash
databricks bundle deploy --target dev --auto-approve \
  --var catalog=your_catalog \
  --var schema=your_schema \
  --var sql_warehouse_id=YOUR_WAREHOUSE_ID
```

### 4. Local development

```bash
npm run dev
# open http://localhost:8000
```

## Architecture

| Tier | What it shows |
|------|----------------|
| **0** | Keyword search on raw catalog (vibe-coded baseline) |
| **1** | Vector Search on `yape_services_raw` |
| **2** | Vector Search on `yape_services_enriched` (hero tier) |
| **3** | Supervisor API + Opus 4.7 + UC function on raw index |

**Hero queries:** `I want to save money` and `quiero ahorrar` → fail T0/T1/T3, succeed T2.

## Prerequisites

Enable in Admin Console → Previews (check with `python setup/0_validate_previews.py`):

1. Unity AI Gateway (Beta)
2. Supervisor API (Beta)
3. Store OpenTelemetry traces in Unity Catalog

## Bundle variables

| Variable | Default | Description |
|----------|---------|-------------|
| `catalog` | `ac_demo` | UC catalog for demo tables |
| `schema` | `agents` | UC schema for demo tables |
| `sql_warehouse_id` | *(required per target)* | Warehouse for SQL + app runtime |

## Key UC objects

| Object | Name |
|--------|------|
| Raw table | `{catalog}.{schema}.yape_services_raw` |
| Enriched table | `{catalog}.{schema}.yape_services_enriched` |
| Eval labels | `{catalog}.{schema}.yape_search_eval` |
| VS indexes | `yape_services_raw_idx`, `yape_services_enriched_idx` |
| UC function | `{catalog}.{schema}.search_yape_services` |

## Models

- **LLM:** `databricks-claude-opus-4-7`
- **Embeddings:** `databricks-qwen3-embedding-0-6b`

## Eval

```bash
python eval/run_benchmark.py
```

## Reference

`reference/yape_recsys.py` — original vibe-coded Streamlit baseline (not deployed).
