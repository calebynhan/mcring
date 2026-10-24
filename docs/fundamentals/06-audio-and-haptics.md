# 6. Audio and haptics

Sound enters the ring through a PDM microphone (`firmware/ring-esp32s3/src/audio_mod.cpp`), leaves it as 132-byte IMA-ADPCM blocks (`lib/mcring_adpcm`), becomes text on the server (`backend/app/stt.py`), becomes an answer, becomes speech again (`backend/app/tts.py`), and is heard in the wearer's headphones or, on the oversized stage-1 ring, through a 10 mm speaker driven by a MAX98357A class-D amplifier (`audio_out.cpp`, `config_audio.h`). Alongside that path the ring talks back in two other ways: short haptic cues from an 8 mm linear resonant actuator on a DRV2605L (`drv2605.cpp`, `cues.cpp`) and the double-tap that starts a hands-free question, detected by a LIS2DW12 accelerometer (`imu_lis2dw12.cpp`, `trigger.cpp`). This chapter gives you the acoustics, the signal processing and the actuator physics behind those files, worked on the project's own numbers: 16 kHz, 8 KB/s, 86 dB at 10 cm, 235 Hz, 0.56 g. Chapter 3 (§3.4 and §3.10) covers the I²S/PDM peripherals and the ADPCM tables, §1.3 the load-switch and ESD back-feed rules, §4.3 the BLE link arithmetic; this chapter does not repeat them and is about why those values were chosen.

## 6.1 Sound, decibels and digital audio: sampling, bit depth, PCM and 16 kHz mono

**Why it matters in mcring.** `VOICE_SAMPLE_RATE 16000` and `I2S_BITS_PER_SAMPLE_16BIT` in `config.h`/`audio_mod.cpp`, `AUDIO_START.sample_rate_div100 = 160` in `protocol/ble-gatt.md`, `RING_RATE = 16000` in `backend/app/audio.py` and `SAMPLE_RATE = 16000` inside Whisper are the same decision made four times. `docs/04` justifies it in one line: "speech at a 16 kHz sample rate (8 kHz bandwidth) is fully intelligible", and the whole BLE budget (8 KB/s for a clip, ~70% of an iOS link for the speaker stream) follows from it.

