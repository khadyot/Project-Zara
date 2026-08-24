import streamlit as st
import asyncio
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

from zara.models import Prospect
from zara.orchestrator import run_end_to_end_pipeline
from zara.s2 import render_decision_card

# --- DESIGN SYSTEM ---
# We inject the SavvyCal style tokens via custom CSS overriding Streamlit defaults.

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&family=Inter:wght@400;700&family=Barlow+Condensed:wght@400;700&display=swap');

/* Base Variables */
:root {
  --color-forest-stage: #0d542b;
  --color-lime-sprout: #b9ff78;
  --color-ember-coral: #f54320;
  --color-cream-paper: #fcf7ed;
  --color-true-black: #000000;
  --color-midnight-ink: #1c1917;
  --color-stone: #44403b;
  --color-fog: #e5e7eb;
}

/* Page Background */
.stApp {
    background-color: var(--color-cream-paper);
    color: var(--color-stone);
    font-family: 'Inter', sans-serif;
}

/* Typography Overrides */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Playfair Display', serif !important;
    color: var(--color-true-black) !important;
    letter-spacing: 0px !important;
}

#zara-hero h1 {
    color: var(--color-lime-sprout) !important;
}

p, .stMarkdown p, label, .st-emotion-cache-10trblm {
    color: var(--color-midnight-ink) !important;
}

#zara-hero p {
    color: var(--color-cream-paper) !important;
}

h1 {
    font-size: 64px !important;
    line-height: 1.08 !important;
}

/* Default Button: Outline Ghost */
.stButton > button {
    background-color: transparent !important;
    color: var(--color-midnight-ink) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
    border: 1.5px solid var(--color-midnight-ink) !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: all 0.1s ease;
}
.stButton > button:hover {
    background-color: var(--color-midnight-ink) !important;
    color: var(--color-cream-paper) !important;
    transform: none !important;
}

/* Primary Button: Lime Sprout */
.stButton > button[kind="primary"] {
    background-color: var(--color-lime-sprout) !important;
    border: none !important;
    color: var(--color-midnight-ink) !important;
    font-weight: 700 !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: var(--color-lime-sprout) !important;
    color: var(--color-midnight-ink) !important;
    transform: scale(1.02) !important;
    box-shadow: 0 0 0 4px rgba(185,255,120,0.25) !important;
}

