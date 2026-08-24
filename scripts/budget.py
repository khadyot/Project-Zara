#!/usr/bin/env python3
import sys
import os
import json
import argparse
import datetime
from zara.utils import quota, telemetry

def format_duration(seconds):
    if seconds == float('inf'):
        return "never"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}h{int(minutes % 60)}m"
    days = hours / 24
    return f"{int(days)}d"

def print_default(headroom, forecast):
    print(f"{'QUOTA':<25} {'used':>10} {'limit':>12} {'remaining':>12} {'resets':>8}   {'status'}")
    for h in headroom:
        def fmt(v, res):
            if "spend" in res or "usd" in res:
                return f"${v:.3f}"
            return f"{int(v):,}"
            
        u = fmt(h['used'], h['resource'])
        l = fmt(h['limit'], h['resource'])
        r = fmt(h['remaining'], h['resource'])
        res = format_duration(h['resets_in_s'])
        
        print(f"{h['resource']:<25} {u:>10} {l:>12} {r:>12} {res:>8}   {h['status']}")

    print("\nRUNS                            value")
    print(f"recorded runs (all time)  {forecast['recorded_runs']:>11}")
    if forecast['recorded_runs'] > 0:
        print(f"avg tokens/run            {int(forecast['mean_tokens']):>11,}")
        print(f"p50 / p90                 {int(forecast['mean_tokens']):,} / {int(forecast['p90_tokens']):,}")
        std = f"{int(forecast['stdev_tokens']):,}" if forecast.get('stdev_tokens') is not None else "n/a  (need >=3 runs)"
        print(f"stdev                     {std:>11}")
        print(f"avg wall time             {forecast['avg_wall_s']:>10.1f}s")
        pct = (forecast['avg_stall_s'] / forecast['avg_wall_s'] * 100) if forecast['avg_wall_s'] > 0 else 0
        print(f"of which 429 stall        {forecast['avg_stall_s']:>10.1f}s  ({pct:.0f}%)")
    else:
        print("avg tokens/run                  n/a")
        
    print("")
    fc = forecast.get('forecast')
    if fc:
        print(f"FORECAST (today, {fc['binding_limit']})")
        print(f"  expected      {fc['expected_runs']} more runs   (at mean {int(forecast['mean_tokens']):,}/run)")
        print(f"  conservative  {fc['conservative_runs']} more runs   (at p90 {int(forecast['p90_tokens']):,}/run)")
        if forecast['recorded_runs'] < 3:
            print("  NOTE: forecast uses recorded runs only; N < 3, treat as indicative")
            
def get_stages():
    with telemetry.connect() as conn:
        q = "SELECT stage, SUM(prompt_tokens + completion_tokens) as t FROM usage WHERE provider != 'fixture' AND status NOT IN ('error', '429') GROUP BY stage ORDER BY t DESC"
        rows = conn.execute(q).fetchall()
        for r in rows:
            print(f"{r['stage']:<25} {r['t']:>10,}")

def get_context():
    with telemetry.connect() as conn:
        q = "SELECT context, SUM(prompt_tokens + completion_tokens) as t FROM usage WHERE provider != 'fixture' AND status NOT IN ('error', '429') GROUP BY context ORDER BY t DESC"
        rows = conn.execute(q).fetchall()
        for r in rows:
            print(f"{r['context']:<15} {r['t']:>10,}")
            
def get_trend(n):
    with telemetry.connect() as conn:
        q = "SELECT run_id, ts, duration_ms FROM runs ORDER BY ts DESC LIMIT ?"
        runs = conn.execute(q, (n,)).fetchall()
        if not runs:
            print("No runs.")
            return
            
        print(f"{'run_id':<12} {'tokens':>10} {'duration':>10}")
        last_3 = []
        for r in runs:
            uq = "SELECT SUM(prompt_tokens + completion_tokens) as t FROM usage WHERE run_id = ? AND status NOT IN ('error', '429')"
            row = conn.execute(uq, (r["run_id"],)).fetchone()
            t = row["t"] if row and row["t"] is not None else 0
            print(f"{r['run_id']:<12} {t:>10,} {r['duration_ms']/1000:>9.1f}s")
            last_3.append(t)
            
        # check trend for last 3 vs mean
        last_3 = last_3[:3]
        mean = quota.forecast().get("mean_tokens", 0)
        if mean > 0 and len(last_3) == 3:
            avg3 = sum(last_3) / 3
            if avg3 > mean * 1.25:
                print(f"\nFLAG: Last 3 runs averaged {int(avg3):,} tokens, which is >25% above the historical mean of {int(mean):,}.")

def get_why(headroom):
    crit = [h for h in headroom if h['status'] in ('critical', 'exhausted')]
    if not crit:
        print("All quota limits are healthy.")
        return
        
    for h in crit:
        print(f"{h['resource'].upper()} is {h['status'].upper()}. Resets in {format_duration(h['resets_in_s'])}.")
        
    # check 429s in last hour
    import datetime
    tz = quota._get_tz()
    hour_ago = (datetime.datetime.now(tz) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    with telemetry.connect() as conn:
        q = "SELECT COUNT(*) as c, SUM(wait_ms) as w FROM usage WHERE status = '429' AND ts >= ?"
        row = conn.execute(q, (hour_ago,)).fetchone()
        c = row["c"] or 0
        w = (row["w"] or 0) / 1000
        print(f"In the last hour: {c} requests rate-limited (429), totaling {w:.1f}s of stall time.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stages", action="store_true")
    parser.add_argument("--context", action="store_true")
    parser.add_argument("--trend", type=int, nargs="?", const=10, metavar="N")
    parser.add_argument("--why", action="store_true")
    args = parser.parse_args()
    
    h = quota.headroom()
    f = quota.forecast()
    
    if args.json:
        print(json.dumps({"headroom": h, "forecast": f}, indent=2))
        return
        
    if args.why:
        get_why(h)
        return
        
    if args.stages:
        print("TOKEN SHARE BY STAGE")
        get_stages()
        return
        
    if args.context:
        print("TOKEN SHARE BY CONTEXT")
        get_context()
        return
        
    if args.trend:
        print(f"TREND (last {args.trend} runs)")
        get_trend(args.trend)
        return
        
    print_default(h, f)

if __name__ == "__main__":
    main()
