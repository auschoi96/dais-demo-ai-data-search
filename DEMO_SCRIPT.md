# Demo Script — Vibe Coding vs AI-Ready Data

**Audience:** DAIS keynote / breakout
**Run time:** 10–15 minutes
**Live app:** https://dais-demo-ai-data-search-1444828305810485.aws.databricksapps.com

The demo's one job is to make the room feel — not just hear — that the bottleneck for "AI on your data" isn't the model. It's whether the data is semantic, governed, and vectorized. Same Opus 4.7. Same Vector Search. Same user. Different data → different outcome.

---

## Pre-flight (do this 5 minutes before going on stage)

1. **Sign in fresh.** Open a new incognito window, hit the live URL, sign in as your Databricks user. This refreshes the OAuth token so Tier 3 has the `ai-gateway` scope cached.
2. **Warm Tier 3.** Run one throwaway query on T3 ("hola"). The first Supervisor call is slow; subsequent calls are fast.
3. **Reset the page.** Hard reload (Cmd/Ctrl+Shift+R) so you start on an empty state.
4. **Default tier selection.** Confirm the header reads `Tiers: 2/4` — T0 + T2 are pre-selected. That's your "before/after" hero pair.
5. **Have the four hero queries memorized:**
   - `I want to save money` — English intent, hero #1
   - `quiero ahorrar` — Spanish intent, hero #2 (bilingual is the kicker)
   - `pagar el alquiler` — pay the rent (utility/intent)
   - `send money to my mom` — semantic phrasing, no keyword overlap

---

## Beat 1 — Set the trap (~1 min)

> "Everyone in this room has been told 'just plug an LLM into your data and it'll work.' We're going to test that on a real fintech catalog — Yape, the largest payments app in Peru. 20 services. Real users. Two languages. And we're going to run the **same model** on the **same vector search**, just on **different data**, and watch what happens."

Click the **Tiers** dropdown so the audience sees the four tiers and their blurbs:

| Tier | What it does |
|---|---|
| T0 | SQL `LIKE` on the raw catalog — the "vibe-coded" baseline |
| T1 | Vector Search on raw catalog fields (name + category + description) |
| T2 | Vector Search on AI-ready data (intent tags + bilingual phrases enriched into `embedding_text`) |
| T3 | Supervisor agent (Opus 4.7) calling a UC function — on the raw index |

Close the dropdown. Leave T0 + T2 checked.

---

## Beat 2 — The keyword baseline fails (~1.5 min)

Type or click `I want to save money`. Send.

Walk the audience through what they're seeing:

- **Left column (T0):** "No matches." Read it out loud. *"Nothing in the catalog literally contains the phrase 'I want to save money,' so substring search returns zero."*
- **Right column (T2):** "Yape Savings Fund" at the top, score ~0.62. *"Same query, same user. Vector Search on AI-ready data ranks the savings product first."*
- **Right sidebar:** Latencies, scores, MLflow trace icon. *"All instrumented in MLflow — production-grade observability, not a notebook trick."*

Key line:
> "T0 isn't broken. SQL `LIKE` is doing exactly what it was asked. The query just isn't expressed in catalog vocabulary."

---

## Beat 3 — Add the raw-data vector search (~1.5 min)

Open the Tiers dropdown. Check **T1** so you're now running T0 + T1 + T2. Re-send `I want to save money`.

Walk it:

- **T0:** still "No matches."
- **T1:** Vector Search now returns hits — but it's running on the *raw* fields. The top result is OK-ish (Savings Fund usually shows up) but the scores are lower than T2 and the ordering is shakier. Point to the score in the sidebar.
- **T2:** clean ~0.62 score on Savings Fund.

Key line:
> "Tier 1 proves the model and the embedding pipeline work. So if the answer were 'just add Vector Search,' we'd be done. We aren't — and we're about to see why."

---

## Beat 4 — Show the data delta (~2 min)

Click **Data Compare** in the top nav.

- Left column: **Raw catalog.** 20 services. Name, category, one-line description. *"This is what you ship if you 'just vibe-coded' a chatbot on your existing DB."*
- Right column: **AI-ready enriched.** Same 20 services. Each row now has:
  - `intent_tags` — `["save", "savings", "ahorro", "alquiler"]`
  - `user_intent_phrases` — `["quiero ahorrar", "I want to save", "guardar plata"]`
  - `embedding_text` — concatenated, the thing the index actually embeds

