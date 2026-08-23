# DESIGN.md: Zamp (zamp.ai)

## Source
- URL: https://www.zamp.ai/ (homepage), plus /security, /blogs, /contact
- Capture date: 2026-08-22
- Evidence: Firecrawl `branding` + `images` extraction on homepage (confidence: colors 0.90, buttons 0.95, overall 0.925); full-page screenshots of all 4 pages (home 1920×5400, security 1920×3774, blogs 1920×2786, contact 1920×1858); page markdown for all 4
- **Scope limit:** only public marketing pages were reachable. Zamp's actual product UI (the "Pace" agent dashboard) sits behind a demo-gated login and was not captured. Everything below describes marketing-site visual language, not observed product/dashboard UI — treat the components section as a style guide to apply to a dashboard, not as an observed dashboard pattern. The /blogs card grid is the closest observed analog to a "list of records" UI and was weighted heavily for that reason.

## Reference Screenshots
- Homepage (full page): `./.firecrawl/zamp-home-fullpage.png`
- Security page (full page): `./.firecrawl/zamp-security-fullpage.png`
- Blog index (full page): `./.firecrawl/zamp-blogs-fullpage.png`
- Contact page (full page): `./.firecrawl/zamp-contact-fullpage.png`

Use these as the visual source of truth for layout, hierarchy, density, and feel. Tokens below describe the same pages in machine-readable form.

## Design Summary
Confident, editorial, slightly experimental "AI-native" brand. Oversized bold black wordmark treatment recurs on every page (hero, and again as a huge dot-textured outline in the footer). A glitchy halftone/dither illustration style appears on hero/decorative imagery specifically (not a global background texture). Monospace type is used deliberately for conversational/body copy (the hero opens with a literal "chat bubble" in monospace — "Hi, I'm Zamp, an AI employee"). Fully-pill-shaped buttons and small rounded-rect tag chips contrast against otherwise sharp-cornered cards and containers. Pages are built as **stacked full-bleed color sections** (white → blue → black, with soft gradient transitions between them) rather than a single fixed page background — the homepage hero is off-white/light-gray, but that is one section's color, not a site-wide token. Reads as a company selling autonomy/agency (copy: "I don't wait for you to prompt me"), not a typical enterprise-SaaS dashboard look — clean but with personality, not sterile.

## Design Tokens

### Colors
| Token | Value | Status |
|---|---|---|
| `--color-primary` | `#005EFF` (blue) | OBSERVED |
| `--color-secondary` | `#4A2D7A` (purple) | OBSERVED |
| `--color-accent` | `#1E58D8` (link blue) | OBSERVED |
| `--color-section-bg-1` | `#EFEFEF` (off-white/light gray — homepage hero only) | OBSERVED |
| `--color-section-bg-2` | `#FFFFFF` (white — security/contact page tops) | OBSERVED |
| `--color-section-bg-3` | `#005EFF`-range blue (mid-page trust/cert sections) | OBSERVED |
| `--color-section-bg-4` | `#000000` (black — FAQ/accordion sections, footer band is blue not black) | OBSERVED |
| `--color-text-primary` | `#000000` | OBSERVED |
| `--color-button-primary-bg` | `#000000` | OBSERVED |
| `--color-button-primary-text` | `#F5F5F5` | OBSERVED |
| `--color-button-secondary-bg` | `#F5F5F5` | OBSERVED |
| `--color-button-secondary-text` | `#1E1E1E` | OBSERVED |
| `--color-button-secondary-border` | `#FAFAFA` | OBSERVED |
| success / warning / error / info | — | **NOT AVAILABLE** — marketing site has no status UI. Must be designed fresh (see Agent Build Instructions). |

Overall palette is deliberately restrained: near-monochrome (black/white/gray) with one saturated blue as the sole brand accent. No visible use of secondary purple in primary UI — likely reserved for illustration/gradient work only.

### Typography
| Role | Value | Status |
|---|---|---|
| Heading / display face | Geist (bold weights) | OBSERVED |
| Body / conversational copy | Monospace — rendered as part of the `Geist` font stack's mono variant | OBSERVED (visually, in the hero chat-bubble text) |
| Body fallback stack | `ui-sans-serif, system-ui, sans-serif, ...` | OBSERVED (computed fallback) |
| H1 / hero wordmark | Extremely large display size (viewport-relative, spans near-full width at 1920px) | INFERRED — extraction reported 460px at this viewport; treat as "as large as layout allows," not a fixed px value |
| Body text | ~16px | OBSERVED |

