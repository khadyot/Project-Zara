import os
import sys
import re
import time
import asyncio
import json
import hashlib
import contextvars
import httpx

# Groq org limits (verified against the account dashboard 2026-08-24):
#   openai/gpt-oss-120b  30 RPM / 1K RPD / 8K TPM / 200K TPD
#   groq/compound        30 RPM / 250 RPD / 70K TPM  -- agentic, runs server-side
#                        web search; its assembled context 413s. Never use it here.
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_MODEL = "gemini-2.5-flash"   # verified callable 2026-08-24
ZAI_MODEL = "glm-4.5-flash"

# Gemini free tier is ~20 requests/day/model, so it is a fallback only -- never primary.

class ProviderProbeFailedError(Exception):
    pass


class DeadlineExceeded(ProviderProbeFailedError):
    pass


# --- global deadline -------------------------------------------------------
# One pipeline run shares one deadline. Without it each of the ~7 calls per
# prospect independently re-discovers an outage and pays a full retry ladder,
# which is how a 5.7s p50 turned into multi-minute hangs.
_deadline = contextvars.ContextVar("zara_deadline", default=None)


def set_deadline(seconds: float):
    """Start a run-wide deadline. Returns the token for reset()."""
    return _deadline.set(time.monotonic() + seconds)


def clear_deadline(token):
    if token is not None:
        _deadline.reset(token)


def remaining_time() -> float | None:
    """Seconds left in the run, or None when no deadline is set."""
    dl = _deadline.get()
    return None if dl is None else dl - time.monotonic()


def _check_deadline(stage: str):
    r = remaining_time()
    if r is not None and r <= 0:
        raise DeadlineExceeded(f"run deadline exceeded before {stage}")


# --- circuit breaker -------------------------------------------------------
# Shared across calls in the process. Once a provider is known down, later
# calls skip it instead of each re-paying the retry ladder.
_breaker: dict[str, dict] = {}


def _breaker_open(name: str) -> str | None:
    st = _breaker.get(name)
    if st and time.monotonic() < st["until"]:
        return st["reason"]
    return None


def _trip_breaker(name: str, seconds: float, reason: str):
    _breaker[name] = {"until": time.monotonic() + seconds, "reason": reason}
    print(f"WARNING: circuit breaker OPEN for {name} for {seconds:.0f}s: {reason}", file=sys.stderr)


def reset_breakers():
    _breaker.clear()

class ProviderAuthError(ProviderProbeFailedError):
    pass

def walk_schema(schema_dict: dict):
    if "type" in schema_dict and schema_dict["type"] == "object":
        schema_dict["additionalProperties"] = False
        props = schema_dict.get("properties", {})
        if props:
            schema_dict["required"] = list(props.keys())
        for v in props.values():
            if isinstance(v, dict):
                walk_schema(v)
                
    if "$defs" in schema_dict:
        for k, v in schema_dict["$defs"].items():
            if isinstance(v, dict):
                walk_schema(v)
                
    if "items" in schema_dict and isinstance(schema_dict["items"], dict):
        walk_schema(schema_dict["items"])
        
    if "anyOf" in schema_dict:
        for item in schema_dict["anyOf"]:
            if isinstance(item, dict):
                walk_schema(item)

def _get_api_key():
    """The primary key. Kept for callers that need exactly one (probe, health)."""
    from zara.utils import keypool
    keys = keypool.groq_keys()
    if not keys:
        raise ProviderAuthError("GROQ_API_KEY is missing from environment variables.")
    return keys[0]

def _get_gemini_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ProviderAuthError("GEMINI_API_KEY is missing from environment variables.")
    return key

def extract_json(text: str):
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            if in_string:
                escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None

def _record_fixture(prompt: str, system_instruction: str, content: str, usage: dict = None):
    h = hashlib.md5((prompt + system_instruction).encode()).hexdigest()
    fixture_path = f"tests/fixtures/{h}.json"
    os.makedirs("tests/fixtures", exist_ok=True)
    
    try:
        parsed_content = json.loads(content)
    except Exception:
        parsed_content = content
        
    fixture_data = {
        "content": parsed_content,
        "prompt_tokens": usage.get("prompt_tokens") if usage else None,
        "completion_tokens": usage.get("completion_tokens") if usage else None
    }
    
    with open(fixture_path, "w") as f:
        json.dump(fixture_data, f, indent=2)

