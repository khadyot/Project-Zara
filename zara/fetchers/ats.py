import time
import httpx
import html
from bs4 import BeautifulSoup
from zara.models import Prospect, SourceResult, SignalCard
from zara.utils.discovery import ATSDiscoverer
from zara.utils.config import load_value_prop

def _extract_dense_snippet(text: str) -> str:
    if not text:
        return "No description"
        
    lower_text = text.lower()
    for boilerplate in ["equal opportunity", "benefits", "compensation", "what we offer", "perks"]:
        idx = lower_text.find(boilerplate)
        if idx != -1:
            text = text[:idx]
            lower_text = lower_text[:idx]
            
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

def _process_jobs(jobs, title_key, url_key, date_key, html_key, source_name, fallback_url):
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

class GreenhouseFetcher:
    rung = 2
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        discoverer = ATSDiscoverer()
        platform, slug = await discoverer.discover(prospect.company, prospect.company_domain)
        
        if platform != "greenhouse" or not slug:
            return SourceResult(
                source="Greenhouse", rung=2, status="empty", reason="not on greenhouse", 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
            if resp.status_code != 200:
                return SourceResult(
                    source="Greenhouse", rung=2, status="empty", reason=f"http {resp.status_code}", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                return SourceResult(
                    source="Greenhouse", rung=2, status="failed", reason=f"API error: {data['error']}",
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            jobs = data.get("jobs", [])
            if not jobs:
                return SourceResult(
                    source="Greenhouse", rung=2, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "title", "absolute_url", "updated_at", "content", "Greenhouse", ""
            )
            
            if cards is None:
                return SourceResult(
                    source="Greenhouse", rung=2, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Greenhouse", rung=2, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )

class LeverFetcher:
    rung = 2
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        discoverer = ATSDiscoverer()
        platform, slug = await discoverer.discover(prospect.company, prospect.company_domain)
        
        if platform != "lever" or not slug:
            return SourceResult(
                source="Lever", rung=2, status="empty", reason="not on lever", 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            if resp.status_code != 200:
                return SourceResult(
                    source="Lever", rung=2, status="empty", reason=f"http {resp.status_code}", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            data = resp.json()
            if not data:
                return SourceResult(
                    source="Lever", rung=2, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                data, "text", "hostedUrl", "createdAt", "descriptionPlain", "Lever", ""
            )
            
            if cards is None:
                return SourceResult(
                    source="Lever", rung=2, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Lever", rung=2, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )

class AshbyFetcher:
    rung = 2
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        discoverer = ATSDiscoverer()
        platform, slug = await discoverer.discover(prospect.company, prospect.company_domain)
        
        if platform != "ashby" or not slug:
            return SourceResult(
                source="Ashby", rung=2, status="empty", reason="not on ashby", 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if resp.status_code != 200:
                return SourceResult(
                    source="Ashby", rung=2, status="empty", reason=f"http {resp.status_code}", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            try:
                data = resp.json()
                jobs = data.get("jobs", [])
            except Exception as e:
                return SourceResult(
                    source="Ashby", rung=2, status="failed", reason=str(e), 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            if not jobs:
                return SourceResult(
                    source="Ashby", rung=2, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "title", "jobUrl", "publishedAt", "descriptionHtml", "Ashby", ""
            )
            
            if cards is None:
                return SourceResult(
                    source="Ashby", rung=2, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Ashby", rung=2, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )

class SmartRecruitersFetcher:
    rung = 2
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        discoverer = ATSDiscoverer()
        platform, slug = await discoverer.discover(prospect.company, prospect.company_domain)
        
        if platform != "smartrecruiters" or not slug:
            return SourceResult(
                source="SmartRecruiters", rung=2, status="empty", reason="not on smartrecruiters", 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings")
            if resp.status_code != 200:
                return SourceResult(
                    source="SmartRecruiters", rung=2, status="empty", reason=f"http {resp.status_code}", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            data = resp.json()
            jobs = data.get("content", [])
            if not jobs:
                return SourceResult(
                    source="SmartRecruiters", rung=2, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "name", "ref", "releasedDate", "name", "SmartRecruiters", ""
            )
            
            if cards is None:
                return SourceResult(
                    source="SmartRecruiters", rung=2, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="SmartRecruiters", rung=2, status="ok", reason=reason, 
                cards=cards, cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )

class RecruiteeFetcher:
    rung = 2
    async def fetch(self, prospect: Prospect) -> SourceResult:
        start = time.time()
        discoverer = ATSDiscoverer()
        platform, slug = await discoverer.discover(prospect.company, prospect.company_domain)
        
        if platform != "recruitee" or not slug:
            return SourceResult(
                source="Recruitee", rung=2, status="empty", reason="not on recruitee", 
                cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
            
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://{slug}.recruitee.com/api/offers")
            if resp.status_code != 200:
                return SourceResult(
                    source="Recruitee", rung=2, status="empty", reason=f"http {resp.status_code}", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
            data = resp.json()
            jobs = data.get("offers", [])
            if not jobs:
                return SourceResult(
                    source="Recruitee", rung=2, status="empty", reason="no open jobs", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            cards, total, rel = _process_jobs(
                jobs, "title", "careers_url", "published_at", "description", "Recruitee", ""
            )
            
            if cards is None:
                return SourceResult(
                    source="Recruitee", rung=2, status="empty", reason=f"{total} roles, none ICP-relevant", 
                    cards=[], cost_usd=0.0, elapsed_ms=int((time.time() - start)*1000)
                )
                
            reason = f"({len(cards)} of {rel} relevant roles shown)" if rel > len(cards) else None
                
            return SourceResult(
                source="Recruitee", rung=2, status="ok", reason=reason, 
                cards=cards, cost_cost=0.0, elapsed_ms=int((time.time() - start)*1000)
            )
