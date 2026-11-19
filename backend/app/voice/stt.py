"""
app/voice/stt.py — Multi-Provider Speech-to-Text (STT) Engine

Transcribes incoming PCM voice buffers using:
  1. Groq Whisper (ultra-fast <200ms latency on Whisper-large-v3)
  2. Deepgram Nova-3 (streaming/rest STT)
  3. OpenAI Whisper
  4. Testing simulation fallback
"""

import io
import time
import wave
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 8000, channels: int = 1) -> bytes:
    """Pack raw 16-bit linear PCM byte buffer into valid WAV container."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return wav_io.getvalue()


async def transcribe_audio_pcm(
    pcm_bytes: bytes,
    sample_rate: int = 8000,
    language: str = "en",
    client: httpx.AsyncClient | None = None,
) -> tuple[str, int]:
    """
    Transcribe raw 16-bit PCM audio.
    Returns: (transcribed_text, latency_ms)
    """
    # Discard audio clips under 0.25 seconds (accidental clicks / background noise)
    min_bytes = int(sample_rate * 2 * 0.25)
    if len(pcm_bytes) < min_bytes:
        return "", 0

    wav_bytes = pcm_to_wav_bytes(pcm_bytes, sample_rate=sample_rate)
    start_time = time.perf_counter()

    # 1. Groq Whisper (Primary low-latency STT)
    if settings.GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
            data = {"model": "whisper-large-v3", "response_format": "json"}

            async def _post(c: httpx.AsyncClient):
                return await c.post(url, headers=headers, files=files, data=data, timeout=8.0)

            if client:
                resp = await _post(client)
            else:
                async with httpx.AsyncClient() as c:
                    resp = await _post(c)

            if resp.status_code == 200:
                transcript = resp.json().get("text", "").strip()
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.info("STT transcription success (Groq)", text=transcript, latency_ms=latency_ms)
                return transcript, latency_ms
        except Exception as e:
            logger.warning("Groq Whisper transcription failed, attempting fallback", error=str(e))

    # 2. Deepgram Nova
    if settings.DEEPGRAM_API_KEY:
        try:
            url = f"https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&encoding=linear16&sample_rate={sample_rate}"
            headers = {
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": "audio/wav",
            }

            async def _dg_post(c: httpx.AsyncClient):
                return await c.post(url, headers=headers, content=wav_bytes, timeout=8.0)

            if client:
                resp = await _dg_post(client)
            else:
                async with httpx.AsyncClient() as c:
                    resp = await _dg_post(c)

            if resp.status_code == 200:
                res_data = resp.json()
                channels_data = res_data.get("results", {}).get("channels", [])
                if channels_data:
                    transcript = (
                        channels_data[0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                        .strip()
                    )
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    return transcript, latency_ms
        except Exception as e:
            logger.warning("Deepgram STT failed, attempting fallback", error=str(e))

    # 3. OpenAI Whisper
    if settings.OPENAI_API_KEY:
        try:
            url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
            data = {"model": "whisper-1", "response_format": "json"}

            async def _oai_post(c: httpx.AsyncClient):
                return await c.post(url, headers=headers, files=files, data=data, timeout=8.0)

            if client:
                resp = await _oai_post(client)
            else:
                async with httpx.AsyncClient() as c:
                    resp = await _oai_post(c)

            if resp.status_code == 200:
                transcript = resp.json().get("text", "").strip()
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                return transcript, latency_ms
        except Exception as e:
            logger.warning("OpenAI Whisper STT failed", error=str(e))

    # Offline / Mock fallback (e.g. for development or testing)
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    logger.debug("STT running in development mode (no external keys responded)")
    return "", latency_ms
