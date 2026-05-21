#!/usr/bin/env python3
"""Generate synthetic yape_transactions seed JSONL.

Persona-biased — Lima skews toward savings + delivery + business; Arequipa/Cusco
skew toward utilities + transfers; 18-24 cohort skews top-ups + streaming; 35+
cohort skews insurance + school + utilities. Amounts are tier-banded so analytics
queries against this data return realistic-looking patterns.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "transactions.jsonl"

random.seed(42)

REGIONS = [
    ("Lima", 0.50),
    ("Arequipa", 0.15),
    ("Trujillo", 0.13),
    ("Cusco", 0.12),
    ("Chiclayo", 0.10),
]
COHORTS = [("18-24", 0.22), ("25-34", 0.40), ("35-44", 0.25), ("45+", 0.13)]
CHANNELS = [("qr", 0.45), ("p2p", 0.30), ("transfer", 0.15), ("biz", 0.10)]

# Service-id → (amount_min_pen, amount_max_pen)
SERVICE_AMOUNTS: dict[str, tuple[float, float]] = {
    "s01": (50, 3000),   # Loans
    "s02": (5, 50),      # Claro
    "s03": (5, 50),      # Entel
    "s04": (30, 300),    # Electricity
    "s05": (20, 200),    # Water
    "s06": (10, 120),    # Rappi
    "s07": (12, 100),    # PedidosYa
    "s08": (10, 500),    # Savings
    "s09": (5, 60),      # Accident insurance
    "s10": (25, 50),     # Netflix
    "s11": (15, 30),     # Spotify
    "s12": (60, 320),    # SOAT
    "s13": (20, 2000),   # Transfer BCP
    "s14": (200, 1500),  # School
    "s15": (10, 800),    # Yape Business
    "s16": (25, 200),    # Online clinic
    "s17": (15, 400),    # Wong
    "s18": (8, 60),      # InDriver
    "s19": (30, 250),    # Gas
    "s20": (5, 600),     # QR
}

# Per-cohort service propensity (weights, not probabilities)
COHORT_WEIGHTS: dict[str, dict[str, float]] = {
    "18-24": {
        "s02": 4, "s03": 4, "s10": 3, "s11": 3, "s06": 3, "s07": 3, "s18": 2,
        "s13": 1.5, "s08": 1.5, "s17": 1, "s20": 1, "s16": 0.5,
    },
    "25-34": {
        "s08": 4, "s13": 4, "s15": 3, "s09": 2.5, "s06": 2.5, "s07": 2,
        "s10": 2, "s11": 2, "s17": 2, "s20": 2, "s04": 1.5, "s12": 1.5,
        "s01": 1.5, "s16": 1,
    },
    "35-44": {
        "s04": 3.5, "s05": 3, "s14": 3, "s19": 3, "s09": 2.5, "s12": 2.5,
        "s13": 2.5, "s17": 2.5, "s15": 2, "s08": 2, "s01": 1.5, "s16": 1.5,
    },
    "45+": {
        "s04": 4, "s05": 4, "s19": 3, "s13": 3, "s17": 3, "s05": 3,
        "s09": 2, "s12": 2, "s14": 1.5, "s08": 2,
    },
}

# Per-region service multipliers (1.0 = neutral)
REGION_MULT: dict[str, dict[str, float]] = {
    "Lima": {"s08": 1.6, "s15": 1.5, "s20": 1.4, "s06": 1.3, "s07": 1.3, "s16": 1.3},
    "Arequipa": {"s04": 1.4, "s05": 1.4, "s19": 1.3, "s14": 1.2, "s13": 1.2},
    "Trujillo": {"s17": 1.3, "s13": 1.2, "s14": 1.2, "s08": 1.1},
    "Cusco": {"s18": 1.5, "s04": 1.2, "s09": 1.2, "s12": 1.3},
    "Chiclayo": {"s17": 1.3, "s04": 1.3, "s13": 1.2, "s14": 1.2},
}


def weighted_choice(pairs: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in pairs)
    r = random.random() * total
    acc = 0.0
    for name, w in pairs:
        acc += w
        if r <= acc:
            return name
    return pairs[-1][0]


def amount_for(service_id: str) -> float:
    lo, hi = SERVICE_AMOUNTS.get(service_id, (5, 100))
    # Skew toward the low end (long tail).
    raw = random.betavariate(2, 5) * (hi - lo) + lo
    return round(raw, 2)


def pick_service(cohort: str, region: str) -> str:
    base = COHORT_WEIGHTS[cohort].copy()
    mult = REGION_MULT.get(region, {})
    weighted = {sid: w * mult.get(sid, 1.0) for sid, w in base.items()}
    return weighted_choice(list(weighted.items()))


def synthesize_user_pool(n: int = 500) -> list[dict]:
    users: list[dict] = []
    for i in range(n):
        region = weighted_choice(REGIONS)
        cohort = weighted_choice(COHORTS)
        users.append({"user_id": f"u{i:04d}", "region": region, "age_cohort": cohort})
    return users


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    users = synthesize_user_pool(500)

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    horizon_days = 90
    rows: list[dict] = []

    n_txns = 8000
    for i in range(n_txns):
        u = random.choice(users)
        service_id = pick_service(u["age_cohort"], u["region"])
        # Time biased toward recent.
        days_ago = int(random.betavariate(1.6, 3.0) * horizon_days)
        ts = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        rows.append({
            "txn_id": f"t{i:06d}",
            "user_id": u["user_id"],
            "service_id": service_id,
            "amount_pen": amount_for(service_id),
            "txn_ts": ts.isoformat(),
            "region": u["region"],
            "age_cohort": u["age_cohort"],
            "channel": weighted_choice(CHANNELS),
        })

    rows.sort(key=lambda r: r["txn_ts"])
    with OUTPUT.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    print(f"Wrote {len(rows)} transactions to {OUTPUT}")
    print(f"Users in pool: {len(users)}")
    # Quick sanity: per-region counts
    from collections import Counter
    region_count = Counter(r["region"] for r in rows)
    cohort_count = Counter(r["age_cohort"] for r in rows)
    svc_count = Counter(r["service_id"] for r in rows)
    print(f"By region: {dict(region_count)}")
    print(f"By cohort: {dict(cohort_count)}")
    print(f"Top services: {svc_count.most_common(5)}")


if __name__ == "__main__":
    main()
