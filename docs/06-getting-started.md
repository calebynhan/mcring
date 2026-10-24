# 6. Getting started (today, with or without hardware)

## A. No hardware: run the AI loop on a photo

```bash
git clone <this repo> && cd mcring
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt -e tools/ring-cli
export ANTHROPIC_API_KEY=sk-ant-...
(cd backend && uvicorn app.main:app --port 8000 &)
mcring ask path/to/any-photo.jpg -q "what is this and is it dangerous?" --speak --beep
```

You will see the spoken answer, the Morse-friendly short answer, and the Morse pattern
flashed in the terminal (and beeped with `--beep`).

## B. Stage-0 bench rig

1. Order `hardware/bom/stage0-devkit.csv`.
2. Wire per `firmware/ring-esp32s3/README.md` (button on D1 is enough to start).
3. `pip install platformio && cd firmware/ring-esp32s3 && pio run -e xiao_esp32s3_sense -t upload`
4. `mcring scan` then `mcring listen --speak --echo` (laptop) — press the button.
5. Or build the phone app: `cd app && npm install && npx expo prebuild && npx expo run:android`.

## C. Tests

```bash
(cd python/mcring_core && pytest)   # codecs + C cross-check (needs a C compiler)
(cd backend && pytest)              # API with mocked providers
(cd tools/ring-cli && pytest)       # BLE client logic with a fake transport
(cd app && npm test && npm run typecheck)
(cd firmware/ring-esp32s3 && pio test -e native)
```
