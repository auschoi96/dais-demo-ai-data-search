import streamlit as st
import pandas as pd
import os
import requests
import json
import random

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Yape RecSys Engine",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Yape brand palette: purple primary, lime/green accent */
    :root {
        --yape-purple: #6B21A8;
        --yape-violet: #7C3AED;
        --yape-light: #EDE9FE;
        --yape-green: #22C55E;
        --yape-yellow: #FBBF24;
        --yape-gray: #F3F4F6;
    }
    .yape-header {
        background: linear-gradient(135deg, #6B21A8 0%, #7C3AED 60%, #A855F7 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 0.75rem;
        margin-bottom: 1.5rem;
    }
    .rec-card {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 0.75rem;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 5px solid #7C3AED;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .rec-card-agentic {
        border-left: 5px solid #22C55E;
        background: linear-gradient(to right, #F0FDF4, white);
    }
    .score-pill {
        display: inline-block;
        background: #EDE9FE;
        color: #6B21A8;
        font-weight: 700;
        font-size: 0.8rem;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
    }
    .score-pill-green {
        background: #DCFCE7;
        color: #15803D;
    }
    .tag-pill {
        display: inline-block;
        background: #F3F4F6;
        color: #374151;
        font-size: 0.75rem;
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
        margin-right: 0.3rem;
    }
    .agent-step {
        background: #FFFBEB;
        border-left: 4px solid #FBBF24;
        padding: 0.6rem 1rem;
        border-radius: 0 0.5rem 0.5rem 0;
        margin-bottom: 0.5rem;
        font-size: 0.87rem;
        color: #374151;
    }
    .arch-box {
        background: white;
        border: 2px solid #7C3AED;
        border-radius: 0.5rem;
        padding: 0.75rem 1rem;
        text-align: center;
        font-weight: 600;
        font-size: 0.85rem;
        color: #6B21A8;
    }
    .arch-box-green {
        border-color: #22C55E;
        color: #15803D;
    }
    .arch-arrow {
        text-align: center;
        font-size: 1.4rem;
        color: #9CA3AF;
        margin: 0.15rem 0;
    }
    .user-chip {
        display: inline-block;
        background: #EDE9FE;
        color: #5B21B6;
        border-radius: 999px;
        padding: 0.25rem 0.75rem;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .sidebar-toggle-label {
        font-weight: 700;
        color: #6B21A8;
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── Databricks AI call (reused from original setup) ────────────────────────
def call_databricks_ai(prompt, system_message=None, max_tokens=600, temperature=0.4):
    """Call Databricks Foundation Model API."""
    try:
        databricks_host  = os.environ.get("DATABRICKS_HOST")
        databricks_token = os.environ.get("DATABRICKS_TOKEN")
        endpoint = os.environ.get("DATABRICKS_SERVING_ENDPOINT", "databricks-meta-llama-3-1-70b-instruct")

        if not databricks_host or not databricks_token:
            return (
                "⚠️ Databricks credentials not configured. "
                "Set DATABRICKS_HOST and DATABRICKS_TOKEN to enable agentic mode."
            )

        url = f"{databricks_host}/serving-endpoints/{endpoint}/invocations"
        headers = {"Authorization": f"Bearer {databricks_token}", "Content-Type": "application/json"}

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        resp = requests.post(url, headers=headers, json=payload, timeout=45)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error calling Databricks AI: {e}"

# ─── Synthetic Data ──────────────────────────────────────────────────────────
USERS = [
    {
        "id": "u_ana",
        "name": "Ana García",
        "avatar": "👩‍💼",
        "segment": "Profesional",
        "age": 29,
        "city": "Lima",
        "monthly_income": 4200,
        "yape_since": "2021-03",
        "tx_count_30d": 38,
        "top_categories": ["Restaurantes", "Transporte", "Utilities"],
        "bio": "Trabaja en fintech, usa Yape para splits y pagos rápidos.",
    },
    {
        "id": "u_carlos",
        "name": "Carlos Mamani",
        "avatar": "👨‍🎓",
        "segment": "Estudiante",
        "age": 22,
        "city": "Arequipa",
        "monthly_income": 800,
        "yape_since": "2022-08",
        "tx_count_30d": 21,
        "top_categories": ["Recargas", "Comida rápida", "Entretenimiento"],
        "bio": "Universitario, recarga frecuente y pide delivery.",
    },
    {
        "id": "u_rosa",
        "name": "Rosa Quispe",
        "avatar": "👩‍🌾",
        "segment": "Microempresaria",
        "age": 45,
        "city": "Cusco",
        "monthly_income": 2100,
        "yape_since": "2020-11",
        "tx_count_30d": 55,
        "top_categories": ["Cobros", "Utilities", "Proveedores"],
        "bio": "Vende artesanías; usa Yape para cobrar y pagar proveedores.",
    },
    {
        "id": "u_diego",
        "name": "Diego Vargas",
        "avatar": "👨‍👧",
        "segment": "Familia",
        "age": 36,
        "city": "Trujillo",
        "monthly_income": 5800,
        "yape_since": "2021-06",
        "tx_count_30d": 29,
        "top_categories": ["Supermercados", "Educación", "Salud"],
        "bio": "Padre de familia, paga colegio, clínica y supermercado.",
    },
    {
        "id": "u_lucia",
        "name": "Lucía Torres",
        "avatar": "👩‍💻",
        "segment": "Tech-savvy",
        "age": 27,
        "city": "Lima",
        "monthly_income": 6500,
        "yape_since": "2020-05",
        "tx_count_30d": 63,
        "top_categories": ["Streaming", "Delivery", "Transferencias"],
        "bio": "Desarrolladora, early adopter. Usa todas las funciones de Yape.",
    },
    {
        "id": "u_miguel",
        "name": "Miguel Condori",
        "avatar": "👨‍🔧",
        "segment": "Trabajador independiente",
        "age": 41,
        "city": "Piura",
        "monthly_income": 1800,
        "yape_since": "2022-01",
        "tx_count_30d": 17,
        "top_categories": ["Recargas", "Utilities", "Transferencias"],
        "bio": "Técnico de gasfitería; cobra con Yape, paga agua y luz.",
    },
]

SERVICES = [
    # (id, name, category, icon, description)
    ("s01", "Yape Préstamos",       "Crédito",        "💰", "Préstamo instantáneo hasta S/ 3,000 sin papeleo."),
    ("s02", "Recarga Claro",         "Recargas",       "📱", "Recarga cualquier línea Claro al instante."),
    ("s03", "Recarga Entel",         "Recargas",       "📡", "Recarga tu línea Entel con descuentos."),
    ("s04", "Pago Luz (Enel)",        "Utilities",      "⚡", "Paga tu recibo de luz sin colas."),
    ("s05", "Pago Agua (SEDAPAL)",   "Utilities",      "💧", "Paga tu recibo de agua al instante."),
    ("s06", "Rappi Pay",             "Delivery",       "🛵", "Paga en Rappi con Yape y gana cashback."),
    ("s07", "PedidosYa",             "Delivery",       "🍔", "Paga tu delivery sin tarjeta."),
    ("s08", "Yape Fondo",            "Inversiones",    "📈", "Invierte desde S/ 10 y gana rendimiento diario."),
    ("s09", "Seguro Accidentes",     "Seguros",        "🛡️", "Seguro personal desde S/ 5/mes."),
    ("s10", "Pago Netflix",          "Streaming",      "🎬", "Paga tu suscripción Netflix con Yape."),
    ("s11", "Pago Spotify",          "Streaming",      "🎵", "Paga Spotify Premium mensual."),
    ("s12", "SOAT Digital",          "Seguros",        "🚗", "Contrata tu SOAT en 2 minutos."),
    ("s13", "Transferir a BCP",      "Transferencias", "🏦", "Transfiere gratis a cuentas BCP."),
    ("s14", "Pago de Colegio",       "Educación",      "🏫", "Paga mensualidades de colegios afiliados."),
    ("s15", "Yape Business",         "Negocios",       "🏪", "Acepta pagos y gestiona tu negocio."),
    ("s16", "Clínica Online",        "Salud",          "🩺", "Consulta médica virtual desde S/ 25."),
    ("s17", "Supermercado Wong",     "Supermercados",  "🛒", "Paga en Wong y recibe puntos bonus."),
    ("s18", "InDriver Pay",          "Transporte",     "🚕", "Paga tus viajes InDriver con Yape."),
    ("s19", "Pago Gas (Cálidda)",    "Utilities",      "🔥", "Paga tu recibo de gas domiciliario."),
    ("s20", "Yape QR Cobros",        "Negocios",       "📲", "Genera tu QR para cobrar en tu negocio."),
]

# Simulated collaborative-filtering scores per user (item_id → score 0–1)
CF_SCORES = {
    "u_ana": {
        "s01": 0.81, "s08": 0.76, "s10": 0.72, "s11": 0.68, "s18": 0.65,
        "s06": 0.61, "s04": 0.57, "s13": 0.54, "s09": 0.49, "s07": 0.44,
    },
    "u_carlos": {
        "s02": 0.88, "s03": 0.82, "s07": 0.77, "s06": 0.73, "s10": 0.69,
        "s11": 0.65, "s01": 0.55, "s04": 0.48, "s13": 0.42, "s18": 0.38,
    },
    "u_rosa": {
        "s20": 0.90, "s15": 0.86, "s04": 0.80, "s05": 0.77, "s19": 0.74,
        "s01": 0.70, "s09": 0.63, "s13": 0.58, "s02": 0.50, "s12": 0.45,
    },
    "u_diego": {
        "s14": 0.85, "s17": 0.82, "s04": 0.78, "s05": 0.74, "s16": 0.70,
        "s12": 0.65, "s01": 0.59, "s09": 0.54, "s13": 0.48, "s19": 0.44,
    },
    "u_lucia": {
        "s10": 0.91, "s11": 0.88, "s06": 0.84, "s07": 0.80, "s08": 0.76,
        "s01": 0.71, "s13": 0.66, "s18": 0.61, "s09": 0.55, "s02": 0.48,
    },
    "u_miguel": {
        "s02": 0.84, "s04": 0.79, "s05": 0.75, "s13": 0.70, "s19": 0.66,
        "s09": 0.60, "s12": 0.55, "s01": 0.50, "s20": 0.45, "s15": 0.40,
    },
}

def get_service(sid):
    for s in SERVICES:
        if s[0] == sid:
            return s
    return None

def get_traditional_recs(user_id, top_n=6):
    """Return top-N ranked items from CF scores."""
    scores = CF_SCORES.get(user_id, {})
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    result = []
    for sid, score in ranked:
        svc = get_service(sid)
        if svc:
            result.append({"id": svc[0], "name": svc[1], "category": svc[2],
                           "icon": svc[3], "description": svc[4], "score": score})
    return result

# ─── Session state ───────────────────────────────────────────────────────────
if "selected_user" not in st.session_state:
    st.session_state.selected_user = USERS[0]["id"]
if "agentic_mode" not in st.session_state:
    st.session_state.agentic_mode = False
if "agentic_recs" not in st.session_state:
    st.session_state.agentic_recs = {}
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; margin-bottom:1rem;'>
        <img src='https://images.seeklogo.com/logo-png/38/1/yape-logo-png_seeklogo-381640.png'
             style='width:64px; height:64px; object-fit:contain; border-radius:12px;'><br>
        <span style='font-size:1.3rem; font-weight:800; color:#6B21A8;'>Yape RecSys</span><br>
        <span style='font-size:0.78rem; color:#6B7280;'>Motor de Recomendaciones</span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("**Selecciona usuario**")
    for u in USERS:
        label = f"{u['avatar']} {u['name']} · {u['segment']}"
        if st.button(label, key=f"usr_{u['id']}",
                     use_container_width=True,
                     type="primary" if st.session_state.selected_user == u["id"] else "secondary"):
            st.session_state.selected_user = u["id"]
            st.session_state.agentic_recs = {}
            st.session_state.search_results = None
            st.rerun()

    st.divider()

    st.markdown('<p class="sidebar-toggle-label">⚡ Modo Agéntico</p>', unsafe_allow_html=True)
    agentic_on = st.toggle(
        "Activar RecsYs Agéntico",
        value=st.session_state.agentic_mode,
        help="Activa el agente LLM para enriquecer y reordenar las recomendaciones en tiempo real.",
    )
    if agentic_on != st.session_state.agentic_mode:
        st.session_state.agentic_mode = agentic_on
        st.session_state.agentic_recs = {}
        st.session_state.search_results = None
        st.rerun()

    if st.session_state.agentic_mode:
        st.success("🟢 Agente activo")
    else:
        st.info("⚪ Modo tradicional")

# ─── Header ───────────────────────────────────────────────────────────────────
mode_label = "🤖 Agéntico" if st.session_state.agentic_mode else "📊 Tradicional"
st.markdown(f"""
<div class="yape-header">
  <div style="display:flex; align-items:center; gap:1.2rem;">
    <img src="https://images.seeklogo.com/logo-png/38/1/yape-logo-png_seeklogo-381640.png"
         style="width:64px; height:64px; object-fit:contain; border-radius:12px; background:white; padding:4px;">
    <div>
      <div style="font-size:1.9rem; font-weight:800; letter-spacing:-0.5px;">Yape RecSys Engine</div>
      <div style="font-size:0.95rem; opacity:0.85;">
        Motor de búsqueda y recomendaciones para Yape · BCP &nbsp;|&nbsp; Modo: <strong>{mode_label}</strong>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── User context bar ─────────────────────────────────────────────────────────
user = next(u for u in USERS if u["id"] == st.session_state.selected_user)
st.markdown(
    f'<div class="user-chip">{user["avatar"]} {user["name"]}</div> '
    f'<div class="user-chip">📍 {user["city"]}</div> '
    f'<div class="user-chip">🏷️ {user["segment"]}</div> '
    f'<div class="user-chip">📅 Desde {user["yape_since"]}</div> '
    f'<div class="user-chip">💳 {user["tx_count_30d"]} tx / 30d</div>',
    unsafe_allow_html=True,
)
st.caption(f"_{user['bio']}_")
st.markdown("")

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_recs, tab_search, tab_arch = st.tabs(
    ["🎯 Recomendaciones", "🔍 Búsqueda Inteligente", "🏗️ Arquitectura"]
)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 · RECOMMENDATIONS
# ════════════════════════════════════════════════════════════════════════════
with tab_recs:

    trad_recs = get_traditional_recs(user["id"])

    if not st.session_state.agentic_mode:
        # ── Traditional RecSys ──────────────────────────────────────────────
        st.subheader("📊 Recomendaciones Tradicionales (Collaborative Filtering)")
        st.caption(
            "Ranking basado en similitud usuario-item con factorización de matrices (ALS). "
            "Las puntuaciones reflejan la probabilidad de interacción estimada por el modelo."
        )
        st.markdown("")

        col_info, col_metric1, col_metric2, col_metric3 = st.columns([3, 1, 1, 1])
        with col_info:
            st.markdown(f"**Algoritmo:** Matrix Factorization (ALS)  |  **Latent factors:** 64  |  **Modelo actualizado:** hace 2h")
        with col_metric1:
            st.metric("Precisión@6", "0.73")
        with col_metric2:
            st.metric("NDCG@6", "0.81")
        with col_metric3:
            st.metric("Cobertura", "68%")

        st.markdown("---")

        for rank, rec in enumerate(trad_recs, 1):
            bar_width = int(rec["score"] * 100)
            st.markdown(f"""
            <div class="rec-card">
              <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                  <span style="font-size:1.5rem;">{rec['icon']}</span>
                  <strong style="font-size:1rem; margin-left:0.4rem;">#{rank} {rec['name']}</strong>
                  <span class="tag-pill" style="margin-left:0.5rem;">{rec['category']}</span>
                </div>
                <span class="score-pill">CF Score: {rec['score']:.2f}</span>
              </div>
              <p style="color:#6B7280; font-size:0.87rem; margin:0.4rem 0 0.5rem 0;">{rec['description']}</p>
              <div style="background:#EDE9FE; border-radius:999px; height:6px; width:100%;">
                <div style="background:#7C3AED; border-radius:999px; height:6px; width:{bar_width}%;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    else:
        # ── Agentic RecSys ──────────────────────────────────────────────────
        st.subheader("🤖 Recomendaciones Agénticas (LLM-Augmented RecSys)")
        st.caption(
            "El agente LLM toma los candidatos del modelo CF, analiza contexto del usuario y "
            "reordena + enriquece las recomendaciones con explicaciones personalizadas en lenguaje natural."
        )
        st.markdown("")

        uid = user["id"]
        cache_key = uid

        if cache_key not in st.session_state.agentic_recs:
            candidates_text = "\n".join(
                f"- [{r['name']}] (categoría: {r['category']}, CF score: {r['score']:.2f}): {r['description']}"
                for r in trad_recs
            )
            user_context = (
                f"Usuario: {user['name']}, segmento '{user['segment']}', {user['age']} años, "
                f"ciudad {user['city']}, ingreso mensual S/ {user['monthly_income']}, "
                f"{user['tx_count_30d']} transacciones en los últimos 30 días. "
                f"Categorías más usadas: {', '.join(user['top_categories'])}. "
                f"Perfil: {user['bio']}"
            )

            prompt = f"""Eres el agente de recomendaciones de Yape, la app de pagos del BCP en Perú.

CONTEXTO DEL USUARIO:
{user_context}

CANDIDATOS DEL MODELO COLABORATIVO (ordenados por CF score):
{candidates_text}

TAREA:
1. Analiza el perfil y comportamiento del usuario.
2. Reordena los candidatos según relevancia contextual (no solo CF score).
3. Para cada recomendación (top 6), devuelve:
   - Nombre del servicio (exactamente como aparece arriba)
   - Puntuación agéntica del 0.00 al 1.00
   - Razón personalizada en 1 oración (máx 20 palabras, tuteo, tono amigable Yape)
4. Devuelve SOLO un JSON válido con esta estructura, sin texto adicional:
{{
  "reasoning": "Breve explicación de la estrategia de reranking en 2 oraciones.",
  "recommendations": [
    {{"name": "...", "agentic_score": 0.00, "reason": "..."}},
    ...
  ]
}}"""

            system_msg = (
                "Eres un motor de recomendaciones agéntico para Yape (BCP Perú). "
                "Personalizas recomendaciones financieras y de servicios con base en el contexto real del usuario. "
                "Responde ÚNICAMENTE con JSON válido, sin markdown, sin texto extra."
            )

            with st.spinner("🤖 Agente analizando perfil y generando recomendaciones personalizadas…"):
                raw = call_databricks_ai(prompt, system_msg, max_tokens=800, temperature=0.3)

            # Parse JSON from LLM
            try:
                # Strip markdown code fences if present
                clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                st.session_state.agentic_recs[cache_key] = {"ok": True, "data": parsed, "raw": raw}
            except Exception:
                st.session_state.agentic_recs[cache_key] = {"ok": False, "raw": raw}

        cached = st.session_state.agentic_recs.get(cache_key, {})

        if cached.get("ok"):
            data = cached["data"]

            # Agent reasoning expander
            with st.expander("🧠 Razonamiento del agente", expanded=True):
                st.markdown(f"""
                <div class="agent-step">💡 <strong>Estrategia de reranking:</strong> {data.get('reasoning', '—')}</div>
                """, unsafe_allow_html=True)
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Señales usadas", "Segmento + Historial + Hora")
                col_b.metric("Candidatos evaluados", len(trad_recs))
                col_c.metric("Top recomendaciones", len(data.get("recommendations", [])))

            st.markdown("---")

            # Build lookup from trad recs for icons / descriptions
            trad_lookup = {r["name"]: r for r in trad_recs}

            for rank, item in enumerate(data.get("recommendations", []), 1):
                svc_name   = item.get("name", "")
                ag_score   = item.get("agentic_score", 0.0)
                reason     = item.get("reason", "")
                trad_info  = trad_lookup.get(svc_name, {})
                icon       = trad_info.get("icon", "🔹")
                cat        = trad_info.get("category", "")
                desc       = trad_info.get("description", "")
                cf_score   = trad_info.get("score", 0.0)
                bar_width  = int(ag_score * 100)
                delta      = ag_score - cf_score

                st.markdown(f"""
                <div class="rec-card rec-card-agentic">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                      <span style="font-size:1.5rem;">{icon}</span>
                      <strong style="font-size:1rem; margin-left:0.4rem;">#{rank} {svc_name}</strong>
                      <span class="tag-pill" style="margin-left:0.5rem;">{cat}</span>
                    </div>
                    <div>
                      <span class="score-pill-green score-pill">Agéntico: {ag_score:.2f}</span>
                      &nbsp;
                      <span class="score-pill" style="opacity:0.6;">CF: {cf_score:.2f}</span>
                    </div>
                  </div>
                  <p style="color:#6B7280; font-size:0.85rem; margin:0.35rem 0 0.25rem 0;">{desc}</p>
                  <div class="agent-step" style="margin-top:0.4rem;">
                    💬 <em>{reason}</em>
                  </div>
                  <div style="background:#DCFCE7; border-radius:999px; height:6px; width:100%; margin-top:0.4rem;">
                    <div style="background:#22C55E; border-radius:999px; height:6px; width:{bar_width}%;"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.error("No se pudo parsear la respuesta del agente. Respuesta raw:")
            st.code(cached.get("raw", "sin respuesta"), language="text")

        if st.button("🔄 Regenerar recomendaciones agénticas", type="secondary"):
            st.session_state.agentic_recs.pop(cache_key, None)
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 · SEARCH
# ════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("🔍 Búsqueda Inteligente de Servicios")

    if not st.session_state.agentic_mode:
        # Traditional keyword search
        st.caption("Modo tradicional: búsqueda por palabras clave en nombre y categoría.")
        query = st.text_input("Buscar servicio en Yape…", placeholder="ej: pago agua, recarga, préstamo")
        if query:
            q_lower = query.lower()
            results = [
                s for s in SERVICES
                if q_lower in s[1].lower() or q_lower in s[2].lower() or q_lower in s[4].lower()
            ]
            if results:
                st.markdown(f"**{len(results)} resultado(s) encontrado(s):**")
                for s in results:
                    st.markdown(f"""
                    <div class="rec-card">
                      <span style="font-size:1.4rem;">{s[3]}</span>
                      <strong style="margin-left:0.4rem;">{s[1]}</strong>
                      <span class="tag-pill" style="margin-left:0.4rem;">{s[2]}</span>
                      <p style="color:#6B7280; font-size:0.85rem; margin:0.3rem 0 0;">{s[4]}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("No se encontraron servicios. Intenta con otras palabras clave.")
    else:
        # Agentic search
        st.caption(
            "Modo agéntico: el agente LLM interpreta tu intención, busca servicios relevantes "
            "y personaliza los resultados según tu perfil Yape."
        )
        col_q, col_btn = st.columns([5, 1])
        with col_q:
            query = st.text_input(
                "¿Qué necesitas?",
                placeholder="ej: quiero ahorrar, necesito pagar mi deuda, enviar dinero a mi mamá",
                key="agentic_search_input",
            )
        with col_btn:
            search_clicked = st.button("Buscar", type="primary", use_container_width=True)

        if search_clicked and query:
            st.session_state.search_query = query
            catalog_text = "\n".join(
                f"- [{s[0]}] {s[1]} (categoría: {s[2]}): {s[4]}"
                for s in SERVICES
            )
            user_ctx = (
                f"Usuario: {user['name']}, segmento '{user['segment']}', "
                f"categorías top: {', '.join(user['top_categories'])}. {user['bio']}"
            )

            search_prompt = f"""Eres el asistente de búsqueda de Yape (BCP Perú).

PERFIL DEL USUARIO:
{user_ctx}

CATÁLOGO DE SERVICIOS DISPONIBLES:
{catalog_text}

CONSULTA DEL USUARIO: "{query}"

TAREA:
1. Interpreta la intención de la consulta.
2. Selecciona los 4 servicios más relevantes del catálogo.
3. Para cada uno, explica por qué encaja con la consulta y el perfil del usuario.
4. Devuelve SOLO JSON válido sin texto adicional:
{{
  "intent": "Intención detectada en 1 oración.",
  "results": [
    {{"id": "sXX", "name": "...", "relevance_score": 0.00, "reason": "..."}},
    ...
  ]
}}"""

            system_msg = (
                "Eres un motor de búsqueda semántica para Yape. "
                "Interpreta intenciones en lenguaje natural y devuelve SOLO JSON válido."
            )

            with st.spinner("🔍 Agente interpretando tu búsqueda…"):
                raw = call_databricks_ai(search_prompt, system_msg, max_tokens=600, temperature=0.3)

            try:
                clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                st.session_state.search_results = {"ok": True, "data": json.loads(clean)}
            except Exception:
                st.session_state.search_results = {"ok": False, "raw": raw}

        if st.session_state.search_results:
            sr = st.session_state.search_results
            if sr.get("ok"):
                data = sr["data"]
                st.markdown(f"""
                <div class="agent-step">
                  🎯 <strong>Intención detectada:</strong> {data.get('intent', '—')}
                </div>
                """, unsafe_allow_html=True)
                st.markdown("")
                svc_lookup = {s[0]: s for s in SERVICES}
                for item in data.get("results", []):
                    svc = svc_lookup.get(item.get("id"), None)
                    icon = svc[3] if svc else "🔹"
                    cat  = svc[2] if svc else ""
                    desc = svc[4] if svc else ""
                    bar  = int(item.get("relevance_score", 0) * 100)
                    st.markdown(f"""
                    <div class="rec-card rec-card-agentic">
                      <span style="font-size:1.4rem;">{icon}</span>
                      <strong style="margin-left:0.4rem;">{item.get('name','')}</strong>
                      <span class="tag-pill" style="margin-left:0.4rem;">{cat}</span>
                      <span class="score-pill-green score-pill" style="float:right;">
                        Relevancia: {item.get('relevance_score',0):.2f}
                      </span>
                      <p style="color:#6B7280; font-size:0.85rem; margin:0.35rem 0 0.25rem 0;">{desc}</p>
                      <div class="agent-step">💬 <em>{item.get('reason','')}</em></div>
                      <div style="background:#DCFCE7; border-radius:999px; height:6px; width:100%; margin-top:0.4rem;">
                        <div style="background:#22C55E; border-radius:999px; height:6px; width:{bar}%;"></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.error("Error parseando resultados del agente.")
                st.code(sr.get("raw", ""), language="text")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 · ARCHITECTURE
# ════════════════════════════════════════════════════════════════════════════
with tab_arch:
    st.subheader("🏗️ Arquitectura del Sistema de Recomendaciones")

    arch_col1, arch_col2 = st.columns(2, gap="large")

    # ── Traditional ──────────────────────────────────────────────────────────
    with arch_col1:
        st.markdown("""
        <div style='text-align:center; margin-bottom:0.75rem;'>
          <span style='background:#EDE9FE; color:#6B21A8; font-weight:700;
                       padding:0.3rem 1rem; border-radius:999px; font-size:0.9rem;'>
            📊 Pipeline Tradicional (Offline Batch)
          </span>
        </div>
        """, unsafe_allow_html=True)

        steps_trad = [
            ("🗄️ Datos de Transacciones", "Historial de pagos, recargas y servicios usados por millones de usuarios Yape."),
            ("🔧 Feature Engineering", "Vectores de usuario-item: frecuencia, recencia, categoría, monto promedio."),
            ("🧮 Matrix Factorization (ALS)", "Factorización de la matriz de interacciones con 64 factores latentes en Spark MLlib."),
            ("📦 Generación de Candidatos", "Top-K items por usuario precalculados y almacenados en Delta Lake."),
            ("📋 Ranking Layer", "Reordenamiento por reglas de negocio (disponibilidad, exclusiones, boost de campañas)."),
            ("📱 API de Recomendaciones", "Endpoint REST que sirve el ranking final a la app Yape en <20ms."),
        ]

        for icon_name, desc in steps_trad:
            st.markdown(f'<div class="arch-box">{icon_name}</div>', unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.78rem; color:#6B7280; text-align:center; padding:0 0.5rem;'>{desc}</div>", unsafe_allow_html=True)
            st.markdown('<div class="arch-arrow">↓</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="arch-box" style="background:#EDE9FE;">🎯 Recomendación final al usuario</div>', unsafe_allow_html=True)

        st.markdown("")
        st.markdown("**Características clave:**")
        st.markdown("""
        - Proceso **batch** que corre cada pocas horas en Databricks Jobs
        - Alta escalabilidad: millones de usuarios con Spark ALS
        - Latencia de inferencia muy baja (pre-computado en Delta)
        - Sin personalización contextual en tiempo real
        - Métricas: Precision@K, NDCG, Coverage, MRR
        """)

    # ── Agentic ──────────────────────────────────────────────────────────────
    with arch_col2:
        st.markdown("""
        <div style='text-align:center; margin-bottom:0.75rem;'>
          <span style='background:#DCFCE7; color:#15803D; font-weight:700;
                       padding:0.3rem 1rem; border-radius:999px; font-size:0.9rem;'>
            🤖 Pipeline Agéntico (Real-Time LLM Augmented)
          </span>
        </div>
        """, unsafe_allow_html=True)

        steps_agentic = [
            ("🗄️ Datos de Transacciones", "Misma fuente de datos base + señales en tiempo real del usuario."),
            ("🔧 Feature Engineering", "Igual al pipeline tradicional, más contexto de sesión actual."),
            ("🧮 Matrix Factorization (ALS)", "Genera candidatos base (Top-K) como el pipeline tradicional."),
            ("📦 Candidatos CF (Top-K)", "Los mejores candidatos del modelo pasan al agente como contexto."),
            ("🤖 Agente LLM (Llama 3.1 70B)", "El LLM recibe perfil del usuario + candidatos + señales contextuales y razona el reranking."),
            ("🛠️ Herramientas del Agente", "• Perfil de usuario en tiempo real\n• Contexto temporal (hora, día, temporada)\n• Segmento y propensión de crédito\n• Historial reciente de 7 días"),
            ("✍️ Reranking + Explicaciones", "El agente reordena los items y genera explicaciones personalizadas en lenguaje natural."),
            ("📱 API Agéntica de Recomendaciones", "Respuesta enriquecida con scores agénticos, razones y mensajes personalizados."),
        ]

        for icon_name, desc in steps_agentic:
            bg = "background:#F0FDF4;" if "Agente" in icon_name or "Herramientas" in icon_name or "Reranking" in icon_name else ""
            border = "border-color:#22C55E; color:#15803D;" if "Agente" in icon_name or "Herramientas" in icon_name or "Reranking" in icon_name else ""
            st.markdown(f'<div class="arch-box" style="{bg}{border}">{icon_name}</div>', unsafe_allow_html=True)
            desc_html = desc.replace("\n", "<br>")
            st.markdown(f"<div style='font-size:0.78rem; color:#6B7280; text-align:center; padding:0 0.5rem;'>{desc_html}</div>", unsafe_allow_html=True)
            st.markdown('<div class="arch-arrow">↓</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="arch-box arch-box-green" style="background:#DCFCE7;">🎯 Recomendación personalizada + explicación</div>', unsafe_allow_html=True)

        st.markdown("")
        st.markdown("**Ventajas del enfoque agéntico:**")
        st.markdown("""
        - **Contextualización en tiempo real**: adapta recomendaciones a la sesión actual
        - **Explicabilidad**: el usuario entiende *por qué* se le recomienda cada servicio
        - **Flexibilidad semántica**: comprende intenciones en lenguaje natural
        - **Reranking dinámico**: ajusta el orden según señales que el modelo CF no captura
        - **Personalización profunda**: considera segmento, ciudad, historial y momento del día
        """)

    st.divider()

    # Comparison table
    st.subheader("⚖️ Comparación: Tradicional vs Agéntico")
    comparison = pd.DataFrame({
        "Dimensión": [
            "Latencia de respuesta", "Costo por consulta", "Escalabilidad",
            "Personalización", "Explicabilidad", "Búsqueda semántica",
            "Actualización del modelo", "Complejidad de mantenimiento",
        ],
        "📊 Tradicional (CF/ALS)": [
            "<20 ms", "Muy bajo", "Alta (millones de usuarios)",
            "Media (historial)", "Baja (scores opacos)", "No",
            "Batch (horas/días)", "Media",
        ],
        "🤖 Agéntico (LLM-Augmented)": [
            "1–5 s", "Medio (tokens LLM)", "Media (API throttling)",
            "Alta (contexto real-time)", "Alta (lenguaje natural)", "Sí",
            "Prompt engineering (inmediato)", "Alta",
        ],
    })
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("""
    <div style='background:#FFFBEB; border:1px solid #FCD34D; border-radius:0.5rem; padding:1rem 1.25rem;'>
      <strong>💡 Recomendación de despliegue para Yape:</strong> usar un enfoque híbrido donde el pipeline
      tradicional (ALS en Databricks) genera los candidatos offline con alta eficiencia, y el agente LLM
      se activa <em>selectivamente</em> para usuarios de alto valor, sesiones de onboarding, o búsquedas
      en lenguaje natural — balanceando costo, latencia y calidad de experiencia.
    </div>
    """, unsafe_allow_html=True)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style='text-align:center; color:#9CA3AF; font-size:0.8rem; padding:0.5rem;'>
  <img src="https://images.seeklogo.com/logo-png/38/1/yape-logo-png_seeklogo-381640.png"
       style="width:18px; height:18px; object-fit:contain; vertical-align:middle; margin-right:4px;">
  Yape RecSys Engine · Demo · Powered by Databricks AI &amp; Apache Spark
  &nbsp;|&nbsp; Banco de Crédito del Perú
</div>
""", unsafe_allow_html=True)
