# Hardware

| File | What |
|---|---|
| `bom/` | Bills of materials for stage 0 (dev kit), stage 1 (oversized ring) and stage 2 (Oura-size), with sources and prices from the research |
| `pinmap.md` | GPIO maps for the XIAO ESP32S3 Sense bench rig, the mcring v1 board and the nRF52840 plan |
| `schematic-notes.md` | Netlist-level description of the stage-1 board (power tree, camera rail, I²C, outputs) ready to enter into KiCad |
| `block-diagram.md` | System, sequence and firmware state diagrams (Mermaid) |
| `power_budget.py` → `power-budget.txt` | Shots-per-charge model for ESP32-S3 vs nRF52840 profiles |
| `enclosure/` | Parametric OpenSCAD ring for stage 1 |

The engineering conclusions that drive these files are in `docs/03-hardware-spec.md` and
`docs/04-feasibility-and-risks.md`; the raw research with links is in `docs/research/`.
