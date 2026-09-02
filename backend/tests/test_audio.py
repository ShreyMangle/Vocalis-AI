from app.audio_utils import (
    mulaw_to_pcm16_bytes, 
    pcm16_to_mulaw_bytes, 
    calculate_mulaw_rms, 
    MulawVADDetector
)
import struct

def test_mulaw_to_pcm16_conversion():
    # 160 bytes of mulaw audio (20ms at 8kHz)
    mulaw_silence = b'\xff' * 160
    pcm16 = mulaw_to_pcm16_bytes(mulaw_silence)
    
    assert len(pcm16) == 320 # 160 samples * 2 bytes/sample
    assert isinstance(pcm16, bytes)

def test_pcm16_to_mulaw_conversion():
    # 160 samples of 16-bit PCM (320 bytes)
    samples = [0] * 160
    pcm_silence = struct.pack(f"<{len(samples)}h", *samples)
    mulaw = pcm16_to_mulaw_bytes(pcm_silence)
    
    assert len(mulaw) == 160
    assert mulaw == b'\xff' * 160

def test_mulaw_roundtrip_fidelity():
    test_samples = [0, 100, 1000, 5000, 15000, -100, -1000, -5000, -15000]
    pcm_bytes = struct.pack(f"<{len(test_samples)}h", *test_samples)
    mulaw = pcm16_to_mulaw_bytes(pcm_bytes)
    recovered_pcm = mulaw_to_pcm16_bytes(mulaw)
    recovered_samples = struct.unpack(f"<{len(test_samples)}h", recovered_pcm)
    
    for orig, rec in zip(test_samples, recovered_samples):
        # Mu-law 8-bit quantization error should be under 2% of sample amplitude or <= 150
        assert abs(orig - rec) <= max(150, abs(orig) * 0.05)

def test_calculate_mulaw_rms():
    # Silence (0xff in mulaw is zero amplitude)
    mulaw_silence = b'\xff' * 160
    rms_silence = calculate_mulaw_rms(mulaw_silence)
    assert rms_silence < 50.0

    # Louder signal pattern
    mulaw_loud = b'\x00\x80' * 80 # Peak amplitudes in mulaw
    rms_loud = calculate_mulaw_rms(mulaw_loud)
    assert rms_loud > 500.0

def test_vad_detector_transitions():
    vad = MulawVADDetector(energy_threshold=400.0, silence_duration_ms=600)
    assert vad.is_speaking is False

    # Simulate quiet background
    for _ in range(5):
        res = vad.process_chunk(b'\xff' * 160)
        assert res["speech_started"] is False
        assert res["speech_ended"] is False
        assert vad.is_speaking is False

    # Simulate loud speech start
    loud_chunk = b'\x00\x80' * 80
    res = vad.process_chunk(loud_chunk)
    assert res["speech_started"] is True
    assert res["is_speaking"] is True
    assert vad.is_speaking is True

    # Continue speaking
    res = vad.process_chunk(loud_chunk)
    assert res["speech_started"] is False
    assert vad.is_speaking is True

    # Simulate 700ms silence (35 chunks of 20ms) to trigger speech_end
    ended = False
    for _ in range(35):
        res = vad.process_chunk(b'\xff' * 160)
        if res["speech_ended"]:
            ended = True
            assert res["buffered_pcm"] is not None
            break
            
    assert ended is True
    assert vad.is_speaking is False