/* Input Fields */
.stTextInput > div > div > input, .stTextArea textarea, .stSelectbox > div > div {
    background-color: #ffffff !important;
    border: 1px solid var(--color-fog) !important;
    border-radius: 8px !important;
    color: var(--color-true-black) !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input:focus, .stTextArea textarea:focus, .stSelectbox > div > div:focus {
    border-color: var(--color-midnight-ink) !important;
    box-shadow: 0 0 0 1px var(--color-midnight-ink) !important;
}

/* Eyebrow Labels */
.eyebrow {
    font-family: 'Barlow Condensed', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 18px;
    color: var(--color-midnight-ink);
    text-decoration: underline wavy var(--color-ember-coral) 2px;
    text-underline-offset: 6px;
    display: inline-block;
    margin-bottom: 16px;
    margin-top: 16px;
}

/* Alerts / Notifications */
div[data-testid="stAlert"] {
    background-color: #ffffff !important;
    border: 1px solid var(--color-fog) !important;
    border-radius: 8px !important;
    padding: 16px !important;
    color: var(--color-stone) !important;
}
div[data-testid="stAlert"] p, div[data-testid="stAlert"] div {
    color: var(--color-stone) !important;
}
div[data-testid="stAlert"]:has([data-testid="stIconMaterial"][title="error"]) {
    border-left: 4px solid var(--color-ember-coral) !important;
}

/* Tabs (Pill Nav) */
div[data-baseweb="tab-list"] {
    border-bottom: none !important;
    gap: 8px;
}
div[data-baseweb="tab-highlight"] {
    display: none !important;
}
button[data-baseweb="tab"] {
    border-radius: 9999px !important;
    background-color: transparent !important;
    color: var(--color-true-black) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
    border: none !important;
    padding: 6px 16px !important;
    margin-right: 0px !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background-color: var(--color-lime-sprout) !important;
    color: var(--color-midnight-ink) !important;
}
button[data-baseweb="tab"] div[data-testid="stMarkdownContainer"] p {
    color: inherit !important;
}

/* Sidebar Background */
section[data-testid="stSidebar"] {
    background-color: var(--color-cream-paper) !important;
}

/* Expanders */
div[data-testid="stExpander"] {
    border: 1px solid var(--color-fog) !important;
    border-radius: 8px !important;
    background-color: transparent !important;
}
div[data-testid="stExpander"] summary {
    background-color: transparent !important;
}
div[data-testid="stExpander"] summary:hover {
    background-color: rgba(229, 231, 235, 0.3) !important;
}

/* Custom Containers (Cards) */
.card-container {
    background-color: #ffffff;
    border: 1px solid var(--color-fog);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 24px;
}

/* Product Screenshot Frame (for Drafts) */
.draft-frame {
    border: 2px solid var(--color-ember-coral);
    border-radius: 24px;
    padding: 32px;
    background-color: #ffffff;
    box-shadow: 0 24px 48px rgba(245, 67, 32, 0.15);
    margin-top: 24px;
    margin-bottom: 32px;
}
</style>
"""

def render_hero():
    # Streamlit hack: inject a full-width HTML hero at the top
    hero_html = """
    <div id="zara-hero" style="
        background: var(--color-forest-stage);
        width: 100%;
        margin-top: -6rem;
        margin-bottom: 3rem;
        padding: 6rem 1rem;
        text-align: center;
        font-family: 'Playfair Display', serif;
    ">
        <h1 style="font-size: 96px; margin-bottom: 1rem;">Project Zara</h1>
        <p style="font-family: 'Inter', sans-serif; color: #fcf7ed; font-size: 20px; max-width: 600px; margin: 0 auto;">
            Automated, grounded, personalized outreach without the hallucination.
        </p>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)


def _run_store():
    from zara.utils.telemetry import connect
    return connect()


def render_budget_meter():
    """Groq's 8K TPM / 200K TPD ceiling works out to roughly 35 prospects a day.
    The person driving the runs should be able to see what is left."""
    try:
        import time
        conn = _run_store()
        today = time.strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(prompt_tokens+completion_tokens),0) tok "
            "FROM runs WHERE ts LIKE ?", (today + "%",)).fetchone()
        n, tok = row["n"], row["tok"]
        st.markdown("<div class='eyebrow' style='font-size: 14px;'>Today</div>", unsafe_allow_html=True)
        st.progress(min(tok / 200_000, 1.0), text=f"{n} runs · {tok:,} / 200,000 tokens")
        if tok > 160_000:
            st.warning("Near the 200K/day Groq ceiling.")
    except Exception:
        pass


