import asyncio
import json
try:
    import tiktoken
except ImportError:
    print("Please install tiktoken: pip install tiktoken")
    exit(1)

from zara.utils.config import load_value_prop
from scripts.record_mock import load_snapshot

def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

async def main():
    vp = load_value_prop()
    
    # Load Thin Prospect snapshot
    path = "tests/fixtures/thin_prospect_snapshot.json"
    try:
        results = load_snapshot(path)
    except FileNotFoundError:
        print(f"File not found: {path}. Cannot run token comparison.")
        return
        
    cards = []
    for r in results:
        cards.extend(r.cards)
        
    # Take top 15 cards
    cards = cards[:15]
    
    system_instruction = f"You are a sales researcher. Here is the value proposition:\n{json.dumps(vp, indent=2)}\n\nFind a hook."
    
    # Simulating the batches (3 batches of 5)
    batch_prompts = []
    for i in range(0, 15, 5):
        batch = cards[i:i+5]
        batch_prompts.append(f"Evaluate these {len(batch)} cards: {json.dumps([c.__dict__ for c in batch])}")
        
    batched_tokens = 0
    for bp in batch_prompts:
        batched_tokens += count_tokens(system_instruction) + count_tokens(bp)
        
    # Simulating the single call (1 batch of 15)
    single_prompt = f"Evaluate these {len(cards)} cards: {json.dumps([c.__dict__ for c in cards])}"
    single_tokens = count_tokens(system_instruction) + count_tokens(single_prompt)
    
    print(f"--- Offline Token Comparison for Thin Prospect ({len(cards)} cards) ---")
    print(f"Batched Strategy (3 calls of 5): {batched_tokens} tokens")
    print(f"Single Call Strategy (1 call of 15): {single_tokens} tokens")
    
    diff = batched_tokens - single_tokens
    print(f"\nConclusion: Batched is {'more' if diff > 0 else 'less'} expensive by {abs(diff)} prompt tokens for a 15-card prospect.")

if __name__ == "__main__":
    asyncio.run(main())
