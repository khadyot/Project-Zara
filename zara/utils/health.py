"""Is this deployment actually wired up?

The one thing a hosted deploy can break that local testing cannot catch is
credential delivery: on Streamlit Cloud the keys arrive as `st.secrets` and are
copied into `os.environ` at startup, and if that copy fails every model call
dies mid-pipeline with an error that looks like a pipeline bug.

Answering that with a full prospect run costs ~8,000 tokens to learn one
boolean, and fails confusingly. These two checks answer it directly:

  presence -- zero cost. All keys arrive through the same st.secrets loop, so
              one missing key indicts the mechanism, not that key.
  probe    -- ~10 tokens. Presence is not validity; only a real call separates
              "a key is set" from "the provider accepts it".

Never returns or logs a key value. A status panel that leaks a key into a
screenshot is worse than no status panel.
"""
import os

# Name -> whether the app degrades or dies without it.
PROVIDER_KEYS = [
    ("GROQ_API_KEY", "required", "primary reasoning model"),
    ("GEMINI_API_KEY", "fallback", "fallback model (~20 req/day)"),
    ("ZAI_API_KEY", "fallback", "last-resort fallback model"),
    ("EXA_API_KEY", "required", "LinkedIn / news / web retrieval"),
    ("TAVILY_API_KEY", "required", "open-web retrieval"),
    ("APIFY_API_TOKEN", "optional", "paid social/firmographic rungs"),
]


def key_status() -> list[dict]:
    """Presence and length of each credential. Never the value."""
    out = []
    for name, tier, purpose in PROVIDER_KEYS:
        raw = os.environ.get(name) or ""
        value = raw.strip()
        out.append({
            "name": name,
            "tier": tier,
            "purpose": purpose,
            "present": bool(value),
            # Length is safe and genuinely diagnostic: the documented failure on
            # this project is a 7-character placeholder shadowing the real key,
            # which is indistinguishable from a healthy key by presence alone.
            "length": len(value),
            "suspicious": bool(value) and len(value) < 20,
        })
    return out


def secrets_bridge_ok() -> bool:
    """Every required key present. The direct read-out of the st.secrets copy."""
    return all(k["present"] for k in key_status() if k["tier"] == "required")


# What to tell the operator for each way the bridge can end up. A panel that
# reports a symptom without naming the cause or the fix is half a tool -- and
# "key absent" alone cannot distinguish "you never saved them" (a two-minute
# fix in a web form) from "the copy loop is broken" (a code bug).
_BRIDGE_ADVICE = {
    "unavailable": "No secrets are configured for this deployment. "
                   "Fix: Manage app -> Settings -> Secrets, then save (the app reboots).",
    "empty": "Secrets are configured but contain no entries. "
             "Fix: Manage app -> Settings -> Secrets, paste the keys as flat TOML.",
    "copied": "The secrets bridge ran and copied values into the environment.",
    "unknown": "The app did not record a bridge result. Expected when running "
               "outside app.py (CLI, tests, the FastAPI entrypoint).",
}


def bridge_status() -> dict:
    """How the st.secrets -> os.environ copy went, and what to do about it.

    app.py records this at import as ZARA_SECRETS_BRIDGE ("state|detail"). Read
    from the environment rather than importing app.py, so the CLI and the tests
    can call this without pulling in Streamlit.
    """
    raw = os.environ.get("ZARA_SECRETS_BRIDGE") or ""
    state, _, detail = raw.partition("|")
    if state not in _BRIDGE_ADVICE:
        state, detail = "unknown", detail or "no bridge result recorded"
    return {
        "state": state,
        "detail": detail,
        "advice": _BRIDGE_ADVICE[state],
        # `copied` is not the same as "all good" -- the loop can run and still
        # copy nothing useful if the TOML nests keys under a [section], since
        # only scalar top-level values are copied.
        "healthy": state == "copied" and secrets_bridge_ok(),
    }


async def groq_probe() -> dict:
    """One ~10-token call. Presence is not validity; this is validity.

    Wraps the existing provider.run_probe(), which already handles retries and
    records to the quota ledger, so a probe appears in usage history like any
    other call.
    """
    from zara.utils.provider import (
        run_probe, ProviderAuthError, ProviderProbeFailedError,
    )

    if not os.environ.get("GROQ_API_KEY"):
        return {
            "status": "no_key",
            "detail": "GROQ_API_KEY is not set in this process. On a hosted "
                      "deploy that means the secrets bridge did not deliver it.",
        }
    try:
        await run_probe()
        return {"status": "ok", "detail": "Groq reachable and the key was accepted."}
    except ProviderAuthError:
        return {
            "status": "rejected",
            "detail": "Groq rejected the key (HTTP 401). It is set but not valid "
                      "here — check the value in the deployment's secrets.",
        }
    except ProviderProbeFailedError as e:
        msg = str(e)
        if "429" in msg:
            return {
                "status": "throttled",
                "detail": "Key works — the per-minute token bucket is full. "
                          "This counts as a pass for connectivity.",
            }
        return {"status": "unreachable", "detail": f"Probe failed: {msg[:200]}"}
    except Exception as e:  # noqa: BLE001 - a status panel must never crash the page
        return {"status": "unreachable", "detail": f"{type(e).__name__}: {str(e)[:200]}"}


async def groq_probe_all() -> list[dict]:
    """Probe every pooled key with one 1-token call each.

    A pool is only worth what its weakest credential is worth, and "five keys are
    configured" is not the same claim as "five keys work". Each row reports the
    HTTP status and that key's own per-minute headroom, which is the thing that
    proves the buckets really are separate rather than five names for one account.

    Costs ~1 token per key. Never returns or logs a key value.
    """
    import httpx

    from zara.utils import keypool
    from zara.utils.provider import GROQ_MODEL, GROQ_URL

    rows = []
    async with httpx.AsyncClient() as client:
        for i, (name, key) in enumerate(keypool.groq_key_sources()):
            row = {"index": i, "name": name, "length": len(key)}
            try:
                r = await client.post(
                    GROQ_URL,
                    json={"model": GROQ_MODEL,
                          "messages": [{"role": "user", "content": "hi"}],
                          "max_tokens": 1},
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=20.0,
                )
                row["http"] = r.status_code
                row["remaining_tokens"] = r.headers.get("x-ratelimit-remaining-tokens")
                row["limit_tokens"] = r.headers.get("x-ratelimit-limit-tokens")
                row["remaining_requests"] = r.headers.get("x-ratelimit-remaining-requests")
                if r.status_code == 200:
                    row["status"] = "ok"
                elif r.status_code == 429:
                    row["status"] = "rate limited"
                elif r.status_code == 401:
                    row["status"] = "rejected"
                else:
                    row["status"] = f"http {r.status_code}"
            except Exception as e:
                row["status"] = "unreachable"
                row["detail"] = type(e).__name__
            rows.append(row)
    return rows
