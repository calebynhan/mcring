# Touch ring: AliExpress prototype

The phase-C build of the R1-class touch ring from [`docs/11-touch-ring-r1-class.md`](../../docs/11-touch-ring-r1-class.md):
a Seeed XIAO nRF52840 Sense and an MPR121 touch module in a 34 × 25 × 10 mm printed pod, glued
to an adjustable stainless ring blank, with four copper-tape electrodes under the lid.

| File | What |
|---|---|
| [`../bom/touch-ring-aliexpress.csv`](../bom/touch-ring-aliexpress.csv) | Shopping list: item number (= drawing balloon), AliExpress search terms, what to check in each listing, rough price range |
| [`build_sheet.py`](build_sheet.py) | Draws the figures and builds the page from the CSV |
| [`out/ring-side-section.svg`](out/ring-side-section.svg) | Side section along the finger (to scale, 8 px/mm) |
| [`out/ring-end-view.svg`](out/ring-end-view.svg) | End view looking along the finger |
| [`out/ring-top-view.svg`](out/ring-top-view.svg) | Lid from above: electrode layout and swipe direction |
| [`out/ring-wiring.svg`](out/ring-wiring.svg) | Wiring schematic |
| [`out/ring-drawing-sheet.png`](out/ring-drawing-sheet.png) | All four drawings on one image (rendered from the SVGs) |
| [`../../docs/touch-ring-build.html`](../../docs/touch-ring-build.html) | All of the above on one page, with a tick-off shopping list ([published copy](https://claude.ai/artifact/3Jt2drFtZ5xueGAW8G7UEY)) |

```bash
python3 hardware/touch-ring/build_sheet.py
```

Wiring in one line: MPR121 IRQ / SDA / SCL to XIAO D3 / D4 / D5, VCC and ADDR to 3V3 (address
0x5B, so it never clashes with a DRV2605L at 0x5A), E0–E3 to the copper strips; LiPo to the
XIAO's BAT pads. Optional health: MAX30102 on the same I2C bus with INT on D8, NTC divider on
D0 (A0) powered from D1.

Prices in the CSV are rough ranges: AliExpress listings could not be opened when this was
written, so check each listing against its "check_in_listing" column. Module sizes vary by seller;
measure the MPR121 and the cell before printing the pod.
