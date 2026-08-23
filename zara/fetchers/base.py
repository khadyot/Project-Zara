from typing import Protocol
from zara.models import Prospect, SourceResult

class Fetcher(Protocol):
    async def fetch(self, prospect: Prospect) -> SourceResult:
        ...
