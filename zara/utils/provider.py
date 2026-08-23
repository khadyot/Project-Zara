import os
import sys
import re
import asyncio
import json
import hashlib
import httpx

class ProviderProbeFailedError(Exception):
    pass

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
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise ProviderAuthError("GROQ_API_KEY is missing from environment variables.")
    return key

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

def _record_fixture(prompt: str, system_instruction: str, content: str):
    h = hashlib.md5((prompt + system_instruction).encode()).hexdigest()
    fixture_path = f"tests/fixtures/{h}.json"
    os.makedirs("tests/fixtures", exist_ok=True)
    with open(fixture_path, "w") as f:
        f.write(content)

def _parse_content(content: str, schema):
    try:
        return schema.model_validate_json(content)
    except Exception:
        salvaged = extract_json(content)
        if salvaged is not None:
            return schema.model_validate(salvaged)
        raise

async def _generate_gemini(prompt: str, schema, system_instruction: str, schema_dict: dict):
    api_key = _get_gemini_api_key()

    schema_prompt = (
        f"{prompt}\n\n"
        f"You must respond with a single JSON object matching this JSON schema exactly "
        f"(all properties required, no additional properties):\n"
        f"{json.dumps(schema_dict, indent=2)}"
    )

    payload = {
        "model": "gemini-flash-latest",
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
        raise ProviderProbeFailedError(f"Gemini fallback failed: {resp.status_code} {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise ProviderProbeFailedError("Gemini fallback returned empty content")

    _record_fixture(prompt, system_instruction, content)
    return _parse_content(content, schema)

async def generate_content_with_retry(prompt: str, schema, system_instruction: str) -> any:
    if os.environ.get("USE_FIXTURES"):
        # Store or load from tests/fixtures/ based on hash of prompt + instruction
        h = hashlib.md5((prompt + system_instruction).encode()).hexdigest()
        fixture_path = f"tests/fixtures/{h}.json"
        if not os.path.exists(fixture_path):
            raise FileNotFoundError(f"Fixture not found for prompt hash {h}. Please record this fixture first.")
        with open(fixture_path, "r") as f:
            data = json.load(f)
        return schema(**data)
        
    api_key = _get_api_key()

    schema_dict = schema.model_json_schema()
    walk_schema(schema_dict)

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema_dict,
                "strict": True
            }
        },
        "temperature": 0.0
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    retries = [2, 4, 60]
    groq_error = None

    for attempt in range(4):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=60.0)

            if resp.status_code == 401:
                raise ProviderAuthError(f"HTTP 401 Unauthorized: {resp.text}")

            if resp.status_code == 429:
                if attempt < len(retries):
                    print(f"WARNING: Groq 429 Rate Limit, retrying in {retries[attempt]}s", file=sys.stderr)
                    await asyncio.sleep(retries[attempt])
                    continue
                else:
                    raise ProviderProbeFailedError(f"Model failed hard: {resp.status_code} {resp.text}")

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            if not content or not content.strip():
                raise Exception("Empty content from Groq")

            # Save fixture if not using fixtures (recording)
            if not os.environ.get("USE_FIXTURES"):
                _record_fixture(prompt, system_instruction, content)

            return schema.model_validate_json(content)

        except ProviderAuthError as e:
            groq_error = e
            break
        except Exception as e:
            if "401" in str(e):
                groq_error = ProviderAuthError(str(e))
                break

            if attempt < len(retries):
                print(f"WARNING: Model failed, retrying in {retries[attempt]}s. Error: {e}", file=sys.stderr)
                await asyncio.sleep(retries[attempt])
            else:
                groq_error = ProviderProbeFailedError(f"Model failed after retries: {e}")

    print(f"WARNING: Groq failed, falling back to Gemini. Error: {groq_error}", file=sys.stderr)
    try:
        return await _generate_gemini(prompt, schema, system_instruction, schema_dict)
    except Exception as gemini_error:
        print(f"WARNING: Gemini failed, falling back to Z.ai. Error: {gemini_error}", file=sys.stderr)
        try:
            return await _generate_zai(prompt, schema, system_instruction, schema_dict)
        except Exception:
            if groq_error is not None:
                raise groq_error
            raise


async def _generate_zai(prompt: str, schema, system_instruction: str, schema_dict: dict):
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
        "model": "glm-4.5-flash",
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
        raise ProviderProbeFailedError(f"Z.ai fallback failed: {resp.status_code} {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"]
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    content = content.strip()
    if not content:
        raise ProviderProbeFailedError("Z.ai fallback returned empty content")

    _record_fixture(prompt, system_instruction, content)
    return _parse_content(content, schema)

async def run_probe():
    # Only for the startup check
    if os.environ.get("USE_FIXTURES"):
        return
        
    api_key = _get_api_key()
    
    payload = {
        "model": "openai/gpt-oss-120b",
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
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10.0)
                
            if resp.status_code == 401:
                raise ProviderAuthError(f"Probe failed hard: HTTP 401 Unauthorized")
                
            if resp.status_code == 429:
                if attempt < len(retries):
                    await asyncio.sleep(retries[attempt])
                    continue
                else:
                    raise ProviderProbeFailedError(f"Probe failed hard: HTTP 429")
                    
            if resp.status_code == 200:
                return
                
            raise Exception(f"HTTP {resp.status_code}")
        except ProviderAuthError:
            raise
        except Exception as e:
            if attempt < len(retries):
                await asyncio.sleep(retries[attempt])
            else:
                raise ProviderProbeFailedError(f"Probe failed after retries: {e}")
