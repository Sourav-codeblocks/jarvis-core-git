"""Jarvis Core — debug the judge chain in isolation.

Makes one raw judge call to Gemini, then one to Groq (skips any provider
with no key configured), and prints either the real response or the FULL
exception — nothing gets silently swallowed here, unlike inside the graph's
tier2_judge node where errors are caught and turned into a 1/1/1/1/1
fallback score by design.

Usage:
    python debug_judge.py
"""

import os
from dotenv import load_dotenv

import llm_router

load_dotenv()

TEST_PROMPT = """You are grading a test response. Score it 1-3 on correctness.
User Request: "What is 2+2?"
System Output: "4"
Respond with ONLY valid JSON: {"correctness": 1}"""


def try_provider(provider_name: str, providers: dict):
    print(f"\n--- Testing {provider_name} ---")
    key_env = {
        "gemini_api": "GEMINI_API_KEY",
        "groq_api": "GROQ_API_KEY",
        "anthropic_api": "ANTHROPIC_API_KEY",
    }.get(provider_name)
    key_present = bool(os.environ.get(key_env, "")) if key_env else True
    print(f"  {key_env} set: {key_present}")
    if not key_present:
        print("  SKIPPING — no key in .env")
        return

    try:
        result, used_provider, used_model = llm_router.call_judge(
            TEST_PROMPT, providers, only_provider=provider_name
        )
        text, usage = result
        print(f"  SUCCESS via {used_provider}/{used_model}")
        print(f"  Raw response: {text!r}")
        print(f"  Usage: {usage}")
    except Exception as err:
        print(f"  FAILED: {type(err).__name__}: {err}")


if __name__ == "__main__":
    providers = llm_router.default_providers()
    try_provider("gemini_api", providers)
    try_provider("groq_api", providers)
    try_provider("anthropic_api", providers)
