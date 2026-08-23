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

## CSS Enforcement
- We use a massive `CUSTOM_CSS` block in `app.py` to overwrite Streamlit's defaults.
- All new Streamlit components (`st.button`, `st.text_input`, etc.) will automatically inherit the SavvyCal styling. You rarely need to write inline styles.
- If a component looks weird, update `CUSTOM_CSS` instead of hardcoding inline styles in `app.py`.
