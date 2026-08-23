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

def main():
    st.set_page_config(page_title="Zara Outreach", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    with st.sidebar:
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
            
            # Async bridge for Streamlit
            async def run_backend():
                results, draft_res = await run_end_to_end_pipeline(prospect, profile="standard", settings=settings)
                return results, draft_res
                
            with st.status("Agent researching...", expanded=True) as status:
                st.write("Initializing fetchers...")
                try:
                    # Use asyncio.run directly (Streamlit handles it well in most recent versions)
                    results, draft_res = asyncio.run(run_backend())
                    
                    status.update(label="Complete!", state="complete", expanded=False)
                    
                    # Render Draft Output
                    st.markdown("## The Draft")
                    if draft_res.draft_text:
                        st.markdown(f"<div class='draft-frame'>{draft_res.draft_text.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                    else:
                        st.warning("No draft generated. Signal might have been blocked or no signal was found.")
                    
                    # Render Decision Card
                    st.markdown("## Decision Card")
                    st.markdown(f"<div class='card-container'>{render_decision_card(draft_res, results).replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
                    
                except Exception as e:
                    status.update(label=f"Error: {str(e)}", state="error", expanded=True)
                    st.exception(e)

if __name__ == "__main__":
    main()