**Distinctive pairing to replicate:** bold sans for headlines/wordmarks, monospace for body/conversational/data text. This is the single most identity-defining typographic choice on the site.

**Lucky match:** this project's `layout.tsx` already loads both `Geist` and `Geist_Mono` via `next/font/google` as CSS variables (`--font-geist-sans`, `--font-geist-mono`) — no new font loading needed. `globals.css` previously overrode body to `Arial` instead of using these variables (flagged in project_audit.md); fixed as of commit `237ec52` — body now reads `var(--font-geist-sans), Arial, Helvetica, sans-serif`. `--font-geist-mono` is loaded and available but still unused anywhere — exactly what the reasoning-trail/data-text styling below calls for.

### Spacing And Layout
| Token | Value | Status |
|---|---|---|
| Base spacing unit | 4px | OBSERVED |
| Border radius (general surfaces/cards) | `0px` — sharp corners | OBSERVED |
| Border radius (buttons/pills) | fully rounded (effectively `9999px` / pill shape) | OBSERVED — raw extraction reported a large px value, which is a pill-radius artifact, not a literal token |
| Button shadow | subtle: `0 4px 6px -1px rgba(0,0,0,.1), 0 2px 4px -2px rgba(0,0,0,.1)` (primary), lighter for secondary | OBSERVED |

**Key layout rule:** sharp-cornered containers/cards + fully-pill-shaped interactive controls (buttons, nav pills). Don't split the difference with medium border-radius everywhere — the contrast is the point.

## Components

- **Primary button:** solid black background, off-white text (`#F5F5F5`), fully pill-shaped, soft drop shadow. Used for the highest-priority CTA ("Book Demo").
- **Secondary button:** light gray fill (`#F5F5F5`), dark text (`#1E1E1E`), near-white border, same pill shape, lighter shadow. Used for secondary actions ("Hire Me").
- **Nav bar:** flat, transparent/background-matched, text links + one pill secondary button + one pill primary button on the right, logo mark (simple geometric "Z"/parallelogram glyph) top-left. Identical across all 4 pages — confirmed persistent chrome, not homepage-only.
- **Tag/badge chip** (OBSERVED, blog index) — solid black background, white uppercase text, small (not full-pill) border radius, tight padding, sits directly under card copy. Two variants seen: category tags ("CROSS-INDUSTRY", "CROSS-FUNCTIONAL") and a metadata tag ("7 MINUTE READ"). **This is the single most directly reusable component for our status pills** (draft status, gate result) — closer to what we need than the CTA buttons are, since chips here already carry a short all-caps label rather than an action verb.
- **Content/record card** (OBSERVED, blog index) — image/thumbnail (16:9-ish) on top, headline below, 1-2 line description, then a row of the tag chips above. No border, no shadow — separation comes from grid gutter spacing alone. This is the closest observed analog to a "run record" card for the dashboard's history list.
- **Feature/info card** (OBSERVED, security page) — white background, small monochrome pixel-art-style icon (clock, cloud, dot-grid, shield — blocky/8-bit rendering, not a smooth line-icon library), short heading, 1-2 line description. Sharp corners, thin border, no shadow. Sits on top of a colored (blue) section background.
- **Certification/seal card** (OBSERVED, security page) — white background, circular badge/seal image (SOC, ISO, GDPR, HIPAA marks — real third-party compliance seals, not custom icons), title, description. Same sharp-corner white-card treatment as feature cards, arranged 3-then-2 in a grid.
- **Pagination** (OBSERVED, blog index) — small circular page-number buttons, current page filled solid black, others plain text; flanking chevron prev/next arrows. Compact, bottom-center.
- **Hero "chat bubble":** light gray rounded rectangle, monospace text, conversational first-person copy — a distinctive component worth borrowing conceptually for anything in our app that reports the pipeline's own reasoning in first person (e.g. `reasoning_trail` entries).
- **Illustration/decoration:** halftone-dither noise texture applied specifically to hero photographic/illustrative elements (not a global texture) — high-effort brand asset, not realistic to replicate for a dashboard; skip rather than approximate poorly.
- **FAQ/accordion pattern** (OBSERVED twice — homepage on light bg, security page on black bg): row = label + chevron-down icon, hairline divider between rows, no card chrome. Same component adapts cleanly to both light and dark section backgrounds by just flipping text/divider color — useful pattern if our dashboard ever has light and dark sections.
- **Trust bar:** horizontal row of customer logos (Sequoia, Uber, DoorDash, etc.), grayscale/flat SVGs.
- **Footer** (OBSERVED, identical structure on all 4 pages): solid blue (`#005EFF`-range) full-bleed band, white text, 3-4 link columns each with a small bullet-point header and arrow-icon links, plus a giant dot-textured outline rendering of the "zamp" wordmark as a decorative bottom element. Highly consistent — treat as fixed site chrome.
- **Third-party embeds:** the contact page is just a white heading + an embedded Calendly widget — no custom form component exists to extract on this site.

