import streamlit as st
import asyncio
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

p, .stMarkdown p, label, .st-emotion-cache-10trblm {
    color: var(--color-midnight-ink) !important;
}

h1 {
    font-size: 64px !important;
    line-height: 1.08 !important;
}

/* Button Overrides */
.stButton > button {
    background-color: var(--color-lime-sprout) !important;
    color: var(--color-midnight-ink) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    transition: transform 0.1s ease;
}

.stButton > button:hover {
    transform: scale(1.02);
}

/* Input Fields */
.stTextInput > div > div > input {
    background-color: #ffffff !important;
    border: 1px solid var(--color-fog) !important;
    border-radius: 8px !important;
    color: var(--color-true-black) !important;
    font-family: 'Inter', sans-serif !important;
}

/* Eyebrow Labels */
.eyebrow {
    font-family: 'Barlow Condensed', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 18px;
    color: var(--color-midnight-ink);
    border-bottom: 2px wavy var(--color-ember-coral);
    display: inline-block;
    margin-bottom: 8px;
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
    <div style="
        background: radial-gradient(circle, #0d542b 0%, #008236 100%);
        margin: -6rem -4rem 3rem -4rem;
        padding: 6rem 4rem;
        text-align: center;
        color: #b9ff78;
        font-family: 'Playfair Display', serif;
    ">
        <h1 style="color: #b9ff78 !important; font-size: 80px; margin-bottom: 1rem;">Project Zara</h1>
        <p style="font-family: 'Inter', sans-serif; color: #fcf7ed; font-size: 20px; max-width: 600px; margin: 0 auto;">
            Automated, grounded, personalized outreach without the hallucination.
        </p>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Zara Outreach", layout="centered")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    render_hero()
    
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
        
        submitted = st.form_submit_button("Run Zara Pipeline")
        
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
            results, draft_res = await run_end_to_end_pipeline(prospect, profile="standard")
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
