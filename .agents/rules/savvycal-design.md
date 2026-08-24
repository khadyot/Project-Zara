# SavvyCal Design Rules

**Context:** The `Project Zara` Streamlit app strictly uses a customized version of the SavvyCal design system. All AI agents working on this UI must abide by these rules.

## Core Rules

1. **NO EMOJIS EVER**: The brand is highly editorial and magazine-like. It relies entirely on typography, whitespace, and coral line-art. Never use emojis (e.g., ⚙️, 🛑, 🎯) in UI elements, buttons, tabs, sidebars, or labels.
2. **Strict Typography**: We only use `Inter` for body/functional UI and `Playfair Display` for headers.
3. **Primary Colors**:
   - `Forest Stage` (`#0d542b`) for hero backgrounds.
   - `Cream Paper` (`#fcf7ed`) for the app surface and content areas.
   - `Lime Sprout` (`#b9ff78`) ONLY for primary action buttons or interactive states (like the active Tab Pill).
4. **Follow `savvycal_style.md`**: Before making ANY visual changes, check `reference/savvycal_style.md`. Do not invent new styles or use default Streamlit styling.

## Where the CSS lives

`CUSTOM_CSS` and `render_hero()` are in **`zara/ui/styles.py`**, not `app.py`. They were
split out so look-and-feel and app logic can be worked on by different agents without
editing the same file. `app.py` imports them and owns behaviour only.

- All new Streamlit components (`st.button`, `st.text_input`, etc.) inherit the SavvyCal
  styling automatically. You rarely need inline styles.
- If a component looks wrong, update `CUSTOM_CSS` in `zara/ui/styles.py` rather than
  hardcoding inline styles in `app.py`.

## Which document governs

`reference/savvycal_style.md` is the **exhaustive** design system — tokens, type scale,
components, surfaces, elevation, and the do's and don'ts. Treat it as the source of truth
for any visual question.

This file is the short list of *project-specific* constraints that the style reference does
not cover (the emoji ban, the Streamlit-override approach, where the CSS lives). It does not
replace the style reference.

`brief/ZAMP_DESIGN_SYSTEM.md` is superseded and should be ignored for UI work.
