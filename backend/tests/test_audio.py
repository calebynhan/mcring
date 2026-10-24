import struct

import pytest

from mcring_core import adpcm as adpcm_codec

from app import audio

from conftest import sine_pcm, zero_crossings


@pytest.mark.parametrize("use_numpy", [True, False])
def test_resample_24k_to_16k_length_and_pitch(monkeypatch, use_numpy):
    if use_numpy:
        pytest.importorskip("numpy")
    else:
        monkeypatch.setattr(audio, "_np", None)
    pcm = sine_pcm(440, 24000, 1.0)
    out = audio.resample(pcm, 24000, 16000)
    assert len(out) == 16000
    # a 440 Hz tone crosses zero 880 times per second whatever the rate
    assert abs(zero_crossings(out) - 880) <= 4
    # amplitude preserved (within a few percent) and nothing clipped
    assert 11000 <= max(out) <= 12500 and min(out) >= -12500


def test_resample_identity_and_upsample():
    pcm = sine_pcm(1000, 16000, 0.1)
    assert audio.resample(pcm, 16000, 16000) == pcm
    up = audio.resample(pcm, 16000, 24000)
    assert len(up) == 2400
    assert abs(zero_crossings(up) - zero_crossings(pcm)) <= 2


def test_polyphase_attenuates_above_new_nyquist():
    pytest.importorskip("numpy")
    # 10 kHz is above 8 kHz Nyquist at 16 kHz: it must (mostly) disappear instead of aliasing to 6 kHz
    pcm = sine_pcm(10000, 24000, 0.5, amp=10000)
    out = audio.resample(pcm, 24000, 16000)
    assert max(abs(s) for s in out[500:-500]) < 1500


def test_linear_fallback_is_finite_and_in_range():
    pcm = [32767, -32768] * 100
    out = audio._resample_linear(pcm, 24000, 16000)
    assert len(out) == 133 and all(-32768 <= s <= 32767 for s in out)


def test_decode_pcm_and_wav():
    pcm = sine_pcm(300, 24000, 0.01)
    raw = struct.pack(f"<{len(pcm)}h", *pcm)
    got, rate = audio.decode_to_pcm(raw, "audio/pcm;rate=24000")
    assert got == pcm and rate == 24000
    got, rate = audio.decode_to_pcm(raw, "audio/pcm")
    assert rate == 24000                                   # default rate
    wav = adpcm_codec.pcm_to_wav(pcm, 22050)
    got, rate = audio.decode_to_pcm(wav, "audio/wav")
    assert got == pcm and rate == 22050
    got, rate = audio.decode_to_pcm(wav, "")               # sniffed via RIFF
    assert rate == 22050
    with pytest.raises(ValueError):
        audio.decode_to_pcm(b"ID3....", "audio/mpeg")


def test_wav_stereo_downmix():
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<4h", 1000, 3000, -2000, -4000))
    got, rate = audio.wav_to_pcm(buf.getvalue())
    assert got == [2000, -3000] and rate == 16000


def test_pcm_to_ring_adpcm_roundtrip_length():
    pcm = sine_pcm(500, 24000, 0.25)           # 6000 samples -> 4000 @16k -> 16 blocks (15.6 rounded up)
    blob = audio.pcm_to_ring_adpcm_from(pcm, 24000)
    assert len(blob) % audio.BLOCK_BYTES == 0 and audio.adpcm_blocks(blob) == 16
    assert audio.adpcm_duration_ms(blob) == 256
    dec = adpcm_codec.decode(blob)
    assert len(dec) == 16 * 256
    assert abs(zero_crossings(dec[:4000]) - 250) <= 6     # 500 Hz over 0.25 s


@pytest.mark.parametrize("data,filename,ct,expect", [
    (b"RIFF\x00\x00\x00\x00WAVEfmt ", "x.bin", "", "wav"),
    (b"\x00\x00\x00\x18ftypM4A ", "", "audio/mp4", "m4a"),
    (b"\x00\x00\x00\x18ftypisom", "clip.mp4", "", "m4a"),
    (b"ID3\x03\x00", "", "", "mp3"),
    (b"\xff\xfb\x90\x00", "", "", "mp3"),
    (b"OggS\x00", "", "", "ogg"),
    (b"fLaC\x00", "", "", "flac"),
    (b"\x1aE\xdf\xa3\x00", "", "", "webm"),
    (b"\x00" * 132, "voice.adpcm", "", "adpcm"),
    (b"\x00" * 264, "", "audio/x-mcring-adpcm", "adpcm"),
    (b"\x00" * 264, "", "", "adpcm"),               # headerless, whole 132-byte blocks
    (b"\x00" * 100, "", "", "unknown"),
    (b"\x00" * 100, "note.m4a", "", "m4a"),
    (b"\x00" * 100, "", "audio/x-m4a", "m4a"),
    # headerless ring clips whose first sample puts an MPEG sync word (FF Fx) in the block header
    (adpcm_codec.encode([-1] * 256), "", "", "adpcm"),
    (adpcm_codec.encode([-257] * 256), "", "", "adpcm"),
    (adpcm_codec.encode([-1] + [0] * 255 + [-513] + [0] * 255), "", "application/octet-stream", "adpcm"),
    # a bare MPEG frame that happens to be 132 bytes long is still mp3 (byte 2 > 88 / byte 3 != 0 break the ADPCM shape)
    (b"\xff\xfb\x90\x00" + b"\x55" * 128, "", "", "mp3"),
    (b"\xff\xfb\x90\x00" + b"\x00" * 128, "", "", "mp3"),
    # sync word with reserved layer / bad bitrate / reserved sample-rate fields is not an mp3 frame
    (b"\xff\xf9\x90\x00", "", "", "unknown"),
    (b"\xff\xfb\xf0\x00", "", "", "unknown"),
    (b"\xff\xfb\x9c\x00", "", "", "unknown"),
    (b"\xff\xeb\x90\x00", "", "", "unknown"),    # reserved MPEG version
])
def test_sniff_audio(data, filename, ct, expect):
    assert audio.sniff_audio(data, filename, ct) == expect


def test_is_ring_adpcm_checks_every_block():
    clip = bytearray(adpcm_codec.encode([-1] * 512))        # 2 blocks, both start FF FF
    assert audio.is_ring_adpcm(bytes(clip))
    clip[132 + 3] = 1                                        # reserved byte of block 2
    assert not audio.is_ring_adpcm(bytes(clip))
    clip[132 + 3] = 0
    clip[132 + 2] = 89                                       # step index out of range
    assert not audio.is_ring_adpcm(bytes(clip))
    assert not audio.is_ring_adpcm(b"") and not audio.is_ring_adpcm(b"\x00" * 131)
