# Native G.711 µ-law (PCMU) 8kHz Audio Transcoder & VAD Engine
import math
import struct

# Pre-computed G.711 mu-law to 16-bit linear PCM lookup table (256 entries)
MULAW_TO_PCM16 = []
for i in range(256):
    mu = ~i & 0xFF
    sign = -1 if (mu & 0x80) else 1
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = (mantissa << (exponent + 3)) + (132 << exponent) - 132
    if sign < 0:
        sample = -sample
    # Clamp to 16-bit signed integer boundaries (-32768 to 32767)
    sample = max(-32768, min(32767, sample))
    MULAW_TO_PCM16.append(sample)

def mulaw_to_pcm16_bytes(mulaw_bytes: bytes) -> bytes:
    """Converts 8kHz G.711 mulaw byte stream directly into 16-bit PCM bytes."""
    pcm_samples = [MULAW_TO_PCM16[b] for b in mulaw_bytes]
    return struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)

def calculate_mulaw_rms(mulaw_bytes: bytes) -> float:
    """Computes RMS audio energy directly from G.711 mulaw byte stream using precomputed lookup table."""
    count = len(mulaw_bytes)
    if count == 0:
        return 0.0
    sum_squares = sum(MULAW_TO_PCM16[b] * MULAW_TO_PCM16[b] for b in mulaw_bytes)
    return math.sqrt(sum_squares / count)

class MulawVADDetector:
    """
    High-performance Voice Activity Detector (VAD) for 8kHz audio streams.
    Tracks speech energy, barge-in interruptions, and silence thresholds.
    """
    def __init__(self, energy_threshold: float = 600.0, silence_duration_ms: int = 800, frame_duration_ms: int = 20):
        self.energy_threshold = energy_threshold
        self.silence_threshold_chunks = max(5, int(silence_duration_ms / frame_duration_ms))
        
        self.is_speaking = False
        self.silent_chunks = 0
        self.audio_buffer = bytearray()

    def process_chunk(self, mulaw_chunk: bytes) -> dict:
        """
        Processes an incoming 8kHz mulaw frame.
        Returns state dict: {"is_speaking": bool, "speech_started": bool, "speech_ended": bool, "buffered_pcm": bytes or None}
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
            "buffered_pcm": buffered_pcm
        }

    def reset(self):
        self.is_speaking = False
        self.silent_chunks = 0
        self.audio_buffer.clear()
