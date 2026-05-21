# Demo Script — Two Agents, One Data Layer

**Audience:** DAIS keynote / breakout
**Run time:** 10–15 minutes
**Live app:** https://dais-demo-ai-data-search-1444828305810485.aws.databricksapps.com

The demo's one job: make the room *feel* — not just hear — that "AI-ready data" isn't a slogan, it's the difference between an agent that answers in one tool call and one that burns 10× the tokens fumbling through raw SQL. Same model. Same prompt scaffolding. Two agents, two tool surfaces. The data work that the AI-ready agent gets to skip is exactly the leverage you're paying for.

---

## Pre-flight (do this 5 minutes before going on stage)

1. **Sign in fresh.** Incognito window → app URL → Databricks SSO. This mints an OAuth token that includes `ai-gateway` + `mcp.functions` scopes — required for the agent loop.
2. **Pick the model.** Top-right dropdown defaults to **Opus 4.6**. For the punchier "even the small model wins with AI-ready data" closer, switch to **Haiku 4.5** in beat 6.
3. **Warm the path.** Send a throwaway query ("hi") so the FastAPI container, the bundled `claude` CLI, and the Databricks AI Gateway are all warm. First call is the slow one.
4. **Reset.** Hard reload so the empty-state agent cards show.
5. **Memorize the queries.** They're in the hero buttons above the input:
   - `What is the average ticket size for Yape Loans by age cohort?` — chain test
   - `How much do users in Lima typically pay for streaming subscriptions?` — category + region cross-cut
   - `¿Qué servicios usan los usuarios para pagar el alquiler?` — Spanish + slang
   - `Top services for sending plata in Cusco this quarter` — slang + region
   - `Compare savings adoption in Lima vs Trujillo` — multi-region
   - `Which insurance product has the highest average ticket?` — multi-service chain

---

## Beat 1 — Set the trap (~1 min)

> "There are two Claude Code agents on screen. Same model. Same system-prompt scaffolding. Same query. The one on the left has one tool — raw SQL against the warehouse. The one on the right has the same SQL tool plus three governed shortcuts. We're going to send them the same question and watch what happens to **wall time**, **tokens**, and **tool calls** as they work."

Point at the empty-state agent cards before sending anything. Read the tool list out loud.

**Vibe-Coded Agent** — *"One tool: raw SQL against the warehouse. Must discover the schema itself."*
- `execute_sql` — Databricks SQL warehouse, full read access to `ac_demo.agents.*`

**AI-Ready Agent** — *"Vector search + governed metric views + raw SQL fallback."*
- `search_yape_services_enriched` — Vector Search on the AI-ready enriched index (intent tags + bilingual phrases)
- `top_services_by_region(region, months_back)` — UC function on a governed **metric view** (`yape_service_adoption`)
- `avg_ticket_by_cohort(service_id)` — UC function on a governed **metric view** (`yape_avg_ticket`)
- `execute_sql` — same raw SQL, kept as a fallback so the agent isn't handcuffed when a question doesn't fit a metric view

Key framing line:
> "Everything the AI-ready agent has *extra* — that's the work a data team did once, in Unity Catalog, with governance and lineage. The vibe agent has to redo that work at runtime, for every query, on every agent run."

---

## Beat 2 — The hero query (~3 min)

Click the hero button: **"What is the average ticket size for Yape Loans by age cohort?"** Send.

Watch the columns stream side-by-side.

**AI-Ready Agent** (~1 tool call, ~3,500 tokens, ~10–15s):
1. `search_yape_services_enriched("Yape Loans")` → resolves to `s01`
2. `avg_ticket_by_cohort("s01")` → returns avg/median PEN by age cohort
3. Final answer with cohort numbers, in seconds.

**Vibe-Coded Agent** (5–8 tool calls, ~15,000–25,000 tokens, 30–60s):
1. `execute_sql("SHOW TABLES IN ac_demo.agents LIKE 'yape_%'")` — discover what's in the schema
2. `execute_sql("DESCRIBE TABLE ac_demo.agents.yape_transactions")` — figure out columns
3. `execute_sql("SELECT … FROM yape_transactions WHERE service_id = …")` — first try, may need refinement
4. Hits `METRIC_VIEW_MISSING_MEASURE_FUNCTION` error → has to learn the `MEASURE()` syntax on the fly
5. Retries with `MEASURE()`
6. Resolves service_id → service name via an extra `SELECT * FROM yape_services_raw`
7. Final answer

