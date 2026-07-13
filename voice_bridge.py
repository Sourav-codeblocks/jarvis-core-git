"""Founder's Core voice bridge — streams mic audio to Deepgram's live
speech-to-text and routes the final transcript through the same founder
tool registry used by the chat path (see founder_ws.py).

This is the "full path" from the WebSocket discussion: raw audio leaves
the browser, crosses this gateway, and only text + JSON ever come back —
no audio ever needs to touch a third party from the browser's side, and
provider keys never leave the server.

Setup required:
    pip install websockets --break-system-packages
    Add to .env:  DEEPGRAM_API_KEY=your_key_here

Wiring (same pattern as founder_ws.py):
    from voice_bridge import router as voice_router
    app.include_router(voice_router)

Model choice: nova-3 with language=multi lets one stream handle mixed
English/Hindi speech without pre-selecting a language — verified against
Deepgram's current docs (multilingual Nova-3, July 2026). Numeral
formatting for Hindi under smart_format is a known gap upstream, not a
bug here — plain words still transcribe fine.
"""

import asyncio
import json
import os

import websockets
from dotenv import load_dotenv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db_client import resolve_tenant, UnknownTenant
from founder_ws import route_founder_query

load_dotenv()  # self-sufficient: don't depend on main.py's import order

router = APIRouter()

DEEPGRAM_API_KEY = os.environ["DEEPGRAM_API_KEY"]
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3&language=multi&smart_format=true"
    "&interim_results=true&punctuate=true"
)


async def _connect_deepgram():
    """websockets' header kwarg was renamed (extra_headers -> additional_headers)
    across versions — try the current name first, fall back for older installs."""
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
    try:
        return await websockets.connect(DEEPGRAM_URL, additional_headers=headers)
    except TypeError:
        return await websockets.connect(DEEPGRAM_URL, extra_headers=headers)


@router.websocket("/ws/founder/{tenant_slug}/voice")
async def founder_voice_socket(websocket: WebSocket, tenant_slug: str):
    # Resolve before accepting: no point opening a Deepgram connection
    # (which costs money the moment it's live) for a tenant_slug that
    # doesn't exist. Same fix as founder_ws.py's chat socket — this path
    # took a tenant_slug in the URL but ignored it in favor of tenant_id=1.
    try:
        tenant = resolve_tenant(tenant_slug)
    except UnknownTenant:
        await websocket.close(code=4404, reason=f"Unknown tenant: {tenant_slug}")
        return

    await websocket.accept()

    dg_ws = await _connect_deepgram()

    async def pump_audio_to_deepgram():
        """Forward every binary chunk from the browser straight to Deepgram."""
        while True:
            chunk = await websocket.receive_bytes()
            await dg_ws.send(chunk)

    async def pump_transcripts_to_client():
        """Read Deepgram's live results; route a completed utterance as a query."""
        async for raw in dg_ws:
            msg = json.loads(raw)
            if msg.get("type") != "Results":
                continue

            alt = msg["channel"]["alternatives"][0]
            transcript = alt["transcript"].strip()
            if not transcript:
                continue

            is_final = msg.get("is_final", False)
            await websocket.send_json(
                {"type": "transcript", "text": transcript, "is_final": is_final}
            )

            # speech_final = Deepgram thinks the speaker finished their turn,
            # not just that this chunk's wording is locked in.
            if is_final and msg.get("speech_final"):
                await websocket.send_json({"type": "status", "content": "thinking"})
                result = await route_founder_query(transcript, tenant["id"])
                await websocket.send_json(
                    {
                        "type": "response",
                        "spokenAnswer": result["spokenAnswer"],
                        "overlay": result["overlay"],
                    }
                )

    try:
        await asyncio.gather(pump_audio_to_deepgram(), pump_transcripts_to_client())
    except WebSocketDisconnect:
        pass
    except Exception as err:  # Deepgram hiccup, malformed frame, etc.
        print(f"Voice bridge error: {err}")
    finally:
        await dg_ws.close()
