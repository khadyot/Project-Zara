import os
import json
import httpx
import asyncio
import re
from typing import Optional, Dict, Tuple
from exa_py import Exa

CACHE_FILE = ".ats_cache.json"

class ATSDiscoverer:
    def __init__(self):
        self.cache = self._load_cache()
        self.exa = Exa(os.getenv("EXA_API_KEY")) if os.getenv("EXA_API_KEY") else None
        
        self.ats_endpoints = {
            "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs",
            "lever": "https://api.lever.co/v0/postings/{}",
            "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}",
            "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{}/postings",
            "recruitee": "https://{}.recruitee.com/api/offers"
        }

    def _load_cache(self) -> Dict[str, dict]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f, indent=2)

    def _generate_slug_variants(self, company: str, domain: str) -> list:
        variants = []
        if domain:
            base = domain.lower().replace("www.", "").split(".")[0]
            variants.append(base)
            
        name = company.lower()
        no_sep = re.sub(r'[\s\.\,\-]+', '', name)
        hyphenated = re.sub(r'[\s\.\,]+', '-', name).strip('-')
        
        for base in [no_sep, hyphenated]:
            if base and base not in variants:
                variants.append(base)
            for suffix in ['inc', 'llc', 'co', 'hq']:
                v = base + suffix
                if v not in variants:
                    variants.append(v)
                    
        return [v for v in variants if v]

    async def _test_slug(self, client: httpx.AsyncClient, platform: str, slug: str) -> bool:
        url = self.ats_endpoints[platform].format(slug)
        try:
            resp = await client.get(url, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return True
                elif isinstance(data, dict):
                    if data.get("totalFound", 0) > 0:
                        return True
                    if len(data.get("content", [])) > 0:
                        return True
                    if len(data.get("jobs", [])) > 0:
                        return True
                    if len(data.get("offers", [])) > 0:
                        return True
        except:
            pass
        return False

    async def discover(self, company: str, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """Returns (platform, slug) or (None, None)"""
        cache_key = domain if domain else company
        if cache_key in self.cache:
            c = self.cache[cache_key]
            return c.get("platform"), c.get("slug")

        variants = self._generate_slug_variants(company, domain)
        
        # Test HTTP variants concurrently
        async with httpx.AsyncClient() as client:
            tasks = []
            for variant in variants:
                for platform in self.ats_endpoints.keys():
                    tasks.append(
                        (platform, variant, asyncio.create_task(self._test_slug(client, platform, variant)))
                    )
            
            # Wait for all and then pick by order
            results_found = []
            for platform, variant, task in tasks:
                if await task:
                    results_found.append((platform, variant))
                    
            if results_found:
                ORDER = {"greenhouse": 1, "lever": 2, "ashby": 3, "recruitee": 4, "smartrecruiters": 5}
                results_found.sort(key=lambda x: ORDER.get(x[0], 99))
                best_platform, best_variant = results_found[0]
                
                self.cache[cache_key] = {"platform": best_platform, "slug": best_variant}
                self._save_cache()
                return best_platform, best_variant

        # Fallback to Exa discovery
        if self.exa:
            try:
                resp = await asyncio.to_thread(
                    self.exa.search,
                    f"{company} careers open jobs",
                    include_domains=[
                        "boards.greenhouse.io", "job-boards.greenhouse.io", 
                        "jobs.lever.co", "jobs.ashbyhq.com", 
                        "careers.smartrecruiters.com", "careers.recruitee.com"
                    ],
                    num_results=1
                )
                if resp.results:
                    url = resp.results[0].url
                    # Extract slug and platform from URL
                    if "greenhouse.io" in url:
                        slug = url.rstrip('/').split('/')[-1]
                        platform = "greenhouse"
                    elif "lever.co" in url:
                        slug = url.rstrip('/').split('/')[-1]
                        platform = "lever"
                    elif "ashbyhq.com" in url:
                        slug = url.rstrip('/').split('/')[-1]
                        platform = "ashby"
                    elif "smartrecruiters.com" in url:
                        slug = url.rstrip('/').split('/')[-1]
                        platform = "smartrecruiters"
                    elif "recruitee.com" in url:
                        slug = url.split("://")[1].split(".")[0]
                        platform = "recruitee"
                    else:
                        slug = None
                        platform = None

                    if platform and slug:
                        self.cache[cache_key] = {"platform": platform, "slug": slug}
                        self._save_cache()
                        return platform, slug
            except Exception as e:
                pass

        # Record empty
        self.cache[cache_key] = {"platform": None, "slug": None}
        self._save_cache()
        return None, None
