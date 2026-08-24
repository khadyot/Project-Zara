import re
with open("zara/utils/provider.py", "r") as f:
    code = f.read()
code = code.replace(
    'payload = {\n        "model": "groq/compound",',
    'payload = {\n        "model": "groq/compound",\n\n    import tiktoken\n    enc = tiktoken.get_encoding("cl100k_base")\n    plen = len(enc.encode(schema_prompt + system_instruction))\n    print(f"PROMPT LENGTH: {plen} tokens", file=sys.stderr)'
)
with open("zara/utils/provider.py", "w") as f:
    f.write(code)
