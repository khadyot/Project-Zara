import asyncio
import pytest
from zara.utils.discovery import ATSDiscoverer
import os

@pytest.mark.asyncio
async def test_gibberish_company():
    # Remove cache if it exists for clean test
    if os.path.exists(".ats_cache.json"):
        os.remove(".ats_cache.json")
        
    discoverer = ATSDiscoverer()
    platform, slug = await discoverer.discover("zzznotarealcompany12345", "zzznotarealcompany12345.com")
    
    assert platform is None, f"Expected None, got platform {platform} with slug {slug}"
    assert slug is None, f"Expected None, got slug {slug}"

@pytest.mark.asyncio
async def test_known_companies():
    if os.path.exists(".ats_cache.json"):
        os.remove(".ats_cache.json")
        
    discoverer = ATSDiscoverer()
    
    # Modern Treasury -> Ashby
    p1, s1 = await discoverer.discover("Modern Treasury", "moderntreasury.com")
    assert p1 == "ashby"
    assert s1 == "moderntreasury"
    
    # ShipBob -> Greenhouse
    p2, s2 = await discoverer.discover("ShipBob", "shipbob.com")
    assert p2 == "greenhouse"
    assert s2 == "shipbobinc"
    
    # Rippling -> None
    p3, s3 = await discoverer.discover("Rippling", "rippling.com")
    assert p3 is None
    assert s3 is None