def _parse_content(content: str, schema):
    try:
        return schema.model_validate_json(content)
    except Exception:
        salvaged = extract_json(content)
        if salvaged is not None:
            return schema.model_validate(salvaged)
        raise

async def _generate_gemini(prompt: str, schema, system_instruction: str, schema_dict: dict):
    _t0 = time.monotonic()
    api_key = _get_gemini_api_key()

    schema_prompt = (
        f"{prompt}\n\n"
        f"You must respond with a single JSON object matching this JSON schema exactly "
        f"(all properties required, no additional properties):\n"
        f"{json.dumps(schema_dict, indent=2)}"
    )

    payload = {
        "model": GEMINI_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": schema_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            json=payload, headers=headers, timeout=60.0
        )

    if resp.status_code != 200:
        from zara.utils import quota
        quota.record("gemini", GEMINI_MODEL, stage=_stage.get(), prompt_tokens=0, completion_tokens=0, status="error", http_status=resp.status_code, elapsed_ms=int((time.monotonic() - _t0) * 1000))
        raise ProviderProbeFailedError(f"Gemini fallback failed: {resp.status_code} {resp.text}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise ProviderProbeFailedError("Gemini fallback returned empty content")

    usage = data.get("usage", {})
    _log_llm("gemini", GEMINI_MODEL, usage, _t0, prompt, system=system_instruction, response=content)
    _record_fixture(prompt, system_instruction, content, usage)
    return _parse_content(content, schema)

_stage: contextvars.ContextVar[str] = contextvars.ContextVar("zara_llm_stage", default="unknown")


# Storing the prompt is what makes "how did it write that?" answerable. Without it
# we can see the draft and the card it came from but not the instructions in
# between, which is where most drafting defects actually live.
_PROMPT_CAP = 20000


def _log_llm(provider: str, model: str, usage: dict, t0: float, prompt: str,
             attempt: int = 1, status: str = "ok", error: str = None,
             system: str = None, response: str = None):
    """Record one model call against the active run trace, if there is one.

    `usage` was already parsed at every one of these sites and handed to
    _record_fixture; live runs simply dropped it on the floor.
    """
    try:
        from zara.utils.telemetry import current
        from zara.utils import quota
        
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        p_tok = (usage or {}).get("prompt_tokens") or 0
        c_tok = (usage or {}).get("completion_tokens") or 0
        quota.record(provider, model, stage=_stage.get(), prompt_tokens=p_tok, completion_tokens=c_tok, status=status, elapsed_ms=elapsed_ms)
        
        t = current()
        if t is None:
            return
        keep = os.environ.get("ZARA_LOG_PROMPTS", "1") != "0"
        t.llm_call(
            stage=_stage.get(), provider=provider, model=model, attempt=attempt,
            status=status, elapsed_ms=int((time.monotonic() - t0) * 1000),
            prompt_tokens=(usage or {}).get("prompt_tokens"),
            completion_tokens=(usage or {}).get("completion_tokens"),
            prompt_chars=len(prompt or ""), error=error,
            system_text=(system or "")[:_PROMPT_CAP] if keep else None,
            prompt_text=(prompt or "")[:_PROMPT_CAP] if keep else None,
            response_text=(response or "")[:_PROMPT_CAP] if keep else None,
        )
    except Exception:
        pass


async def generate_content_with_retry(prompt: str, schema, system_instruction: str,
                                      stage: str = "unknown") -> any:
    _stage.set(stage)
    # USE_FIXTURES=1     replay only; a missing hash is a hard error (the test gate).
    # USE_FIXTURES=fill   replay every fixture that EXISTS, go live only for the ones
    #                     that are missing, and record those.
    #
    # `fill` exists because re-recording after a prompt change used to mean running the
    # whole pipeline live. That re-answers the prompts whose fixtures were already fine,
    # overwriting good recordings with fresh non-deterministic output -- and worse, a
    # downstream prompt's hash DEPENDS on upstream output. Score the cards live and the
    # shortlist shifts, so the hook prompt text changes, so its hash never matches the
    # one the test is asking for. That failure presents as an inexplicable "hash
    # mismatch" and cost ~50 wasted live calls and most of a day's Groq budget before
    # it was understood. Record with `fill`, never with fixtures off.
    _fx_mode = os.environ.get("USE_FIXTURES")
    _fx_path = None
    if _fx_mode:
        h = hashlib.md5((prompt + system_instruction).encode()).hexdigest()
        _fx_path = f"tests/fixtures/{h}.json"
        if not os.path.exists(_fx_path):
            if _fx_mode == "fill":
                print(f"FIXTURE FILL: missing hash {h} (stage={stage}) -- recording live",
                      file=sys.stderr)
                _fx_path = None
            else:
                raise FileNotFoundError(f"Fixture not found for prompt hash {h}. Please record this fixture first.")

    if _fx_path:
        _fx_t0 = time.monotonic()
        with open(_fx_path, "r") as f:
            data = json.load(f)
            
        # Support new fixture format with usage metrics
        if isinstance(data, dict) and "content" in data and ("prompt_tokens" in data or "completion_tokens" in data):
            content_data = data["content"]
            # Expose recorded usage on the returned object if possible, though pydantic schemas might not accept it directly.
            # We will patch this at the caller level or just rely on global/thread-local tracking if needed.
            # Actually, the user asked to "have replay report the recorded numbers."
            # The ranker/classifier parses the return value. We can inject it into a global or thread-local dict mapping hashes to usage.
            if not hasattr(sys, "_fixture_usage"):
                sys._fixture_usage = {}
            sys._fixture_usage[h] = {
                "prompt_tokens": data.get("prompt_tokens"),
                "completion_tokens": data.get("completion_tokens")
            }
            # Replays log too, using the recorded counts, so a fixture run and a
            # live run produce the same shape of trace.
            _log_llm("fixture", "replay", sys._fixture_usage[h], _fx_t0, prompt,
                     system=system_instruction, response=json.dumps(content_data)[:20000])
            if isinstance(content_data, str):
                return schema.model_validate_json(content_data)
            return schema(**content_data)
            
        # Old fixture format
        if not hasattr(sys, "_fixture_usage"):
            sys._fixture_usage = {}
        sys._fixture_usage[h] = {"prompt_tokens": "unknown", "completion_tokens": "unknown"}
        return schema(**data)
        
    schema_dict = schema.model_json_schema()
    walk_schema(schema_dict)

    schema_prompt = (
        f"{prompt}\n\n"
        f"You must respond with a single JSON object matching this JSON schema exactly "
        f"(all properties required, no additional properties):\n"
        f"{json.dumps(schema_dict, indent=2)}"
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": schema_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        # Best effort only. gpt-oss-120b is an MoE served with batching, so identical
        # inputs can still differ; the seed narrows that, it does not close it. The
        # run fingerprint in telemetry is what we actually rely on to tell a code
        # change apart from model variance.
        "seed": 42,
    }

    _check_deadline("groq call")

    groq_error = None
    tripped = _breaker_open("groq")
    if tripped:
        groq_error = ProviderProbeFailedError(f"skipped, breaker open: {tripped}")
    else:
        from zara.utils import keypool
        _keys = keypool.groq_keys()
        if not _keys:
            raise ProviderAuthError("GROQ_API_KEY is missing from environment variables.")
        # Start this call on the next key in the rotation. Groq's 8K TPM bucket is
        # per key, and one run spends ~4 calls, so spreading them is what stops a
        # run stalling ~45s against its own earlier calls.
        _key_pos = keypool.next_start()
        _keys_tried = 0

        # 8K TPM is the binding limit for ONE key. A 429 means that key's bucket is
        # empty -- so move to the next key immediately, and only sleep once every
        # key has refused. The reset header is honoured when we do have to wait.
        for attempt in range(max(4, len(_keys))):
            api_key = _keys[_key_pos % len(_keys)]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            _t0 = time.monotonic()
            try:
                budget = remaining_time()
                timeout = 60.0 if budget is None else max(5.0, min(60.0, budget))
                async with httpx.AsyncClient() as client:
                    resp = await client.post(GROQ_URL, json=payload, headers=headers, timeout=timeout)

                if resp.status_code == 401:
                    _trip_breaker("groq", 300, "401 Unauthorized")
                    from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage=_stage.get(), prompt_tokens=0, completion_tokens=0, status="error", http_status=401, elapsed_ms=int((time.monotonic() - _t0) * 1000))
                    raise ProviderAuthError(f"HTTP 401 Unauthorized: {resp.text}")

                if resp.status_code == 413:
                    # Request too large for the model's context. Never transient.
                    from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage=_stage.get(), prompt_tokens=0, completion_tokens=0, status="error", http_status=413, elapsed_ms=int((time.monotonic() - _t0) * 1000))
                    raise ProviderProbeFailedError(f"HTTP 413 Payload Too Large: {resp.text[:300]}")

                if resp.status_code == 429:
                    # The TPD ceiling appears in no header -- only in this body.
                    from zara.utils import ratelimit
                    ratelimit.observe("groq", resp.headers, status_code=429, body=resp.text)
                    wait = _parse_reset(resp.headers.get("x-ratelimit-reset-tokens")) or \
                           _parse_reset(resp.headers.get("retry-after")) or 20.0
                    from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage=_stage.get(), prompt_tokens=0, completion_tokens=0, status="429", http_status=429, elapsed_ms=int((time.monotonic() - _t0) * 1000), wait_ms=int(wait * 1000))
                    _keys_tried += 1
                    if _keys_tried < len(_keys):
                        # Another key still has an untouched bucket. Free, instant.
                        _key_pos += 1
                        print(f"WARNING: Groq 429, switching key ({_keys_tried}/{len(_keys)} exhausted)",
                              file=sys.stderr)
                        continue

                    budget = remaining_time()
                    if budget is not None and wait >= budget:
                        _trip_breaker("groq", wait, f"429, reset in {wait:.0f}s exceeds run budget")
                        raise ProviderProbeFailedError(f"429 rate limited, reset in {wait:.0f}s")
                    if attempt >= max(3, len(_keys)):
                        _trip_breaker("groq", wait, "429 after retries")
                        raise ProviderProbeFailedError(f"429 rate limited after retries: {resp.text[:200]}")
                    print(f"WARNING: Groq 429, all {len(_keys)} key(s) rate limited, "
                          f"waiting {wait:.1f}s (bucket reset)", file=sys.stderr)
                    await asyncio.sleep(wait)
                    _keys_tried = 0
                    _key_pos += 1
                    continue

                if resp.status_code != 200:
                    from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage=_stage.get(), prompt_tokens=0, completion_tokens=0, status="error", http_status=resp.status_code, elapsed_ms=int((time.monotonic() - _t0) * 1000))
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:300]}")

                from zara.utils import ratelimit
                ratelimit.observe("groq", resp.headers, status_code=resp.status_code)

                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                if not content or not content.strip():
                    raise Exception("Empty content from Groq")

                usage = data.get("usage", {})
                _log_llm("groq", GROQ_MODEL, usage, _t0, prompt, attempt=attempt + 1, system=system_instruction, response=content)
                _record_fixture(prompt, system_instruction, content, usage)
                return _parse_content(content, schema)

            except (ProviderAuthError, ProviderProbeFailedError) as e:
                groq_error = e
                break
            except Exception as e:
                if "401" in str(e):
                    groq_error = ProviderAuthError(str(e))
                    break
                budget = remaining_time()
                if attempt == 3 or (budget is not None and budget < 5):
                    groq_error = ProviderProbeFailedError(f"Model failed after retries: {e}")
                    break
                backoff = min(4.0 * (attempt + 1), budget if budget else 8.0)
                print(f"WARNING: Groq failed, retrying in {backoff:.1f}s. Error: {e}", file=sys.stderr)
                await asyncio.sleep(backoff)

    print(f"WARNING: Groq unavailable, falling back. Error: {groq_error}", file=sys.stderr)

    for name, fn in (("gemini", _generate_gemini), ("zai", _generate_zai)):
        tripped = _breaker_open(name)
        if tripped:
            print(f"WARNING: skipping {name}, breaker open: {tripped}", file=sys.stderr)
            continue
        if remaining_time() is not None and remaining_time() <= 0:
            break
        try:
            return await fn(prompt, schema, system_instruction, schema_dict)
        except ProviderAuthError as e:
            _trip_breaker(name, 300, str(e)[:120])
        except Exception as e:
            _trip_breaker(name, 60, str(e)[:120])
            print(f"WARNING: {name} failed: {e}", file=sys.stderr)

    if groq_error is not None:
        raise groq_error
    raise ProviderProbeFailedError("all providers failed")