Key line:
> "This is the work. Nobody escapes it. The question is whether you do it once, governed, in Unity Catalog, with lineage and access control — or whether every team re-does it in a notebook and the answers diverge."

Pause on the `user_intent_phrases` column. *"Notice these are bilingual. The customer phrased it. The product team named it. We let the model match across both."*

---

## Beat 5 — The bilingual moment (~2 min)

Back to **Search**. Send `quiero ahorrar` (Spanish, "I want to save").

- **T0:** No matches.
- **T1:** Weak or wrong — the raw catalog is English.
- **T2:** Yape Savings Fund at the top, often a *higher* score than the English query (~0.63).

Key line:
> "Zero translation layer. The model doesn't speak Spanish 'because it's multilingual.' It works because the **data** was enriched with the phrasing real users actually use."

If you have time, run `pagar el alquiler` — rent-payment intent surfaces the Rent service, again only on T2.

---

## Beat 6 — The agent doesn't save you (~3 min)

Open Tiers. Check **T3** (and leave T0/T1/T2 on). Re-send `I want to save money`.

Wait for all four columns to populate. ~1 second each.

- **T3:** Supervisor + Opus 4.7. Calls the `search_yape_services` UC function. The function is bound to the **raw** index by design.
- The agent runs the tool. The tool returns the raw-index results. T3 looks a lot like T1.

Click the MLflow trace icon in the sidebar. Show the trace: tool call → vector search → response. *"This is a real agent loop, fully traced, governed by Unity AI Gateway."*

Key line:
> "Tier 3 is the punchline. If a better agent could rescue bad data, T3 would beat T2. It doesn't — and it can't. The supervisor is brilliant. The data underneath it is thin. Garbage in, garbage out, even with Opus."

---

## Beat 7 — The benchmark (~1 min)

Click **Benchmark** in the top nav. Hit@4 / MRR per tier.

Numbers to land:

- T0 ≈ 0% — keyword can't handle intent
- T1 lifts but plateaus — VS without enriched data
- T2 → ~90% Hit@4 — AI-ready data clears the bar
- T3 ≈ T1 — agent loop doesn't fix the data gap

Key line:
> "We measure this. Every change to the enrichment pipeline gets re-scored against 15 labeled queries. That's the Databricks loop: governed data, evaluation in MLflow, traces in UC. Not a guess. Not a vibe."

---

## Beat 8 — Close (~1 min)

> "Four words. **Semantic. Governed. Vectorized. Measured.** That's what 'AI-ready data' actually means on the Databricks platform. The model didn't change between T1 and T2. The data did. And it's the only thing that did.
>
> If you only remember one thing from this demo: **don't pay for a better agent before you've earned a better dataset.**"

---

## Recovery plays (when things go sideways)

| Situation | Move |
|---|---|
| T3 returns 502 / "ai-gateway scope missing" | Your OAuth token is stale. Open a fresh incognito tab and sign back in. Or skip T3 and use Tier 1 as the "raw index even with an agent fails" framing. |
| Vector Search returns nothing for any tier | Check VS endpoint `yape-search-demo-endpoint` is ONLINE in the workspace UI; trigger a sync on the enriched index. |
| App is slow on first hit | The MEDIUM-sized container cold-starts on idle. Hit `/` once during pre-flight so the Node process is warm. |
| Audience asks "why not just translate the query?" | "Translation is a guess about what user means. Enrichment is a record of what they actually said. Translation works one direction; intent tags work in both, plus across phrasing changes English-to-English." |
| Audience asks "isn't this just a RAG?" | "It's the data layer underneath every RAG you'll ever build. The same enriched table feeds chat, search ranking, ad targeting, and the agent in Tier 3. One source of truth, many consumers." |

---

## Cheat sheet — what to point at on screen

- **Tier picker dropdown** — proof the tiers are explicit, not magical
- **Right sidebar latency** — proves vector search is real-time, not batch
- **Right sidebar score** — single number that explains why T2 wins
- **MLflow trace icon (T3)** — proves the agent is governed and observable
- **Data Compare page** — the *only* slide of "before/after data" that matters

That's the script. Same model. Same query. Different data. Different outcome.
