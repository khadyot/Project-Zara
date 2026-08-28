"""Presentation layer: stylesheet and hero.

Split out of app.py so the look-and-feel and the app logic can be worked on
independently -- app.py was 814 lines holding both, which made concurrent edits
to styling and to UI behaviour collide in one file.

This module owns how Zara looks. app.py owns what it does.

Design system: SavvyCal, per reference/savvycal_style.md.

WHERE THINGS LIVE
-----------------
Anything Streamlit can express as a theme token lives in .streamlit/config.toml
-- palette, radii, borders, the type ramp, semantic state colours, chart
colours. Streamlit applies those to every widget it renders, including ones no
hand-written selector would reach. This file holds only what the theme API
cannot say: the hero, the page measure, and Zara's own components.

Do not re-declare a colour or a font size here that config.toml already sets.
Two sources of truth for the same value is how the previous build ended up with
three different greens and thirteen different font sizes.

THE TYPE RAMP
-------------
Six steps, and nothing off-ramp. A literal px font-size below is a bug --
hierarchy comes from weight, case, tracking and colour before it comes from
size, which is why the ramp can be this short.
"""
import streamlit as st


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap');

:root{
  /* ── Colours ── verbatim from reference/savvycal_style.md ───────── */
  --forest-stage:#0d542b;
  --lime-sprout:#b9ff78;
  --ember-coral:#f54320;
  --coral-whisper:#ffe3e3;
  --cream-paper:#fcf7ed;
  --true-black:#000000;
  --midnight-ink:#1c1917;
  --stone:#44403b;
  --slate:#292524;
  --ash:#d6d3d1;
  --fog:#e5e7eb;
  --pure-white:#ffffff;
  --moss:#008236;

  /* ── Faces ──────────────────────────────────────────────────────
     Inter carries the entire interface and is loaded by config.toml.
     The display serif appears in exactly one place -- the hero
     wordmark, where it is a logo rather than text. Mono is reserved
     for verbatim machine output (st.text / st.code), where character
     alignment is the point.                                        */
  --font-display:'Instrument Serif',serif;
  --font-mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;

  --track-ui:0.02em;
  --track-label:0.08em;
  --track-body:-0.007em;

  /* ── TYPE RAMP ─────────────────────────────────────────────────
     Six steps, and each one has a RULE for what belongs to it. A ramp
     without rules is just a list of sizes, and things drift back out.

       t-title  26/700   the page. Exactly one per screen.
       t-h2     19/700   a major section OF that page. Siblings all sit
                         here: Sources, Draft, Verifier, Quota headroom,
                         Recent stalls. If two things are peers, they
                         are the same size -- no exceptions.
       t-head   15/700   a division INSIDE a section. Rare on purpose.
       t-body   15/400   every piece of running text, and every control
                         the user reads or types into: form labels,
                         inputs, buttons, alerts, row names, dropdowns.
       t-meta   13/400   secondary readings only: captions, timings,
                         reasons, URLs, the detail column of a row.
       t-label  11/600   uppercase micro-labels: eyebrows, state words,
                         metric captions.

     PRIORITY decides the level, not the widget. An alert is a sentence
     the user reads, so it sits at t-body however much larger Streamlit
     ships it; a button label is read and acted on, so it sits at
     t-body however much smaller Streamlit ships it. Both are pinned
     below, because left alone each Streamlit component picks its own
     size and the page ends up with a dozen of them.

     1rem = 15px = --t-body, set by baseFontSize in config.toml. */
  --t-mark:1.6rem;    --lh-mark:1;
  --t-title:1.733rem; --lh-title:1.2;    /* h1 — page title, once      */
  --t-h2:1.267rem;    --lh-h2:1.3;      /* h2 — major section          */
  --t-head:1rem;      --lh-head:1.4;    /* h3 — subsection (body+bold) */
  --t-body:1rem;      --lh-body:1.55;
  --t-meta:0.867rem;  --lh-meta:1.45;
  --t-label:0.733rem; --lh-label:1.2;

  /* ── 8px grid ───────────────────────────────────────────────────
     Reference base unit. Every margin and pad below is a multiple. */
  --s-1:8px; --s-2:16px; --s-3:24px; --s-4:32px; --s-5:40px; --s-6:48px; --s-8:64px;

  --page-pad:32px;
  --page-max:1200px;
  --card-pad:24px;

  --r-card:8px; --r-pill:9999px;
}

