from dataclasses import dataclass, field
from typing import Literal

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
    proximity: Literal["authored", "attributed", "company_action", "database"]
    recency_days: int | None
    score: float
    excluded: str | None

@dataclass(frozen=True)
class RankedProspect:
    prospect: Prospect
    cards: list[RankedCard]
    icp_fit: Literal["fit", "not_a_fit", "unknown"]
    winning_card: RankedCard | None

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
    claim_strength: Literal["person_authored", "person_attributed", "company_action", "database_only", "no_signal"]

