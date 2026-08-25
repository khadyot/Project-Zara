import streamlit as st
import asyncio
import html
import yaml
import os
import glob
import hmac
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Bridge Streamlit Cloud's st.secrets into os.environ, which is where
# zara/utils/provider.py and the fetchers read their keys from.
#
# This used to end in `except Exception: pass`. Non-fatal is right -- there is no
# secrets file locally and the app must still start off .env.local -- but silent
# is not: three very different causes all presented identically as "key absent",
# and only one of them is a code bug.
#
#   unavailable -> st.secrets raised; no secrets configured for this deployment
#   empty       -> configured but nothing in it, or the wrong app
#   copied N    -> the bridge worked
#
# Recorded rather than logged so the Provider status panel can name the cause and
# point at the fix. Counts and key NAMES only -- never a value.
SECRETS_BRIDGE_STATUS = ("unavailable", "not attempted")
try:
    _copied = []
    _seen = 0
    for k, v in st.secrets.items():
        _seen += 1
        if isinstance(v, (str, int, float, bool)):
            if not os.environ.get(k):
                os.environ[k] = str(v)
                _copied.append(k)
    if _seen == 0:
        SECRETS_BRIDGE_STATUS = ("empty", "st.secrets contains no entries")
    else:
        SECRETS_BRIDGE_STATUS = ("copied", f"{len(_copied)} of {_seen} entries copied")
except Exception as _e:
    # Locally this is the normal path: no secrets.toml exists.
    SECRETS_BRIDGE_STATUS = ("unavailable", type(_e).__name__)

os.environ["ZARA_SECRETS_BRIDGE"] = f"{SECRETS_BRIDGE_STATUS[0]}|{SECRETS_BRIDGE_STATUS[1]}"

from zara.models import Prospect
from zara.orchestrator import run_end_to_end_pipeline
from zara.s2 import render_decision_card
from zara.ui.styles import CUSTOM_CSS, render_hero

# --- DESIGN SYSTEM ---
# We inject the SavvyCal style tokens via custom CSS overriding Streamlit defaults.

def _run_store():
    from zara.utils.telemetry import connect
    return connect()


def _age_label(days):
    """How old the evidence is, in the words a reviewer thinks in.

    The decision card buried "1826 days old" in the audit trail while the hook a
    reviewer reads first said "You recently discussed...". Nobody should have to
    scroll to notice the lead signal is five years old (Compass IX).
    """
    if days is None:
        return "undated", True
    if days >= 365:
        return f"{days / 365.25:.1f} years old", days > 180
    if days <= 1:
        return "today" if days == 0 else "1 day old", False
    return f"{days} days old", days > 180