/* ═══ PAGE MEASURE ════════════════════════════════════════════════
   layout="wide" runs body text edge-to-edge; on a wide display that is
   a 200-character measure against the reference's 65-75. The
   --page-max token existed in the previous build and was never
   consumed by anything. */
.stMain .block-container{
  max-width:var(--page-max);
  padding-left:var(--page-pad);
  padding-right:var(--page-pad);
  padding-top:var(--s-2);
  padding-bottom:var(--s-8);
}

/* ═══ PAGE HEADER ═════════════════════════════════════════════════
   Replaces the forest band that used to float in the main column. The
   dark zone is now the sidebar; the main column is the light zone, and
   it opens the way a document opens — an eyebrow saying where you are,
   a title, and one line of orientation. Same three parts on every page,
   so the eye starts in the same place each time. */
.zpage{
  margin:0 0 var(--s-5);
  padding-bottom:var(--s-3);
  border-bottom:1px solid var(--fog);
}
.zpage .zpage-eyebrow{
  font-size:var(--t-label);font-weight:600;
  text-transform:uppercase;letter-spacing:var(--track-label);
  color:var(--slate);display:block;margin-bottom:var(--s-1);
}
.zpage h1,.zpage .zpage-title{
  font-size:var(--t-title);line-height:var(--lh-title);
  font-weight:700;letter-spacing:-0.02em;color:var(--true-black);
  margin:0;
}
.zpage .zpage-sub{
  font-size:var(--t-meta);line-height:var(--lh-meta);
  color:var(--slate);margin-top:6px;
}

/* ═══ TYPOGRAPHY ══════════════════════════════════════════════════
   Sizes and weights come from config.toml headingFontSizes /
   headingFontWeights. Only colour and tracking are set here.
   True Black for headings, Stone for body -- the reference forbids
   pure black body copy on cream. */
h1,h2,h3,h4,h5,h6,
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3{
  color:var(--true-black);
  letter-spacing:var(--track-body);
}
h1{letter-spacing:-0.02em;}
/* Sections need air above them and almost none below — the gap belongs
   between a section and the one before it, not between a heading and
   the content it labels. */
.stMarkdown h2{margin-top:var(--s-5)!important;margin-bottom:var(--s-2)!important;}
.stMarkdown h3{margin-top:var(--s-3)!important;margin-bottom:var(--s-1)!important;}
body,.stApp{letter-spacing:var(--track-body);text-wrap:pretty;}

/* st.caption -- secondary metadata, one step down. */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p{
  font-size:var(--t-meta)!important;
  line-height:var(--lh-meta)!important;
  color:var(--slate)!important;
}

/* ═══ MICRO-LABELS ════════════════════════════════════════════════
   One treatment for every small uppercase label in the app.
   Replaces the previous build's Barlow Condensed eyebrows and their
   coral squiggle underline -- a second face and a decoration that
   both fought the interface at dashboard density. */
.eyebrow,.eyebrow-sm,.candidate-status{
  font-family:inherit;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:var(--track-label);
  line-height:var(--lh-label);
  color:var(--slate);
  display:inline-block;
}
.eyebrow{font-size:var(--t-label);color:var(--midnight-ink);margin:var(--s-3) 0 var(--s-1);}
.eyebrow-sm{font-size:var(--t-label);color:var(--midnight-ink);margin:var(--s-2) 0 var(--s-1);}
.candidate-status{font-size:var(--t-label);}

/* ═══ BUTTONS ═════════════════════════════════════════════════════
   Fill, radius and text colour all come from config.toml primaryColor.
   Only the ghost/secondary treatment and the interaction states are
   said here, because Streamlit has no token for them. */
