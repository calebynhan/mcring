# Touch ring: everything inside the band

The phase-C build of the R1-class touch ring from [`docs/11-touch-ring-r1-class.md`](../../docs/11-touch-ring-r1-class.md).
Nothing sits on top: like the Even R1 and Oura, the electronics live inside an 8.4 × 2.9 mm band
(size 10). One 52.8 × 6.6 mm two-layer flex wraps around the inside, carrying the touch slider on
its outer face and the parts on its inner face; a curved 15–20 mAh cell fills the rest; a printed
U-channel shell is potted with clear epoxy, which forms the inner surface.

| File | What |
|---|---|
| [`../bom/touch-ring-parts.csv`](../bom/touch-ring-parts.csv) | Parts for a first batch of 5 rings: item number (= drawing balloon), where to buy, MPN or search text, what to check, rough price range |
| [`build_sheet.py`](build_sheet.py) | Draws the figures and builds the page from the CSV; all geometry is in its constants |
| [`out/ring-end-view.svg`](out/ring-end-view.svg) | End view from the fingertip: where every part sits around the band |
| [`out/ring-band-sections.svg`](out/ring-band-sections.svg) | Cuts across the band at the top (touch), side (battery) and palm (sensor) |
| [`out/ring-flex-layout.svg`](out/ring-flex-layout.svg) | The flex laid flat, both faces, to scale: the outline for KiCad |
| [`out/ring-wiring.svg`](out/ring-wiring.svg) | Wiring schematic |
| [`out/ring-drawing-sheet.png`](out/ring-drawing-sheet.png) | All of the above on one image |
| [`../../docs/touch-ring-build.html`](../../docs/touch-ring-build.html) | Drawings, wiring, tick-off parts list and build order on one page ([published copy](https://claude.ai/artifact/3Jt2drFtZ5xueGAW8G7UEY)) |

```bash
python3 hardware/touch-ring/build_sheet.py
```

Main parts: u-blox ANNA-B402 (nRF52833 with antenna, 6.5 × 6.5 × 1.2 mm; alternate Taiyo Yuden
EYSHSNZWZ, 3.25 × 8.55 × 0.9 mm), Azoteq IQS7211E touch controller, ST LIS2DW12 accelerometer,
TI BQ25100 charger, XC6206 3.0 V LDO, LPCV160722-class curved cell. Optional health: MAX30102
bare sensor behind a clear window at the palm side, NTC thermistor.

Things that decide whether it works: the module's antenna end needs a copper keep-out and a range
check from inside the band; the flex can only be flashed by wire before potting, so a Bluetooth
firmware update has to be proven first; the layout is drawn for size 10 and needs a shorter cell
below size 8. Prices in the CSV are rough ranges, not quotes.
