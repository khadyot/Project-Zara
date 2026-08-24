"""Presentation layer: stylesheet and hero.

Split out of app.py so the look-and-feel and the app logic can be worked on
independently -- app.py was 814 lines holding both, which made concurrent edits
to styling and to UI behaviour collide in one file.

This module owns how Zara looks. app.py owns what it does.
"""
import streamlit as st


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&family=Inter:wght@400;700&family=Barlow+Condensed:wght@400;700&display=swap');

/* Base Variables */
:root {
  /* Colors */
  --color-forest-stage: #0d542b;
  --color-lime-sprout: #b9ff78;
  --color-ember-coral: #f54320;
  --color-coral-whisper: #ffe3e3;
  --color-cream-paper: #fcf7ed;
  --color-true-black: #000000;
  --color-midnight-ink: #1c1917;
  --color-stone: #44403b;
  --color-slate: #292524;
  --color-ash: #d6d3d1;
  --color-fog: #e5e7eb;
  --color-pure-white: #ffffff;
  --color-moss: #008236;

  /* Typography — Font Families */
  --font-gt-alpina-condensed: 'GT Alpina Condensed', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-gt-america-standard: 'GT America Standard', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-gt-america-extended: 'GT America Extended', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-gt-america-condensed: 'GT America Condensed', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-intervariable: 'InterVariable', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Typography — Scale */
  --text-caption: 10px;
  --leading-caption: 1;
  --text-body-sm: 14px;
  --leading-body-sm: 1.43;
  --text-body: 16px;
  --leading-body: 1.5;
  --tracking-body: -0.007px;
  --text-subheading: 20px;
  --leading-subheading: 1.5;
  --tracking-subheading: -0.14px;
  --text-heading-sm: 24px;
  --leading-heading-sm: 1.33;
  --tracking-heading-sm: -0.17px;
  --text-heading: 30px;
  --leading-heading: 1.38;
  --tracking-heading: -0.21px;
  --text-heading-lg: 38px;
  --leading-heading-lg: 1.38;
  --tracking-heading-lg: -0.95px;
  --text-display: 96px;
  --leading-display: 1.08;

  /* Typography — Weights */
  --font-weight-regular: 400;
  --font-weight-bold: 700;

  /* Spacing */
  --spacing-unit: 8px;
  --spacing-8: 8px;
  --spacing-16: 16px;
  --spacing-24: 24px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-64: 64px;
  --spacing-104: 104px;

  /* Layout */
  --page-max-width: 1200px;
  --section-gap: 64px;
  --card-padding: 24px;
  --element-gap: 16px;

  /* Border Radius */
  --radius-lg: 8px;
  --radius-3xl: 24px;

  /* Named Radii */
  --radius-cards: 8px;
  --radius-pills: 9999px;
  --radius-buttons: 8px;
  --radius-productframes: 24px;

  /* Surfaces */
  --surface-forest-stage: #0d542b;
  --surface-cream-paper: #fcf7ed;
  --surface-pure-white-card: #ffffff;
  --surface-coral-whisper: #ffe3e3;
}

/* Page Background */
.stApp {
    background-color: var(--color-cream-paper);
    color: var(--color-stone);
    font-family: 'Inter', sans-serif;
    font-feature-settings: 'cv11';
    letter-spacing: -0.007em;
}

/* Typography Overrides */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Playfair Display', serif !important;
    color: var(--color-true-black) !important;
    letter-spacing: 0px !important;
}

#zara-hero {
    background: radial-gradient(circle, #0d542b 0%, #008236 100%);
    width: 100%;
    margin-top: -6rem;
    margin-bottom: 3rem;
    padding: 6rem 1rem;
    text-align: center;
}

#zara-hero h1 {
    font-family: 'Playfair Display', serif !important;
    font-weight: 700 !important;
    font-size: 96px !important;
    line-height: 1.08 !important;
    color: var(--color-lime-sprout) !important;
    margin-bottom: 1rem !important;
}

p, .stMarkdown p, label {
    color: var(--color-stone) !important;
}

#zara-hero p {
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
    font-size: 18px !important;
    color: var(--color-cream-paper) !important;
    max-width: 600px !important;
    margin: 0 auto !important;
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
    font-weight: 400 !important;
    padding: 12px 24px !important;
    border-radius: var(--radius-lg) !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: var(--color-lime-sprout) !important;
    color: var(--color-midnight-ink) !important;
    transform: scale(1.02) !important;
    box-shadow: 0 0 0 4px rgba(185,255,120,0.25) !important;
}

/* Input Fields */
.stTextInput > div > div > input, .stTextArea textarea, .stSelectbox > div > div {
    background-color: var(--color-pure-white) !important;
    border: 1px solid var(--color-fog) !important;
    border-radius: var(--radius-lg) !important;
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
    position: relative;
    text-decoration: none;
    display: inline-block;
    margin-bottom: 16px;
    margin-top: 16px;
}
.eyebrow::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: -6px;
    width: 60%;
    height: 3px;
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 3"><path d="M 0 1.5 Q 3 0 6 1.5 T 12 1.5" stroke="%23f54320" stroke-width="2" fill="none"/></svg>');
    background-repeat: repeat-x;
    background-size: 12px 3px;
}

/* Small eyebrow variant — sidebar labels overridden to 14px.
   Shorter squiggle (50%, 2px) so it doesn't crowd a short label. */
