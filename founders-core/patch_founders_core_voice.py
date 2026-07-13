"""Run this from inside the founders-core/ directory:
    python3 patch_founders_core_voice.py
Patches dataAdapter.ts and voice.ts to use VITE_GATEWAY_URL instead of
hardcoded localhost:8000, so the built app can reach the real gateway."""

# --- dataAdapter.ts ---
path = "src/lib/dataAdapter.ts"
src = open(path).read()

old = 'const GATEWAY_WS_URL = "ws://localhost:8000/ws/founder/kesari-pipes";'
assert old in src, f"ANCHOR NOT FOUND in {path}"
new = (
    'const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000";\n'
    'const GATEWAY_WS_URL = `${GATEWAY_URL.replace(/^http/, "ws")}/ws/founder/kesari-pipes`;'
)
src = src.replace(old, new, 1)
open(path, "w").write(src)
print(f"Patched {path}")

# --- voice.ts ---
path = "src/lib/voice.ts"
src = open(path).read()

old_tts = 'const TTS_URL = "http://localhost:8000/tts/founder";'
assert old_tts in src, f"ANCHOR (TTS_URL) NOT FOUND in {path}"
new_tts = (
    'const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000";\n'
    'const TTS_URL = `${GATEWAY_URL}/tts/founder`;'
)
src = src.replace(old_tts, new_tts, 1)

old_ws = 'const VOICE_WS_URL = "ws://localhost:8000/ws/founder/kesari-pipes/voice";'
assert old_ws in src, f"ANCHOR (VOICE_WS_URL) NOT FOUND in {path}"
new_ws = 'const VOICE_WS_URL = `${GATEWAY_URL.replace(/^http/, "ws")}/ws/founder/kesari-pipes/voice`;'
src = src.replace(old_ws, new_ws, 1)

open(path, "w").write(src)
print(f"Patched {path}")

print("Done.")
