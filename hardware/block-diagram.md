# System block diagrams

Voice-first: hold the ring → ask (ring mic or headset mic) → hear Claude in your headphones, or
from the on-ring speaker on the stage-1 oversized ring. The ring never pairs to headphones; the
phone routes all audio.

## End-to-end

```mermaid
flowchart LR
  subgraph Ring
    T["Trigger<br/>button hold / double-tap = ask<br/>short press / touch = photo"] --> MCU["MCU<br/>ESP32-S3 stage 0/1<br/>nRF52840 stage 2"]
    CAM["Camera<br/>OV2640 / HM01B0 / OVM7692"] -->|"DVP 8-bit JPEG"| MCU
    MIC["PDM mic"] -->|"PCM to IMA-ADPCM 16 kHz"| MCU
    MCU -->|"RTP on/off"| HAP["DRV2605 + LRA<br/>cues: 1 tick listening, 2 ticks answer, buzz error"]
    MCU --> LED["RGB LED cues"]
    MCU -.-> BUZ["Piezo beep cues, optional"]
    MCU -.->|"I2S 16 kHz, stage 1 only"| AMP["MAX98357A + 10 mm speaker<br/>optional on-ring output"]
    BAT["LiPo 16-40 mAh"] --> PMIC["Charger + LDO/buck<br/>BQ25100, load switches"] --> MCU
  end
  MCU <-->|"BLE GATT 7a3b0001-...mcring<br/>events, ADPCM clip, JPEG, cues, AUDIO_OUT stream"| PHONE["Companion<br/>phone app / desktop CLI"]
  PHONE -->|"phone audio routing"| EAR["User's Bluetooth headphones<br/>or phone speaker"]
  EAR -.->|"headset mic, phone-mic mode"| PHONE
  PHONE <-->|"HTTPS multipart<br/>POST /v1/ask, /v1/transcribe, /v1/speech"| BE["Backend<br/>FastAPI"]
  BE <-->|"structured JSON, photo optional"| LLM["Claude Opus 5.5<br/>or OpenAI"]
  BE <-->|"speech-to-text"| STT["OpenAI gpt-4o-mini-transcribe<br/>or local faster-whisper"]
  BE -.->|"optional text-to-speech<br/>mp3 or 16 kHz ADPCM"| TTS["OpenAI gpt-4o-mini-tts"]
```

## One voice turn

```mermaid
sequenceDiagram
  participant R as Ring
  participant P as Phone / CLI
  participant H as Headphones
  participant B as Backend
  participant L as Claude
  Note over R,P: user holds the button (or double-taps)
  R->>P: EVENT BUTTON_DOWN
  R->>R: listening cue (1 tick)
  alt ring mic (MIC_SOURCE_HINT = 0)
    R->>R: capture JPEG, start PDM recording
    R->>P: EVENT CAPTURE_STARTED / CAPTURE_DONE
    R->>P: EVENT REC_STARTED(max s)
    Note over R: user speaks, button held (max 8 s)
    R->>P: EVENT BUTTON_UP(held tenths), REC_STOPPED(tenths)
    R->>P: XFER JPEG then XFER ADPCM (START, chunks, END, ACK)
  else phone / headset mic (MIC_SOURCE_HINT = 1)
    P->>H: start recording (headset mic, 16 kHz m4a)
    P->>R: CONTROL CAPTURE (optional, when a photo is wanted)
    R->>P: XFER JPEG
    R->>P: EVENT BUTTON_UP(held tenths)
    P->>P: stop recording
  end
  P->>B: POST /v1/ask (audio, image?, session_id, speech_format)
  B->>B: speech-to-text
  B->>L: system + question (+ photo), JSON schema
  L-->>B: answer, subject, confidence, warnings, follow_up
  B-->>P: speech_text, transcript, mode, had_image (+ mp3 / ADPCM)
  P->>R: FEEDBACK CUE 2 (answer ready, 2 ticks)
  alt phone output (default)
    P->>H: speak speech_text (phone TTS or server mp3)
  else ring speaker (stage 1, SPEAKER_OK)
    P->>R: AUDIO_OUT START, DATA x N, END
    R-->>P: EVENT AUDIO_DONE(0)
  end
  Note over R,P: holding the button again interrupts playback and starts the next question
```

## Ring speaker streaming (AUDIO_OUT, stage 1)

```mermaid
sequenceDiagram
  participant P as Phone / CLI
  participant R as Ring
  P->>R: AUDIO_START {sr/100 = 160, codec = 2, volume}
  loop prebuffer burst: 24 blocks (about 400 ms)
    P->>R: AUDIO_DATA {seq, 1-3 whole 132-byte blocks}
  end
  R->>R: install I2S TX, start playback
  loop paced: keep at most 22 unplayed blocks queued, 6-block bursts
    P->>R: AUDIO_DATA {seq, blocks}
    R->>R: decode ADPCM, scale by volume x SPEAKER_VOLUME, write I2S
  end
  opt queue runs dry
    R-->>P: EVENT AUDIO_UNDERRUN (silence inserted, resumes after 8 blocks)
  end
  P->>R: AUDIO_END
  R->>R: drain queue and DMA, uninstall I2S
  R-->>P: EVENT AUDIO_DONE(0)
  opt user barges in or app cancels
    P->>R: AUDIO_STOP (or ABORT)
    R-->>P: EVENT AUDIO_DONE(1)
  end
```

## Firmware state machine

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Capturing: short press / touch / CAPTURE
  Capturing --> Idle: fail (error cue, CAPTURE_DONE 0)
  Capturing --> Transferring: connected
  Capturing --> Idle: not connected (queued in PSRAM)
  Idle --> Transferring: connect and queue > 0
  Transferring --> Idle: ACK ok / give up after 5 rounds
  Idle --> Asking: long press / double tap / RECORD_START
  state Asking {
    [*] --> ListeningCue
    ListeningCue --> RingMicRecording: MIC_SOURCE_HINT 0 (photo first)
    ListeningCue --> PhoneMicWait: MIC_SOURCE_HINT 1 (events only)
  }
  Asking --> Transferring: release / RECORD_STOP / 8 s (REC_STOPPED, JPEG + ADPCM queued)
  Asking --> Idle: phone-mic release (BUTTON_UP)
  Idle --> Cue: CUE write (listening / answer ready / error)
  Cue --> Idle: ticks done
  Idle --> PlayingAudio: AUDIO_START (speaker board)
  PlayingAudio --> Idle: AUDIO_END drained (AUDIO_DONE 0) / STOP (AUDIO_DONE 1)
  Idle --> Pattern: MORSE_* / PATTERN write (legacy, optional)
  Pattern --> Idle: done / STOP
  Idle --> DeepSleep: disconnected > idle_sleep_s
  DeepSleep --> Idle: button (EXT0), short/long press decided on wake
  DeepSleep --> Asking: IMU tap (EXT1), hands-free ask on reconnect
```