.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button{
  /* Ships smaller than body text. A button label is read and acted
     on -- body size, same as the paragraph beside it. */
  font-size:var(--t-body)!important;
  font-weight:500;
  letter-spacing:var(--track-ui);
  padding:10px 22px;
  transition:background-color .1s ease,color .1s ease,border-color .1s ease,box-shadow .1s ease;
}
.stButton > button[kind="secondary"],
.stDownloadButton > button{
  background-color:transparent;
  color:var(--midnight-ink);
  border:1.5px solid var(--midnight-ink);
}
.stButton > button[kind="secondary"]:hover,
.stDownloadButton > button:hover{
  background-color:var(--midnight-ink);
  color:var(--cream-paper);
  border-color:var(--midnight-ink);
}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button:hover{
  filter:brightness(1.12);
  box-shadow:0 0 0 4px rgba(13,84,43,.18);
}
.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible,
.stFormSubmitButton > button:focus-visible{
  outline:2px solid var(--midnight-ink);
  outline-offset:2px;
}
.stButton > button:disabled,
.stDownloadButton > button:disabled{
  opacity:.4;filter:none;box-shadow:none;cursor:not-allowed;
}
.stButton > button:disabled:hover{
  background-color:transparent;color:var(--midnight-ink);
}

.stButton > button p,
.stDownloadButton > button p,
.stFormSubmitButton > button p{font-size:var(--t-body)!important;}

/* Form labels, expander summaries and selectbox values are all read at
   the same priority as body copy. Streamlit sizes each independently;
   pinned here so a form, a dropdown and a paragraph agree. */
/* Size applies in both zones; COLOUR must not. Scoping this to the
   main column was the bug -- Stone is near-black and the sidebar is
   forest green. */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label{
  font-size:var(--t-body)!important;
  line-height:var(--lh-body)!important;
}
.stMain [data-testid="stWidgetLabel"] p,
.stMain [data-testid="stWidgetLabel"] label{color:var(--stone)!important;}
[data-testid="stExpander"] summary p{
  font-size:var(--t-body)!important;font-weight:500!important;
}
[data-baseweb="select"] div,
[data-baseweb="popover"] li,
[data-baseweb="menu"] li{font-size:var(--t-body)!important;}

/* ═══ PILL TABS ═══════════════════════════════════════════════════
   Reference's Top Nav Pill Tab: active = lime fill, ink text,
   9999px radius. CSS-only -- no markup change in app.py. */
div[data-baseweb="tab-list"]{border-bottom:none!important;gap:var(--s-1);}
div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"]{display:none!important;}
button[data-baseweb="tab"]{
  border-radius:var(--r-pill)!important;
  background-color:transparent!important;
  color:var(--midnight-ink)!important;
  font-size:var(--t-meta)!important;
  font-weight:500!important;
  letter-spacing:var(--track-ui)!important;
  border:none!important;
  padding:5px 14px!important;
  margin-right:0!important;
}
button[data-baseweb="tab"]:hover{background-color:rgba(214,211,209,.35)!important;}
button[data-baseweb="tab"][aria-selected="true"]{
  background-color:var(--lime-sprout)!important;
  color:var(--midnight-ink)!important;
}
button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p{
  color:inherit!important;font-size:inherit!important;font-weight:inherit!important;
}

/* ═══ CONTAINERS ══════════════════════════════════════════════════ */
[data-testid="stExpander"]{
  background-color:var(--pure-white);
  box-shadow:none!important;
}
[data-testid="stExpander"] summary{background-color:transparent;}
[data-testid="stExpander"] summary:hover{background-color:rgba(229,231,235,.35);}
[data-testid="stExpanderDetails"]{font-size:var(--t-meta);}

/* Ships larger than body text. An alert is a sentence -- body size. */
[data-testid="stAlert"]{
  border-radius:var(--r-card)!important;
  padding:var(--s-2) var(--s-3)!important;
  box-shadow:none!important;
}
[data-testid="stAlert"],
[data-testid="stAlertContainer"],
[data-testid="stAlertContent"],
[data-testid="stAlertTitle"],
[data-testid="stAlert"] *:not(code):not(pre):not(svg):not(path){
  font-size:var(--t-body)!important;
  line-height:var(--lh-body)!important;
}
[data-testid="stAlertTitle"]{font-weight:700!important;}