def render_run_history():
    st.markdown("<div class='eyebrow'>Run History</div>", unsafe_allow_html=True)
    st.markdown("## Every run, and why it chose what it chose")
    try:
        conn = _run_store()
        runs = [dict(r) for r in conn.execute(
            "SELECT * FROM runs ORDER BY ts DESC, rowid DESC LIMIT 100")]
    except Exception as e:
        st.error(f"Could not open the run store: {e}")
        return

    if not runs:
        st.info("No runs recorded yet. Run a prospect and it will appear here.")
        return

    labels = {}
    for r in runs:
        v = r["verification_status"] or ("CRASH" if r["outcome"] == "crash" else "-")
        labels[f"{(r['ts'] or '')[5:16]}  {r['person_name']} @ {r['company']}  ·  {v}  ·  {r['run_id']}"] = r

    choice = st.selectbox("Pick a run", list(labels.keys()))
    r = labels[choice]
    rid = r["run_id"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wall time", f"{(r['duration_ms'] or 0)/1000:.1f}s")
    c2.metric("Tokens", f"{(r['prompt_tokens'] or 0) + (r['completion_tokens'] or 0):,}")
    c3.metric("Claim strength", r["claim_strength"] or "—")
    c4.metric("Verifier", r["verification_status"] or "—")

    st.caption(f"code `{r['git_sha']}` · value_prop `{r['value_prop_sha']}` · model `{r['groq_model']}`")

    if r["outcome"] == "crash":
        st.error(f"CRASHED: {r['error']}")
        with st.expander("Traceback"):
            st.code(r["traceback"] or "")

    st.markdown("### Draft")
    if r["draft_text"]:
        st.markdown(f"<div class='draft-frame'>{r['draft_text']}</div>", unsafe_allow_html=True)
    else:
        st.info("No draft produced.")

    st.markdown("### Verifier")
    st.write(f"**{r['verification_status']}** · passed={bool(r['verification_passed'])} "
             f"· self-corrected={bool(r['self_corrected'])} "
             f"· failed at: `{r['verification_failed_pass'] or '—'}`")
    if r["verification_reason"]:
        st.write(r["verification_reason"])
    import json as _json
    for x in _json.loads(r["first_pass_hallucinations"] or "[]"):
        st.write(f"- ungrounded: `{x}`")

    st.markdown("### What it considered")
    cards = [dict(c) for c in conn.execute(
        "SELECT * FROM cards WHERE run_id=? ORDER BY is_winner DESC, score DESC", (rid,))]
    st.caption(f"{r['cards_total'] or 0} candidates · {r['cards_eligible'] or 0} eligible")
    for c in cards:
        mark = "**WINNER**" if c["is_winner"] else ("~~excluded~~" if c["excluded"] else "eligible")
        with st.expander(f"[{c['score'] or 0:.2f}] {mark} · {c['source']} · {c['proximity']} — {(c['claim'] or '')[:80]}"):
            st.write(f"**Claim:** {c['claim']}")
            if c["pain_id"]:
                st.write(f"**Pain match:** `{c['pain_id']}` ({c['pain_score']:.2f})")
                st.write(f"**Why:** {c['pain_reason']}")
            if c["attributed_to"]:
                st.warning(f"Attributed to: {c['attributed_to']} — not the prospect")
            if c["excluded"]:
                st.write(f"**Excluded:** {c['excluded']}")
            if c["guardrail_hit"]:
                st.write(f"**Guardrail:** {c['guardrail_hit']}")
            st.caption(c["source_url"] or "")
            st.text((c["snippet"] or "")[:1200])

    hooks = [dict(h) for h in conn.execute(
        "SELECT * FROM hooks WHERE run_id=? ORDER BY strength DESC", (rid,))]
    st.markdown(f"### Hook options ({len(hooks)})")
    for h in hooks:
        st.write(f"**[{h['strength']:.2f}]** {h['hook_text']}")
        st.caption(f"why: {h['rationale']}  ·  bridge: {h['bridge']}")

    st.markdown("### Sources")
    for s in conn.execute("SELECT * FROM source_calls WHERE run_id=? ORDER BY seq", (rid,)):
        icon = {"ok": "OK", "empty": "--", "failed": "XX", "skipped": ">>"}.get(s["status"], "·")
        detail = f"{s['cards']} cards" if s["status"] == "ok" else (s["reason"] or "")[:90]
        st.markdown(f"`{icon}` **{s['source']}** — {s['status']} — {s['elapsed_ms']/1000:.1f}s — {detail}")

    st.markdown("### Model calls")
    for c in conn.execute("SELECT * FROM llm_calls WHERE run_id=? ORDER BY seq", (rid,)):
        with st.expander(f"{c['stage']} · {c['provider']} · "
                         f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
                         f"{c['elapsed_ms']/1000:.1f}s"):
            if c["system_text"]:
                st.caption("SYSTEM")
                st.text(c["system_text"])
            if c["prompt_text"]:
                st.caption("PROMPT — how this stage was instructed")
                st.text(c["prompt_text"])
            if c["response_text"]:
                st.caption("RESPONSE")
                st.text(c["response_text"][:4000])


def main():
    st.set_page_config(page_title="Zara Outreach", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    with st.sidebar:
        page = st.radio("View", ["Draft", "Run History"], horizontal=True, label_visibility="collapsed")
        render_budget_meter()
        st.markdown("---")
        st.header("Zara Settings")
        st.markdown("Tune the pipeline parameters.")
        st.markdown("---")
        
        st.markdown("<div class='eyebrow' style='font-size: 14px; margin-bottom: 2px;'>1. Identity</div>", unsafe_allow_html=True)
        sender_name = st.text_input("Sender Name (Company)", value="Zamp")
        product = st.text_area("Product/Offer", value="We help operations teams automate manual, reconciliation-heavy processes", height=80)
        proof_point = st.text_area("Proof Point (Optional)", value="", height=80)
        
        st.markdown("<br><div class='eyebrow' style='font-size: 14px; margin-bottom: 2px;'>2. Strictness</div>", unsafe_allow_html=True)
        strictness = st.radio(
            "Ranker Mode",
            ["Brand Safety (Strict)", "Pipeline Max (Permissive)"],
            help="Strict mode requires verbatim evidence of pain. Permissive mode allows structural inferences."
        )
        
        st.markdown("<br><div class='eyebrow' style='font-size: 14px; margin-bottom: 2px;'>3. Data Sources</div>", unsafe_allow_html=True)
        use_ats = st.checkbox("ATS Fetchers (Free)", value=True)
        use_exa = st.checkbox("Exa (Web/News)", value=True)
        use_apify = st.checkbox("Apify (LinkedIn/Social)", value=True)
        
        st.markdown("<br><div class='eyebrow' style='font-size: 14px; margin-bottom: 2px;'>4. Developer Mode</div>", unsafe_allow_html=True)
        admin_pass = st.text_input("Admin Password", type="password")

        st.markdown("---")
        from zara.utils import budget
        try:
            tv = budget.get_credit_usage("tavily")
            st.markdown(
                f"<div style='font-size:12px;color:var(--color-stone);'>"
                f"tavily: <b>{tv['used']}</b>/{tv['limit']} credits ({tv['month']}) · "
                f"apify spend: <b>${budget.get_mtd_spend():.3f}</b> MTD</div>",
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    settings = {
        "identity": {
            "sender_name": sender_name,
            "product": product,
            "proof_point": proof_point if proof_point else None
        },
        "strictness": "permissive" if "Permissive" in strictness else "strict",
        "use_ats": use_ats,
        "use_exa": use_exa,
        "use_apify": use_apify
    }
    
    if page == "Run History":
        render_run_history()
        return

    render_hero()
    
    # Wrap all content below hero in a centered column
    _, col_main, _ = st.columns([1, 4, 1])
    with col_main:
        if admin_pass == "123":
            st.markdown("<div class='eyebrow'>Advanced Configuration</div>", unsafe_allow_html=True)
            st.markdown("## Visual Settings Engine")
            st.info("You are editing the engine configuration visually. Changes take effect on the next run.")
            try:
                with open("value_prop.yaml", "r") as f:
                    vp = yaml.safe_load(f)
                
                tab1, tab2, tab3, tab4 = st.tabs(["ICP & Targeting", "Weights", "Pains Engine", "Guardrails"])
                
                # Mutable state for saving
                new_vp = vp.copy()
                
                with tab1:
                    st.subheader("Headcount Criteria")
                    colA, colB = st.columns(2)
                    with colA:
                        hc_min = st.number_input("Min Headcount", value=vp.get('icp', {}).get('headcount', {}).get('min', 50))
                    with colB:
                        hc_max = st.number_input("Max Headcount", value=vp.get('icp', {}).get('headcount', {}).get('max', 500))
                    new_vp['icp'] = new_vp.get('icp', {})
                    new_vp['icp']['headcount'] = {"min": hc_min, "max": hc_max}
                    
                    st.subheader("Target Sectors")
                    sectors_str = "\n".join(vp.get('icp', {}).get('sectors', []))
                    new_sectors = st.text_area("Sectors (one per line)", value=sectors_str, height=100)
                    new_vp['icp']['sectors'] = [s.strip() for s in new_sectors.split("\n") if s.strip()]
                    
                    st.subheader("Buyer Titles")
                    titles_str = "\n".join(vp.get('buyer_titles', []))
                    new_titles = st.text_area("Titles (one per line)", value=titles_str, height=100)
                    new_vp['buyer_titles'] = [t.strip() for t in new_titles.split("\n") if t.strip()]

                with tab2:
                    st.subheader("Signal Proximity Weights")
                    st.markdown("Controls tie-breaking logic in the Ranker.")
                    pw = vp.get("proximity_weights", {"authored": 4, "attributed": 3, "company_action": 2, "database": 1})
                    authored_w = st.slider("Authored (LinkedIn Posts)", 1, 10, pw.get("authored", 4))
                    attributed_w = st.slider("Attributed (News Quotes)", 1, 10, pw.get("attributed", 3))
                    company_action_w = st.slider("Company Action (Press Releases)", 1, 10, pw.get("company_action", 2))
                    database_w = st.slider("Database (Job Postings, Firmographics)", 1, 10, pw.get("database", 1))
                    new_vp['proximity_weights'] = {
                        "authored": authored_w,
                        "attributed": attributed_w,
                        "company_action": company_action_w,
                        "database": database_w
                    }
                    
                with tab3:
                    st.subheader("Pain Points")
                    pains = vp.get("pains", [])
                    new_pains = []
                    for i, p in enumerate(pains):
                        with st.expander(f"Pain: {p.get('id', f'Pain {i}')}"):
                            pid = st.text_input("ID", value=p.get('id', ''), key=f"pid_{i}")
                            stmt = st.text_input("Statement", value=p.get('statement', ''), key=f"stmt_{i}")
                            obs_str = "\n".join(p.get('observable_via', []))
                            obs = st.text_area("Observable Via (one per line)", value=obs_str, height=100, key=f"obs_{i}")
                            new_pains.append({
                                "id": pid,
                                "statement": stmt,
                                "observable_via": [o.strip() for o in obs.split("\n") if o.strip()]
                            })
                    new_vp['pains'] = new_pains
                    
                with tab4:
                    st.subheader("Firmographic Vetoes")
                    vetoes_str = "\n".join(vp.get('icp', {}).get('vetoes', []))
                    new_vetoes = st.text_area("Vetoes (one per line)", value=vetoes_str, height=100)
                    new_vp['icp']['vetoes'] = [v.strip() for v in new_vetoes.split("\n") if v.strip()]
                    
                    st.subheader("Never Reference Topics")
                    st.markdown("Signals containing these topics will be immediately blocked.")
                    nr = vp.get("never_reference", [])
                    new_nr = []
                    for i, n in enumerate(nr):
                        with st.expander(f"Topic: {n.get('id', f'Topic {i}')}"):
                            nid = st.text_input("Topic ID", value=n.get('id', ''), key=f"nid_{i}")
                            terms_str = ", ".join(n.get('terms', []))
                            terms = st.text_input("Trigger Terms (comma separated)", value=terms_str, key=f"nterms_{i}")
                            new_nr.append({
                                "id": nid,
                                "terms": [t.strip() for t in terms.split(",") if t.strip()]
                            })
                    new_vp['never_reference'] = new_nr
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Deploy Engine Updates", type="primary", use_container_width=True):
                    with open("value_prop.yaml", "w") as f:
                        yaml.dump(new_vp, f, sort_keys=False)
                    # load_value_prop is lru_cached, so the engine keeps serving the
                    # pre-save config until the process restarts. Without this the next
                    # run silently uses the old settings (D19).
                    from zara.utils.config import load_value_prop
                    load_value_prop.cache_clear()
                    st.success("Configuration successfully deployed!")
            except Exception as e:
                st.error(f"Failed to load config: {e}")
            st.markdown("---")
        
        st.markdown("<div class='eyebrow'>Scheduling Experience</div>", unsafe_allow_html=True)
        st.markdown("## Generate Draft")
        
        with st.form("prospect_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Prospect Name", placeholder="e.g. Dimitri Dadiomov")
            with col2:
                company = st.text_input("Company", placeholder="e.g. Modern Treasury")
                
            domain = st.text_input("Domain (Optional)", placeholder="e.g. moderntreasury.com")
            linkedin = st.text_input("LinkedIn URL (Optional)", placeholder="https://linkedin.com/in/...")
            
            submitted = st.form_submit_button("Run Zara Pipeline", type="primary")
            
        if submitted:
            if not name or not company:
                st.error("Name and Company are required.")
                return

            prospect = Prospect(
                person_name=name,
                company=company,
                company_domain=domain if domain else None,
                linkedin_url=linkedin if linkedin else None
            )

            st.markdown("---")

            progress_lines = []

            def on_event(e):
                if e.get("type") == "stage":
                    line = f"**{e['name']}** — {e.get('status', '')}" + (f": {e['detail']}" if e.get("detail") else "")
                elif e.get("type") == "source":
                    icon = {"ok": "✅", "empty": "⚪", "failed": "❌", "skipped": "⏭️", "running": "⏳"}.get(e["status"], "·")
                    line = f"{icon} {e['name']} — {e['status']}" + (f" ({e['detail']})" if e.get("detail") else "")
                elif e.get("type") == "hook":
                    line = f"★ Hook [{e['strength']:.2f}]: {e['text']}"
                else:
                    return
                progress_lines.append(line)
                try:
                    st.write(line)
                except Exception:
                    pass

            from zara.utils.telemetry import trace_run

            async def run_backend(tr):
                # The trace lives in a ContextVar, and asyncio.run creates a fresh
                # context, so it has to be opened inside the coroutine to be visible
                # to the provider and orchestrator.
                with trace_run(prospect, trigger="ui", profile="standard") as t:
                    tr["id"] = t.run_id
                    t.on_event_sink = True
                    return await run_end_to_end_pipeline(
                        prospect, profile="standard", settings=settings,
                        on_event=lambda e: (t.event(e), on_event(e))[1],
                    )

            with st.status("Zara is researching...", expanded=True) as status:
                tr = {}
                try:
                    results, draft_res = asyncio.run(run_backend(tr))
                    st.session_state["zara_cache"] = {
                        "prospect": prospect, "results": results,
                        "draft_res": draft_res, "settings": settings,
                        "run_id": tr.get("id"),
                    }
                    status.update(label="Done — draft ready for review", state="complete", expanded=False)
                    if tr.get("id"):
                        st.caption(f"run `{tr['id']}` recorded")
                except Exception as e:
                    status.update(label=f"Error: {str(e)}", state="error", expanded=True)
                    st.exception(e)
                    if tr.get("id"):
                        st.caption(f"crashed run `{tr['id']}` recorded")
                    return

        cache = st.session_state.get("zara_cache")
        if not cache:
            st.info("Run the pipeline to generate a draft. You'll get the draft, the hook options behind it, and the full audit trail.")
            return

        prospect = cache["prospect"]
        results = cache["results"]
        settings = cache["settings"]
        from zara.s2 import process_prospect

        # --- Resolution banner ---
        res_info = cache["draft_res"].ranked_prospect.resolution
        if res_info and res_info.input_company.strip() != res_info.resolved_company:
            st.info(f"Resolved company: '{res_info.input_company}' → '{res_info.resolved_company}'"
                    + (f" ({res_info.domain})" if res_info.domain else ""))

        # --- Deviations (informational, never blocking) ---
        icp_notes = getattr(cache["draft_res"].ranked_prospect, "icp_notes", None)
        if icp_notes:
            st.caption("Deviations: " + " · ".join(icp_notes))

        # --- Regeneration controls ---
        st.markdown("### Regenerate")
        col_style, col_regen, col_deep = st.columns([2, 1, 1])
        with col_style:
            style = st.selectbox("Draft style", [
                "auto", "observation-led", "question-led", "peer-to-peer",
                "insight-led", "congratulation-led", "story-led",
            ])
        with col_regen:
            regen = st.button("Regenerate", type="primary", use_container_width=True)
        with col_deep:
            deep = st.button("Deep Search", use_container_width=True,
                             help="Force Tavily paid search for more person-level signal.")

        async def redraft(hook=None, style_name="auto"):
            return await process_prospect(
                prospect, results,
                strictness=settings.get("strictness", "strict"),
                vp_override=settings.get("identity"),
                resolution=res_info, hook=hook, style=style_name,
            )

        draft_res = cache["draft_res"]

        if regen:
            with st.status("Redrafting...", expanded=True):
                draft_res = asyncio.run(redraft(hook=None, style_name=style))
                st.session_state["zara_cache"]["draft_res"] = draft_res

        if deep:
            from zara.fetchers.tavily import TavilyFetcher
            with st.status("Running Tavily deep search...", expanded=True) as dstat:
                tav_res = asyncio.run(TavilyFetcher(force=True).fetch(prospect))
                st.write(f"Tavily: {tav_res.status} ({len(tav_res.cards)} cards)")
                results = [r for r in results if r.source != "Tavily"] + [tav_res]
                st.session_state["zara_cache"]["results"] = results
                draft_res = asyncio.run(redraft(hook=None, style_name=style))
                st.session_state["zara_cache"]["draft_res"] = draft_res
                dstat.update(label="Deep search complete", state="complete", expanded=False)

        ranked = draft_res.ranked_prospect

        # --- Confidence badge ---
        badge_map = {
            "person_authored": ("● strong — person-authored evidence", "#0d542b"),
            "person_attributed": ("● medium — person-attributed evidence", "#8a6d1a"),
            "company_action": ("● company-level evidence", "#8a6d1a"),
            "database_only": ("● weak — database only", "#a33a1a"),
            "no_signal": ("● no signal", "#f54320"),
        }
        badge_text, badge_color = badge_map.get(draft_res.claim_strength, ("● unknown", "#44403b"))
        st.markdown(
            f"<div style='font-family:Inter,sans-serif;font-size:14px;color:{badge_color};"
            f"font-weight:600;'>{badge_text}</div>",
            unsafe_allow_html=True,
        )

        # --- Hook options panel ---
        st.markdown("### Hook options")
        if ranked.hooks:
            for i, h in enumerate(ranked.hooks):
                with st.expander(f"[{h.strength:.2f}] {h.hook_text}"):
                    st.markdown(f"**Why it matters:** {h.rationale}")
                    st.markdown(f"**Bridge to offer:** {h.bridge}")
                    if st.button(f"Draft with this hook", key=f"hook_{i}", use_container_width=True):
                        with st.status("Redrafting with selected hook...", expanded=True):
                            draft_res = asyncio.run(redraft(hook=h, style_name=style))
                            st.session_state["zara_cache"]["draft_res"] = draft_res
                        st.rerun()
        else:
            st.caption("No alternative hooks articulated for this prospect.")

        # --- Editable draft ---
        st.markdown("### The draft (editable)")
        if draft_res.draft_text:
            # The key must change when the draft does. Streamlit gives session_state
            # precedence over `value=` for a keyed widget, so a fixed key made this box
            # stick on whatever it was first rendered with and silently ignore every
            # later draft -- including regenerations. Keying on the draft's own digest
            # means new text gets a fresh widget, while an unchanged draft keeps any
            # edits the user has made.
            import hashlib as _hl
            _dk = _hl.md5((draft_res.draft_text or "").encode()).hexdigest()[:10]
            edited = st.text_area("Draft", value=draft_res.draft_text, height=260,
                                  key=f"draft_editor_{_dk}", label_visibility="collapsed")
            st.download_button("Download draft", data=edited, file_name="zara_draft.txt",
                               mime="text/plain", use_container_width=True)
        else:
            st.warning("No draft generated. Try Deep Search for more signal, or loosen strictness.")

        # --- Verification status ---
        if draft_res.verification:
            v = draft_res.verification
            if v.passed:
                st.success(f"Verifier: passed ({v.status})" + (" — self-corrected after one hallucination retry" if v.self_corrected else ""))
            elif v.status == "blocked_hallucination":
                st.error(f"Verifier: blocked hallucination. {v.reason or ''}")
            else:
                st.warning(f"Verifier: {v.status}. {v.reason or ''}")

        # --- Decision card ---
        with st.expander("Decision card (full audit trail)"):
            st.markdown(render_decision_card(draft_res, results))

        # --- Sources ---
        with st.expander(f"Sources ({len(results)})"):
            for r in sorted(results, key=lambda x: (x.rung, x.source)):
                icon = {"ok": "✅", "empty": "⚪", "failed": "❌", "skipped": "⏭️"}.get(r.status, "·")
                detail = f"{len(r.cards)} cards" if r.status == "ok" else (r.reason or "")
                st.markdown(f"{icon} `{r.source}` — **{r.status}** — {detail}")

if __name__ == "__main__":
    main()
