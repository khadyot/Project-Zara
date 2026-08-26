import asyncio
import pytest
from zara.utils.discovery import ATSDiscoverer
import os

# Both tests in this file reach the real ATS APIs over the network. That makes
# them the only non-deterministic thing in a suite whose contract is "zero live
# calls under fixtures", and they fail for reasons that have nothing to do with
# this code: a slow endpoint, a captive network, a vendor rebuild. HANDOFF.md has
# carried "test_known_companies is flaky" as a known-and-tolerated note, which is
# the problem -- a gate you have learned to ignore is not a gate, and the day it
# fails for a real reason nobody will look.
#
# They still earn their place: the SmartRecruiters-returns-200-for-gibberish
# finding came from exactly this check, and only a live call can catch a vendor
# changing that behaviour again. So they are opt-in rather than deleted.
#
#   ZARA_LIVE_TESTS=1 pytest tests/test_discovery.py
#
live_only = pytest.mark.skipif(
    not os.environ.get("ZARA_LIVE_TESTS"),
    reason="hits live ATS APIs; set ZARA_LIVE_TESTS=1 to run",
)

@live_only
@pytest.mark.asyncio
async def test_gibberish_company():
    # Remove cache if it exists for clean test
    if os.path.exists(".ats_cache.json"):
        os.remove(".ats_cache.json")
        
    discoverer = ATSDiscoverer()
    platform, slug = await discoverer.discover("zzznotarealcompany12345", "zzznotarealcompany12345.com")
    
    assert platform is None, f"Expected None, got platform {platform} with slug {slug}"
    assert slug is None, f"Expected None, got slug {slug}"

@live_only
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
