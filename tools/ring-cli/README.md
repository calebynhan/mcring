# mcring desktop companion (`mcring` CLI)

A Python stand-in for the phone app. It talks BLE to the ring with [bleak](https://github.com/hbldh/bleak)
(macOS / Linux / Windows), forwards photos to the backend, speaks the answer with the OS
text-to-speech, and sends the Morse pattern back to the ring. It also lets you exercise the
whole AI loop with **no hardware at all** (`mcring ask photo.jpg`).

```bash
cd tools/ring-cli
pip install -e ../../python/mcring_core -e .
mcring ask ~/Pictures/any-photo.jpg -q "is it safe to touch?" --speak --beep   # no ring
mcring scan                                   # find the ring
mcring listen --backend http://localhost:8000 --speak --echo   # the real loop
mcring send "R TOXIC" --wpm 12                # play Morse on the ring
mcring config trigger_mask 3                  # button + double tap
mcring morse "SOS" --beep --hex               # local playback + ring packet bytes
```

Inside `listen`, type `c` + Enter to trigger a capture from the computer, `say HELLO` to play
Morse, `p` to ping. Captures are saved under `captures/`.

Tests: `pytest` (BLE is mocked).
