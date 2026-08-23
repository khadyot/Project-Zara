import json
import os
from filelock import FileLock

BUDGET_FILE = ".budget.json"
BUDGET_LOCK_FILE = ".budget.json.lock"

def get_mtd_spend() -> float:
    if not os.path.exists(BUDGET_FILE):
        return 0.0
    
    with FileLock(BUDGET_LOCK_FILE):
        try:
            with open(BUDGET_FILE, "r") as f:
                data = json.load(f)
                return float(data.get("mtd_spend_usd", 0.0))
        except (json.JSONDecodeError, ValueError):
            return 0.0

def add_spend(amount: float):
    if amount <= 0:
        return
        
    with FileLock(BUDGET_LOCK_FILE):
        current_spend = 0.0
        if os.path.exists(BUDGET_FILE):
            try:
                with open(BUDGET_FILE, "r") as f:
                    data = json.load(f)
                    current_spend = float(data.get("mtd_spend_usd", 0.0))
            except (json.JSONDecodeError, ValueError):
                pass
        
        new_spend = current_spend + amount
        with open(BUDGET_FILE, "w") as f:
            json.dump({"mtd_spend_usd": new_spend}, f)
