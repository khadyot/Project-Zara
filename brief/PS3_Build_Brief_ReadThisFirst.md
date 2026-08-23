# PS-3 Build Brief — Read This, Not the Full Dossier

This is the compressed version. The full research dossier stays as reference material for if a specific question comes up later, you don't need to read it end to end.

## The one-sentence frame

You're building a single-prospect research-and-drafting agent: given a name, it finds real signal, judges what's actually relevant, and produces a personalized outreach draft for human review, never auto-sends. Zamp has no shipped GTM product to be measured against, so you're setting the bar yourself, not matching theirs.

## Why this build is hard to differentiate, and what actually differentiates it

The pipeline shape (research → score → draft) is something every AI SDR demo on the internet has already shown. Nobody will be impressed by the plumbing. What's actually rare, and what every credible source converged on independently, is **restraint**: an agent that knows when it doesn't have enough to say something real, and says so instead of guessing. That single behavior is your differentiator. Build for it deliberately, don't let it be an afterthought.

## Your hook-ranking rule (locked)

Authored content (a LinkedIn post, a quote, an interview) beats observed business events (funding, hiring, launches) beats static firmographic data (industry, size, headcount). Reasoning: authored content reveals current intent, a public event is something that happened *to* the company and everyone researching them sees the same fact. Lead with the most self-authored signal available; relegate public business events to a single supporting line, never the headline.

When there's no authored signal at all: don't force a weak personalization and don't silently discard the record either. Route it to a visible "needs human judgment" state with the reason stated plainly. This is a feature, not a failure state, show it in your demo as evidence of judgment.

## Your three edge cases (locked)

1. **Hallucinated facts** — agent invents something not actually in its source material.
2. **Real-signal-wrong-inference** — the signal is true, but the conclusion drawn from it isn't (a job posting for a role that's already filled, a "like" mistaken for active evaluation).
3. **Personalized-opener-generic-offer** — the hook is real and specific, but the pitch that follows it is generic and doesn't connect back to it.

Each needs its own distinct test scenario. They're testing different failure modes, not variations of one.

## The anti-fabrication mechanism (build this first, it's your MVP core)

Gate generation behind a signal-confidence check. If the signal is weak or unverifiable, the agent explicitly declines to fabricate, rather than guessing. This is now the single most independently-confirmed idea across every source researched: Clay's own guide, two separate Deep Research passes, an open-source repo, and a company (11x) that burned three months learning it the hard way, all landed on some version of this. If you build nothing else well, build this well.

A stronger, second-pass version exists (Twain's approach: verify every claim in a finished draft against source evidence, strip anything unsupported) but that's a stretch goal, not day-one scope. Get the simple gate solid first.

## Real risks, not hypothetical ones

- **Vercel + a multi-step pipeline can hit serverless time limits.** DECIDED: enable Fluid Compute and raise `maxDuration` (800s GA on Pro) rather than standing up a background-job queue (Inngest/Trigger.dev/Vercel Workflow) — single-prospect, single-request pipeline doesn't need that complexity. Verify actual timing in T8/T9; only escalate to a job queue if real runs approach the limit.
- **Live research is not optional — it's the product.** The system must actually work on a real, arbitrary name, not only the 5 fixtures. Build signal discovery (T3) against Claude's native `web_search` tool (server-side, cited, no scraper to maintain). Fixtures remain the regression suite and the demo-reliability fallback (LinkedIn blocks direct scraping, so don't gamble the live interview demo on a fresh scrape succeeding) — but they are not a substitute for the system working end-to-end on new input.
- **Don't skip the "existing context" check just because it's invisible in a five-minute demo.** A minimal fake CRM/suppression check (don't draft outreach to someone already in an active deal) is exactly the kind of realistic operational detail the case study guide says separates a considered build from a toy one, and it's cheap to fake convincingly.

## What NOT to build

Deliverability infrastructure (domain warming, spam-filter avoidance), batch/list processing, actual sending. The case study is single-prospect and explicitly wants a human in the loop before anything goes out. Building sending capability is scope you don't need and can't safely demo anyway.
