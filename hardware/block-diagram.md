# System block diagrams

## End-to-end

```mermaid
flowchart LR
  subgraph Ring
    T[Trigger<br/>button · double-tap · touch] --> MCU[MCU<br/>ESP32-S3 (stage 0/1)<br/>nRF52840 (stage 2)]
    CAM[Camera<br/>OV2640 / HM01B0 / OVM7692] -->|DVP 8-bit JPEG or raw| MCU
    MIC[PDM mic] -->|PCM → ADPCM| MCU
    MCU -->|RTP on/off| HAP[DRV2605 + LRA]
    MCU --> LED[RGB LED]
    MCU --> BUZ[Piezo]
    MCU -.-> AUX[Aux: air puff (stage 1 experiment)]
    BAT[LiPo 16–40 mAh] --> PMIC[Charger + LDO/buck<br/>BQ25100 · load switch] --> MCU
  end
  MCU <-->|BLE GATT<br/>7a3b0001-…mcring| PHONE[Companion<br/>phone app / desktop CLI]
  PHONE <-->|HTTPS multipart<br/>POST /v1/ask| BE[Backend<br/>FastAPI]
  BE <-->|vision + structured JSON| LLM[Claude Opus 5.5<br/>(or OpenAI)]
  BE -.->|optional| TTS[TTS]
  PHONE -->|speech| EAR[Phone speaker / earbuds]
```

## Request sequence

```mermaid
sequenceDiagram
  participant R as Ring
  participant P as Phone
  participant B as Backend
  participant L as LLM
  R->>R: trigger → camera on → JPEG → camera off
  R->>P: XFER START {len, crc, w, h}
  loop chunks (notifications, no per-chunk ack)
    R->>P: XFER DATA {id, idx, bytes}
  end
  R->>P: XFER END
  P->>R: ACK {missing idx list}  (repeat until empty)
  P->>B: POST /v1/ask (image, question?, voice?)
  B->>L: system + image + question, JSON schema
  L-->>B: {answer, short, confidence, warnings}
  B-->>P: answer + Morse units + ring packet (+ mp3)
  P->>P: speak(answer)
  P->>R: FEEDBACK MORSE_UNITS (split to MTU)
  R->>R: play on LED / haptic / buzzer
```

## Firmware state machine

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Capturing: trigger / CAPTURE
  Capturing --> Idle: fail (<HH> blink)
  Capturing --> Transferring: connected
  Capturing --> Idle: not connected (queued in PSRAM)
  Idle --> Transferring: connect && queue>0
  Transferring --> Idle: ACK ok / give up after 5 rounds
  Idle --> Recording: long press
  Recording --> Transferring: release → ADPCM queued
  Idle --> Feedback: MORSE_* write
  Feedback --> Idle: pattern done / STOP
  Idle --> DeepSleep: disconnected > idle_sleep_s
  DeepSleep --> Capturing: button (EXT0) / tap (EXT1)
```
