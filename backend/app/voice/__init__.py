"""
app/voice package — Voice Pipeline, VAD, STT, TTS & Media Stream Handlers.
"""

from app.voice.audio_utils import (
    MulawVADDetector,
    calculate_mulaw_rms,
    mulaw_to_pcm16_bytes,
    pcm16_to_mulaw_bytes,
)
from app.voice.pipeline import VoicePipeline, split_into_sentences
from app.voice.session import CallSession
from app.voice.stt import pcm_to_wav_bytes, transcribe_audio_pcm
from app.voice.tts import generate_mock_mulaw_tone, synthesize_speech

__all__ = [
    "MulawVADDetector",
    "calculate_mulaw_rms",
    "mulaw_to_pcm16_bytes",
    "pcm16_to_mulaw_bytes",
    "CallSession",
    "VoicePipeline",
    "split_into_sentences",
    "transcribe_audio_pcm",
    "pcm_to_wav_bytes",
    "synthesize_speech",
    "generate_mock_mulaw_tone",
]
