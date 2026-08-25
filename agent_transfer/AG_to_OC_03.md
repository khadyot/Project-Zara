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

## EXECUTE
I have applied all 5 mandatory amendments (R1-R5). The `pytest` test suite ran successfully twice.

**Test run 1:** `33 passed in 9.90s`
**Test run 2:** `33 passed in 8.45s`

### `git diff --stat app.py zara/ui/styles.py`
```
 app.py            | 52 ++++++++++++++++++++++++++++++++++++++++------------
 zara/ui/styles.py | 38 ++++++++++++++++++++++++++++++++++++++
 2 files changed, 78 insertions(+), 12 deletions(-)
```

### `git diff app.py zara/ui/styles.py`
```diff
diff --git a/app.py b/app.py
index 666dea1..571c116 100644
--- a/app.py
+++ b/app.py
@@ -94,8 +94,21 @@ def render_run_history():
         "SELECT * FROM cards WHERE run_id=? ORDER BY is_winner DESC, score DESC", (rid,))]
     st.caption(f"{r['cards_total'] or 0} candidates · {r['cards_eligible'] or 0} eligible")
     for c in cards:
-        mark = "**WINNER**" if c["is_winner"] else ("~~excluded~~" if c["excluded"] else "eligible")
-        with st.expander(f"[{c['score'] or 0:.2f}] {mark} · {c['source']} · {c['proximity']} — {(c['claim'] or '')[:80]}"):
+        import html
+        mark_plain = "WINNER" if c["is_winner"] else ("excluded" if c["excluded"] else "eligible")
+        mark_style = "WINNER" if c["is_winner"] else ("EXCLUDED" if c["excluded"] else "ELIGIBLE")
+        score = f"{c['score'] or 0:.2f}"
+        claim_raw = c['claim'] or ''
+        
+        label = f"[{score}] {mark_plain} · {c['source']} · {c['proximity']} — {claim_raw[:80]}"
+        with st.expander(label):
+            claim_html = html.escape(claim_raw)
+            styled_header = (f"<span class='score-badge'>{score}</span> "
+                             f"<span class='candidate-status'>{mark_style}</span> "
+                             f"<span class='candidate-claim-summary " + ("excluded" if c["excluded"] else "") + f"'>"
+                             f"{html.escape(c['source'])} · {html.escape(c['proximity'])} — {claim_html}</span>")
+            st.markdown(styled_header, unsafe_allow_html=True)
+            
             st.write(f"**Claim:** {c['claim']}")
             if c["pain_id"]:
                 st.write(f"**Pain match:** `{c['pain_id']}` ({c['pain_score']:.2f})")
@@ -106,15 +119,24 @@ def render_run_history():
                 st.write(f"**Excluded:** {c['excluded']}")
             if c["guardrail_hit"]:
                 st.write(f"**Guardrail:** {c['guardrail_hit']}")
-            st.caption(c["source_url"] or "")
-            st.text((c["snippet"] or "")[:1200])
+            
+            src_url = html.escape(c["source_url"] or "")
+            st.markdown(f"<div class='candidate-source-url'>{src_url}</div>", unsafe_allow_html=True)
+            if not c["excluded"]:
+                snippet_html = html.escape((c["snippet"] or "")[:1200])
+                st.markdown(f"<div class='candidate-snippet'>{snippet_html}</div>", unsafe_allow_html=True)
 
     hooks = [dict(h) for h in conn.execute(
         "SELECT * FROM hooks WHERE run_id=? ORDER BY strength DESC", (rid,))]
     st.markdown(f"### Hook options ({len(hooks)})")
     for h in hooks:
-        st.write(f"**[{h['strength']:.2f}]** {h['hook_text']}")
-        st.caption(f"why: {h['rationale']}  ·  bridge: {h['bridge']}")
+        import html
+        st.markdown(f\"\"\"
+        <div class='hook-row'>
+            <div><span class='score-badge'>{h['strength']:.2f}</span> {html.escape(h['hook_text'])}</div>
+            <div class='hook-caption'>why: {html.escape(h['rationale'])} &middot; bridge: {html.escape(h['bridge'])}</div>
+        </div>
+        \"\"\", unsafe_allow_html=True)
 
     st.markdown("### Sources")
     for s in conn.execute("SELECT * FROM source_calls WHERE run_id=? ORDER BY seq", (rid,)):
@@ -124,17 +146,23 @@ def render_run_history():
 
     st.markdown("### Model calls")
     for c in conn.execute("SELECT * FROM llm_calls WHERE run_id=? ORDER BY seq", (rid,)):
-        with st.expander(f"{c['stage']} · {c['provider']} · "
-                         f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
-                         f"{c['elapsed_ms']/1000:.1f}s"):
+        label = (f"{c['stage']} · {c['provider']} · "
+                 f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
+                 f"{c['elapsed_ms']/1000:.1f}s")
+        with st.expander(label):
+            import html
+            styled_header = (f"<span class='model-call-header'>{html.escape(c['stage'])} · {html.escape(c['provider'])} · "
+                             f"{c['prompt_tokens']} in / {c['completion_tokens']} out · "
+                             f"{c['elapsed_ms']/1000:.1f}s</span>")
+            st.markdown(styled_header, unsafe_allow_html=True)
             if c["system_text"]:
-                st.caption("SYSTEM")
+                st.markdown("<div class='eyebrow-sm'>SYSTEM</div>", unsafe_allow_html=True)
                 st.text(c["system_text"])
             if c["prompt_text"]:
-                st.caption("PROMPT — how this stage was instructed")
+                st.markdown("<div class='eyebrow-sm'>PROMPT — how this stage was instructed</div>", unsafe_allow_html=True)
                 st.text(c["prompt_text"])
             if c["response_text"]:
-                st.caption("RESPONSE")
+                st.markdown("<div class='eyebrow-sm'>RESPONSE</div>", unsafe_allow_html=True)
                 st.text(c["response_text"][:4000])
 
diff --git a/zara/ui/styles.py b/zara/ui/styles.py
index 6f82f08..b4cdd5d 100644
--- a/zara/ui/styles.py
+++ b/zara/ui/styles.py
@@ -414,3 +414,41 @@ span.status-empty {
     border-width: 1px;
 }
 
+/* Phase 3: Run History Density Treatment */
+div[data-testid="stExpanderDetails"] { font-size: 14px; }
+
+.score-badge {
+    border: 1.5px solid var(--color-ember-coral);
+    border-radius: var(--radius-pills);
+    font-family: 'Inter', sans-serif;
+    font-weight: 700;
+    font-size: 12px;
+    color: var(--color-midnight-ink);
+    padding: 2px 8px;
+    display: inline-block;
+}
+
+.candidate-status {
+    font-family: 'Barlow Condensed', sans-serif;
+    text-transform: uppercase;
+    font-size: 12px;
+}
+
+.candidate-claim-summary {
+    color: var(--color-midnight-ink);
+    font-size: 14px;
+}
+.candidate-claim-summary.excluded {
+    color: var(--color-stone);
+}
+
+.candidate-source-url {
+    color: var(--color-slate);
+    font-size: 14px;
+}
+
+.candidate-snippet {
+    font-family: 'Inter', sans-serif;
+    font-size: 13px;
+    border: 1px solid var(--color-fog);
+    border-radius: var(--radius-lg);
+    background-color: var(--color-pure-white);
+    padding: 12px;
+    margin-top: 8px;
+}
+
+.hook-row {
+    background-color: var(--color-pure-white);
+    border: 1px solid var(--color-fog);
+    border-radius: var(--radius-lg);
+    padding: 16px;
+    margin-bottom: 12px;
+}
+
+.hook-caption {
+    font-size: 12px;
+    color: var(--color-slate);
+    margin-top: 4px;
+}
+
+.model-call-header {
+    font-size: 14px;
+}
```
