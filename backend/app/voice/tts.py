"""
app/voice/tts.py — Multi-Provider Text-to-Speech (TTS) Engine

Synthesizes conversational spoken sentences into 8kHz audio streams.
Supports:
  1. Cartesia Sonic (ultra-low latency ~40ms first audio byte)
  2. Deepgram Aura
  3. Development / Mock synthesis for testing
"""

import math
import struct
import time
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.voice.audio_utils import pcm16_to_mulaw_bytes

logger = structlog.get_logger(__name__)


def generate_mock_mulaw_tone(duration_ms: int = 500, frequency: float = 440.0) -> bytes:
    """Generate a simple sine tone in 8kHz G.711 mu-law for offline test streams."""
    sample_rate = 8000
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    pcm_samples = []
    for i in range(num_samples):
        # 16-bit sine wave scaled to 25% amplitude
        val = int(8000 * math.sin(2 * math.pi * frequency * (i / sample_rate)))
        pcm_samples.append(val)
    pcm_bytes = struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)
    return pcm16_to_mulaw_bytes(pcm_bytes)


async def synthesize_speech(
    text: str,
    voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
    provider: str = "cartesia",
    speech_speed: float = 1.0,
    client: httpx.AsyncClient | None = None,
) -> tuple[bytes, int]:
    """
    Synthesizes text into 8kHz G.711 mu-law audio bytes.
    Returns: (mulaw_audio_bytes, latency_ms)
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return b"", 0

    start_time = time.perf_counter()

    # 1. Cartesia Sonic TTS (Primary high-performance engine)
    if settings.CARTESIA_API_KEY:
        try:
            url = "https://api.cartesia.ai/tts/bytes"
            headers = {
                "X-API-Key": settings.CARTESIA_API_KEY,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json",
            }
            body = {
                "transcript": cleaned_text,
                "model_id": "sonic-english",
                "voice": {"mode": "id", "id": voice_id},
                "output_format": {
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": 8000,
                },
            }

            async def _cartesia_call(c: httpx.AsyncClient):
                return await c.post(url, json=body, headers=headers, timeout=5.0)

            if client:
                resp = await _cartesia_call(client)
            else:
                async with httpx.AsyncClient() as c:
                    resp = await _cartesia_call(c)

            if resp.status_code == 200:
                raw_pcm = resp.content
                mulaw_bytes = pcm16_to_mulaw_bytes(raw_pcm)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.info("TTS synthesis success (Cartesia)", latency_ms=latency_ms, length=len(mulaw_bytes))
                return mulaw_bytes, latency_ms
        except Exception as e:
            logger.warning("Cartesia TTS synthesis failed, attempting fallback", error=str(e))

    # 2. Deepgram Aura TTS
    if settings.DEEPGRAM_API_KEY:
        try:
            deepgram_voice = voice_id if "aura" in voice_id else "aura-asteria-en"
            url = f"https://api.deepgram.com/v1/speak?model={deepgram_voice}&encoding=mulaw&sample_rate=8000"
            headers = {
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": "application/json",
            }
            body = {"text": cleaned_text}

            async def _dg_call(c: httpx.AsyncClient):
                return await c.post(url, json=body, headers=headers, timeout=5.0)

            if client:
                resp = await _dg_call(client)
            else:
                async with httpx.AsyncClient() as c:
                    resp = await _dg_call(c)

            if resp.status_code == 200:
                mulaw_bytes = resp.content
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                return mulaw_bytes, latency_ms
        except Exception as e:
            logger.warning("Deepgram TTS synthesis failed", error=str(e))

    # Offline / Test fallback: generate lightweight synthetic response tone
    duration = min(1200, max(300, len(cleaned_text) * 30))
    mulaw_bytes = generate_mock_mulaw_tone(duration_ms=duration)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return mulaw_bytes, latency_ms
