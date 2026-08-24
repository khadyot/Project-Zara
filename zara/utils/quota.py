import os
import datetime
import math
import sys

try:
    import zoneinfo
except ImportError:
    # Fallback if somehow on older python, but we are on 3.13
    import datetime as dt
    class zoneinfo:
        @staticmethod
        def ZoneInfo(name):
            return dt.timezone.utc

from zara.utils import telemetry

LIMITS = {
    "groq_tokens/day": {"provider": "groq", "metric": "tokens", "window": "day", "limit": 200000, "env": "GROQ_TPD_LIMIT"},
    "groq_requests/day": {"provider": "groq", "metric": "requests", "window": "day", "limit": 1000, "env": "GROQ_RPD_LIMIT"},
    "groq_tokens/min": {"provider": "groq", "metric": "tokens", "window": "minute", "limit": 8000, "env": "GROQ_TPM_LIMIT"},
    "groq_requests/min": {"provider": "groq", "metric": "requests", "window": "minute", "limit": 30, "env": "GROQ_RPM_LIMIT"},
    "gemini_requests/day": {"provider": "gemini", "metric": "requests", "window": "day", "limit": 20, "env": "GEMINI_RPD_LIMIT"},
    "tavily_credits/month": {"provider": "tavily", "metric": "credits", "window": "month", "limit": 1000, "env": "TAVILY_CREDIT_LIMIT"},
    "apify_spend": {"provider": "apify", "metric": "usd", "window": "month", "limit": 4.00, "env": "APIFY_SPEND_LIMIT"},
}

def _get_tz():
    tz_name = os.environ.get("ZARA_QUOTA_TZ", "UTC")
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return datetime.timezone.utc

def _window_start_and_reset(window: str, now: datetime.datetime):
    if window == "minute":
        start = now - datetime.timedelta(seconds=60)
        reset_in = 60
    elif window == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_day = start + datetime.timedelta(days=1)
        reset_in = (next_day - now).total_seconds()
    elif window == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        reset_in = (next_month - now).total_seconds()
    else:
        start = datetime.datetime.min.replace(tzinfo=now.tzinfo)
        reset_in = float('inf')
        
    return start.astimezone(datetime.timezone.utc), reset_in

def get_limit(key: str) -> float:
    meta = LIMITS[key]
    val = os.environ.get(meta["env"])
    if val is not None:
        return float(val)
    return float(meta["limit"])

def context() -> str:
    return os.environ.get("ZARA_CONTEXT", "unknown")

def record(provider: str, model: str, *, stage: str, prompt_tokens: int, completion_tokens: int, 
           status: str, http_status: int = None, elapsed_ms: int = None, wait_ms: int = 0):
    try:
        t = telemetry.current()
        run_id = t.run_id if t else None
        
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        ctx = context()
        
        row = {
            "ts": ts,
            "provider": provider,
            "model": model,
            "stage": stage,
            "context": ctx,
            "run_id": run_id,
            "prompt_tokens": prompt_tokens or 0,
            "completion_tokens": completion_tokens or 0,
            "status": status,
            "http_status": http_status,
            "elapsed_ms": elapsed_ms,
            "wait_ms": wait_ms,
        }
        
        with telemetry.connect() as conn:
            cols = list(row.keys())
            conn.execute(
                f"INSERT INTO usage ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                list(row.values())
            )
    except Exception as e:
        print(f"[quota] record failed: {e}", file=sys.stderr)

def headroom() -> list[dict]:
    tz = _get_tz()
    now = datetime.datetime.now(tz)
    
    results = []
    
    with telemetry.connect() as conn:
        for key, meta in LIMITS.items():
            limit = get_limit(key)
            start_utc, reset_in = _window_start_and_reset(meta["window"], now)
            start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%S")
            
            used = 0
            if meta["provider"] in ("groq", "gemini", "zai"):
                q = """
                    SELECT SUM(prompt_tokens + completion_tokens) as tokens, COUNT(*) as reqs
                    FROM usage 
                    WHERE provider = ? 
                      AND ts >= ? 
                      AND provider != 'fixture' 
                      AND status NOT IN ('error', '429')
                """
                row = conn.execute(q, (meta["provider"], start_str)).fetchone()
                if meta["metric"] == "tokens":
                    used = row["tokens"] or 0
                elif meta["metric"] == "requests":
                    used = row["reqs"] or 0
            elif meta["provider"] in ("tavily", "apify"):
                # Read the persistent ledger in .budget.json, not source_calls.
                #
                # source_calls is written by RunTrace.capture_sources, so it only
                # exists when a trace is active -- the same blind spot as the
                # _log_llm early return this module was built to fix. A Tavily call
                # from the app's force-fetch button, or any CLI probe, never lands
                # there. The JOIN to runs made it stricter still.
                #
                # It was also matching on the wrong value: SourceResult.source holds
                # the fetcher class name ('Tavily', 'ApifyLinkedInCompany'), never
                # 'tavily'/'apify', so both queries returned 0 unconditionally.
                # Measured: headroom said 0 credits and $0.00 while the ledger held
                # 104 credits and $0.332.
                from zara.utils import budget as _budget
                if meta["provider"] == "tavily":
                    used = _budget.get_credit_usage("tavily")["used"]
                else:
                    used = _budget.get_mtd_spend()
                
            remaining = limit - used
            pct = (used / limit) if limit > 0 else 1.0
            
            if pct < 0.7:
                status = "ok"
            elif pct < 0.9:
                status = "warn"
            elif pct < 1.0:
                status = "critical"
            else:
                status = "exhausted"
                
            results.append({
                "resource": key.replace("_", " "),
                "window": meta["window"],
                "used": used,
                "limit": limit,
                "remaining": remaining,
                "pct_used": pct,
                "resets_in_s": reset_in,
                "status": status
            })
            
    return results