No data tables or dashboard-grid chrome exist anywhere across the 4 pages — confirmed absent on this evidence, not missed in extraction. The tag-chip and record-card pair from `/blogs` are the best stand-ins for that gap.

## Page Patterns
- **Homepage:** hero (huge wordmark + chat-bubble hook, off-white bg) → trust logos → "About me" tabs (Roles/Testimonials/How I work/FAQs) → 4-step process (Day 1–4) → security/compliance teaser → blue footer.
- **Security:** white hero ("You focus, we fortify") → gradient white-to-blue → 4 feature cards (icon+text) on blue → "Audit-ready, always" cert-seal card grid on blue → gradient blue-to-black → FAQ accordion on black → blue footer.
- **Blogs:** white page, 3-column card grid (thumbnail + headline + description + tag chips), pagination, blue footer.
- **Contact:** white page, centered heading, embedded Calendly widget, blue footer.

Common thread: **long-scroll, single-column-to-grid transitions, full-bleed color-block sections** (not boxed/contained cards on a neutral canvas), generous vertical whitespace within sections despite a tight 4px base spacing unit, and the blue footer band as a constant closing element on every page.

## Content Style
First-person, conversational, slightly informal ("Hi, I'm Zamp, an AI employee" / "I don't wait for you to prompt me"). Short declarative sentences. CTA labels are plain verbs ("Hire Me", "Book Demo") in sentence case, not corporate jargon. Confident/assertive tone ("Velocity is Survival").

## Agent Build Instructions

For the PS-3 run-view (T6) and dashboard (T7), translate this system as follows:

1. **Base palette:** white (`#FFFFFF`) as the dashboard's primary canvas, not the homepage's `#EFEFEF` — that gray is one hero section's color, not a global background token. Black text/primary surfaces, `#005EFF` as the one accent (active/running-stage indicator, links). Reserve full black/blue/white color-block sections for section-level chrome if used at all — a dense dashboard should read closer to the white `/blogs` and `/contact` pages than the gradient-heavy `/security` page.
2. **Status pills (run-level): use the observed tag-chip component, don't invent a new one.** The `/blogs` card tags (solid black bg, white uppercase text, small border-radius, tight padding) are a real, directly-reusable pattern for `gate_result` / `draft_status`. Keep them monochrome-black by default (matches brand restraint) and reserve color only for the states that most need visual urgency — suggested: black = drafted/approved/complete, `#005EFF` outline or fill = running/pending_review, a single muted warm tone (not bright red) = needs_human_judgment/rejected. Don't build a 5-color traffic-light system; it fights the brand's near-monochrome discipline. **This is a separate status vocabulary from per-source status below — don't reuse the same colors for both, or a source failure will visually read as a run outcome.**

