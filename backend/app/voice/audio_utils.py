"""
app/voice/audio_utils.py — Audio Transcoding & Voice Activity Detection (VAD)

Ultra-fast G.711 mu-law (8kHz PCMU) transcoder and audio energy detector.
Used by Twilio/VoBiz telephony media streams and browser sandbox WebSocket.
"""

import math
import struct
from typing import Any

# ── Pre-computed G.711 mu-law to 16-bit linear PCM lookup table (256 entries) ─
MULAW_TO_PCM16: list[int] = []
for i in range(256):
    mu = ~i & 0xFF
    sign = -1 if (mu & 0x80) else 1
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = (mantissa << (exponent + 3)) + (132 << exponent) - 132
    if sign < 0:
        sample = -sample
    sample = max(-32768, min(32767, sample))
    MULAW_TO_PCM16.append(sample)


# ── Pre-computed 16-bit linear PCM to G.711 mu-law lookup table (65536 entries)
def _pcm16_to_mulaw_sample(pcm_val: int) -> int:
    BIAS = 0x84
    CLIP = 32635
    sign = 0
    if pcm_val < 0:
        pcm_val = -pcm_val
        sign = 0x80
    if pcm_val > CLIP:
        pcm_val = CLIP
    pcm_val += BIAS
    exponent = 7
    mask = 0x4000
    while (pcm_val & mask) == 0 and exponent > 0:
        exponent -= 1
        mask >>= 1
    mantissa = (pcm_val >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


PCM16_TO_MULAW = bytes([_pcm16_to_mulaw_sample(i - 32768) for i in range(65536)])


def mulaw_to_pcm16_bytes(mulaw_bytes: bytes) -> bytes:
    """Converts 8kHz G.711 mulaw byte stream into 16-bit linear PCM bytes."""
    pcm_samples = [MULAW_TO_PCM16[b] for b in mulaw_bytes]
    return struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)


def pcm16_to_mulaw_bytes(pcm_bytes: bytes) -> bytes:
    """Converts 16-bit linear PCM byte stream to 8-bit G.711 mulaw byte stream."""
    sample_count = len(pcm_bytes) // 2
    if sample_count == 0:
        return b""
    shorts = struct.unpack(f"<{sample_count}h", pcm_bytes)
    return bytes([PCM16_TO_MULAW[s + 32768] for s in shorts])


def calculate_mulaw_rms(mulaw_bytes: bytes) -> float:
    """Computes RMS audio energy from G.711 mulaw byte stream using lookup table."""
    count = len(mulaw_bytes)
    if count == 0:
        return 0.0
    sum_squares = sum(MULAW_TO_PCM16[b] * MULAW_TO_PCM16[b] for b in mulaw_bytes)
    return math.sqrt(sum_squares / count)


class MulawVADDetector:
    """
    Voice Activity Detector (VAD) for 8kHz audio streams.
    Tracks caller speech bursts, barge-in interruptions, and speech conclusion.
    """

    def __init__(
        self,
        energy_threshold: float = 600.0,
        silence_duration_ms: int = 800,
        frame_duration_ms: int = 20,
    ):
        self.energy_threshold = energy_threshold
        self.silence_threshold_chunks = max(1, int(silence_duration_ms / frame_duration_ms))

        self.is_speaking = False
        self.silent_chunks = 0
        self.audio_buffer = bytearray()

    def process_chunk(self, mulaw_chunk: bytes) -> dict[str, Any]:
        """
        Process an incoming 8kHz mulaw frame.
        Returns dict with:
          rms: float
          is_speaking: bool
          speech_started: bool
          speech_ended: bool
          buffered_pcm: bytes | None
        """
        rms = calculate_mulaw_rms(mulaw_chunk)
        speech_started = False
        speech_ended = False
        buffered_pcm = None

        if rms > self.energy_threshold:
            if not self.is_speaking:
                self.is_speaking = True
                speech_started = True

            self.silent_chunks = 0
            self.audio_buffer.extend(mulaw_to_pcm16_bytes(mulaw_chunk))
        else:
            if self.is_speaking:
                self.audio_buffer.extend(mulaw_to_pcm16_bytes(mulaw_chunk))
                self.silent_chunks += 1

                if self.silent_chunks >= self.silence_threshold_chunks:
                    self.is_speaking = False
                    speech_ended = True
                    buffered_pcm = bytes(self.audio_buffer)
                    self.audio_buffer.clear()
                    self.silent_chunks = 0

        return {
            "rms": rms,
            "is_speaking": self.is_speaking,
            "speech_started": speech_started,
            "speech_ended": speech_ended,
            "buffered_pcm": buffered_pcm,
        }

    def reset(self) -> None:
        """Reset internal state."""
        self.is_speaking = False
        self.silent_chunks = 0
        self.audio_buffer.clear()
