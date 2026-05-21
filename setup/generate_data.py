#!/usr/bin/env python3
"""Generate seed JSONL files for the Yape search demo."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"  # yape-search-demo/data/

RAW_SERVICES = [
    ("s01", "Yape Loans", "Credit", "💰", "Instant loan up to S/ 3,000 with no paperwork."),
    ("s02", "Claro Recharge", "Top-ups", "📱", "Recharge any Claro mobile line instantly."),
    ("s03", "Entel Recharge", "Top-ups", "📡", "Recharge your Entel line with discounts."),
    ("s04", "Electricity Payment (Enel)", "Utilities", "⚡", "Pay your electricity bill without waiting in line."),
    ("s05", "Water Payment (SEDAPAL)", "Utilities", "💧", "Pay your water bill instantly."),
    ("s06", "Rappi Pay", "Delivery", "🛵", "Pay on Rappi with Yape and earn cashback."),
    ("s07", "PedidosYa", "Delivery", "🍔", "Pay for food delivery without a card."),
    ("s08", "Yape Savings Fund", "Investments", "📈", "Invest from S/ 10 and earn daily returns."),
    ("s09", "Accident Insurance", "Insurance", "🛡️", "Personal accident insurance from S/ 5/month."),
    ("s10", "Netflix Payment", "Streaming", "🎬", "Pay your Netflix subscription with Yape."),
    ("s11", "Spotify Payment", "Streaming", "🎵", "Pay Spotify Premium monthly."),
    ("s12", "Digital SOAT", "Insurance", "🚗", "Get your vehicle SOAT insurance in 2 minutes."),
    ("s13", "Transfer to BCP", "Transfers", "🏦", "Transfer for free to BCP bank accounts."),
    ("s14", "School Tuition Payment", "Education", "🏫", "Pay monthly fees at affiliated schools."),
    ("s15", "Yape Business", "Business", "🏪", "Accept payments and manage your business."),
    ("s16", "Online Clinic", "Health", "🩺", "Virtual doctor consultation from S/ 25."),
    ("s17", "Wong Supermarket", "Supermarkets", "🛒", "Pay at Wong and earn bonus points."),
    ("s18", "InDriver Pay", "Transport", "🚕", "Pay InDriver rides with Yape."),
    ("s19", "Gas Payment (Cálidda)", "Utilities", "🔥", "Pay your home gas bill."),
    ("s20", "Yape QR Payments", "Business", "📲", "Generate a QR code to get paid at your business."),
]

ENRICHMENTS: dict[str, dict] = {
    "s01": {
        "semantic_description": "Instant personal credit and micro-loans for users who need cash quickly, pay off debt, or cover emergencies without bank paperwork.",
        "intent_tags": ["loan", "credit", "debt", "prestamo", "deuda"],
        "user_intent_phrases": ["I need to pay off debt", "tengo deuda que pagar", "need a quick loan", "prestamo rapido"],
        "synonyms": ["personal loan", "microcredit", "prestamo personal"],
        "target_segments": ["Professional", "Independent worker", "Student"],
    },
    "s02": {
        "semantic_description": "Mobile top-up for Claro prepaid lines in Peru.",
        "intent_tags": ["recharge", "claro", "mobile", "recarga"],
        "user_intent_phrases": ["claro recharge", "recarga claro", "top up my phone"],
        "synonyms": ["Claro top-up", "recarga movil Claro"],
        "target_segments": ["Student", "Independent worker"],
    },
    "s08": {
        "semantic_description": "Savings and investment product for users who want to save money, grow small balances, or start investing with daily returns from S/ 10.",
        "intent_tags": ["savings", "invest", "ahorro", "inversion", "rendimiento"],
        "user_intent_phrases": ["I want to save money", "quiero ahorrar", "grow my savings", "hacer crecer mi plata"],
        "synonyms": ["savings fund", "investment pocket", "fondo de inversion"],
        "target_segments": ["Professional", "Tech-savvy", "Family"],
    },
    "s13": {
        "semantic_description": "Send money to family and friends via free transfers to BCP accounts.",
        "intent_tags": ["transfer", "send money", "family", "plata", "enviar"],
        "user_intent_phrases": ["send money to my mom", "enviar plata a mi mamá", "transfer to family"],
        "synonyms": ["money transfer", "enviar dinero"],
        "target_segments": ["Family", "Professional", "Student"],
    },
    "s16": {
        "semantic_description": "Telehealth and virtual doctor visits for users seeking medical advice online without visiting a clinic.",
        "intent_tags": ["doctor", "health", "telemedicine", "consulta"],
        "user_intent_phrases": ["online doctor visit", "doctor por internet", "virtual medical consultation"],
        "synonyms": ["telemedicine", "consulta medica virtual"],
        "target_segments": ["Family", "Professional"],
    },
    "s20": {
        "semantic_description": "QR payment acceptance for street vendors and small merchants who collect payments on their phone.",
        "intent_tags": ["qr", "merchant", "collect payments", "cobrar", "negocio"],
        "user_intent_phrases": ["I sell on the street and get paid on my phone", "cobrar con qr", "accept payments at my shop"],
        "synonyms": ["QR cobros", "merchant QR"],
        "target_segments": ["Micro-entrepreneur", "Business"],
    },
}

DEFAULT_ENRICHMENT = {
    "semantic_description": "",
    "intent_tags": [],
    "user_intent_phrases": [],
    "synonyms": [],
    "target_segments": ["General"],
}


def _embedding_text(row: dict) -> str:
    parts = [
        row["name"],
        row.get("semantic_description", ""),
        row.get("description", ""),
        " ".join(row.get("intent_tags", [])),
        " ".join(row.get("user_intent_phrases", [])),
        " ".join(row.get("synonyms", [])),
    ]
    return " ".join(p for p in parts if p).strip()


def _default_enrichment(sid: str, name: str, category: str, description: str) -> dict:
    base = {
        **DEFAULT_ENRICHMENT,
        "semantic_description": f"{name} — {description} Category: {category}.",
        "intent_tags": [category.lower(), name.split()[0].lower()],
        "user_intent_phrases": [name.lower(), f"pay {name.lower()}"],
        "synonyms": [category.lower()],
    }
    return ENRICHMENTS.get(sid, base)


USERS = [
    {"user_id": "u_ana", "name": "Ana Garcia", "avatar": "👩‍💼", "segment": "Professional", "age": 29, "city": "Lima", "monthly_income": 4200, "yape_since": "2021-03", "tx_count_30d": 38, "top_categories": ["Restaurants", "Transport", "Utilities"], "bio": "Works in fintech; uses Yape for splits and quick payments."},
    {"user_id": "u_carlos", "name": "Carlos Mamani", "avatar": "👨‍🎓", "segment": "Student", "age": 22, "city": "Arequipa", "monthly_income": 800, "yape_since": "2022-08", "tx_count_30d": 21, "top_categories": ["Top-ups", "Fast food", "Entertainment"], "bio": "College student; frequent top-ups and delivery."},
    {"user_id": "u_rosa", "name": "Rosa Quispe", "avatar": "👩‍🌾", "segment": "Micro-entrepreneur", "age": 45, "city": "Cusco", "monthly_income": 2100, "yape_since": "2020-11", "tx_count_30d": 55, "top_categories": ["Collections", "Utilities", "Suppliers"], "bio": "Sells crafts; uses Yape to collect and pay suppliers."},
    {"user_id": "u_diego", "name": "Diego Vargas", "avatar": "👨‍👧", "segment": "Family", "age": 36, "city": "Trujillo", "monthly_income": 5800, "yape_since": "2021-06", "tx_count_30d": 29, "top_categories": ["Supermarkets", "Education", "Health"], "bio": "Parent; pays school, clinic, and grocery bills."},
    {"user_id": "u_lucia", "name": "Lucia Torres", "avatar": "👩‍💻", "segment": "Tech-savvy", "age": 27, "city": "Lima", "monthly_income": 6500, "yape_since": "2020-05", "tx_count_30d": 63, "top_categories": ["Streaming", "Delivery", "Transfers"], "bio": "Developer and early adopter of all Yape features."},
    {"user_id": "u_miguel", "name": "Miguel Condori", "avatar": "👨‍🔧", "segment": "Independent worker", "age": 41, "city": "Piura", "monthly_income": 1800, "yape_since": "2022-01", "tx_count_30d": 17, "top_categories": ["Top-ups", "Utilities", "Transfers"], "bio": "Plumber; collects payment with Yape and pays utilities."},
]

EVAL_QUERIES = [
    {"query": "claro recharge", "language": "EN", "expected_service_ids": ["s02"], "tier": "easy"},
    {"query": "recarga claro", "language": "ES", "expected_service_ids": ["s02"], "tier": "easy"},
    {"query": "pay electricity bill", "language": "EN", "expected_service_ids": ["s04"], "tier": "medium"},
    {"query": "pago de luz", "language": "ES", "expected_service_ids": ["s04"], "tier": "medium"},
    {"query": "I want to save money", "language": "EN", "expected_service_ids": ["s08"], "tier": "hard"},
    {"query": "quiero ahorrar", "language": "ES", "expected_service_ids": ["s08"], "tier": "hard"},
    {"query": "send money to my mom", "language": "EN", "expected_service_ids": ["s13"], "tier": "hard"},
    {"query": "enviar plata a mi mamá", "language": "ES", "expected_service_ids": ["s13"], "tier": "hard"},
    {"query": "I need to pay off debt", "language": "EN", "expected_service_ids": ["s01"], "tier": "hard"},
    {"query": "online doctor visit", "language": "EN", "expected_service_ids": ["s16"], "tier": "hard"},
    {"query": "doctor por internet", "language": "ES", "expected_service_ids": ["s16"], "tier": "hard"},
    {"query": "I sell on the street and get paid on my phone", "language": "EN", "expected_service_ids": ["s20"], "tier": "hard"},
    {"query": "netflix subscription", "language": "EN", "expected_service_ids": ["s10"], "tier": "medium"},
    {"query": "protection if I get in an accident", "language": "EN", "expected_service_ids": ["s09"], "tier": "hard"},
    {"query": "pay school tuition", "language": "EN", "expected_service_ids": ["s14"], "tier": "medium"},
]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    raw_rows = []
    enriched_rows = []
    for sid, name, category, icon, description in RAW_SERVICES:
        raw = {
            "service_id": sid,
            "name": name,
            "category": category,
            "icon": icon,
            "description": description,
        }
        raw_rows.append(raw)
        enrich = _default_enrichment(sid, name, category, description)
        enriched = {**raw, **enrich}
        enriched["embedding_text"] = _embedding_text(enriched)
        enriched_rows.append(enriched)

    write_jsonl(DATA_DIR / "services_raw.jsonl", raw_rows)
    write_jsonl(DATA_DIR / "services_enriched.jsonl", enriched_rows)
    write_jsonl(DATA_DIR / "users.jsonl", USERS)
    write_jsonl(DATA_DIR / "search_eval.jsonl", EVAL_QUERIES)
    print(f"Wrote {len(raw_rows)} services, {len(USERS)} users, {len(EVAL_QUERIES)} eval queries to {DATA_DIR}")


if __name__ == "__main__":
    main()
