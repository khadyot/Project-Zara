## PLAN — Phase 3: Run History density treatment

### 1. `zara/ui/styles.py` Changes (CSS Additions)
I will append the following CSS classes to the end of the file to style the new elements according to the Phase 3 specifications:

```css
/* Phase 3: Run History Density Treatment */
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

.candidate-card-body {
    font-size: 14px;
}

.candidate-source-url {
    color: var(--color-slate);
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
```

### 2. `app.py` Changes (Markup / Class Wrappers)

**A. Candidate `st.expander` rows (approx lines 97-110)**
Change the expander label to include the HTML spans, and wrap the interior in `.candidate-card-body`. Conditionally render the snippet and style the excluded claim.
```python
        mark = "WINNER" if c["is_winner"] else ("EXCLUDED" if c["excluded"] else "ELIGIBLE")
        score = f"{c['score'] or 0:.2f}"
        
        # Note: Injecting HTML into st.expander label. If Streamlit escapes this, 
        # it will render literally, but applying per instructions.
        label = (f"<span class='score-badge'>{score}</span> "
                 f"<span class='candidate-status'>{mark}</span> "
                 f"<span class='candidate-claim-summary " + ("excluded" if c["excluded"] else "") + f"'>"
                 f"{c['source']} · {c['proximity']} — {(c['claim'] or '')[:80]}</span>")
        
        with st.expander(label):
            st.markdown("<div class='candidate-card-body'>", unsafe_allow_html=True)
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
            st.caption(f"<span class='candidate-source-url'>{c['source_url'] or ''}</span>", unsafe_allow_html=True)
            if not c["excluded"]:
                st.markdown(f"<div class='candidate-snippet'>{c['snippet'] or ''}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
```

**B. Hook Options (approx lines 115-117)**
Replace the standard `st.write` and `st.caption` with the new HTML `.hook-row` structure via `st.markdown(..., unsafe_allow_html=True)`.
```python
    for h in hooks:
        st.markdown(f"""
        <div class='hook-row'>
            <div><span class='score-badge'>{h['strength']:.2f}</span> {h['hook_text']}</div>
            <div class='hook-caption'>why: {h['rationale']} &middot; bridge: {h['bridge']}</div>
        </div>
        """, unsafe_allow_html=True)
```

**C. Model-call Expanders (approx lines 127-138)**
Inject `.model-call-header` into the expander label, and replace the `st.caption("SYSTEM")` labels with `.eyebrow-sm` divs.
```python
    for c in conn.execute("SELECT * FROM llm_calls WHERE run_id=? ORDER BY seq", (rid,)):
        label = (f"<span class='model-call-header'>{c['stage']} · {c['provider']} · "
                 f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
                 f"{c['elapsed_ms']/1000:.1f}s</span>")
        with st.expander(label):
            if c["system_text"]:
                st.markdown("<div class='eyebrow-sm'>SYSTEM</div>", unsafe_allow_html=True)
                st.text(c["system_text"])
            if c["prompt_text"]:
                st.markdown("<div class='eyebrow-sm'>PROMPT — how this stage was instructed</div>", unsafe_allow_html=True)
                st.text(c["prompt_text"])
            if c["response_text"]:
                st.markdown("<div class='eyebrow-sm'>RESPONSE</div>", unsafe_allow_html=True)
                st.text(c["response_text"][:4000])
```

Will STOP here and wait for REVIEW in `OC_to_AG_03.md`.

## PLAN (revised)
1. Kept `st.expander` labels as plain text strings.
2. Injected the styled header as the FIRST element using `st.markdown(..., unsafe_allow_html=True)` inside the expander context for Candidate cards and Model Calls.
3. Dropped the `candidate-card-body` wrapper completely, and instead added `div[data-testid="stExpanderDetails"] { font-size: 14px; }` to `zara/ui/styles.py`.
4. Swapped `st.caption` lines that needed styling for `st.markdown(..., unsafe_allow_html=True)`.
5. Added `import html` in loops and applied `html.escape()` on all external strings (claims, rationales, URLs, provider tags, etc) before injecting them into HTML f-strings.

Proceeding directly to EXECUTE.
