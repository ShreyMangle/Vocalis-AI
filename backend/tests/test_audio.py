"""
tests/test_audio.py — Unit Tests for G.711 mu-law Audio Transcoder & VAD Engine
"""

from app.voice.audio_utils import (
    MulawVADDetector,
    calculate_mulaw_rms,
    mulaw_to_pcm16_bytes,
    pcm16_to_mulaw_bytes,
)


def test_mulaw_pcm16_roundtrip():
    # 160 samples (20ms at 8kHz) of silence (0)
    pcm_zeros = b"\x00\x00" * 160
    mulaw = pcm16_to_mulaw_bytes(pcm_zeros)
    assert len(mulaw) == 160

    # Convert back to PCM
    pcm_recovered = mulaw_to_pcm16_bytes(mulaw)
    assert len(pcm_recovered) == 320  # 160 samples * 2 bytes


def test_calculate_mulaw_rms():
    # Test silence
    pcm_zeros = b"\x00\x00" * 80
    mulaw_silence = pcm16_to_mulaw_bytes(pcm_zeros)
    rms_silence = calculate_mulaw_rms(mulaw_silence)
    assert rms_silence < 50.0

    # Test loud signal
    pcm_loud = b"\x00\x40" * 80  # high amplitude 16-bit values
    mulaw_loud = pcm16_to_mulaw_bytes(pcm_loud)
    rms_loud = calculate_mulaw_rms(mulaw_loud)
    assert rms_loud > 1000.0


def test_mulaw_vad_detector_silence_and_speech():
    vad = MulawVADDetector(energy_threshold=500.0, silence_duration_ms=40, frame_duration_ms=20)

    # 1. Feed silence
    silence_frame = pcm16_to_mulaw_bytes(b"\x00\x00" * 160)
    res1 = vad.process_chunk(silence_frame)
    assert res1["is_speaking"] is False
    assert res1["speech_started"] is False

    # 2. Feed loud speech frame
    loud_frame = pcm16_to_mulaw_bytes(b"\x00\x40" * 160)
    res2 = vad.process_chunk(loud_frame)
    assert res2["is_speaking"] is True
    assert res2["speech_started"] is True

    # 3. Feed silence chunks until speech_ended triggers
    res3 = vad.process_chunk(silence_frame)
    assert res3["speech_ended"] is False
    res4 = vad.process_chunk(silence_frame)
    assert res4["speech_ended"] is True
    assert res4["buffered_pcm"] is not None


def test_mulaw_vad_detector_reset():
    vad = MulawVADDetector(energy_threshold=500.0)
    loud_frame = pcm16_to_mulaw_bytes(b"\x00\x40" * 160)
    vad.process_chunk(loud_frame)
    assert vad.is_speaking is True

    vad.reset()
    assert vad.is_speaking is False
    assert len(vad.audio_buffer) == 0