def _parse_reset(val: str | None) -> float | None:
    """Groq reset headers look like '13.207s' or '2m52.8s'."""
    if not val:
        return None
    m = re.findall(r"(\d+(?:\.\d+)?)(ms|m|s|h)", val)
    if not m:
        try:
            return float(val)
        except ValueError:
            return None
    mult = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(n) * mult[u] for n, u in m)


async def _generate_zai(prompt: str, schema, system_instruction: str, schema_dict: dict):
    _t0 = time.monotonic()
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        raise ProviderAuthError("ZAI_API_KEY is missing from environment variables.")

    schema_prompt = (
        f"{prompt}\n\n"
        f"You must respond with a single JSON object matching this JSON schema exactly "
        f"(all properties required, no additional properties):\n"
        f"{json.dumps(schema_dict, indent=2)}"
    )

    payload = {
        "model": ZAI_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": schema_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            json=payload, headers=headers, timeout=60.0
        )

    if resp.status_code != 200:
        from zara.utils import quota
        quota.record("zai", ZAI_MODEL, stage=_stage.get(), prompt_tokens=0, completion_tokens=0, status="error", http_status=resp.status_code, elapsed_ms=int((time.monotonic() - _t0) * 1000))
        raise ProviderProbeFailedError(f"Z.ai fallback failed: {resp.status_code} {resp.text}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    content = content.strip()
    if not content:
        raise ProviderProbeFailedError("Z.ai fallback returned empty content")

    usage = data.get("usage", {})
    _log_llm("zai", ZAI_MODEL, usage, _t0, prompt, system=system_instruction, response=content)
    _record_fixture(prompt, system_instruction, content, usage)
    return _parse_content(content, schema)

async def run_probe():
    # Only for the startup check
    if os.environ.get("USE_FIXTURES"):
        return
        
    api_key = _get_api_key()
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": "probe"}
        ],
        "max_tokens": 5
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    retries = [2, 4, 60]
    for attempt in range(4):
        _t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(GROQ_URL, json=payload, headers=headers, timeout=10.0)
                
            if resp.status_code == 401:
                from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage="probe", prompt_tokens=0, completion_tokens=0, status="error", http_status=401, elapsed_ms=int((time.monotonic() - _t0) * 1000))
                raise ProviderAuthError(f"Probe failed hard: HTTP 401 Unauthorized")
                
            if resp.status_code == 429:
                from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage="probe", prompt_tokens=0, completion_tokens=0, status="429", http_status=429, elapsed_ms=int((time.monotonic() - _t0) * 1000), wait_ms=int(retries[attempt]*1000) if attempt < len(retries) else 0)
                if attempt < len(retries):
                    await asyncio.sleep(retries[attempt])
                    continue
                else:
                    raise ProviderProbeFailedError(f"Probe failed hard: HTTP 429")
                    
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage="probe", prompt_tokens=usage.get("prompt_tokens",0), completion_tokens=usage.get("completion_tokens",0), status="ok", http_status=200, elapsed_ms=int((time.monotonic() - _t0) * 1000))
                return
                
            from zara.utils import quota; quota.record("groq", GROQ_MODEL, stage="probe", prompt_tokens=0, completion_tokens=0, status="error", http_status=resp.status_code, elapsed_ms=int((time.monotonic() - _t0) * 1000))
            raise Exception(f"HTTP {resp.status_code}")
        except ProviderAuthError:
            raise
        except Exception as e:
            if attempt < len(retries):
                await asyncio.sleep(retries[attempt])
            else:
                raise ProviderProbeFailedError(f"Probe failed after retries: {e}")
