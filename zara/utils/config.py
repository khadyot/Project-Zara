import os
import yaml
from functools import lru_cache

@lru_cache(maxsize=1)
def load_value_prop() -> dict:
    # Resolve relative to the package root (one level up from utils)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(base_dir, "value_prop.yaml")
    
    if not os.path.exists(path):
        raise RuntimeError(f"value_prop.yaml missing at {path}")
        
    with open(path, "r") as f:
        return yaml.safe_load(f)
