import asyncio
from zara.classifier import classify_social_signals
from zara.models import SourceResult, SignalCard

async def main():
    card = SignalCard(
        claim="Data from ExaYouTube",
        signal_type="social",
        source_url="https://youtube.com/something",
        published_date=None,
        snippet="My family went to the beach today! #vacation",
        tier="person",
        source="ExaYouTube"
    )
    result = SourceResult(
        source="ExaYouTube",
        rung=1,
        status="ok",
        reason=None,
        cards=[card],
        cost_usd=0,
        elapsed_ms=0
    )
    out = await classify_social_signals([result])
    print(out[0].cards[0].eligibility)

asyncio.run(main())
