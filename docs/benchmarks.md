# Benchmarks (to be filled in on hardware)

| Metric | Target | Measured | Setup / date |
|---|---|---|---|
| Capture latency (trigger → JPEG ready), QVGA q12 | < 300 ms | | |
| JPEG size QVGA q12 / VGA q15 | 8–15 KB / 30–50 KB | | |
| BLE transfer 15 KB → Android (2M PHY) | < 0.3 s | | |
| BLE transfer 15 KB → iPhone | < 1 s | | |
| Retransmit rounds per transfer | 0–1 | | |
| Backend latency (Claude, QVGA) | 2–5 s | | |
| Button release → first spoken word (phone TTS) | < 4 s | | |
| Button release → first word from the ring speaker (adpcm16k stream) | < 5 s | | |
| Ring speaker playback current (10 s answer) | 100–150 mA avg | | |
| Capture current peak / average | — / 150 mA | | shunt + scope / PPK2 |
| Deep-sleep current (camera gated) | < 30 µA | | |
| Double-tap false positives per hour of normal hand use | < 1 | | |