def render_budget_meter():
    """What is left, in the only unit that matters to the operator: runs.

    Tokens are the meter the provider enforces, but nobody plans in tokens.
    The number worth surfacing on every page is "how many more prospects can I
    put through this today", plus the reason it is that number and not more.
    """
    try:
        from zara.utils import quota
        hrs = quota.headroom()
        h = next((x for x in hrs if x["resource"] == "groq tokens/day"), None)
        if not h:
            return

        st.markdown("<div class='eyebrow-sm'>Today</div>", unsafe_allow_html=True)
        pct = min(h["pct_used"], 1.0)
        st.progress(pct, text=f"{int(h['used']):,} / {int(h['limit']):,} tokens")

        fc = quota.forecast()
        f = fc.get("forecast")
        if f:
            runs = f["expected_runs"]
            tone = "var(--color-ember-coral)" if runs <= 2 else "var(--color-stone)"
            st.markdown(
                f"<div style='font-size:13px;color:{tone};margin-top:-6px;'>"
                f"<b>~{runs} runs left today</b> &middot; {f['conservative_runs']} at p90 "
                f"&middot; capped by {f['binding_limit']}</div>",
                unsafe_allow_html=True,
            )
            if fc.get("run_vs_tpm"):
                st.markdown(
                    f"<div style='font-size:12px;color:var(--color-stone);'>"
                    f"one run &asymp; {fc['run_vs_tpm']:.0%} of the per-minute bucket "
                    f"&mdash; expect a stall</div>",
                    unsafe_allow_html=True,
                )
        if h["status"] in ("critical", "exhausted"):
            st.warning("Near or at Groq TPD ceiling.")
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
    if r.get("offer_is_generic"):
        st.warning("**No prospect-specific signal found.** The opener is company-level and the offer is generic — human judgment required before sending.")
    if r["draft_text"]:
        content = ""
        if r.get("subject"):
            content += f"<strong>Subject:</strong> {html.escape(r['subject'])}<br><br>"
        content += html.escape(r['draft_text']).replace('\n', '<br>')
        st.markdown(f"<div class='draft-frame'>{content}</div>", unsafe_allow_html=True)
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
        mark_plain = "WINNER" if c["is_winner"] else ("excluded" if c["excluded"] else "eligible")
        mark_style = "WINNER" if c["is_winner"] else ("EXCLUDED" if c["excluded"] else "ELIGIBLE")
        score = f"{c['score'] or 0:.2f}"
        claim_raw = c['claim'] or ''
        
        label = f"[{score}] {mark_plain} · {c['source']} · {c['proximity']} — {claim_raw[:80]}"
        with st.expander(label):
            claim_html = html.escape(claim_raw)
            styled_header = (f"<span class='score-badge'>{score}</span> "
                             f"<span class='candidate-status'>{mark_style}</span> "
                             f"<span class='candidate-claim-summary " + ("excluded" if c["excluded"] else "") + f"'>"
                             f"{html.escape(c['source'])} · {html.escape(c['proximity'])} — {claim_html}</span>")
            st.markdown(styled_header, unsafe_allow_html=True)
            
            st.write(f"**Claim:** {c['claim']}")
            if c["pain_id"]:
                st.write(f"**Pain match:** `{c['pain_id']}` (relevance {c['score']:.2f}, raw match {c['pain_score']:.2f})")
                st.write(f"**Why:** {c['pain_reason']}")
            if c["attributed_to"]:
                st.warning(f"Attributed to: {c['attributed_to']} — not the prospect")
            if c["excluded"]:
                st.write(f"**Excluded:** {c['excluded']}")
            if c["guardrail_hit"]:
                st.write(f"**Guardrail:** {c['guardrail_hit']}")
            
            src_url = html.escape(c["source_url"] or "")
            st.markdown(f"<div class='candidate-source-url'>{src_url}</div>", unsafe_allow_html=True)
            # Excluded cards keep their snippet: "why was this thrown away?" is
            # unanswerable without it. Dimmed, not hidden.
            snippet_cls = "candidate-snippet excluded" if c["excluded"] else "candidate-snippet"
            snippet_html = html.escape((c["snippet"] or "")[:1200])
            st.markdown(f"<div class='{snippet_cls}'>{snippet_html}</div>", unsafe_allow_html=True)

    hooks = [dict(h) for h in conn.execute(
        "SELECT * FROM hooks WHERE run_id=? ORDER BY strength DESC", (rid,))]
    st.markdown(f"### Hook options ({len(hooks)})")
    for h in hooks:
        st.markdown(f"""
        <div class='hook-row'>
            <div><span class='score-badge'>{h['strength']:.2f}</span> {html.escape(h['hook_text'])}</div>
            <div class='hook-caption'>why: {html.escape(h['rationale'])} &middot; bridge: {html.escape(h['bridge'])}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Sources")
    for s in conn.execute("SELECT * FROM source_calls WHERE run_id=? ORDER BY seq", (rid,)):
        icon = f"<span class='status-dot status-{s['status']}'></span>"
        detail = f"{s['cards']} cards" if s["status"] == "ok" else (s["reason"] or "")[:90]
        st.markdown(f"{icon} **{s['source']}** — {s['status']} — {s['elapsed_ms']/1000:.1f}s — {detail}", unsafe_allow_html=True)

    st.markdown("### Model calls")
    for c in conn.execute("SELECT * FROM llm_calls WHERE run_id=? ORDER BY seq", (rid,)):
        label = (f"{c['stage']} · {c['provider']} · "
                 f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
                 f"{c['elapsed_ms']/1000:.1f}s")
        with st.expander(label):
            styled_header = (f"<span class='model-call-header'>{html.escape(c['stage'])} · {html.escape(c['provider'])} · "
                             f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
                             f"{c['elapsed_ms']/1000:.1f}s</span>")
            st.markdown(styled_header, unsafe_allow_html=True)
            if c["system_text"]:
                st.markdown("<div class='eyebrow-sm'>SYSTEM</div>", unsafe_allow_html=True)
                st.text(c["system_text"])
            if c["prompt_text"]:
                st.markdown("<div class='eyebrow-sm'>PROMPT — how this stage was instructed</div>", unsafe_allow_html=True)
                st.text(c["prompt_text"])
            if c["response_text"]:
                st.markdown("<div class='eyebrow-sm'>RESPONSE</div>", unsafe_allow_html=True)
                st.text(c["response_text"][:4000])


def render_provider_status():
    """Is this deployment wired up? The one failure local testing cannot catch.

    On a hosted deploy the keys arrive as st.secrets and are copied into
    os.environ at startup. If that copy fails, every model call dies mid-pipeline
    with something that reads like a pipeline bug. Presence is free to check;
    the probe costs ~10 tokens and is the only thing that separates "a key is
    set" from "the provider accepts it", so it is on demand, never on render.
    """
    from zara.utils import health

    st.markdown("### Provider status")
    rows = health.key_status()
    ok = health.secrets_bridge_ok()

    bridge = health.bridge_status()

    if ok:
        st.success("All required credentials are present in this process.")
    else:
        missing = [r["name"] for r in rows if r["tier"] == "required" and not r["present"]]
        st.error(
            "Missing required credentials: " + ", ".join(missing) + ".\n\n"
            f"**Cause — secrets bridge: {bridge['state']}** ({bridge['detail']}). "
            f"{bridge['advice']}"
        )

    st.caption(f"Secrets bridge: {bridge['state']} — {bridge['detail']}")

    for r in rows:
        if r["present"]:
            mark = "present"
            note = f"{r['length']} chars"
            if r["suspicious"]:
                mark, note = "suspicious", f"only {r['length']} chars — looks like a placeholder"
        else:
            mark = "absent"
            note = "not set"
        st.markdown(
            f"<div style='font-family:Geist Mono,monospace;font-size:13px;'>"
            f"<b>{r['name']}</b> &middot; {mark} &middot; {note} "
            f"<span style='color:var(--color-stone);'>({r['tier']} — {r['purpose']})</span></div>",
            unsafe_allow_html=True,
        )

    st.caption("Key names and lengths only — values are never read or displayed.")

    if st.button("Test Groq connection (~10 tokens)"):
        with st.spinner("Probing Groq…"):
            res = asyncio.run(health.groq_probe())
        if res["status"] in ("ok", "throttled"):
            st.success(f"{res['status']}: {res['detail']}")
        else:
            st.error(f"{res['status']}: {res['detail']}")


def render_budget_and_quota():
    st.markdown("<div class='eyebrow'>System</div>", unsafe_allow_html=True)
    st.markdown("## Budget & Quota")

    render_provider_status()
    st.markdown("---")
    
    try:
        from zara.utils import quota, telemetry
        import pandas as pd
        
        hrs = quota.headroom()
        fc = quota.forecast()
        
        st.markdown("### Quota Headroom")
        for h in hrs:
            color = "green" if h["status"] == "ok" else ("orange" if h["status"] == "warn" else "red")
            st.markdown(f"**{h['resource']}**: {h['used']:.0f} / {h['limit']:.0f} (resets in {int(h['resets_in_s']//60)}m) - <span style='color:{color}'>{h['status'].upper()}</span>", unsafe_allow_html=True)
            st.progress(min(h["pct_used"], 1.0))
            
        st.markdown("### Runs & Forecast")
        c1, c2, c3 = st.columns(3)
        c1.metric("Recorded Runs", fc["recorded_runs"])
        c2.metric("Avg tokens/run", f"{int(fc['mean_tokens']):,}")
        c3.metric("Avg stall time", f"{fc['avg_stall_s']:.1f}s")
        
        f = fc.get("forecast")
        if f:
            st.info(f"**Forecast ({f['binding_limit']}):** Expected {f['expected_runs']} more runs, Conservative {f['conservative_runs']} more runs.")
            basis = fc.get("basis")
            if basis == "replayed":
                st.caption(
                    "Estimated from replayed runs. Their token counts were measured live when "
                    "recorded, so the cost basis is real \u2014 replaying them spent no quota."
                )
            elif basis == "ui_runs":
                st.caption("Estimated from real runs you triggered.")
            if fc.get("run_vs_tpm"):
                st.caption(
                    f"One run is about {fc['run_vs_tpm']:.0%} of the 8,000 tokens/minute bucket. "
                    "Tokens-per-day caps how many runs you get; tokens-per-minute caps how fast. "
                    "A single run routinely stalls because its last call crosses the ceiling \u2014 "
                    "structural on the free tier, not a fault."
                )
            
        st.markdown("### Token Share by Stage")
        with telemetry.connect() as conn:
            rows = conn.execute("SELECT stage, SUM(prompt_tokens+completion_tokens) as t FROM usage WHERE provider != 'fixture' AND status NOT IN ('error', '429') GROUP BY stage ORDER BY t DESC").fetchall()
            if rows:
                df = pd.DataFrame([dict(r) for r in rows])
                if not df.empty and 'stage' in df.columns:
                    st.bar_chart(df.set_index("stage"))
                
        st.markdown("### Recent 429 Stalls")
        with telemetry.connect() as conn:
            stalls = conn.execute("SELECT ts, stage, wait_ms FROM usage WHERE status = '429' ORDER BY ts DESC LIMIT 20").fetchall()
            if stalls:
                for s in stalls:
                    st.caption(f"`{s['ts']}` | **{s['stage']}** — waited {s['wait_ms']/1000:.1f}s")
            else:
                st.info("No recent stalls recorded.")
    except Exception as e:
        st.error(f"Error rendering budget: {e}")


def main():
    st.set_page_config(page_title="Zara Outreach", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    try:
        app_pw = st.secrets.get("APP_PASSWORD")
    except Exception:
        app_pw = None

    if app_pw and not st.session_state.get("authenticated", False):
        st.title("Zara Outreach")
        with st.form("password_gate"):
            pwd = st.text_input("Enter Password", type="password")
            submit_pw = st.form_submit_button("Submit")
            if submit_pw:
                # compare_digest raises TypeError on a non-ASCII str, and app_pw is
                # whatever type the TOML gave us (an unquoted 1234 is an int). Bytes.
                if hmac.compare_digest(pwd.encode(), str(app_pw).encode()):
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
        st.stop()

    with st.sidebar:
        page = st.radio("View", ["Draft", "Run History", "Budget & Quota"], horizontal=True, label_visibility="collapsed")
        render_budget_meter()
        st.markdown("---")
        st.header("Zara Settings")
        st.markdown("Tune the pipeline parameters.")
        st.markdown("---")
        
        st.markdown("<div class='eyebrow-sm'>1. Identity</div>", unsafe_allow_html=True)
        sender_name = st.text_input("Sender Name (Company)", value="Zamp")
        product = st.text_area("Product/Offer", value="We help operations teams automate manual, reconciliation-heavy processes", height=80)
        proof_point = st.text_area("Proof Point (Optional)", value="", height=80)
        
        st.markdown("<br><div class='eyebrow-sm'>2. Strictness</div>", unsafe_allow_html=True)
        strictness = st.radio(
            "Ranker Mode",
            ["Brand Safety (Strict)", "Pipeline Max (Permissive)"],
            help="Strict mode requires verbatim evidence of pain. Permissive mode allows structural inferences."
        )
        
        st.markdown("<br><div class='eyebrow-sm'>3. Data Sources</div>", unsafe_allow_html=True)
        use_exa = st.checkbox("Exa (Web/News)", value=True)
        use_apify = st.checkbox("Apify (LinkedIn/Social)", value=True)
        
        st.markdown("<br><div class='eyebrow-sm'>4. Developer Mode</div>", unsafe_allow_html=True)
        admin_pass = st.text_input("Admin Password", type="password")

        st.markdown("<br><div class='eyebrow-sm'>5. Demo mode (offline)</div>", unsafe_allow_html=True)
        demo_mode = st.checkbox("Demo mode (offline)")
        replay_snapshot = None
        if demo_mode:
            snapshots = sorted(glob.glob("tests/fixtures/*_snapshot.json"))
            if snapshots:
                replay_snapshot = st.selectbox("Select Snapshot", snapshots, format_func=lambda x: os.path.basename(x))
            else:
                st.warning("No snapshots found — demo mode will still hit the network.")
            os.environ["USE_FIXTURES"] = "1"
        else:
            os.environ.pop("USE_FIXTURES", None)

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
        "use_exa": use_exa,
        "use_apify": use_apify
    }
    
    if demo_mode and replay_snapshot:
        settings["replay_snapshot"] = replay_snapshot
    
    if page == "Run History":
        render_run_history()
        return

    if page == "Budget & Quota":
        render_budget_and_quota()
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
                        hc_min = st.number_input("Min Headcount", value=vp.get('icp', {}).get('headcount', {}).get('preferred_min', 50))
                    with colB:
                        hc_max = st.number_input("Max Headcount", value=vp.get('icp', {}).get('headcount', {}).get('preferred_max', 500))
                    new_vp['icp'] = new_vp.get('icp', {})
                    new_vp['icp']['headcount'] = {"preferred_min": hc_min, "preferred_max": hc_max}
                    
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
        
        st.markdown("<div class='eyebrow'>Single Prospect</div>", unsafe_allow_html=True)
        st.markdown("## Generate Draft")
        
        with st.form("prospect_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Prospect Name", placeholder="e.g. Dimitri Dadiomov")
            with col2:
                company = st.text_input("Company", placeholder="e.g. Modern Treasury")
                
            title = st.text_input("Title / Role (Optional)", placeholder="e.g. VP Finance")
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
                title=title if title else None,
                company_domain=domain if domain else None,
                linkedin_url=linkedin if linkedin else None
            )

            st.markdown("---")

            progress_lines = []

            def on_event(e):
                if e.get("type") == "stage":
                    line = f"**{e['name']}** — {e.get('status', '')}" + (f": {e['detail']}" if e.get("detail") else "")
                elif e.get("type") == "source":
                    dot = f"<span class='status-dot status-{e['status']}'></span>"
                    line = f"{dot} {e['name']} — {e['status']}" + (f" ({e['detail']})" if e.get("detail") else "")
                elif e.get("type") == "hook":
                    line = f"**Hook** [{e['strength']:.2f}] — {e['text']}"
                else:
                    return
                progress_lines.append(line)
                try:
                    st.markdown(line, unsafe_allow_html=True)
                except Exception:
                    pass

            from zara.utils.telemetry import trace_run

            async def run_backend(tr):
                # The trace lives in a ContextVar, and asyncio.run creates a fresh
                # context, so it has to be opened inside the coroutine to be visible
                # to the provider and orchestrator.
                with trace_run(prospect, trigger="ui", profile="standard") as t:
                    tr["id"] = t.run_id
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

        async def redraft(hook=None, style_name="auto", trigger="ui_redraft", fetch_tavily=False):
            from zara.utils.telemetry import trace_run
            with trace_run(prospect, trigger=trigger, profile="standard") as t:
                new_results = list(results)
                
                if fetch_tavily:
                    from zara.fetchers.tavily import TavilyFetcher
                    tav_res = await TavilyFetcher(force=True).fetch(prospect)
                    st.write(f"Tavily: {tav_res.status} ({len(tav_res.cards)} cards)")
                    
                    for i, r in enumerate(new_results):
                        if r.source == "Tavily":
                            new_results[i] = tav_res
                            break
                    else:
                        new_results.append(tav_res)
                        
                t.capture_sources(new_results)
                
                res = await process_prospect(
                    prospect, new_results,
                    strictness=settings.get("strictness", "strict"),
                    vp_override=settings.get("identity"),
                    resolution=res_info, hook=hook, style=style_name,
                )
                t.capture_draft(res)
                return new_results, res, t.run_id

        draft_res = cache["draft_res"]

        if regen:
            with st.status("Redrafting...", expanded=True):
                _, draft_res, new_run_id = asyncio.run(redraft(hook=None, style_name=style))
                st.session_state["zara_cache"]["draft_res"] = draft_res
                st.session_state["zara_cache"]["run_id"] = new_run_id

        if deep:
            with st.status("Running Tavily deep search...", expanded=True) as dstat:
                results, draft_res, new_run_id = asyncio.run(redraft(hook=None, style_name=style, trigger="ui_boost", fetch_tavily=True))
                st.session_state["zara_cache"]["results"] = results
                st.session_state["zara_cache"]["draft_res"] = draft_res
                st.session_state["zara_cache"]["run_id"] = new_run_id
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
        sq = getattr(draft_res.ranked_prospect, "signal_quality", "ok")
        sq_str = " (thin signal)" if sq == "thin" else ""
        st.markdown(
            f"<div style='font-family:Inter,sans-serif;font-size:14px;color:{badge_color};"
            f"font-weight:600;'>{badge_text}{sq_str}</div>",
            unsafe_allow_html=True,
        )

        # --- Hook options panel ---
        st.markdown("### Hook options")
        if ranked.hooks:
            for i, h in enumerate(ranked.hooks):
                age_text, is_stale = _age_label(getattr(h, "recency_days", None))
                flag = "  ⚠ stale" if is_stale else ""
                with st.expander(f"[{h.strength:.2f}] · {age_text}{flag} — {h.hook_text}"):
                    if is_stale:
                        st.caption(
                            f"This evidence is {age_text}. Lead with it only if it still stands, "
                            "and never describe it as recent."
                        )
                    st.markdown(f"**Why it matters:** {h.rationale}")
                    st.markdown(f"**Bridge to offer:** {h.bridge}")
                    if st.button(f"Draft with this hook", key=f"hook_{i}", use_container_width=True):
                        with st.status("Redrafting with selected hook...", expanded=True):
                            _, draft_res, new_run_id = asyncio.run(redraft(hook=h, style_name=style))
                            st.session_state["zara_cache"]["draft_res"] = draft_res
                            st.session_state["zara_cache"]["run_id"] = new_run_id
                        st.rerun()
        else:
            st.caption("No alternative hooks articulated for this prospect.")

        # --- Editable draft ---
        if getattr(draft_res, "offer_is_generic", False):
            st.warning("**No prospect-specific signal found.** The opener is company-level and the offer is generic — human judgment required before sending.")
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
            if getattr(draft_res, "subject", None):
                st.text_input("Subject", value=draft_res.subject, key=f"draft_subject_{_dk}")
            edited = st.text_area("Draft", value=draft_res.draft_text, height=260,
                                  key=f"draft_editor_{_dk}", label_visibility="collapsed")
            
            download_text = f"Subject: {draft_res.subject}\n\n{draft_res.draft_text}" if getattr(draft_res, "subject", None) else draft_res.draft_text
            st.download_button("Download draft", data=download_text, file_name="zara_draft.txt",
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
                dot = f"<span class='status-dot status-{r.status}'></span>"
                detail = f"{len(r.cards)} cards" if r.status == "ok" else (r.reason or "")
                st.markdown(f"{dot} `{r.source}` — **{r.status}** — {detail}",
                            unsafe_allow_html=True)

if __name__ == "__main__":
    main()