[data-testid="stMetric"]{
  background-color:var(--pure-white);
  border:1px solid var(--fog);
  border-radius:var(--r-card);
  padding:var(--s-2);
}
[data-testid="stMetricLabel"] p{
  font-size:var(--t-label)!important;
  font-weight:600!important;
  text-transform:uppercase;
  letter-spacing:var(--track-label)!important;
  color:var(--slate)!important;
}

/* ═══ VERBATIM MACHINE OUTPUT ═════════════════════════════════════
   st.text() renders the raw system / prompt / response bodies. This is
   the one context in the app that earns a monospace face: it is a
   transcript, and character alignment is the point. Everything else --
   IDs, timings, scores, source names -- is Inter with tabular figures. */
[data-testid="stText"],
[data-testid="stText"] pre,
div[data-testid="stText"] > pre{
  font-family:var(--font-mono)!important;
  font-size:var(--t-meta)!important;
  line-height:1.65!important;
  color:var(--slate)!important;
  background-color:var(--cream-paper)!important;
  border:1px solid var(--fog)!important;
  border-radius:var(--r-card)!important;
  padding:var(--s-2)!important;
  white-space:pre-wrap!important;
  word-break:break-word;
  max-height:260px;overflow:auto;
}

/* ═══ THE ROW ═════════════════════════════════════════════════════
   Four places in this app show the same shape of information —
   a marker, a name, a state, a detail, and a number:

       sources          dot   ExaNews    ok       2 cards      1.9s
       quota headroom   dot   groq TPD   ok       resets 646m  0/200k
       stalls           dot   drafter    waited   2026-08-25   10.6s
       stages           dot   drafter    fixture  812 in       297 out

   They were four different ad-hoc layouts — ragged markdown, a
   full-width progress bar that vanished at 0%, and a pipe-separated
   caption. One grid now serves all four, so the columns line up down
   the page and the vocabulary is learned once.

   Numbers are right-aligned with tabular figures so digits stack. */