**The concepts.** Sound is a pressure wave; its level is quoted in decibels of sound pressure, SPL = 20·log10(p / 20 µPa), so 0 dB is the threshold of hearing, 60 dB is conversation at a metre, 94 dB is 1 Pa (the reference at which microphone sensitivity is specified). Speech has fundamentals at 85–255 Hz, but intelligibility lives in the formants and consonants up to about 8 kHz; the telephone band of 300–3,400 Hz is understandable but loses the difference between "s" and "f". Digitising a wave means sampling it f_s times a second and quantising each sample to b bits. Nyquist: the sample rate must exceed twice the highest frequency you want to keep, so 16 kHz captures everything up to 8 kHz and anything above must be removed first by an anti-aliasing low-pass filter, or it folds back into the band as a distorted ghost. Bit depth sets dynamic range: each bit adds about 6 dB, so 16 bits give ~96 dB between the quietest step and full scale (0 dBFS = 32,767); speech needs far less, but 16-bit hardware is universal. PCM is simply that stream of integers. The arithmetic the project lives by: 16,000 samples/s × 2 bytes = 32,000 B/s = 256 kbit/s, so a maximum 8 s clip is 256 KB raw and 66,000 bytes after ADPCM (500 blocks × 132 B; the codec is §3.10). Mono is enough because there is one microphone and speech recognisers take one channel. `audio_finish()` scales each clip so its peak lands at 24,000, about −2.7 dBFS, leaving headroom while using most of the 16 bits (the Q8 integer maths behind it is in §3.10).

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Xiph.org: Digital Show & Tell (Monty Montgomery)](https://xiph.org/video/vid2.shtml) | video | 30 min | Sampling, Nyquist, quantisation and dither demonstrated on an oscilloscope; the clearest half hour on why 16 kHz/16-bit is enough |
| [Digital Signal Processing: Theory and Computational Examples (S. Spors, Univ. of Rostock)](https://github.com/spatialaudio/digital-signal-processing-lecture) | interactive (Jupyter) | 2 h | Run the quantisation and spectral-analysis notebooks yourself: quantisation noise, SNR per bit, the spectrum of a 16 kHz signal, with code you can point at a ring clip |
| [openai/whisper `audio.py`](https://github.com/openai/whisper/blob/main/whisper/audio.py) | code | 10 min | `SAMPLE_RATE = 16000`, `N_FFT = 400`, `HOP_LENGTH = 160`: the recogniser's own numbers, matching the ring's |

**Check yourself.**

1. The speaker is specified at 86 dB SPL at 10 cm. What level reaches an ear at 30 cm (arm's length) and at 1 m?
2. How many bytes is a 5 s question as raw PCM, and as mcring ADPCM?
3. A microphone has a 64 dB(A) SNR. What is its noise floor in dB SPL, and how far above it is 60 dB speech?
4. Why would recording at 8 kHz (telephone rate) hurt speech-to-text more than it hurts a human listener?

<details><summary>Answers</summary>

1. Level falls 20·log10(d₂/d₁): 86 − 20·log10(3) = 76.5 dB at 30 cm; 86 − 20 = 66 dB at 1 m, the figure in `docs/04`.
2. Raw: 5 × 32,000 = 160,000 B. ADPCM: 5 × 16,000 / 256 = 312.5 → 313 blocks × 132 B = 41,316 B.
3. Sensitivity is referenced to 94 dB SPL, so the floor is 94 − 64 = 30 dB SPL; speech at 60 dB sits 30 dB above it, which is what `docs/04` says about the T3902.
4. 8 kHz keeps only 4 kHz of bandwidth, erasing the fricative energy ("s", "f", "th") that recognisers use to tell words apart; humans fill in from context, models trained on 16 kHz audio do worse.

</details>

## 6.2 Microphones: PDM versus I²S, the T3902 and the acoustic port

**Why it matters in mcring.** `audio_start_recording()` installs I²S0 in `I2S_MODE_PDM` receive mode on `PIN_PDM_CLK 42` / `PIN_PDM_DATA 41`, then `audio_finish()` removes the DC offset and applies up to 8× gain in Q8 fixed point because "PDM mics on the Sense board are quiet". The stage-1 board uses a TDK T3902 bottom-port PDM mic under a Ø0.6 mm hole through the PCB and a Ø0.8 mm port with a 1.8 mm tube in the lid (`docs/03`, `hardware/cad/`); `docs/04` works out that the port is a Helmholtz resonator at 8–10 kHz, above speech. Stage 2 keeps PDM because the nRF52840 has a native PDM peripheral and the pin budget is tight.

**The concepts.** A MEMS microphone is a silicon diaphragm over a back-plate forming a capacitor, plus an ASIC. The ASIC's output defines the type. An analog mic gives a small voltage and needs an ADC. A PDM mic (pulse-density modulation) runs a sigma-delta modulator at a clock the host supplies, typically 1–3 MHz, and outputs one bit per clock: the density of 1s tracks the pressure. At 64× oversampling a 16 kHz output needs a 16,000 × 64 = 1.024 MHz clock; the host's decimation filter (a CIC stage followed by a FIR) averages the bit stream down to 16-bit samples and, because sigma-delta noise shaping has pushed the quantisation noise up to high frequencies, that low-pass also removes most of it. PDM costs two wires (CLK, DATA), lets two mics share the line on opposite clock edges, and puts the filter in the MCU, which the ESP32-S3's I²S block and the nRF52840's PDM peripheral both have in hardware (driver side, `I2S_MODE_PDM`, DMA buffers and `i2s_read`: §3.4). An I²S mic contains the decimator itself and emits 24-bit PCM frames on three wires; simpler to use on a bench, larger, and with no pin or power advantage on a ring. Microphone datasheets quote sensitivity in dBFS at 94 dB SPL (−26 dBFS is typical) and SNR in dB(A); noise floor = 94 − SNR, and the maximum acoustic input (AOP, ~120 dB SPL) says when it clips. Acoustics of the port: a hole of area A and length L in front of a small cavity of volume V resonates at f = (c / 2π)·√(A / (V·L)); a long thin tube lowers f and narrows the peak, which is why `docs/04` wanted the resonance kept at 8–10 kHz where speech has little energy, and why the gasket between mic and shell must seal (a leak costs low frequencies). The firmware's clean-up is textbook: decimators leave a DC offset (remove the mean), a quiet mic needs gain (target peak 24,000), and a hard 8× clamp stops a silent room from being amplified into hiss; the Q8 arithmetic is worked in §3.10, question 3.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Understanding PDM Digital Audio (Audio Precision, T. Kite)](https://www.ap.com/download/understanding-pdm-digital-audio-2) | article (PDF) | 1 h | The definitive explanation of sigma-delta, noise shaping and decimation for PDM microphones; also the intuition for why oversampling plus a good low-pass beats "more bits" |
| [nRF52840 Product Specification v1.8](https://infocenter.nordicsemi.com/pdf/nRF52840_PS_v1.8.pdf) | datasheet (PDF) | 30 min | The PDM chapter: clock ratios, built-in decimation, 16 kHz output; the stage-2 microphone path |
| [Zephyr sample: Audio DMIC (PDM microphone) on nRF52840DK](https://github.com/zephyrproject-rtos/zephyr/tree/main/samples/drivers/audio/dmic) | code | 30 min | The stage-2 mic path as working code: PDM clock, one- and two-channel capture through the DMIC API on the SoC the ring moves to |

**Check yourself.**

1. What PDM clock does a 16 kHz output need at 64× oversampling, and at 128×?
2. A digital MEMS mic specified at −26 dBFS (94 dB SPL, 1 kHz) hears speech arriving at 60 dB SPL, the level `docs/04` assumes at the ring. What rms level in dBFS and roughly what 16-bit amplitude does that produce, and why is that the reason `audio_finish()` has a gain stage at all?
3. The lid's mic tube is lengthened from 1.8 mm to 3.6 mm. Which way does the Helmholtz resonance move, and does it matter for speech?
4. Why does a bottom-port mic need a hole through the PCB, and what does a poor gasket do to the recording?

<details><summary>Answers</summary>

1. 16,000 × 64 = 1.024 MHz; at 128×, 2.048 MHz.
2. 60 dB SPL is 34 dB below the 94 dB reference, so the output is −26 − 34 = −60 dBFS: 32,767 × 10^(−60/20) ≈ 33 counts rms, with speech peaks a few times higher, roughly 100–150. That is why raw ring clips are "quiet": even the 8× clamp in `audio_finish()` only lifts them to around 1,000 counts. A recogniser copes, because Whisper's front end (`audio.py`) works on a log-mel spectrogram clamped to 80 dB below the loudest frame, so a uniformly quiet clip mostly shifts the features; what it cannot recover is speech buried in the mic's own noise, which is why the 30 dB SNR margin of 6.1, question 3 matters more than the gain (the gain arithmetic itself is §3.10, question 3).
3. f ∝ 1/√L, so doubling L lowers f by √2, from ~9 kHz to ~6.4 kHz. Still above the 300–3,400 Hz core of speech, but closer to the 8 kHz band edge; keep tubes short.
4. The acoustic port is on the underside of the package, so sound has to reach it through the board; a leak around the port lets sound reach the diaphragm from both sides, cancelling low frequencies and letting in body noise.

</details>

## 6.3 IMA-ADPCM in `lib/mcring_adpcm` and the 24→16 kHz resample in `backend/app/audio.py`

**Why it matters in mcring.** The ring encodes the microphone clip (`audio_finish()`), the ring decodes the phone's speaker stream (`stage_block()` in `audio_out.cpp`), the backend converts clips to WAV for the recogniser and TTS output to blocks for the speaker, and `python/mcring_core/mcring_core/adpcm.py` must produce byte-identical output to the C library (checked in `python/mcring_core/tests/test_proto.py`). The 132-byte block is also the protocol's unit: one `AUDIO_DATA` write carries whole blocks, one block per write at the iOS MTU of 185 (the MTU arithmetic is §4.3). `sniff_audio()` even recognises a headerless ring clip by its block structure (first sample, step index ≤ 88, reserved byte 0).

**The concepts.** ADPCM sends differences, not samples: the decoder keeps a predictor (the last reconstructed sample) and a step size; each 4-bit code says "move by sign × (b₂ + b₁/2 + b₀/4 + 1/8) × step", and the step then adapts, shrinking after a small code and growing after a large one, so the quantiser follows loud passages and fine-tunes quiet ones. The 89-entry step table, the index table, the 132-byte block layout (4-byte header plus 255 nibbles per 256 samples, 8,250 B/s, 3.88:1) and the predictor-reset-per-block rule are worked through once in §3.10; this section is about what the codec trades and what the backend does to the audio around it. The trade is quality for determinism and size: 4 bits per sample leaves "toll grade" speech, audible hiss on music, no problem for a recogniser or a 10 mm speaker, and a codec made of integer tables runs identically in C, Python and TypeScript, which is what `test_proto.py` checks. The backend's other job is sample-rate conversion: TTS providers return 24 kHz PCM and the ring wants 16 kHz, a 3:2 ratio. `_resample_polyphase()` zero-stuffs to the common rate (×2 → 48 kHz), low-passes with a windowed-sinc FIR whose cutoff is 0.92 × the lower Nyquist (0.92 × 8 kHz = 7.36 kHz, so nothing above 8 kHz aliases), then keeps every third sample; it builds 32 × max(up, down) + 1 = 97 Hamming-windowed taps. Ratios that need more than 32 in either direction (44.1 → 16 kHz is 441:160) fall back to plain interpolation, as does a machine without numpy; for speech into a small speaker that is acceptable, for music it would not be.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Dr. Dobb's: Inside IMA ADPCM](https://www.drdobbs.com/database/algorithm-alley/184410326) | article | 30 min | The encoder with worked numbers; why a block header carries the first sample and step index (the decode tables are linked from §3.10) |
| [FFmpeg `libavcodec/adpcm.c`](https://github.com/FFmpeg/FFmpeg/blob/master/libavcodec/adpcm.c) | code | 30 min | A production IMA decoder (`adpcm_ima_expand_nibble`, `ff_adpcm_step_table`, `ff_adpcm_index_table`) to read next to `mcring_adpcm.c`: the same 4-bit expansion, clamp and index update |
| [SciPy `signal/_signaltools.py` (`resample_poly`)](https://github.com/scipy/scipy/blob/main/scipy/signal/_signaltools.py) | code | 30 min | The textbook polyphase resampler the backend's `_resample_polyphase()` imitates: up/down factors, a windowed FIR, keep every n-th sample; compare the two before trusting 24 → 16 kHz |

**Check yourself.**

1. Encode one sample by hand: step = 16, difference to predict = +37. Which 4-bit code results, what difference does the decoder reconstruct, and how does the step index change?
2. How many bytes is a 3.3 s clip, and how long does it take over an iOS link at ~11 KB/s?
3. For 24 → 16 kHz, give the up/down factors, the FIR tap count and the cutoff frequency in Hz. Why does 44.1 → 16 kHz take the fallback path?
4. Why does `is_ring_adpcm()` check every block's step index and reserved byte rather than just the length?

<details><summary>Answers</summary>

1. 37 ≥ 16 → b₂ = 1 (remainder 21); 21 ≥ 8 → b₁ = 1 (13); 13 ≥ 4 → b₀ = 1: code 0b0111 = 7. Reconstructed diff = 16 + 8 + 4 + 2 = 30 (error 7). Magnitude 7 adds +8 to the step index.
2. 3.3 × 16,000 = 52,800 samples → 207 blocks (206.25 rounded up) × 132 = 27,324 B; about 2.5 s on iOS, 0.5 s on Android at ~50 KB/s (link ceilings from §4.3).
3. gcd(24,000, 16,000) = 8,000 → up 2, down 3; taps = 32 × 3 + 1 = 97; cutoff 0.92 × 8,000 = 7,360 Hz. 44,100/16,000 reduces to 441/160, both > 32, so `np.interp` is used.
4. An mp3 whose length happens to be a multiple of 132 would otherwise be mistaken for a clip; a bare MPEG frame can even start with 0xFF 0xFx, which looks like a negative first sample. Checking the structure of every block makes the false-positive rate negligible.

</details>

## 6.4 Loudness, the 10 mm speaker and the MAX98357A class-D amplifier

**Why it matters in mcring.** `hardware/schematic-notes.md` puts U10, a MAX98357A, on `IO35 BCLK / IO36 LRCLK / IO37 DIN` with `GAIN` set to 3 dB by R21 = 100 kΩ so a full-scale sample is 1.41 Vrms = 0.25 W into the 8 Ω PUI AS01008MR-2-R (Ø10 × 2.9 mm, 0.3 W, 86 dB at 10 cm); U11, a TPS22916 on `IO34 = PIN_SPEAKER_EN`, gates the amp's rail because an always-on amp idles at 2.4 mA, "58 mAh/day, twice the cell" (`docs/04`); the load-switch pattern itself is §1.3. `audio_out.cpp` duplicates the mono sample into both I²S slots and `driver_stop()` parks the three I²S pins low. The outcome is spelled out in `docs/03`: ~66 dB at 1 m, arm's length in a quiet room, and no speaker at all at Oura size.

**The concepts.** Loudness falls 20·log10(d₂/d₁) dB with distance in free air: 86 dB at 10 cm is 76 dB at 30 cm, 66 dB at 1 m, and a ported 1.2 mm resin wall takes a few dB more; conversation is ~60 dB at 1 m, so the ring speaker is audible at arm's length in a quiet room and lost in a café. Doubling electrical power adds 3 dB; a perceived doubling of loudness needs about +10 dB, ten times the power, which a 30 mAh cell does not have. Small drivers are quiet for a physical reason: radiated power grows with (cone area × acceleration)², and reproducing low frequencies needs excursion a 10 mm cone cannot make, so the output rolls off below the driver's ~1 kHz resonance; speech intelligibility (300–3,400 Hz) survives, warmth does not. The amplifier: a class-D stage does not pass the audio through a linear transistor; it converts the PCM into a high-frequency switching pattern (hundreds of kHz) and drives the speaker from an H-bridge between the rails, so the transistors are either fully on or off and 85–90% of the battery energy reaches the voice coil, against ~50% for a linear class-AB stage. The speaker's own inductance smooths the switching, which is why "filterless" works with the short leads the stage-1 shell allows. The MAX98357A takes I²S directly (16-bit stereo frames; the 512 kHz BCLK arithmetic and the driver are §3.4) and its GAIN pin selects 3, 6, 9, 12 or 15 dB: at 0 dBFS the output is about 1.0 V × 10^(gain/20) rms, so 3 dB → 1.41 V → P = V²/R = 0.25 W, 6 dB → 2.0 V → 0.5 W (the speaker's maximum), and 9 dB would ask for 2.83 V, more than a 3.3 V bridge can swing (~2.3 Vrms), so it clips. Current: 0.25 W / (0.9 × 3.3 V) ≈ 84 mA for a full-scale sine; speech averages well below full scale, but the ESP32 is awake and the radio is streaming, hence the 100–150 mA in `docs/04` and the 280–420 µAh per 10 s answer, two to three photos. The SD_MODE pin is tied to the gated rail so one GPIO both powers and enables the amp; the three I²S pins are parked low after `i2s_driver_uninstall()` because of the ESD-diode back-feed path through R22–R24, explained once in §1.3.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Adafruit: MAX98357 I2S Class-D Mono Amp](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp) | guide | 30 min | The breakout the stage-0 rig uses: SD/MODE channel select, the GAIN pin table, wiring and first sounds |
| [NXP I²S bus specification (UM11732)](https://www.nxp.com/docs/en/user-manual/UM11732.pdf) | spec (PDF) | 20 min | The frame format the amp expects: WS one BCLK early, MSB first, 32 BCLK per stereo frame |
| [TI SLVA652: Basics of Load Switches](https://www.ti.com/lit/SLVA652) | article (PDF) | 30 min | Why gating the amp's rail beats a shutdown pin for leakage, and what inrush the 100 µF bulk cap causes; the TPS22916 datasheet itself is linked from §1.3 |

**Check yourself.**

1. What SPL reaches a listener at 0.5 m from a source rated 86 dB at 0.1 m? And at 2 m?
2. Compute the 0 dBFS output voltage and power at the 12 dB gain setting, and explain why the board notes call it unusable from 3.3 V.
3. The dev kit leaves SD tied high. How many days would the amp's 2.4 mA idle alone take to empty a 30 mAh cell?
4. If `AUDIO_OUT_SAMPLE_RATE` were raised to 24 kHz, what BCLK would the I²S peripheral run, and what else in the protocol would have to change?

<details><summary>Answers</summary>

1. 86 − 20·log10(5) = 72 dB at 0.5 m; 86 − 20·log10(20) = 60 dB at 2 m, equal to the room's conversation level.
2. 1.0 V × 10^(12/20) = 3.98 Vrms → 1.98 W into 8 Ω on paper. An H-bridge on 3.3 V cannot swing more than ~3.3 V peak (~2.3 Vrms), so the waveform clips hard and the 0.3 W speaker would be overdriven anyway.
3. 30 mAh / 2.4 mA = 12.5 h, about half a day: the un-gated amp alone kills the ring, independent of any audio.
4. BCLK = 32 × 24,000 = 768 kHz (§3.4). `AUDIO_START.sample_rate_div100` would be 240, blocks would last 10.7 ms instead of 16, the 24-block prebuffer would be ~256 ms, and the stream would need 12.4 KB/s, more than an iOS link reliably gives.

</details>

## 6.5 Speech-to-text and text-to-speech: the pipeline and where the seconds go

**Why it matters in mcring.** `backend/app/stt.py` transcribes with OpenAI `gpt-4o-mini-transcribe` or a local faster-whisper `base.en` model in int8, after `prepare_audio()` turns a headerless ring clip into WAV; `backend/app/tts.py` asks the provider for 24 kHz PCM and `audio.py` resamples and encodes it for the speaker; the phone's default is to speak `speech_text` with its own engine (`expo-speech`). `docs/04` budgets the round trip at 2–4 s (STT 0.5–1 s, Claude 1–3 s, TTS 0.5–1 s) plus ~1 s of BLE clip transfer on iOS in ring-mic mode, against requirement N2's 6 s to the first spoken word, and lists streaming TTS and phone-side STT as backlog.

**The concepts.** Everything after the button release runs in series, so the latency is a sum. Clip transfer: ring-mic mode must move up to 66 KB over BLE before anything else can start, 1.3 s on Android at ~50 KB/s but up to 6 s for an 8 s clip on iOS at ~11 KB/s (`docs/07` §1.6), which is why the phone-mic path exists: the phone records between `BUTTON_DOWN` and `BUTTON_UP` and the clip never crosses BLE. Speech-to-text: Whisper-family models resample to 16 kHz, compute an 80-band log-mel spectrogram with a 25 ms window (`N_FFT = 400`) every 10 ms (`HOP_LENGTH = 160`, so 100 frames per second), pad to a 30 s chunk and run an encoder-decoder transformer that emits text tokens; faster-whisper reimplements it on CTranslate2 and quantises to int8, which the project uses to run `base.en` (~150 MB) on a CPU in roughly real time for a short clip, while the hosted model is faster but adds a network hop. The language model: time to first token plus ~100 output tokens; prompt caching of the stable system prompt trims the input side, the one-to-three-sentence rule in `prompts.py` trims the output side, and streaming could overlap the next stage with generation. Text-to-speech: the phone's built-in engine starts in well under a second with no network; server TTS costs a round trip and a download, but produces the 16 kHz ADPCM the ring speaker needs; the ring then buffers 24 blocks (~400 ms) before it plays. The levers, in order of payoff: use the phone mic on iOS, keep the answer short, cache the prompt, stream (Claude's SSE stream and sentence-by-sentence TTS turn a 3 s wait into a 1 s one), and make the wait legible with the *listening* and *answer ready* cues so three seconds feel intentional rather than broken.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [openai/whisper (GitHub)](https://github.com/openai/whisper) | code + paper link | 45 min | The model the local STT path runs; README links the paper, shows the load → pad/trim → log-mel → decode steps |
| [openai/whisper `audio.py`](https://github.com/openai/whisper/blob/main/whisper/audio.py) | code | 10 min | 16 kHz, 400-sample FFT, 160-sample hop, 80 mel bands, 30 s chunks: the front end in 100 lines |
| [SYSTRAN/faster-whisper (GitHub)](https://github.com/SYSTRAN/faster-whisper) | code | 20 min | What `MCRING_STT_PROVIDER=local` installs: CTranslate2, int8, the benchmark tables that justify `compute_type=int8` |
| [Claude docs: Reducing latency](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency) | docs | 15 min | Time-to-first-token, shorter outputs, streaming: the backend side of the budget |
| [Claude docs: Streaming messages](https://platform.claude.com/docs/en/build-with-claude/streaming) | docs | 30 min | The SSE event stream a future sentence-by-sentence TTS would consume |
| [expo-speech (expo/expo on GitHub)](https://github.com/expo/expo/tree/main/packages/expo-speech) | code/docs | 15 min | The phone's on-device text-to-speech the app uses by default; zero network latency, routed to the headphones by the OS |

**Check yourself.**

1. A wearer holds the button for 8 s in ring-mic mode on an iPhone. How long does the clip take to reach the phone, and what does switching to the phone mic save?
2. How many log-mel frames does Whisper compute per second of audio, and for a 3 s clip padded to 30 s?
3. `max_speech_chars = 1500`. Roughly how many seconds of speech is that, how many ADPCM bytes, and can an iOS link stream it to the ring speaker in real time?
4. Put the `docs/04` numbers in a table and add streaming: which stage can be overlapped with which, and what is the best-case time to the first spoken word?

<details><summary>Answers</summary>

1. 66,000 B / 11,000 B/s ≈ 6 s before transcription even starts; the phone-mic path saves all of it (the phone already holds the audio) and leaves only the HTTPS upload.
2. 16,000 / 160 = 100 frames per second; the padded 30 s chunk is 3,000 frames regardless of clip length, which is why short clips are not proportionally faster on Whisper.
3. ~250 words, about 100 s at 150 words per minute; 100 s × 8,250 B/s ≈ 825 KB. The stream needs 8.25 KB/s against the ~10–12 KB/s an iOS link gives (§4.3), so it keeps up with ~30% margin, which is why the ring prebuffers 400 ms and reports `AUDIO_UNDERRUN` rather than clicking (§3.4, answer 2).
4. BLE clip 0–6 s (0 with phone mic) → STT 0.5–1 s → Claude 1–3 s → TTS 0.5–1 s. STT cannot start before the clip ends; Claude can stream its first sentence while generating the rest; TTS can synthesise sentence 1 while sentence 2 is still being generated. Best case with phone mic, cached prompt and streaming: roughly 0.7 s STT + ~1 s to Claude's first sentence + ~0.3 s TTS ≈ 2 s.

</details>

## 6.6 Haptics: LRA versus ERM, resonance, the DRV2605L in RTP mode, and cue design

**Why it matters in mcring.** `drv2605.cpp` configures the DRV2605L for an LRA (`REG_FEEDBACK` bit 7), writes `REG_RATED_V = 0x3E` and `REG_OD_CLAMP = 0x8C` "for an 8 mm 235 Hz LRA", selects library 6 and leaves the chip in RTP mode, where `drv2605_set(amp)` writes one amplitude byte to register 0x02 and the chip does the rest; `cues.cpp` plays a 60 ms tick for *listening*, two ticks for *answer ready* and a 420 ms buzz for *error* (`CUE_TICK_MS 60`, `P_TICK`/`P_DOUBLE`/`P_LONG`). `docs/04` notes that LRA rise and fall take 20–40 ms, so 60 ms is near the floor; `docs/07` §1.8 has the autocal procedure and `docs/build-helpers/tuning_calc.py drv2605` converts motor ratings into those two registers. On the stage-1 board `PIN_HAPTIC` is −1 because EN is tied to 3V3 and IO3 is the charger's `/CHG` line.

**The concepts.** An ERM (eccentric rotating mass) is a DC motor with an off-centre weight: cheap, drivable from one MOSFET, but its vibration frequency is its speed, so amplitude and frequency are coupled, and spinning up and down takes tens of milliseconds to over a hundred, which blurs short cues. An LRA (linear resonant actuator) is a sprung magnet mass inside a voice coil: driven with an AC signal at its resonant frequency f₀ = (1/2π)·√(k/m), typically 170–240 Hz, it produces a clean sinusoidal acceleration, 0.9–1.3 g for the 6–8 mm parts in `docs/research/03`. Resonance is also its weakness: the response is narrow-band (high Q), so a drive a few hertz off f₀ wastes most of the power, and f₀ shifts with temperature, mounting and the finger pressing on it. That is what the DRV2605L's closed loop does: between drive half-cycles it samples the coil's back-EMF, tracks the true resonance ("auto-resonance"), and brakes by driving in anti-phase, which is how a 60 ms tick gets 20–40 ms edges instead of ringing on. Skin is tuned for it: the Pacinian corpuscles that sense vibration peak near 200–300 Hz. The registers you touch: MODE (0x01, 5 = real-time playback, bit 6 = standby, < 4 µA), RTP_INPUT (0x02, signed amplitude; the firmware uses 0…127), FEEDBACK_CONTROL (0x1A, LRA/ERM, brake factor, loop gain), RATED_VOLTAGE (0x16) and OD_CLAMP (0x17). The datasheet's LRA equation, as coded in `tuning_calc.py`: V_rms = reg × 20.58 mV / √(1 − (4·t_sample + 300 µs)·f₀) with t_sample = 300 µs, and OD_CLAMP = V_peak / 21.22 mV, the overdrive allowed while starting and braking. Decode the firmware: 0x3E = 62 → 62 × 0.02058 / √(1 − 1.5 ms × 235 Hz) = 1.276 / 0.805 = 1.59 Vrms (the comment says "~1.8 Vrms", but the register corresponds to about 1.6 V, roughly 10% under the motor's rating; `python3 docs/build-helpers/tuning_calc.py drv2605 --decode 0x3E 0x8C --freq 235` shows the same), and 0x8C = 140 × 21.22 mV = 2.97 Vp. For the INEED LRA0825BC-0167F (1.25 Vrms, 240 Hz) the calculator gives 0x31 and 0x6C, the values `docs/07` tells you to edit in. Auto-calibration (`drv2605_autocal()`) runs the motor, measures back-EMF and resonance, and stores compensation; it fails (DIAG bit) on a free-floating motor, which is why the build guide says to stick the LRA to something with mass. Cue design follows from the physics: distinguish cues by count and duration, never by amplitude (amplitude discrimination on skin is poor and changes with how tight the ring sits); keep every on and off segment ≥ 60 ms so the actuator actually reaches and leaves full amplitude; three cues is about the vocabulary people learn without thinking. Energy is negligible: a C08-005 draws ~75 mA, so a 60 ms tick is 1.25 µAh, a hundredth of a photo, and standby is the register bit, not a GPIO.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Precision Microdrives AB-020: Understanding Linear Resonant Actuator Characteristics](https://www.precisionmicrodrives.com/ab-020) | article | 45 min | The mass-spring model, equivalent circuit, resonance and why a sine at f₀ is the right drive; the one LRA primer worth reading |
| [Precision Microdrives VAB-03: How Do LRAs Work?](https://www.precisionmicrodrives.com/vab-03) | video | 10 min | The AB-020 content animated; watch before the article |
| [TI DRV2605L datasheet: waveform playback using RTP mode](https://www.ti.com/document-viewer/DRV2605/datasheet/waveform-playback-using-rtp-mode-slos8549159) | datasheet | 1 h | The mode `drv2605.cpp` uses, plus the neighbouring sections on auto-resonance, auto-calibration and the rated-voltage equation |
| [TI DRV2605L product page](https://www.ti.com/product/DRV2605L) | datasheet | 10 min | The PDF download and the register map; the 10-VSSOP and 9-DSBGA packages the stage-1/2 boards use |
| [adafruit/Adafruit_DRV2605_Library (GitHub)](https://github.com/adafruit/Adafruit_DRV2605_Library) | code | 20 min | A second, readable register-level driver for the same breakout; compare its init sequence with `drv2605_init()` |

**Check yourself.**

1. Decode the firmware's `REG_RATED_V 0x3E` at 235 Hz and at 175 Hz. Why does the same register mean a different voltage at a different frequency?
2. Compute RATED_VOLTAGE and OD_CLAMP for a 2.0 Vrms, 175 Hz LRA with the calculator's 30% overdrive default.
3. One hundred cues a day, averaging 1.5 ticks each: how many µAh, and how does that compare with one photo?
4. Why would amplitude-coded cues (soft tick = listening, hard tick = ready) be a bad design, and why does `PIN_HAPTIC` have to stay −1 on `mcring_v1`?

<details><summary>Answers</summary>

1. 235 Hz: 1.59 Vrms (above). 175 Hz: k = √(1 − 1.5 ms × 175) = √0.7375 = 0.859, so 1.276 / 0.859 = 1.49 Vrms. The chip stops driving for a fixed sampling-and-blanking slice of every half-cycle; that slice is a larger share of a shorter period, so the correction factor √(1 − t·f₀) shrinks as f₀ rises and one register value means more rms at a higher f₀ (1.59 V at 235 Hz, 1.49 V at 175 Hz). Set the register for the motor you actually have, then confirm with autocal.
2. k = 0.859; reg = 2.0 × 0.859 / 0.02058 = 83.5 → 0x53 or 0x54 (83 = 0x53 gives 1.99 V). V_peak = 2.0 × √2 × 1.3 = 3.68 V → 3.68 / 0.02122 = 173 = 0xAD.
3. 150 ticks × 1.25 µAh = 188 µAh ≈ 0.19 mAh per day, about 1.2 photos; three days of cues cost less than one speaker answer.
4. The perceived strength of a tick depends on ring fit, finger, temperature and attention, so a "soft" and a "hard" tick are routinely confused, while one versus two ticks never is. On the v1 board IO3 is wired to the BQ25100's open-drain `/CHG` output; driving it as the haptic enable would fight the charger, and the DRV2605L's EN is already tied high, so standby is done over I²C.

</details>

## 6.7 Tap detection on the LIS2DW12 accelerometer

**Why it matters in mcring.** `imu_init()` programs the LIS2DW12 for 400 Hz high-performance mode (`CTRL1 = 0x74`), ±2 g full scale (`CTRL6 = 0x04`), a tap threshold of 9 on all axes (`TAP_THS_*`), `INT_DUR = (7 << 4) | (2 << 2) | 2`, double-tap enable (`WAKE_UP_THS = 0x80`) and double-tap on INT1 (`CTRL4_INT1 = 0x08`), which is `PIN_IMU_INT`, an RTC-capable GPIO that wakes the ESP32-S3 from deep sleep. `trigger_tick()` adds an 800 ms burst filter. `docs/03` warns that this mode costs ~90 µA against ~1 µA at a low-power data rate, and `docs/04` lists false double taps as a named risk now that a tap starts a recording; `tuning_calc.py tap` does the register arithmetic.

**The concepts.** A MEMS accelerometer is a proof mass on silicon springs; acceleration displaces it and changes a differential capacitance, which the ASIC converts to a 12- or 14-bit value per axis. It measures gravity too (1 g = 9.81 m/s² when still), so a tap is a brief spike riding on a 1 g offset, on whichever axis the knock travels along. Full scale ±2 g suits taps (a knock on a ring is a few g at most; a dropped ring is tens). The tap engine is a little state machine with four parameters. TAP_THS: the spike must exceed it; LSB = FS / 32 = 62.5 mg at ±2 g, so 9 → 0.5625 g. SHOCK: the spike must fall back below the threshold within this time; LSB = 8 / ODR = 20 ms at 400 Hz, so 2 → 40 ms. QUIET: after the spike the signal must stay below the threshold for this long or the event is treated as shaking, not a tap; LSB = 4 / ODR = 10 ms, so 2 → 20 ms. LATENCY: the window within which a second tap makes it a double tap; LSB = 32 / ODR = 80 ms, so 7 → 560 ms. Packed, (7 << 4) | (2 << 2) | 2 = 0x7A. The data rate matters because a real knock lasts a few milliseconds; at 100 Hz the engine samples every 10 ms and can miss the peak entirely, hence 400 Hz, and hence the ~90 µA that the stage-2 budget has to decide whether to pay (the alternative is a lower ODR with a wake-up threshold, then a short burst at 400 Hz). The interrupt pulses INT1; `trigger_tick()` reads TAP_SRC (which clears on read) to confirm the DOUBLE_TAP bit and ignores anything within 800 ms of the last event, because a single knock on a desk can produce a burst of qualifying spikes. False positives are the real engineering: typing, clapping, setting the hand down and opening a door all produce double spikes in the 100–500 ms range. The tools are the threshold (raise it until deliberate taps still register), the axis enables and priority in TAP_THS_Z bits 7:5 (a ring is tapped through one face; restricting the axis halves the false rate), a shorter LATENCY, a longer QUIET, the firmware burst filter, "second double tap stops the recording", and logging TAP_SRC during a day of normal use before trusting any setting.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ST LIS2DW12 product page](https://www.st.com/content/st_com/en/products/mems-and-sensors/accelerometers/lis2dw12.html) | datasheet | 1 h | The datasheet (register map, TAP_THS/INT_DUR LSB definitions, current per ODR and mode) and the AN5038 application note with the tap-recognition chapter |
| [STMicroelectronics/lis2dw12-pid (GitHub)](https://github.com/STMicroelectronics/lis2dw12-pid) | code | 30 min | ST's platform-independent C driver: every register and bit field named; compare with the raw writes in `imu_lis2dw12.cpp` |
| [STMems_Standard_C_drivers: LIS2DW12 examples (GitHub)](https://github.com/STMicroelectronics/STMems_Standard_C_drivers/tree/master/lis2dw12_STdC/examples) | code | 30 min | `lis2dw12_tap_double.c` and `lis2dw12_wake_up.c`: ST's own reference settings for double tap and wake-on-motion |
| [ESP-IDF: GPIO & RTC GPIO (ESP32-S3, v4.4)](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-reference/peripherals/gpio.html) | docs | 20 min | Which pins can wake the chip from deep sleep, and why `PIN_IMU_INT` is GPIO7 |
| [Random Nerd Tutorials: ESP32 Deep Sleep and Wake Up Sources](https://randomnerdtutorials.com/esp32-deep-sleep-arduino-ide-wake-up-sources/) | guide | 30 min | External-interrupt wake in the Arduino framework, the mechanism behind tap-to-wake |
| [SparkFun: I2C](https://learn.sparkfun.com/tutorials/i2c/all) | article | 30 min | Register-style reads and writes, `endTransmission(false)` repeated starts, the 0x18/0x19 SA0 address trick |

**Check yourself.**

1. Compute TAP_THS and INT_DUR for a 0.8 g threshold, a 300 ms double-tap window, QUIET 20 ms and SHOCK 40 ms at ODR = 200 Hz.
2. Decode `INT_DUR = 0x7A` at 400 Hz and at 100 Hz.
3. The IMU stays at 400 Hz high-performance (~90 µA). How many mAh per day is that, and how many days does a 30 mAh cell at 80% usable last if the rest of standby is 25 µA?
4. Why does `imu_isr()` only set a flag, with the TAP_SRC read happening later in `trigger_tick()`?

<details><summary>Answers</summary>

1. 0.8 / 0.0625 = 12.8 → 13 (0.8125 g). At 200 Hz: LATENCY LSB 160 ms → 2 (320 ms); QUIET LSB 20 ms → 1; SHOCK LSB 40 ms → 1. INT_DUR = (2 << 4) | (1 << 2) | 1 = 0x25.
2. LATENCY 7, QUIET 2, SHOCK 2. At 400 Hz: 560 / 20 / 40 ms. At 100 Hz every LSB is 4× longer: 2,240 / 80 / 160 ms, far too slow for a tap.
3. 90 µA × 24 h = 2.16 mAh/day. Total 115 µA → 2.76 mAh/day; 24 mAh / 2.76 ≈ 8.7 days of pure standby, versus 24 / 0.6 = 40 days at 25 µA. Tap-to-wake costs most of the standby budget, which is the stage-2 decision `docs/03` flags.
4. The interrupt runs on the NimBLE/Arduino core with I²C possibly mid-transaction; an I²C read inside an ISR can deadlock or corrupt a transfer. Setting a `volatile` flag and reading the register in the cooperative loop (chapter 3.9) is the safe pattern.

</details>
