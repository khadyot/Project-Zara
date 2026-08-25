from dataclasses import dataclass, field
from typing import Literal

from zara.utils.resolve import ResolutionInfo

RetrievalStatus = Literal["ok", "empty", "failed", "skipped"]

@dataclass(frozen=True)
class Prospect:
    person_name: str
    company: str
    title: str | None = None
    company_domain: str | None = None
    linkedin_url: str | None = None

@dataclass(frozen=True)
class SignalCard:
    claim: str
    signal_type: Literal["hiring", "news", "funding", "product", "person_mention", "profile", "firmographic", "social"]
    source_url: str
    published_date: str | None
    snippet: str          # VERBATIM from source, never paraphrased
    tier: Literal["company", "person"]
    source: str
    eligibility: Literal["professional", "personal", "ambiguous", "unknown", "eligible"] = "eligible"

@dataclass(frozen=True)
class SourceResult:
    source: str
    rung: int
    status: RetrievalStatus
    reason: str | None
    cards: list[SignalCard]
    cost_usd: float
    elapsed_ms: int

    def __post_init__(self):
        # The ticket dictates: reason non-None whenever status != "ok"
        if self.status != "ok" and self.reason is None:
            raise ValueError(f"SourceResult with status '{self.status}' must have a reason.")
        
        # cards empty whenever status != "ok"
        if self.status != "ok" and len(self.cards) > 0:
            raise ValueError(f"SourceResult with status '{self.status}' must have an empty cards list.")

@dataclass(frozen=True)
class ClassifierResult:
    status: Literal["ok", "failed", "skipped"]
    reason: str | None
    results: list[SourceResult]

@dataclass(frozen=True)
class PainMatch:
    pain_id: str        # must be one of the ids in value_prop.yaml
    score: float        # 0.0 - 1.0
    reason: str         # ONE line. Why THIS snippet evidences THIS pain.

@dataclass(frozen=True)
class RankedCard:
    card: SignalCard
    pain_match: PainMatch | None
    # "colleague_authored": on-the-record words from a NAMED person at the company
    # who is not the prospect. Real evidence about how that org works, but it must
    # never be written as if the prospect said it. See attributed_to.
    proximity: Literal["authored", "colleague_authored", "attributed", "company_action", "database"]
    recency_days: int | None
    score: float
    excluded: str | None
    guardrail_hit: str | None = None
    attributed_to: str | None = None   # whose words, when not the prospect's

@dataclass(frozen=True)
class HookProposal:
    card_index: int
    hook_text: str
    rationale: str
    bridge: str
    strength: float
    # card_index indexes the shortlist passed to _articulate_hooks, NOT
    # RankedProspect.cards, so the UI cannot recover the card -- and therefore
    # its age -- on its own. A reviewer reading "[0.85] You recently
    # discussed..." needs to see that the evidence is five years old without
    # opening the audit trail (Compass IX).
    recency_days: int | None = None

@dataclass(frozen=True)
class RankedProspect:
    prospect: Prospect
    cards: list[RankedCard]
    icp_fit: Literal["fit", "unknown"]
    winning_card: RankedCard | None
    hooks: list[HookProposal] = field(default_factory=list)
    resolution: ResolutionInfo | None = None
    icp_notes: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    status: Literal["clean", "blocked_hallucination", "could_not_run"]
    reason: str | None
    self_corrected: bool = False
    first_pass_hallucinations: list[str] | None = None

@dataclass(frozen=True)
class DraftResult:
    ranked_prospect: RankedProspect
    draft_text: str | None
    verification: VerificationResult | None
    claim_strength: Literal["person_authored", "person_attributed", "colleague_authored", "company_action", "database_only", "no_signal"]

    # True when the drafter had no winning card: the opener is company-level and
    # the offer is not tied to any signal we actually found. The email is still
    # written -- Compass I is "degrade, never refuse" -- but "never silently" is
    # the other half, so this flag exists to be rendered on the output's face.
    # Without it a no-signal draft is visually indistinguishable from a grounded
    # one, which is the single failure this project's thesis cannot survive.
    offer_is_generic: bool = False