.eyebrow-sm {
    font-family: 'Barlow Condensed', sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 14px;
    color: var(--color-midnight-ink);
    position: relative;
    text-decoration: none;
    display: inline-block;
    margin-bottom: 2px;
}
.eyebrow-sm::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: -4px;
    width: 50%;
    height: 2px;
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 2"><path d="M 0 1 Q 3 0 6 1 T 12 1" stroke="%23f54320" stroke-width="1.5" fill="none"/></svg>');
    background-repeat: repeat-x;
    background-size: 10px 2px;
}

/* Sidebar View toggle — horizontal radio restyled as Top Nav Pill Tabs
   (active = lime fill, ink text, 9999px radius). CSS-only, no markup change. */
section[data-testid="stSidebar"] div[role="radiogroup"] {
    gap: 8px;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] {
    border-radius: var(--radius-pills) !important;
    padding: 4px 12px !important;
    background-color: transparent !important;
    border: none !important;
    cursor: pointer;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
    background-color: rgba(229, 231, 235, 0.4) !important;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
    /* hide the radio circle — the pill fill is the selected state */
    display: none !important;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:last-child p {
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    letter-spacing: 0.02em !important;
    font-weight: 400 !important;
    color: var(--color-true-black) !important;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
    background-color: var(--color-lime-sprout) !important;
}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) > div:last-child p {
    color: var(--color-midnight-ink) !important;
}

/* Alerts / Notifications */
div[data-testid="stAlert"] {
    background-color: var(--color-pure-white) !important;
    border: 1px solid var(--color-fog) !important;
    border-radius: var(--radius-lg) !important;
    padding: 24px !important;
    color: var(--color-stone) !important;
    box-shadow: none !important;
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
    border-radius: var(--radius-pills) !important;
    background-color: transparent !important;
    color: var(--color-true-black) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
    font-size: 14px !important;
    letter-spacing: 0.02em !important;
    border: none !important;
    padding: 4px 12px !important;
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
    background-color: var(--color-pure-white) !important;
    border: 1px solid var(--color-fog) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: none !important;
}
div[data-testid="stExpander"] summary {
    background-color: transparent !important;
}
div[data-testid="stExpander"] summary:hover {
    background-color: rgba(229, 231, 235, 0.3) !important;
}

/* Custom Containers (Cards) */
.card-container {
    background-color: var(--color-pure-white);
    border: 1px solid var(--color-fog);
    border-radius: var(--radius-lg);
    padding: var(--spacing-24);
    margin-bottom: var(--spacing-24);
    box-shadow: none;
}

/* Metrics (Run History stat cards) */
div[data-testid="stMetric"] {
    background-color: var(--color-pure-white);
    border: 1px solid var(--color-fog);
    border-radius: var(--radius-lg);
    padding: 16px;
}
div[data-testid="stMetricLabel"] p {
    font-family: 'Barlow Condensed', sans-serif !important;
    text-transform: uppercase;
    font-size: 12px !important;
    letter-spacing: 0.05em !important;
    color: var(--color-stone) !important;
}
div[data-testid="stMetricValue"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 24px !important;
    color: var(--color-midnight-ink) !important;
}

/* Status Dots (source/verification status markers — emoji-free) */
.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: var(--radius-pills);
    margin-right: 8px;
    vertical-align: middle;
}
.status-ok { background-color: #b9ff78; }
.status-empty { background-color: #d6d3d1; }
.status-failed { background-color: #f54320; }
.status-skipped { background-color: transparent; border: 2px solid #d6d3d1; box-sizing: border-box; }
.status-running { background-color: #008236; }

/* Product Screenshot Frame (for Drafts) */
.draft-frame {
    border: 2px solid var(--color-ember-coral);
    border-radius: var(--radius-3xl);
    padding: 32px;
    background-color: var(--color-pure-white);
    box-shadow: 0 24px 48px rgba(245, 67, 32, 0.15);
    margin-top: var(--spacing-24);
    margin-bottom: var(--spacing-32);
}
</style>
"""


def render_hero():
    # Streamlit hack: inject a full-width HTML hero at the top
    hero_html = """
    <div id="zara-hero">
        <h1>Project Zara</h1>
        <p>
            Automated, grounded, personalized outreach without the hallucination.
        </p>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)



/* Phase 3: Run History Density Treatment */
div[data-testid="stExpanderDetails"] { font-size: 14px; }

.score-badge {
    border: 1.5px solid var(--color-ember-coral);
    border-radius: var(--radius-pills);
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 12px;
    color: var(--color-midnight-ink);
    padding: 2px 8px;
    display: inline-block;
}

.candidate-status {
    font-family: 'Barlow Condensed', sans-serif;
    text-transform: uppercase;
    font-size: 12px;
}

.candidate-claim-summary {
    color: var(--color-midnight-ink);
    font-size: 14px;
}
.candidate-claim-summary.excluded {
    color: var(--color-stone);
}

.candidate-source-url {
    color: var(--color-slate);
    font-size: 14px;
}

.candidate-snippet {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    border: 1px solid var(--color-fog);
    border-radius: var(--radius-lg);
    background-color: var(--color-pure-white);
    padding: 12px;
    margin-top: 8px;
}

.hook-row {
    background-color: var(--color-pure-white);
    border: 1px solid var(--color-fog);
    border-radius: var(--radius-lg);
    padding: 16px;
    margin-bottom: 12px;
}

.hook-caption {
    font-size: 12px;
    color: var(--color-slate);
    margin-top: 4px;
}

.model-call-header {
    font-size: 14px;
}
