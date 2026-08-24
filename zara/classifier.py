import os
import sys
import json
import asyncio
from pydantic import BaseModel, Field
from typing import Literal

from zara.models import SourceResult, SignalCard, ClassifierResult
from zara.utils.provider import run_probe, generate_content_with_retry, ProviderProbeFailedError

_probe_lock = asyncio.Lock()
_probe_run = False

async def _ensure_probe_run():
    global _probe_run
    async with _probe_lock:
        if _probe_run:
            return
        await run_probe()
        _probe_run = True

class Classification(BaseModel):
    index: int
    classification: Literal["professional", "personal", "ambiguous", "unknown"]
    
class ClassificationsResponse(BaseModel):
    results: list[Classification]

def _mark_all_unknown(results: list[SourceResult], to_classify: list) -> list[SourceResult]:
    new_results = list(results)
    for r_idx, c_idx, old_card in to_classify:
        new_card = SignalCard(
            claim=old_card.claim,
            signal_type=old_card.signal_type,
            source_url=old_card.source_url,
            published_date=old_card.published_date,
            snippet=old_card.snippet,
            tier=old_card.tier,
            source=old_card.source,
            eligibility="unknown"
        )
        new_cards = list(new_results[r_idx].cards)
        new_cards[c_idx] = new_card
        new_results[r_idx] = SourceResult(
            source=new_results[r_idx].source,
            rung=new_results[r_idx].rung,
            status=new_results[r_idx].status,
            reason=new_results[r_idx].reason,
            cards=new_cards,
            cost_usd=new_results[r_idx].cost_usd,
            elapsed_ms=new_results[r_idx].elapsed_ms
        )
    return new_results

async def classify_social_signals(results: list[SourceResult]) -> ClassifierResult:
    try:
        await _ensure_probe_run()
    except Exception as e:
        # We need to gather social cards and mark them unknown, then return failed
        to_classify = []
        for r_idx, r in enumerate(results):
            for c_idx, c in enumerate(r.cards):
                if c.signal_type == "social":
                    to_classify.append((r_idx, c_idx, c))
        new_results = _mark_all_unknown(results, to_classify)
        return ClassifierResult(status="failed", reason=f"Probe failed: {e}", results=new_results)
        
    # Gather cards to classify
    to_classify = []
    for r_idx, r in enumerate(results):
        for c_idx, c in enumerate(r.cards):
            if c.signal_type == "social":
                to_classify.append((r_idx, c_idx, c))
                
    if not to_classify:
        return ClassifierResult(status="skipped", reason="no social signals", results=results)
        
    try:
        classifications = []
        chunk_size = 15
        
        for chunk_idx in range(0, len(to_classify), chunk_size):
            chunk = to_classify[chunk_idx:chunk_idx + chunk_size]
            
            prompt = "Classify the following social media snippets as professional, personal, or ambiguous. Professional: B2B relevance, industry thought leadership, product launch. Personal: family, politics, pets, vacations, non-B2B.\n\n"
            for i, (_, _, card) in enumerate(chunk):
                abs_i = chunk_idx + i
                prompt += f"[{abs_i}] {card.snippet[:500]}\n\n"
                
            classifications_obj = await generate_content_with_retry(
                prompt=prompt,
                schema=ClassificationsResponse,
                system_instruction="You are an expert B2B sales classifier."
            )
            classifications.extend(classifications_obj.results)
        
        # Apply classifications by replacing the frozen dataclasses
        new_results = list(results)
        for cl in classifications:
            idx = cl.index
            if 0 <= idx < len(to_classify):
                r_idx, c_idx, old_card = to_classify[idx]
                new_card = SignalCard(
                    claim=old_card.claim,
                    signal_type=old_card.signal_type,
                    source_url=old_card.source_url,
                    published_date=old_card.published_date,
                    snippet=old_card.snippet,
                    tier=old_card.tier,
                    source=old_card.source,
                    eligibility=cl.classification
                )
                
                # Replace card in result
                new_cards = list(new_results[r_idx].cards)
                new_cards[c_idx] = new_card
                
                new_results[r_idx] = SourceResult(
                    source=new_results[r_idx].source,
                    rung=new_results[r_idx].rung,
                    status=new_results[r_idx].status,
                    reason=new_results[r_idx].reason,
                    cards=new_cards,
                    cost_usd=new_results[r_idx].cost_usd,
                    elapsed_ms=new_results[r_idx].elapsed_ms
                )
        return ClassifierResult(status="ok", reason=None, results=new_results)
        
    except ProviderProbeFailedError as e:
        new_results = _mark_all_unknown(results, to_classify)
        return ClassifierResult(status="failed", reason=str(e), results=new_results)
