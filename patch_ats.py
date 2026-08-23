import os
import re

ats_path = "/Users/khadyot/Desktop/Ongoing/Projects_AI IDE/Project Zara/zara/fetchers/ats.py"
with open(ats_path, "r") as f:
    content = f.read()

new_imports = """import time
import httpx
import html
from bs4 import BeautifulSoup
from zara.models import Prospect, SourceResult, SignalCard
from zara.utils.discovery import ATSDiscoverer
from zara.utils.config import load_value_prop

def _extract_dense_snippet(text: str) -> str:
    if not text:
        return "No description"
    if len(text) <= 500:
        return text
    
    pain_keywords = ["close", "match", "month-end", "psp", "ledger", "settlement", "payment ops", "excel", "sheets", "manual", "reconciliation", "spreadsheet"]
    
    best_window = ""
    best_score = -1
    
    for i in range(0, max(1, len(text) - 500), 100):
        window = text[i:i+500]
        lower_window = window.lower()
        score = sum(1 for term in pain_keywords if term in lower_window)
        if score > best_score:
            best_score = score
            best_window = window
            
    if not best_window:
        return text[:500]
    return best_window

def _process_jobs(jobs, title_key, url_key, date_key, html_key, source_name, fallback_url, html_is_func=False):
    vp = load_value_prop()
    role_terms = vp.get("icp", {}).get("role_terms", [])
    
    total_jobs = len(jobs)
    relevant_jobs = []
    
    for job in jobs:
        title = job.get(title_key, "Unknown") if not callable(title_key) else title_key(job)
        lower_title = title.lower()
        if any(term.lower() in lower_title for term in role_terms):
            relevant_jobs.append((job, title))
            
    if total_jobs > 0 and len(relevant_jobs) == 0:
        return None, total_jobs, 0
        
    cards = []
    for job, title in relevant_jobs[:5]:
        html_content = html_key(job) if callable(html_key) else job.get(html_key, "")
        text_content = ""
        if html_content:
            decoded_content = html.unescape(html_content)
            soup = BeautifulSoup(decoded_content, "html.parser")
            text_content = soup.get_text(separator=' ', strip=True)
            
        snippet = _extract_dense_snippet(text_content)
        url = url_key(job) if callable(url_key) else job.get(url_key, fallback_url)
        date = date_key(job) if callable(date_key) else job.get(date_key)
        
        cards.append(SignalCard(
            claim=f"Hiring for {title}",
            signal_type="hiring",
            source_url=url,
            published_date=str(date) if date else None,
            snippet=snippet,
            tier="company",
            source=source_name
        ))
        
    return cards, total_jobs, len(relevant_jobs)
"""

content = re.sub(r'import time.*?from zara\.utils\.discovery import ATSDiscoverer', new_imports, content, flags=re.DOTALL)

# Greenhouse
gh_replace = """            jobs = data.get("jobs", [])
            if not jobs:
                return SourceResult(
                    source="Greenhouse", rung=0, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "title", "absolute_url", "updated_at", "content", "Greenhouse", url
            )
            
            if cards is None:
                return SourceResult(
                    source="Greenhouse", rung=0, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Greenhouse", rung=0, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )"""
content = re.sub(r'            jobs = data\.get\("jobs", \[\]\)\n.*?(?:return SourceResult.*?\n            \))', gh_replace, content, flags=re.DOTALL, count=1)

# Lever
lever_replace = """            if not data:
                return SourceResult(
                    source="Lever", rung=0, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                data, "text", "hostedUrl", "createdAt", "descriptionPlain", "Lever", url
            )
            
            if cards is None:
                return SourceResult(
                    source="Lever", rung=0, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Lever", rung=0, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )"""
content = re.sub(r'            if not data:\n.*?(?:return SourceResult.*?\n            \))', lever_replace, content, flags=re.DOTALL, count=1)

# Ashby
ashby_replace = """            jobs = data.get("jobs", [])
            if not jobs:
                return SourceResult(
                    source="Ashby", rung=0, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "title", "jobUrl", "publishedAt", "descriptionHtml", "Ashby", url
            )
            
            if cards is None:
                return SourceResult(
                    source="Ashby", rung=0, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Ashby", rung=0, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )"""
content = re.sub(r'            jobs = data\.get\("jobs", \[\]\)\n.*?(?:return SourceResult.*?\n            \))', ashby_replace, content, flags=re.DOTALL, count=1)

# SmartRecruiters
smart_replace = """            jobs = data.get("content", [])
            if not jobs:
                return SourceResult(
                    source="SmartRecruiters", rung=0, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "name", "ref", "releasedDate", "name", "SmartRecruiters", url
            )
            
            if cards is None:
                return SourceResult(
                    source="SmartRecruiters", rung=0, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="SmartRecruiters", rung=0, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )"""
content = re.sub(r'            jobs = data\.get\("content", \[\]\)\n.*?(?:return SourceResult.*?\n            \))', smart_replace, content, flags=re.DOTALL, count=1)

# Recruitee
recruitee_replace = """            jobs = data.get("offers", [])
            if not jobs:
                return SourceResult(
                    source="Recruitee", rung=0, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "title", "careers_url", "published_at", "description", "Recruitee", url
            )
            
            if cards is None:
                return SourceResult(
                    source="Recruitee", rung=0, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Recruitee", rung=0, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )"""
content = re.sub(r'            jobs = data\.get\("offers", \[\]\)\n.*?(?:return SourceResult.*?\n            \))', recruitee_replace, content, flags=re.DOTALL, count=1)

with open(ats_path, "w") as f:
    f.write(content)

print("ats.py patched successfully")