def forecast() -> dict:
    with telemetry.connect() as conn:
        q = """
            SELECT run_id, 
                   SUM(prompt_tokens + completion_tokens) as tokens,
                   COUNT(*) as reqs
            FROM usage
            WHERE provider = 'groq' 
              AND run_id IS NOT NULL 
              AND status NOT IN ('error', '429')
            GROUP BY run_id
        """
        rows = conn.execute(q).fetchall()
        runs_count = len(rows)
        
        if runs_count == 0:
            return {
                "recorded_runs": 0,
                "mean_tokens": 0,
                "p90_tokens": 0,
                "mean_reqs": 0,
                "p90_reqs": 0,
                "stdev_tokens": None,
                "avg_wall_s": 0,
                "avg_stall_s": 0,
                "forecast": None
            }
            
        tokens = sorted([r["tokens"] for r in rows if r["tokens"] is not None])
        reqs = sorted([r["reqs"] for r in rows if r["reqs"] is not None])
        
        mean_tokens = sum(tokens) / len(tokens)
        p90_tokens = tokens[int(len(tokens) * 0.9)] if len(tokens) > 0 else 0
        
        mean_reqs = sum(reqs) / len(reqs)
        p90_reqs = reqs[int(len(reqs) * 0.9)] if len(reqs) > 0 else 0
        
        q_wall = "SELECT duration_ms FROM runs WHERE run_id IN (SELECT DISTINCT run_id FROM usage WHERE provider = 'groq')"
        wall_rows = conn.execute(q_wall).fetchall()
        avg_wall_s = (sum(r["duration_ms"] for r in wall_rows) / len(wall_rows)) / 1000 if wall_rows else 0
        
        q_stall = "SELECT SUM(wait_ms) as total_wait FROM usage WHERE provider = 'groq' AND run_id IS NOT NULL"
        stall_row = conn.execute(q_stall).fetchone()
        avg_stall_s = (stall_row["total_wait"] or 0) / runs_count / 1000 if runs_count > 0 else 0
        
    hrs = headroom()
    
    groq_tpd = next((h for h in hrs if h["resource"] == "groq tokens/day"), None)
    groq_rpd = next((h for h in hrs if h["resource"] == "groq requests/day"), None)
    
    def calc_forecast(tpd_h, rpd_h, m_tok, p_tok, m_req, p_req):
        if not tpd_h or not rpd_h or m_tok == 0 or m_req == 0:
            return None
            
        exp_runs_t = int(tpd_h["remaining"] // m_tok)
        exp_runs_r = int(rpd_h["remaining"] // m_req)
        
        con_runs_t = int(tpd_h["remaining"] // p_tok) if p_tok > 0 else exp_runs_t
        con_runs_r = int(rpd_h["remaining"] // p_req) if p_req > 0 else exp_runs_r
        
        expected_runs = min(exp_runs_t, exp_runs_r)
        conservative_runs = min(con_runs_t, con_runs_r)
        
        bind_limit = "groq TPD" if exp_runs_t <= exp_runs_r else "groq RPD"
        
        return {
            "expected_runs": max(0, expected_runs),
            "conservative_runs": max(0, conservative_runs),
            "binding_limit": bind_limit
        }

    def _stdev(vals):
        if len(vals) < 3:
            return None
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
        return var ** 0.5

    return {
        "recorded_runs": runs_count,
        "mean_tokens": mean_tokens,
        "p90_tokens": p90_tokens,
        "stdev_tokens": _stdev(tokens),
        "avg_wall_s": avg_wall_s,
        "avg_stall_s": avg_stall_s,
        "forecast": calc_forecast(groq_tpd, groq_rpd, mean_tokens, p90_tokens, mean_reqs, p90_reqs)
    }
