"""List Gemini models actually available for your key right now.
Gemini's lineup has moved fast in 2026 (2.0 shut down June 1, 3.x already
out) — rather than guess the next name and hit another 404, ask the API
directly what your key can use.

Usage:
    python list_gemini_models.py
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    print("GEMINI_API_KEY not found in .env")
    raise SystemExit(1)

resp = httpx.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    params={"key": key},
    timeout=30,
)
print(f"HTTP status: {resp.status_code}\n")

if resp.status_code != 200:
    print(resp.text)
    raise SystemExit(1)

data = resp.json()
print("Models supporting generateContent:\n")
for m in data.get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(f"  {m['name']}")
