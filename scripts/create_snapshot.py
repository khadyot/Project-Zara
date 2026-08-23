import asyncio
import json
import os
from zara.models import Prospect
from zara.fetchers.ats import GreenhouseFetcher

async def main():
    prospect = Prospect("Test", "ShipBob")
    fetcher = GreenhouseFetcher()
    res = await fetcher.fetch(prospect)
    
    # Save the result as a snapshot
    # Convert to dict
    def obj_to_dict(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: obj_to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
        elif isinstance(obj, list):
            return [obj_to_dict(i) for i in obj]
        else:
            return obj
            
    snapshot = obj_to_dict(res)
    os.makedirs("tests/fixtures", exist_ok=True)
    with open("tests/fixtures/shipbob_snapshot.json", "w") as f:
        json.dump(snapshot, f, indent=2)
    print("Snapshot saved to tests/fixtures/shipbob_snapshot.json")

if __name__ == "__main__":
    asyncio.run(main())