.zrow{
  display:grid;
  grid-template-columns:11px minmax(0,18rem) 7.5rem minmax(0,1fr) auto;
  align-items:baseline;
  gap:var(--s-2);
  padding:7px 0;
  border-bottom:1px solid var(--fog);
  font-size:var(--t-meta);
  line-height:var(--lh-meta);
}
.zrow:last-of-type{border-bottom:none;}
.zrow .zr-name{
  font-size:var(--t-body);font-weight:500;color:var(--midnight-ink);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.zrow .zr-state{
  font-size:var(--t-label);font-weight:600;
  text-transform:uppercase;letter-spacing:var(--track-label);
  color:var(--slate);
}
.zrow .zr-detail{color:var(--stone);overflow:hidden;text-overflow:ellipsis;}
.zrow .zr-value{
  color:var(--slate);font-variant-numeric:tabular-nums;
  text-align:right;white-space:nowrap;
}
.zrow.is-muted{opacity:.62;}
.zrow.is-alert .zr-state{color:var(--midnight-ink);}

/* A quota row carries a fill level. A 2px rule under the row reads at a
   glance and costs no vertical space — unlike st.progress, which
   reserved a full bar that was invisible at 0% and left ~50px holes
   between every reading. */
.zrow.has-fill{border-bottom:none;padding-bottom:2px;}
.zfill{
  height:2px;background:var(--fog);
  margin:0 0 7px;border-bottom:1px solid transparent;
}
.zfill > span{display:block;height:100%;background:var(--forest-stage);}
.zfill.is-alert > span{background:var(--ember-coral);}

/* ═══ CHIP ════════════════════════════════════════════════════════
   Claim strength used to render as a '●' glyph plus one of five
   hardcoded hex colours, two of which were not in the palette at all.
   It is a verdict, not a source state, so it gets its own shape -- but
   the same three-level language the rest of the app uses: solid = we
   have it, outline = partial, coral stroke = weak or absent. */
.zchip{
  display:inline-block;
  font-size:var(--t-label);font-weight:600;
  text-transform:uppercase;letter-spacing:var(--track-label);
  padding:4px 11px;border-radius:var(--r-pill);
  border:1.5px solid var(--ash);color:var(--slate);
  background:transparent;
}
.zchip.is-strong{background:var(--midnight-ink);border-color:var(--midnight-ink);color:var(--cream-paper);}
.zchip.is-medium{border-color:var(--midnight-ink);color:var(--midnight-ink);}
.zchip.is-weak{border-color:var(--ember-coral);color:var(--midnight-ink);}

/* ═══ INLINE CODE ═════════════════════════════════════════════════
   app.py wraps IDs, timestamps, stage names and key names in markdown
   backticks. Those mean "this is a literal value", not "this is source
   code" -- but they render in the mono face at a different size,
   scattered mid-sentence, which is the loudest source of the interface
   looking like three different products. They keep a tint and tabular
   figures so they still read as values, and take the interface's own
   face. Block code (st.code) is deliberately NOT included: that really
   is source, and stays monospace. */
.stMarkdown :not(pre) > code,
[data-testid="stCaptionContainer"] code{
  font-family:inherit!important;
  font-size:0.933em!important;
  font-weight:500;
  font-variant-numeric:tabular-nums;
  color:var(--slate)!important;
  background-color:rgba(214,211,209,.30)!important;
  padding:1px 5px;
  border-radius:4px;
  white-space:nowrap;
}

/* ═══ ZARA COMPONENTS ═════════════════════════════════════════════ */

/* Source / verification status. SavvyCal has no status vocabulary, so
   this is designed fresh against Compass 7: `failed` and `skipped` must
   never be confusable -- one is a fault in our plumbing, the other a
   deliberate choice. Shape carries the meaning; colour only reinforces
   it, so the distinction survives greyscale and colour-blindness.
   Note the previous build used Lime for `ok` and a coral FILL for
   `failed`: the first overloaded the one interactive colour, the second
   broke the reference's hardest rule (coral is stroke, never fill). */
.status-dot{
  display:inline-block;width:11px;height:11px;
  border-radius:var(--r-pill);
  margin-right:var(--s-1);
  vertical-align:baseline;
  box-sizing:border-box;
}
.status-ok      { background-color:var(--midnight-ink); }
.status-empty   { background-color:transparent;border:1.5px solid var(--ash); }
.status-skipped { background-color:transparent;border:1.5px dashed var(--ash);opacity:.6; }
.status-failed  { background-color:transparent;border:3px solid var(--ember-coral); }
.status-running { background-color:var(--lime-sprout);border:1.5px solid var(--moss);
                  animation:zara-pulse 1.4s ease-in-out infinite; }
@keyframes zara-pulse{0%,100%{opacity:1}50%{opacity:.45}}
@media (prefers-reduced-motion:reduce){.status-running{animation:none}}

/* The draft. Reference's Product Screenshot Frame -- 2px coral stroke,
   24px radius, warm coral-tinted shadow. The one shadow the system
   permits, and the draft is the product artifact, so this is its home. */
.draft-frame{
  border:2px solid var(--ember-coral);
  border-radius:24px;
  padding:var(--s-4);
  background-color:var(--pure-white);
  box-shadow:0 24px 48px rgba(245,67,32,.15);
  margin:var(--s-3) 0 var(--s-4);
  font-size:var(--t-body);
  line-height:1.7;
  color:var(--midnight-ink);
  max-width:62ch;
}

.score-badge{
  border:1.5px solid var(--ember-coral);
  border-radius:var(--r-pill);
  font-weight:700;
  font-size:var(--t-label);
  letter-spacing:var(--track-ui);
  color:var(--midnight-ink);
  padding:3px 10px;
  display:inline-block;
  font-variant-numeric:tabular-nums;
}

.candidate-claim-summary{color:var(--midnight-ink);font-size:var(--t-body);}
.candidate-claim-summary.excluded{color:var(--stone);}
.candidate-source-url{
  color:var(--slate);font-size:var(--t-meta);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.candidate-snippet{
  font-size:var(--t-meta);
  line-height:var(--lh-meta);
  border:1px solid var(--fog);
  border-radius:var(--r-card);
  background-color:var(--pure-white);
  padding:var(--s-2);
  margin-top:var(--s-1);
}
.candidate-snippet.excluded{color:var(--stone);}

.hook-row{
  background-color:var(--pure-white);
  border:1px solid var(--fog);
  border-radius:var(--r-card);
  padding:var(--s-2);
  margin-bottom:var(--s-1);
  font-size:var(--t-body);
}
.hook-caption{
  font-size:var(--t-meta);
  line-height:var(--lh-meta);
  color:var(--slate);
  margin-top:var(--s-1);
  padding-top:var(--s-1);
  border-top:1px solid var(--fog);
}

.model-call-header{font-size:var(--t-body);font-variant-numeric:tabular-nums;}

/* ═══ RESPONSIVE ══════════════════════════════════════════════════ */
@media (max-width:820px){
  :root{--page-pad:16px;}
  #zara-hero{padding:var(--s-3) var(--page-pad);}
}

/* ═══ SIDEBAR — the Forest Stage zone ═════════════════════════════
   Surface, text and border colours come from [theme.sidebar] in
   config.toml. What is said here is only what the theme has no token
   for: the brand mark, and Lime used as a text accent. Lime cannot be
   a widget fill in the sidebar for the same reason as everywhere else
   — Streamlit paints white text on primaryColor — but as ink on
   forest it is the brand's most recognisable pairing. */
section[data-testid="stSidebar"] .zbrand{
  font-family:var(--font-display);
  font-size:var(--t-mark);line-height:var(--lh-mark);
  color:var(--cream-paper);
  letter-spacing:0.01em;
  display:block;
  margin:0 0 var(--s-1);
}
section[data-testid="stSidebar"] .zbrand em{
  color:var(--lime-sprout);font-style:italic;
}
section[data-testid="stSidebar"] .zbrand-sub{
  font-size:var(--t-label);font-weight:600;
  text-transform:uppercase;letter-spacing:var(--track-label);
  color:rgba(252,247,237,.55);
  display:block;margin-bottom:var(--s-3);
}
section[data-testid="stSidebar"] .eyebrow,
section[data-testid="stSidebar"] .eyebrow-sm{
  color:var(--lime-sprout);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{color:var(--cream-paper)!important;}
section[data-testid="stSidebar"] hr{border-color:rgba(252,247,237,.16);}
section[data-testid="stSidebar"] .zr-name{color:var(--cream-paper);}
section[data-testid="stSidebar"] .zrow{border-bottom-color:rgba(252,247,237,.14);}
section[data-testid="stSidebar"] .zfill{background:rgba(252,247,237,.20);}
section[data-testid="stSidebar"] .zfill > span{background:var(--lime-sprout);}
/* Perplexity-style inline citation: a small raised number after the sentence it
   supports, linking straight to the source so a claim can be checked in one click
   and the reader can come back. */
.zcline{margin:0 0 .5rem 0;line-height:1.6;}
.zcite{
  display:inline-block;margin-left:3px;padding:0 5px;
  font-size:.68em;font-weight:600;vertical-align:super;line-height:1.5;
  color:var(--forest-deep,#0d542b);background:var(--sage-mist,#e7efe8);
  border:1px solid var(--fog,#e5e7eb);border-radius:2px;text-decoration:none;
}
.zcite:hover{background:var(--forest-deep,#0d542b);color:#fff;}
/* A quiet line often carries a URL or an error string, neither of which has a
   space to break on. Without this they push the column wider than the page. */
.zquiet{overflow-wrap:anywhere;word-break:break-word;}
/* Emphasis numbers in the dark zone: lime as ink. */
section[data-testid="stSidebar"] .zaccent{color:var(--lime-sprout);font-weight:600;}
section[data-testid="stSidebar"] .zquiet{color:rgba(252,247,237,.60);}
section[data-testid="stSidebar"] .stMarkdown :not(pre) > code{
  color:var(--lime-sprout)!important;
  background-color:rgba(252,247,237,.10)!important;
}
/* Anything that carries an explicit dark ink in the light zone has to
   be restated here, or it renders near-black on forest. */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] li,
section[data-testid="stSidebar"] .stMarkdown{
  color:var(--cream-paper)!important;
}

/* Captions inherit --slate, which is near-black and vanishes against
   forest. In the dark zone they are cream at low opacity. */
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{
  color:rgba(252,247,237,.62)!important;
}

/* The row grid is sized for a 1200px main column. In a 264px sidebar
   the name column collapsed and ellipsised "~33 runs left" to "~...".
   The sidebar gets a two-column form of the same component: name and
   number, nothing else. */
section[data-testid="stSidebar"] .zrow{
  grid-template-columns:11px minmax(0,1fr) auto;
  gap:var(--s-1);
}
section[data-testid="stSidebar"] .zrow .zr-state,
section[data-testid="stSidebar"] .zrow .zr-detail{display:none;}
section[data-testid="stSidebar"] .zr-value{
  color:var(--lime-sprout);font-weight:600;
}

/* Streamlit gives sidebar widgets 13.125px -- close to t-meta (13.005)
   without being it. Pinned, so the rail is deliberately one step down
   rather than accidentally almost one step down. .zr-name/.zr-value are
   spans and stay at their own level: the runs-left figure is the one
   thing in here that outranks the controls. */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] button p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{
  font-size:var(--t-meta)!important;
}

/* Inputs on forest: the theme sets the fill, this softens the edge. */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea{color:var(--cream-paper)!important;}
</style>
"""


import html as _html


def render_brand():
    """The wordmark, at the top of the Forest Stage zone."""
    st.markdown(
        "<span class='zbrand'>Zara<em>.</em></span>"
        "<span class='zbrand-sub'>Outreach, drafted for review</span>",
        unsafe_allow_html=True,
    )


def render_page_header(eyebrow, title, sub=None):
    """Every page opens the same way: where you are, what this is, why.

    Replaces the forest band that used to float in the main column and
    said the same marketing line on every screen.
    """
    parts = [
        "<div class='zpage'>",
        f"<span class='zpage-eyebrow'>{_html.escape(eyebrow)}</span>",
        f"<span class='zpage-title'>{_html.escape(title)}</span>",
    ]
    if sub:
        parts.append(f"<div class='zpage-sub'>{sub}</div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def zrow(name, state=None, detail=None, value=None, status=None,
         fill=None, muted=False, alert=False, escape=True):
    """One row of the app's only tabular vocabulary.

    Sources, quota headroom, stalls and stages are all this shape:
    a status marker, a name, a state word, a detail, and a number. They
    used to be four different ad-hoc layouts; this is the one.

    `status` is a SourceResult state -- ok / empty / failed / skipped /
    running -- and draws the marker. `fill` (0..1) draws a 2px level rule
    under the row for quota-style readings.
    """
    e = (lambda x: _html.escape(str(x))) if escape else (lambda x: str(x))
    cls = "zrow"
    if muted:        cls += " is-muted"
    if alert:        cls += " is-alert"
    if fill is not None: cls += " has-fill"

    dot = f"<span class='status-dot status-{status}'></span>" if status else "<span></span>"
    out = (
        f"<div class='{cls}'>{dot}"
        f"<span class='zr-name'>{e(name)}</span>"
        f"<span class='zr-state'>{e(str(state).replace('_', ' ')) if state else ''}</span>"
        f"<span class='zr-detail'>{e(detail) if detail else ''}</span>"
        f"<span class='zr-value'>{e(value) if value else ''}</span>"
        f"</div>"
    )
    if fill is not None:
        pct = max(0.0, min(float(fill), 1.0)) * 100
        bar = "zfill is-alert" if alert else "zfill"
        out += f"<div class='{bar}'><span style='width:{pct:.1f}%'></span></div>"
    st.markdown(out, unsafe_allow_html=True)