2b. **Per-source retrieval status board (T6 headline element, not a detail) — grounded directly in `src/lib/sources/outcome.ts`, verified in the repo, not secondhand.** Every source adapter reports exactly one of four states: `ok` (signals found), `empty` (genuinely nothing — an honest finding, not a fault), `failed` (couldn't retrieve — timeout/rate-limit/auth/quota/upstream error — excluded from scoring), `skipped` (deliberately not run, e.g. LinkedIn by design). `RetrievalSummary.incomplete` is true when any source failed, and that flag is what keeps a "no signal found" result honest — it must be visible, not buried.

   Live source rows today (verified against actual adapter files, not just the `SourceId` type — `web_search` is a leftover union member with no adapter behind it, never design a row for it): `exa`, `firecrawl`, `greenhouse`/`ashby`/`lever` (ATS, one row each or grouped — designer's call), `operator_supplied`. Later, if time permits: `people_data_labs`, `x_api`, `bright_data`. Still 7-9 rows either way, and the user has explicitly rejected trimming T3's source list down — design for several plausibly `failed` on any live run against an unknown name, since that's what an actual demo run will produce, not the clean-fixture case.

   Design as a **status board** — one row per source, always visible during/after signal discovery — using four visual treatments of the existing tag-chip shape, distinguished by fill/border/weight rather than by adding new colors:
   - `ok` — solid black chip: "exa — 4 signals"
   - `empty` — hollow chip, border only, no fill: "people_data_labs — no data"
   - `skipped` — reduced-opacity chip, dashed border: "LinkedIn — not consulted (by design)"
   - `failed` — solid chip in the one warm accent reserved for this, bold label: "firecrawl — UNAVAILABLE (rate-limited)"

   **The `failed` vs `skipped` distinction must never be ambiguous** — it's the exact distinction the product's credibility rests on (a chosen absence vs. a fault in our own plumbing). Carry it in shape *and* label text ("not consulted" vs "UNAVAILABLE"), not color alone, so it survives colorblindness and stays inside the brand's monochrome discipline.

   `greenhouse` is dual-purpose (signal source *and* ICP-fit verifier — a job posting quoting the exact pain phrase is simultaneously a hook and fit proof). Its `ok` row should expand into or link to a distinct "ICP fit confirmed" element rather than reading as one more generic signal-count chip — treat it visually closer to the confidence-gate's own pass/fail marker than to a plain source row.
3. **Run-history cards:** model directly on the `/blogs` record card — thumbnail/status-icon area on top (or skip it), headline (prospect name/company), 1-2 line summary (gate reason or draft subject), tag-chip row underneath (status + timestamp, exactly like "CROSS-INDUSTRY" + "7 MINUTE READ" today). No border/shadow, rely on grid gutter spacing, matches observed evidence better than a bordered/shadowed card guess would.
4. **Feature/info-card style (icon + heading + description, sharp corners, thin border, no shadow)** — use this for any per-stage detail panel in the run view (e.g. "Signal Discovery" card showing what was found), not the chat-bubble style, which should stay reserved for reasoning-trail text specifically.
5. **Icons:** match the observed pixel/8-bit icon style (blocky, monochrome, small) for section/category icons rather than defaulting to a smooth line-icon library (Lucide/Heroicons) — it's a real, distinctive brand signal, not a guess.
6. **Typography:** headings/section titles in Geist (bold), all data/reasoning-trail/log/timestamp/ID/tag-chip text in Geist Mono — this directly mirrors Zamp's own headline-vs-monospace-body split and suits a "run log" UI naturally.
7. **Buttons:** primary = solid black pill; secondary = light gray pill with hairline border. Pill shape is for buttons only — tag chips get small (not full) radius, and cards/panels/table containers stay sharp-cornered (radius 0).
8. **The reasoning trail (`DraftRecord.reasoning_trail`) is the natural place to borrow the "chat bubble" component** — render each stage's output in a light-gray rounded panel with monospace text, first-person or system-log phrasing, mirroring the hero's conversational style.
9. **FAQ/accordion component** transfers directly to any collapsible "why did the system decide this" detail section in the dashboard (e.g. expand to see full reasoning trail per run) — same hairline-divider, chevron-row pattern works on both light and dark backgrounds.
10. **Don't attempt the halftone/dither illustration or the giant dot-textured wordmark** — both are bespoke, high-effort brand assets, not reproducible CSS patterns; a flat, restrained UI without them is more faithful to "the system" than a poor imitation.
11. **Density:** every observed page is spacious/long-scroll; a dashboard needs to be denser. Keep the 4px base unit but tighten section/card spacing considerably — the underlying spacing philosophy (small base unit, sharp corners, restrained color) transfers fine to a denser layout even though every observed page is airy.

## Rerun Inputs
```
workflow: firecrawl-website-design-clone
source_url: https://www.zamp.ai/
target_stack: Next.js + TypeScript + CSS Modules (existing project: Project Zebra / PS-3)
output: ZAMP_DESIGN_SYSTEM.md
```
