"""Founder's Core TTS — converts text into speech via Deepgram's Aura-2
REST API, proxied through the gateway so the browser never holds the
Deepgram API key directly.

Reuses the same DEEPGRAM_API_KEY as voice_bridge.py — one Deepgram
account covers both STT (mic in) and TTS (voice out).

Wiring (same pattern as founder_ws.py / voice_bridge.py):
    from tts import router as tts_router
    app.include_router(tts_router)
"""

import os

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

load_dotenv()  # self-sufficient, same reasoning as voice_bridge.py

router = APIRouter()

DEEPGRAM_API_KEY = os.environ["DEEPGRAM_API_KEY"]
# aura-2-helena-en: a clear, professional voice — swap the model name to
# try others from Deepgram's voice list without touching any other code.
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak?model=aura-2-helena-en"


class SpeakRequest(BaseModel):
    text: str


@router.post("/tts/founder")
async def synthesize_speech(req: SpeakRequest):
    """Text in, MP3 audio out. Errors bubble up as the underlying HTTP
    status so the frontend's fetch().ok check catches them cleanly."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DEEPGRAM_TTS_URL,
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"text": req.text},
        )
        resp.raise_for_status()
        return Response(content=resp.content, media_type="audio/mpeg")
