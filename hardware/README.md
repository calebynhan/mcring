# Hardware

| File | What |
|---|---|
| `bom/` | Bills of materials for stage 0 (dev kit), stage 1 (oversized ring) and stage 2 (Oura-size), with sources and prices from the research |
| `pinmap.md` | GPIO maps for the XIAO ESP32S3 Sense bench rig, the mcring v1 board and the nRF52840 plan |
| `schematic-notes.md` | Netlist-level description of the stage-1 board (power tree, camera rail, I²C, outputs); the generated netlist in `electrical/` is the authority where they differ |
| `electrical/` | Stage-1 netlist model (`mcring_v1.py`): KiCad netlist, grouped BOM, net listing, ERC, schematic sheets; the GPIO map is checked against `firmware/.../config.h` |
| `pcb/` | Stage-1 floorplan (`floorplan.py` → `board_params.json`, the numbers the enclosure is generated from) and the stage-0 bench wiring diagram |
| `block-diagram.md` | System, sequence and firmware state diagrams (Mermaid) |
| `power_budget.py` → `power-budget.txt` | Shots-per-charge model for ESP32-S3 vs nRF52840 profiles |
| `cad/` | Stage-1 enclosure: CadQuery model generated from `pcb/board_params.json` → shell / lid / key STLs, STEP assembly, views, `fit_report.md` |
| `enclosure/` | Pointer only — the OpenSCAD concept was replaced by `cad/` |

The engineering conclusions that drive these files are in `docs/03-hardware-spec.md` and
`docs/04-feasibility-and-risks.md`; the raw research with links is in `docs/research/`.
