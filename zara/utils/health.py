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