Point at the **comparison sidebar** when both finish. Numbers to call out verbatim:
- Wall-time delta (typically 3–5× slower for vibe)
- Token delta (typically 4–6× more tokens for vibe)
- Extra tool calls (typically +5 to +7)

Key line:
> "Both agents got the right answer. They both used the same metric-view data underneath. The difference is that the AI-ready agent **knew** the metric view existed because someone put a `top_services_by_region(region, months_back)` UC function in front of it with a description. The vibe agent had to *re-derive* that contract from `DESCRIBE TABLE`."

---

## Beat 3 — Why this lowers token cost (~2 min)

Stay on the result screen. Point at the **Comparison** sidebar's "AI-ready delta" callout. Open one of the vibe agent's tool-call rows so the audience can see the actual SQL it had to write.

Frame it as cost arithmetic:

> "Think about what's happening token-wise. Every time the vibe agent runs a tool, the *entire conversation so far* — including all the previous tool outputs — gets fed back into the next model call. That's how LLM agent loops work. So a 7-step trajectory isn't 7× the cost of a 1-step trajectory. It's quadratic-ish."

Concrete numbers to keep in your pocket:

| Metric | Vibe-coded | AI-ready | Multiplier |
|---|---|---|---|
| Tool calls (hero query #1) | ~7 | ~2 | 3.5× |
| Total tokens | ~20k | ~3.5k | **5.7×** |
| Wall time (Opus 4.6) | ~45s | ~13s | **3.5×** |
| Estimated cost per run | ~$0.30 | ~$0.05 | 6× |

> "Multiply that by ten thousand agent runs a day, across one product team, and the data work the AI-ready agent gets to skip is paying for itself in *one quarter*. And that's just the LLM bill — it doesn't count engineer hours debugging hallucinated SQL."

---

## Beat 4 — The ambiguity moment (~2 min)

Send hero #3: **`¿Qué servicios usan los usuarios para pagar el alquiler?`** (What services do users use to pay rent?)

Watch carefully — Yape has **no service literally called "rent"**. The data team mapped that intent into `s13` Transfer to BCP via enriched `user_intent_phrases: ["pagar el alquiler", "rent", "alquiler"]` and `intent_tags: ["alquiler"]`.

**AI-Ready Agent** — 1 tool call: `search_yape_services_enriched("pagar el alquiler")` → returns Transfer to BCP with a high relevance score → done.

**Vibe-Coded Agent** — has to guess. Common failure modes you'll see:
- Greps `yape_services_raw` for "alquiler" or "rent" → 0 rows → confused
- Tries to use Spanish in SQL `WHERE` clauses → still nothing
- Eventually settles on Transfer to BCP via intuition or fails to commit
- Often answers "I couldn't find a specific rent service" — *which is technically true on raw data*

Key line:
> "Translation is a guess about what the user meant. Enrichment is a *record* of what they actually said. The AI-ready agent didn't translate Spanish to English — it pattern-matched to a phrase a real customer support log captured a year ago. That's the work."

If time: also run hero #4 (`Top services for sending plata in Cusco this quarter`). "Plata" is Peruvian slang for money — the enriched intent phrases catch it; raw SQL has no chance.

---

## Beat 5 — The data layer tour (~2 min)

Click **Data Compare** in the top nav.

Left: **Raw catalog** — 20 services, name + category + 1-line description. *"This is what you ship if your AI strategy is 'just plug an LLM into our existing DB.'"*

Right: **AI-ready enriched** — same 20 services + `intent_tags`, `user_intent_phrases` (bilingual), `embedding_text`. *"Same rows. The diff is the work."*

Now describe what the audience *isn't* seeing on this page — the part underneath the agent's metric-view tools:

> "Three **Unity Catalog metric views** sit on top of an 8,000-row `yape_transactions` fact table:
>
> - `yape_service_adoption` — dimensions: service, region, age cohort, month, channel; measures: distinct users, total transactions, total volume PEN.
> - `yape_avg_ticket` — dimensions: service, age cohort, region; measures: avg / median ticket, count.
> - `yape_segment_behavior` — joined against a `yape_user_segments` view that classifies every user into usage tier (heavy/medium/light) and value tier (high/mid/low) by transaction history. Dimensions add the two tiers; measures match adoption + ticket.
>
> **Six UC functions** wrap them: `search_yape_services_enriched`, `list_services_by_category`, `top_services_by_region`, `compare_regions_adoption`, `avg_ticket_by_cohort`, `services_for_segment`. Each has named, typed parameters and an LLM-readable docstring. Plus a generic `query_metric_view` introspector for cross-cuts the named tools don't cover — same governance, more flexibility. The agent doesn't write SQL — it sees these contracts and picks the right one. That's what makes the difference."

Key line:
> "If your platform doesn't have governed metric views + UC function wrappers, your agents will always be writing schema-discovery SQL at runtime. *Every. Single. Run.*"

---

## Beat 6 — Even Haiku wins (optional, ~1.5 min)

Switch the **Model** dropdown to **Haiku 4.5**. Re-send hero #1.

Haiku is roughly 10× cheaper than Opus and 3× faster, but more error-prone on long tool-use trajectories. Expected behavior:

- **AI-Ready Haiku** still finishes cleanly — 1–2 tool calls, ~4–8s. The metric view's pre-aggregated answer is small enough that Haiku reasons over it accurately.
- **Vibe Haiku** struggles more — sometimes gets confused on `MEASURE()` syntax and gives up, sometimes hallucinates column names, sometimes produces a partially-correct answer.

Key line:
> "The data layer didn't just make Opus faster. It made *Haiku competent.* That's what good data does — it widens the model space that can serve your business. Without it, you're paying Opus prices to do schema discovery."

---

## Beat 7 — Close (~1 min)

> "Same model. Same query. Same user. Two agents — one with raw SQL, one with the work done. The AI-ready agent isn't smarter. It isn't a better prompt. It's just *better fed.*
>
> The takeaway: **don't pay for a better agent before you've earned a better dataset.** Vector search on raw text, metric views on governed transactions, UC functions with descriptions an LLM can read — none of this is exotic. It's what your data platform is supposed to do.
>
> The agent on the right is the demo. The data layer underneath it is the product."

---

## Recovery plays

| Situation | Move |
|---|---|
| Either agent stalls "Thinking…" past 90s | Hit the red stop button, then re-send. The bundled CLI occasionally cold-starts slow. |
| `ai-gateway` or `mcp.functions` scope error | OAuth token is stale. Open a fresh incognito tab and sign back in. |
| Vibe agent fails the SHOW TABLES step | Warehouse may have just woken up — first SQL call after idle is slow. Re-send. |
| AI-ready agent reaches for `execute_sql` instead of the metric view | The query genuinely doesn't fit a metric view (e.g. a channel cross-cut). Pivot — *"good — it knows when to fall back, instead of hallucinating a tool that doesn't exist."* |
| Audience asks "but what about cost of building the metric views?" | "One-time. Governed. Versioned in UC. Now powers every agent + dashboard + Genie space in the org. Compare that to every team writing the same aggregation SQL into their own notebook." |
| Audience asks "could you just give the vibe agent a bigger context window?" | "Sure, and pay 10× more per token while still doing schema discovery in the loop. The cost isn't context — it's the *work.*" |

---

## Cheat sheet — what to point at on screen

- **Empty-state agent cards** — proof that the tool diff is the *only* variable
- **Tool-call count badges** at the top of each column — single biggest visual contrast
- **Token count badges** — translates "ugly trajectory" into "your AWS bill"
- **AI-ready delta callout in the sidebar** — Vibe was Xx slower, Yx more tokens, +N tool calls
- **Vibe's expanded tool calls** — open one to show the actual SHOW TABLES / DESCRIBE noise
- **Data Compare page** — the upfront work, not the demo

Same model. Same query. Different data plumbing. Different outcome.
