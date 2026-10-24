# 5. Cameras and images

The ring's camera is the OV2640 on the XIAO ESP32S3 Sense (stage 0/1) and, on paper, the 2.8 × 3.2 mm OmniVision OVM7692 for stage 2 (`docs/03-hardware-spec.md`, `docs/research/01-camera-modules.md`). Everything the firmware does with it is in one file, `firmware/ring-esp32s3/src/camera_mod.cpp`: power the sensor, configure 14 pins and a 20 MHz clock, let the auto-exposure settle for three frames, grab one JPEG, power it down. The phone forwards that JPEG to `backend/app/images.py` and `backend/app/llm.py`, which hand it to Claude as a base64 image block. This chapter explains the physics and the formats behind those few hundred lines: what a pixel measures, what resolution and field of view really buy you, why the photo is 8–15 KB, what it costs the vision model, and why a lens the size of a grain of rice struggles in a dim restaurant. Read it with `docs/04-feasibility-and-risks.md` ("Physics sanity checks") open.

## 5.1 How a CMOS image sensor makes a picture

**Why it matters in mcring.** `camera_init()` in `camera_mod.cpp` switches on white balance, AWB gain, exposure control, gain control and lens-shading correction (`set_whitebal`, `set_awb_gain`, `set_exposure_ctrl`, `set_gain_ctrl`, `set_lenc`) and nothing else; knowing what those blocks do inside the sensor tells you which knob to turn when a photo comes back dark, green or vignetted (`docs/07-build-guide.md` §1.5). The three stage candidates differ exactly at this level: OV2640 is a colour 1/4" sensor with 2.2 µm pixels, OVM7692 a colour 1/13" with 1.75 µm pixels, HM01B0 a monochrome 3.6 µm sensor with no colour filter (`docs/research/01`, §2 and §7).

**The concepts.** Each pixel is a photodiode in a tiny well: photons knock electrons loose, the electrons accumulate during the exposure, and at readout an amplifier and a 10-bit ADC turn the charge into a number. A pixel measures brightness only; colour comes from a Bayer filter mosaic (RGGB) in front of the array, so every pixel sees one colour band and the missing two are interpolated from neighbours (demosaicing). The sensor's image signal processor (ISP) then does black-level subtraction, white balance (scaling the R and B channels so grey looks grey under the current light), a colour matrix, gamma, lens-shading correction (brightening the corners a small lens darkens), sharpening, scaling to the requested frame size and, on the OV2640, JPEG compression. The "1/4-inch" in a sensor name is a legacy label from vacuum-tube cameras, not a measurement; the useful numbers are pixel pitch and array size. OV2640: 1600 × 1200 at 2.2 µm is a 3.59 × 2.68 mm active area (the datasheet says 3590 × 2684 µm). OVM7692: 640 × 480 at 1.75 µm is 1.12 × 0.84 mm. HM01B0: 320 × 320 at 3.6 µm is 1.15 mm square, and because it has no colour filter every pixel gets all the light. When the OV2640 delivers QVGA, its DSP scales the full 1600 × 1200 frame down by 5 in each direction: the field of view is unchanged, and if it averages rather than drops pixels, 25 photodiodes feed every output pixel, which is why a stage-1 QVGA photo is far cleaner than a native 320 × 240 sensor would be. One datasheet-reading lesson: the OV2640 copies in circulation disagree on standby current (600 vs 900 µA) and well capacity; always note which revision you read.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Branch Education: How do Smartphone Cameras Work?](https://www.youtube.com/watch?v=GU3ABAWA-Jk) | video | 20 min | Animated walk from lens to photodiode to Bayer filter to ISP; the best first exposure to what a pixel is |
| [Edmund Optics: How Do Cameras Work? (video tutorial)](https://www.edmundoptics.com/knowledge-center/video/tutorials/how-do-cameras-work/) | video | 10 min | A machine-vision vendor's short, correct explanation of sensor, pixels and lens working together |
| [Cambridge in Colour tutorials](https://www.cambridgeincolour.com/) | article (site) | 2 h | The reference tutorial site for photographers: digital sensors, Bayer demosaicing, white balance, noise, diffraction; interactive diagrams |
| [OV2640 datasheet (Waveshare copy)](https://files.waveshare.com/wiki/common/OV2640DS_en.pdf) | datasheet (PDF) | 1 h | The actual sensor: pixel size, image area, the DSP block diagram, the AEC/AGC/AWB registers the driver pokes |
| [OmniVision OVM7692 product brief](https://www.ovt.com/wp-content/uploads/2026/04/OVM7692-PB-v1.9-WEB.pdf) | datasheet (PDF) | 20 min | The stage-2 candidate: 1/13", 1.75 µm, 2.8 × 3.2 × 2.6 mm, DVP + SCCB, 2.8 V |

**Check yourself.**

1. From pixel pitch and array size, compute the OV2640's active area and compare it with the datasheet's 3590 × 2684 µm.
2. If the OV2640's QVGA scaler averages the 5 × 5 input pixels behind each output pixel, by how much does the shot-noise SNR improve, in linear terms and in dB?
3. Why does `camera_init()` enable `set_lenc`, and what would a QVGA photo look like without it on a 2.8 mm lens?
4. A stage-2 OVM7692 photo looks magenta on a lawn. Which ISP block is to blame and why does a lawn confuse it?

<details><summary>Answers</summary>

1. 1600 × 2.2 µm = 3520 µm; 1200 × 2.2 µm = 2640 µm. Close to, but a little under, 3590 × 2684 µm; the difference is the black-level and dummy pixels around the active array.
2. Averaging 25 samples improves SNR by √25 = 5×, about +14 dB, if the noise is independent per pixel (shot and read noise are).
3. Lens-shading correction brightens the edges; a tiny wide-angle lens delivers much less light to the corners, so without it the photo has dark corners (vignetting) that the model may read as "dim scene".
4. Auto white balance. Its grey-world assumption is that the scene averages to grey; a frame that is mostly green gets its green pulled down and R/B pushed up, giving a magenta cast. A second shot with something neutral in frame fixes it.

</details>

## 5.2 Resolution, pixel size, focal length and field of view

**Why it matters in mcring.** `protocol/ble-gatt.md` lets the phone pick frame sizes 1–5 (QQVGA 160 × 120 to XGA 1024 × 768) and `config.h` defaults to QVGA; `docs/04` argues that "a ~70–90° FOV forgives aim" and that depth of field is effectively infinite from ~15 cm; `hardware/cad/mcring_stage1.py` has a Ø4.6 mm lens bore for the OV2640 head and a `--lens-d 3.5` option for the HM01B0 module. Those are field-of-view and focal-length decisions, and they are what makes a fixed-focus ring camera usable at all.

**The concepts.** A camera is, to first order, a pinhole: the sensor sits a focal length f behind the lens, and an object at angle θ lands at x = f·tan θ from the centre. The horizontal field of view is therefore HFOV = 2·atan(w / 2f), where w is the active width of the sensor. For the OV2640 (w = 3.59 mm) a 70° HFOV needs f = 3.59 / (2·tan 35°) = 2.56 mm, and 90° needs 1.80 mm; that is why the FPC camera head is a few millimetres long. For the OVM7692 (w = 640 × 1.75 µm = 1.12 mm) the same 70° needs f = 0.80 mm: the lens is sub-millimetre and most of the 2.6 mm cube is package. Resolution turns into angular resolution: 320 px / 70° = 4.6 px per degree at QVGA, 9.1 at VGA. A 10 cm object at 50 cm subtends 2·atan(5/50) = 11.4°, so 52 px at QVGA, plenty for "what is this"; a 5 mm letter at 30 cm subtends 0.95°, so 4.4 px at QVGA and 8.7 px at VGA, which is why the `read_text` mode in `backend/app/prompts.py` wants VGA, not QVGA. Depth of field follows from the hyperfocal distance H = f² / (N·c), with N the f-number and c the acceptable blur circle (take two pixels at the output resolution). For an f = 2.5 mm, f/2.8 lens at QVGA, c = 2 × 3.59 mm / 320 = 22 µm and H = 6.25 / (2.8 × 0.0224) ≈ 100 mm: everything from H/2 ≈ 5 cm to infinity is sharp, so no focus mechanism is needed. At VGA c halves, H doubles to ~20 cm and the near limit moves to ~10 cm. Finally, resolution changes pixels, not framing, only if the sensor scales the full frame (OV2640 does); a sensor that crops a window to reach a smaller size narrows the field of view instead.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Edmund Optics: Understanding Focal Length and Field of View](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/understanding-focal-length-and-field-of-view/) | article | 30 min | The FOV equations with worked examples, and the honest caveat that the lens "vertex" is an approximation |
| [Arducam: OV2640 overview](https://www.arducam.com/blog/ov2640/) | article | 20 min | What the OV2640 modules on the market are, lens options and FOVs, the ESP32-CAM lineage |
| [OV2640 datasheet (Espressif copy)](https://dl.espressif.com/dl/schematics/Camera_OV2640.pdf) | datasheet (PDF) | 30 min | Image area and pixel size for the arithmetic above; the scaler/windowing registers that decide crop vs scale |
| [OmniVision OVM7692 product page](https://www.ovt.com/products/ovm7692/) | datasheet | 10 min | The stage-2 numbers (1/13", 1.75 µm) that make the lens sub-millimetre |
| [Cambridge in Colour tutorials](https://www.cambridgeincolour.com/) | article (site) | 1 h | Depth of field, hyperfocal distance and diffraction tutorials with calculators |

**Check yourself.**

1. How many pixels per degree does XGA (1024 × 768) give at 70° HFOV, and how many pixels tall is a 5 mm letter at 30 cm?
2. What focal length gives the OVM7692 an 80° HFOV?
3. The stage-1 head is swapped for a lens with f = 3.5 mm. What happens to the HFOV, and is that better or worse for a finger-pointed camera?
4. A hypothetical sensor reaches QQVGA by cropping a 160 × 120 window out of its 640 × 480 array. How does the field of view change compared with scaling?

<details><summary>Answers</summary>

1. 1024 / 70 = 14.6 px/°; 0.95° × 14.6 ≈ 14 px tall, comfortably legible.
2. f = 1.12 / (2·tan 40°) = 1.12 / 1.678 = 0.67 mm.
3. HFOV = 2·atan(3.59 / 7.0) = 54°. Narrower: more pixels on the subject but less forgiving of aim; `docs/04` wants 70–90°.
4. Cropping keeps the same pixel pitch and focal length, so the HFOV shrinks by 4× in each direction (a 70° lens becomes ~19°); scaling keeps the 70° and just lowers detail.

</details>

## 5.3 Exposure, gain, AEC/AGC/AWB, and rolling versus global shutter

**Why it matters in mcring.** `camera_capture()` throws away three frames "to let AEC/AWB settle (~100–150 ms at QVGA)" before keeping one, and `docs/07` §1.5 says a dark or green photo means that was not enough. `protocol/ble-gatt.md` budgets 150–400 ms for `CAPTURE_STARTED` → `CAPTURE_DONE`, and `docs/04` turns that into the "point, hold, ask" gesture: the photo is taken before the listening tick. The OV2640 and OVM7692 are rolling-shutter sensors on a moving hand; the research report lists the global-shutter OVM6211 as the "watch list" alternative.

**The concepts.** The signal in a pixel is proportional to scene brightness × exposure time × pixel area / N² (the f-number squared), and the ISP then multiplies it by a gain. Auto-exposure control (AEC) adjusts exposure time, auto-gain control (AGC) adjusts the multiplier, and both are feedback loops that look at the previous frame's brightness and correct the next one. Each iteration costs a frame: at 20–30 fps a QVGA frame is 33–50 ms, so three frames are 100–150 ms and a scene that changed a lot (dark pocket to bright window) may need five or six. Exposure time cannot exceed the frame time unless the sensor lowers its frame rate, which the OV2640 does in the dark, so capture gets slower exactly when it is already noisy. The driver's `set_aec2(s, 1)` selects the OV2640's alternative auto-exposure algorithm, commonly enabled for stills because it converges better on high-contrast scenes; `set_gain_ctrl` lets AGC run; `set_whitebal` + `set_awb_gain` enable auto white balance, another feedback loop (so the "green" photo is simply AWB caught mid-convergence). Mains lighting flickers at 100/120 Hz; an exposure much shorter than 10 ms samples that flicker as horizontal bands, which sensor banding filters suppress. Rolling shutter means rows are exposed and read one after another, top to bottom, over roughly one frame time; anything moving during that 33 ms is skewed: a hand moving at 0.5 m/s shifts the scene 0.5 × 0.033 = 16 mm between the first and last row, which is a visibly leaning bottle. A global shutter exposes all rows at once and reads them out from per-pixel storage, at the cost of pixel area (and, for the OVM6211, availability). The practical rule for the ring is in `docs/04`: hold still for the 150–400 ms after the trigger, and expect the photo to lag the moment you pressed.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [esp32-camera `sensor.h`](https://github.com/espressif/esp32-camera/blob/master/driver/include/sensor.h) | code | 20 min | The exact `sensor_t` API `camera_mod.cpp` calls: `set_exposure_ctrl`, `set_aec2`, `set_aec_value`, `set_agc_gain`, `set_gainceiling`, `set_whitebal`, `set_awb_gain`, `set_wb_mode` |
| [OV2640 datasheet (Waveshare copy)](https://files.waveshare.com/wiki/common/OV2640DS_en.pdf) | datasheet (PDF) | 1 h | The AEC/AGC/AWB register descriptions behind those calls; banding filter; frame-rate control |
| [Teledyne Vision Solutions: Rolling vs Global Shutter](https://teledynevisionsolutions.com/learn/learning-center/imaging-fundamentals/rolling-vs-global-shutter) | article | 15 min | The clearest diagrams of row-by-row readout and the skew it produces |
| [Teledyne Photometrics: Rolling vs Global Shutter](https://photometrics.com/learn/advanced-imaging/rolling-vs-global-shutter) | article | 15 min | The same topic from the scientific-camera side, including why global shutter costs read noise or pixel area |
| [Cambridge in Colour tutorials](https://www.cambridgeincolour.com/) | article (site) | 1 h | Camera exposure (aperture, shutter, ISO) and white balance tutorials; the mental model behind AEC/AGC/AWB |

**Check yourself.**

1. The sensor runs at 25 fps in a dim room. How long do the three discarded frames take, and what does the trigger-to-photo latency become if you raise the discard count to six?
2. Estimate the rolling-shutter skew for a 1 m/s hand sweep at a 33 ms frame time, and at a 10 ms frame time (bright light, high frame rate).
3. Three extra warm-up frames at ~40 ms each on a board drawing ~150 mA: how many µAh is that, and what fraction of the 154 µAh photo in `hardware/power-budget.txt`?
4. Why can a photo be both dark and green at the same time?

<details><summary>Answers</summary>

1. 3 × 40 ms = 120 ms; six frames are 240 ms, so the latency grows from the protocol's 150–400 ms toward ~300–500 ms. Make the count adaptive (check frame brightness) rather than always six.
2. 1 m/s × 33 ms = 33 mm of skew at the subject plane; at 10 ms, 10 mm. Faster frame rates (bright scenes) shrink the artefact.
3. 0.12 s × 150 mA = 18 mA·s = 5 µAh, about 3% of a 154 µAh shot: cheap insurance.
4. AEC and AWB are independent loops that both start from power-on defaults every capture (the driver is re-initialised each time); after three frames the exposure may still be short (dark) and the channel gains still at their defaults (a green cast, because the Bayer array has twice as many green pixels and raw frames look green until AWB corrects them).

</details>

## 5.4 The DVP parallel bus, why it needs 13-plus pins, and SCCB

**Why it matters in mcring.** `config.h` lists fourteen camera GPIOs on the XIAO: `CAM_PIN_Y2`…`Y9` (eight data lines), `XCLK`, `PCLK`, `VSYNC`, `HREF`, `SIOD` and `SIOC`; `PWDN` and `RESET` are −1 because the Sense board ties them off. That pin count is the whole reason the stage-1 board needs an ESP32-S3 and the whole stage-2 problem: `docs/04` notes that "no BLE SoC has a camera interface" and plans a bit-banged 8-bit DVP at QQVGA grayscale on the nRF52840, with the HM01B0's 1-bit mode as the fallback (`docs/research/01` §8). The TPS22916 load switch on `PIN_CAM_PWR` exists because an un-gated camera idles at 3 mA (`docs/03`).

**The concepts.** DVP (digital video port) is the old-fashioned parallel camera interface: the host feeds the sensor a master clock, XCLK (20 MHz from LEDC timer 0 in `camera_init()`), and the sensor streams back one byte per PCLK edge on D0–D7, with VSYNC marking frame boundaries and HREF (or HSYNC) marking the valid bytes of each line. That is 8 + 3 + 1 = 12 signal lines, plus the two-wire control bus (13–14 GPIOs), plus optional PWDN and RESET. The data rate is what makes it hard: an uncompressed QVGA YUV422 frame is 320 × 240 × 2 = 153,600 bytes, 4.6 MB/s at 30 fps, and PCLK runs at tens of MHz. In JPEG mode the OV2640's DSP emits only ~10 KB per frame, but PCLK keeps running and HREF gates the valid bytes, so the host still has to catch every edge. The ESP32-S3 does this with its LCD_CAM peripheral: it latches a byte per PCLK edge and the GDMA engine writes the stream into a frame buffer in PSRAM (`fb_location = CAMERA_FB_IN_PSRAM` in `camera_mod.cpp`) with the CPU idle. The nRF52840 has no such peripheral, so a bit-bang has the CPU read the GPIO port on every PCLK edge (or uses GPIOTE + PPI to trigger a TIMER/DMA trick); at 64 MHz that caps out around a megabyte per second in practice, which is why the stage-2 plan is 160 × 120 8-bit grayscale (19.2 KB per frame) at a few frames per second, or the HM01B0's 1-bit serial mode with only four lines. SCCB (Serial Camera Control Bus) is OmniVision's control interface: two wires (SIO_C, SIO_D), I²C-like timing at 100–400 kHz, an 8-bit register address and 8-bit data, write address 0x60 on the OV2640 (7-bit 0x30). It differs from I²C in that the ninth bit is "don't care" rather than an acknowledge and there is no clock stretching; it is close enough that `esp32-camera` drives it with the ordinary I²C peripheral. The OV2640's registers live in two banks selected through register 0xFF (DSP bank and sensor bank), which is the first thing to know when reading its datasheet.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [ESP32-S3 Technical Reference Manual](https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf) | datasheet (PDF) | 1 h | The LCD_CAM chapter: how PCLK/VSYNC/HREF become a DMA stream; read it once to see what the nRF52840 lacks |
| [OmniVision SCCB specification v2.2 (Cornell course mirror)](https://people.ece.cornell.edu/land/courses/ece4760/FinalProjects/f2021/jfw225_aei23_dsb298/jfw225_aei23_dsb298/SCCBSpec_AN.pdf) | spec (PDF) | 30 min | The actual bus definition: 2- and 3-wire modes, the don't-care ninth bit, timing |
| [espressif/esp32-camera (GitHub)](https://github.com/espressif/esp32-camera) | code | 1 h | The driver `camera_mod.cpp` uses: `camera_config_t`, pin assignment, frame buffers, supported sensors (OV2640, OV3660, HM0360, GC0308...) |
| [Seeed wiki: Camera usage on XIAO ESP32S3 Sense](https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/) | guide | 30 min | The board's exact pin map (the numbers in `config.h`) and a known-good capture sketch |
| [nRF52840 Product Specification v1.8](https://infocenter.nordicsemi.com/pdf/nRF52840_PS_v1.8.pdf) | datasheet (PDF) | 45 min | GPIOTE, PPI and TIMER chapters: the only tools a stage-2 bit-bang has; confirm for yourself there is no camera peripheral |
| [ArduCAM/RPI-Pico-Cam (GitHub)](https://github.com/ArduCAM/RPI-Pico-Cam) | code | 30 min | HM01B0 captured by an RP2040: a working example of a small MCU reading a DVP-class sensor without a camera peripheral |

**Check yourself.**

1. Count the camera GPIOs in `config.h` for `BOARD_XIAO_ESP32S3_SENSE`. How many would a design need if it also drove PWDN and RESET?
2. At 30 fps, how many bytes per second does a QVGA YUV422 stream carry, and how long is one frame's worth of bytes at a 10 MHz PCLK?
3. Why is XCLK generated by LEDC timer 0 rather than a GPIO toggled in software, and what happens to the LED PWM channel that shares that timer (see chapter 3.4)?
4. A bit-banging MCU misses one PCLK edge in the middle of a JPEG frame. What does the decoder see?

<details><summary>Answers</summary>

1. 14 (8 data + XCLK, PCLK, VSYNC, HREF + SIOD, SIOC). 16 with PWDN and RESET.
2. 153,600 × 30 = 4.6 MB/s. At 10 MHz one byte per edge, 153,600 bytes take 15.4 ms (the rest of the 33 ms frame is blanking).
3. A 20 MHz square wave needs hardware; software toggling cannot reach it and would jitter. LEDC at 80 MHz / 20 MHz has only 4 counts per period (2 bits of duty resolution), so that timer is useless for dimming and the LED must use another.
4. Every later byte is shifted by one position: the JPEG entropy stream is corrupted and the decoder reports a missing end-of-image marker (the "NO-EOI" error that `esp32-camera` users see) or garbage blocks; the firmware's `fb->len < 100` check only catches total failures.

</details>

## 5.5 JPEG: why a 320 × 240 photo is 8–15 KB

**Why it matters in mcring.** `camera_init()` asks for `PIXFORMAT_JPEG` with `jpeg_quality = DEFAULT_JPEG_QUALITY` (12, range 1 best … 63 worst, `config.h`); the `CAPTURE` opcode and `SET_CONFIG DEFAULT_QUALITY` expose the same number to the phone (`protocol/ble-gatt.md`). `docs/02` quotes "≈ 8–15 KB" for a q12 QVGA, the README's rule is "keep images ≤ 30 KB so the BLE leg stays under ~1 s on iPhone", and `backend/app/images.py` deliberately passes small JPEGs through untouched rather than re-encoding them.

**The concepts.** Uncompressed, a 320 × 240 colour image is 320 × 240 × 3 = 230,400 bytes; JPEG gets it to 8–15 KB, a 15–30:1 ratio, by throwing away what eyes do not notice. The pipeline: convert RGB to YCbCr (brightness plus two colour-difference channels); subsample the colour channels (4:2:0 keeps one Cb and one Cr per 2 × 2 block, so colour costs half a byte per pixel instead of two, and the image is already 1.5 bytes/pixel); cut each channel into 8 × 8 blocks and apply the discrete cosine transform, which turns 64 pixel values into 64 frequency coefficients, most of the energy sitting in the top-left low frequencies; divide each coefficient by an entry of a quantisation table and round, which turns most of the high-frequency coefficients into zeros; then read the block in a zigzag, run-length-code the zeros and Huffman-code the rest. The "quality" number scales the quantisation table: a lower OV2640 quality value means smaller divisors, finer steps and bigger files. Smooth scenes (a wall, sky) compress to a few KB, textured ones (foliage, text) to 15–20 KB, and VGA has four times the pixels, hence the protocol's 40–60 KB. Below a quality of roughly 5 the OV2640's JPEG output becomes unreliable (users report truncated frames with missing end-of-image markers at UXGA and quality 0), so stay in the 8–20 range. The file size is also the transfer time: 15,000 bytes in 178-byte iOS chunks is 85 notifications, about 1.4 s at the ~11 KB/s the protocol expects; in 510-byte Android chunks it is 30 notifications, about 0.3 s. On the backend, `images.py` re-encodes only when an upload is larger than `max_image_edge` (1024 px), at Pillow quality 88, and fixes EXIF rotation; Claude's own vision guidance warns that repeated lossy passes add artefacts and make text harder to read, which is one more reason to send the ring's JPEG as is.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Parametric Press: Unraveling the JPEG](https://parametric.press/issue-01/unraveling-the-jpeg/) | interactive | 45 min | Edit a real JPEG's YCbCr, subsampling, DCT and quantisation in the browser and watch the bytes and the picture change |
| [Computerphile: JPEG DCT, Discrete Cosine Transform (JPEG Pt2)](https://www.youtube.com/watch?v=Q2aEzeMDHMA) | video | 15 min | Mike Pound on 8 × 8 blocks, DCT and quantisation with real numbers; part 1 covers colour spaces |
| [PetaPixel: How JPEG Handles Colors and Compression](https://petapixel.com/2015/05/24/how-jpeg-handles-colors-and-compression/) | article | 10 min | A photographer's summary of the Computerphile series; good for a second pass |
| [ParametricPress/01-unraveling-the-jpeg (GitHub)](https://github.com/ParametricPress/01-unraveling-the-jpeg) | code | 30 min | The JavaScript encoder/decoder behind the article: a readable reference if you ever decode a JPEG on the phone |
| [esp32-camera component (Espressif registry)](https://components.espressif.com/components/espressif/esp32-camera) | docs | 15 min | The `jpeg_quality` 0–63 definition, frame-buffer sizing and the sensors that produce JPEG in hardware |

**Check yourself.**

1. A 12 KB QVGA JPEG: what compression ratio is that against the raw 24-bit image, and against the 4:2:0 YCbCr intermediate?
2. How many 178-byte chunks does a 55 KB VGA photo need on iOS, and how long at 11 KB/s? Compare with the README's ≤ 30 KB rule.
3. A photo of a printed menu compresses to 22 KB at q12 while a photo of a wall is 6 KB. Why, in terms of DCT coefficients?
4. Which frame size and quality would you pick for `read_text` mode, and what transfer time does that imply on iOS?

<details><summary>Answers</summary>

1. 230,400 / 12,000 = 19:1 raw; the 4:2:0 intermediate is 320 × 240 × 1.5 = 115,200 bytes, so 9.6:1 from there.
2. 55,000 / 178 = 309 chunks, about 5 s. That is why the rule exists: QVGA by default, VGA only when text must be read.
3. Text and edges put energy into high-frequency coefficients that survive quantisation; a flat wall has almost only the DC coefficient per block, so nearly every block is a handful of bytes.
4. VGA (code 3) at q10–12, roughly 40–60 KB, 4–5 s on iOS or ~1 s on Android; or QVGA with the ring held closer. Make it a per-request `CAPTURE quality, frame_size` rather than a persisted default.

</details>

## 5.6 Image tokens and what a photo costs the vision model

**Why it matters in mcring.** `backend/app/llm.py` wraps the JPEG as a base64 `image` content block and calls `claude-opus-5-5` (`backend/app/config.py`) with the stable system prompt in `backend/app/prompts.py`, written to cache well; `images.py` caps uploads at a 1024 px long edge. `docs/04` estimates "~1–1.5 K tokens" per QVGA image; the current Claude vision documentation gives a formula that makes a QVGA photo far cheaper than that, and worth checking yourself.

**The concepts.** Claude processes images in 28 × 28 pixel patches, each one visual token, so an image costs ⌈w/28⌉ × ⌈h/28⌉ tokens. QVGA: ⌈320/28⌉ × ⌈240/28⌉ = 12 × 9 = 108 tokens. QQVGA: 6 × 5 = 30. VGA: 23 × 18 = 414. SVGA: 29 × 22 = 638. XGA, the backend's 1024 px cap: 37 × 28 = 1,036. Models from Claude 4.7 on accept up to a 2,576 px long edge and 4,784 tokens before downscaling; the docs' example table lists a 1000 × 1000 image at 1,296 tokens and a 1092 × 1092 image at 1,521, which is roughly where the "1–1.5 K" figure in `docs/04` comes from, a 1-megapixel image, not a QVGA one. Cost is tokens × the model's input price: at Claude Opus 5.5's $4 per million input tokens at the time of writing (check the pricing page; it changes), a QVGA photo is 108 × $4 / 10⁶ = $0.00043, about 43 cents per thousand photos. The image is therefore not what the voice turn costs; the fixed parts are: the system prompt (about 540 tokens by the old four-characters-per-token rule, nearer 700 under the Claude 4.7+ tokenizer, both estimates until measured; cacheable only if it is at least 512 tokens, and cache reads on Opus 5.5 are billed at 0.05× the input price), the transcript, and the answer (~100 output tokens at $20 per million, $0.002, five times the photo). Two practical consequences. First, prompt caching needs a prefix of at least 512 tokens on Opus 5.5 or the `cache_control` marker is silently ignored (no error, just `cache_creation_input_tokens: 0`); measure `SYSTEM_PROMPT` with the free `count_tokens` endpoint, which accepts images too, and treat `usage.cache_read_input_tokens > 0` on the second request as the only proof that the cache works. Chapter 9.4 quotes the same prompt at ~540 tokens; that is the estimate, not a measurement, and the prompt sits close enough to the minimum that measuring it is not optional. Second, resolution should be chosen for legibility, not cost: Claude's guidance says small images and small text are where it errs, so QVGA for identification and VGA for `read_text` is the right split, and both are cheap. The docs also recommend putting the image before the text in the content list and warn against multiple lossy re-encodes.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Claude docs: Vision](https://platform.claude.com/docs/en/build-with-claude/vision) | docs | 30 min | The 28 × 28 patch formula, size limits, the example token table, image-quality guidance and the base64 block `llm.py` builds |
| [Claude docs: Token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting) | docs | 15 min | `count_tokens` accepts base64 images: measure a real ring JPEG plus the system prompt instead of guessing |
| [Claude docs: Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | docs | 30 min | Why `prompts.py` keeps the system prompt static, the 512-token minimum and the cache-read discount |
| [Claude pricing](https://claude.com/pricing) | docs | 5 min | The per-million-token prices to plug into the formula; revisit whenever the model string in `config.py` changes |

**Check yourself.**

1. Compute the visual tokens for 160 × 120, 320 × 240, 640 × 480 and 800 × 600, and show that the backend's 1024 px cap bounds any photo at ~1,036 tokens.
2. A user takes 50 photo questions a day for a month. What do the images cost at $4 per million input tokens, and what do the ~100-token answers cost at $20 per million?
3. `SYSTEM_PROMPT` in `prompts.py` is 2,151 characters (366 words). Is it safely above the 512-token caching minimum? How would you find out for certain, and what would you change if it is not?
4. Why is `docs/04`'s "~1–1.5 K tokens per QVGA image" wrong, and what image size does that figure actually describe?

<details><summary>Answers</summary>

1. 6 × 5 = 30; 12 × 9 = 108; 23 × 18 = 414; 29 × 22 = 638; 1024 × 768 → 37 × 28 = 1,036 (and a 1024 × 1024 square would be 37 × 37 = 1,369).
2. 1,500 photos × 108 tokens = 162 K tokens → $0.65. Answers: 1,500 × 100 = 150 K output tokens → $3.00. The text side dominates.
3. Not safely. English prose runs roughly 4 characters per token on older tokenizers, so 2,151 characters is ~540 tokens (the figure chapter 9.4 uses); the Claude 4.7+ tokenizer counts about 30% more, so ~700. Both are estimates and the lower one is barely above 512. Measure once with `client.messages.count_tokens(model="claude-opus-5-5", system=SYSTEM_PROMPT, messages=[...])`, which is free, then confirm in real traffic that `usage.cache_read_input_tokens > 0` on a second request within five minutes. If both `cache_creation_input_tokens` and `cache_read_input_tokens` stay 0, the prefix is below the minimum: lengthen the stable part of the prompt (more rules, never per-request content); adding more `cache_control` markers does nothing.
4. The formula gives 108 for QVGA. 1,000–1,500 tokens is a ~1-megapixel image (1000 × 1000 = 1,296; 1092 × 1092 = 1,521), i.e. the backend's 1024 px cap case, not the ring's default photo. Update the doc.

</details>

## 5.7 Low light with a tiny lens

**Why it matters in mcring.** `docs/04` says it plainly: "a 2.8 mm camera cube has a ~1 mm aperture... low light will be noisy. A flower in daylight is fine; a menu in a dim restaurant is marginal. Stage-1 OV2640 (1/4") is much better in low light." The system prompt in `prompts.py` even tells the model what to say when "the image is too dark, blurred or shows nothing identifiable". There is no flash LED in the design because the power budget cannot carry one.

**The concepts.** Light arrives as photons, and counting photons is noisy: the standard deviation of a count S is √S, so the best possible signal-to-noise ratio of a pixel is SNR = S/√S = √S. Ten times less light means √10 ≈ 3.2× less SNR, −10 dB. Photons per pixel scale with illuminance × exposure time × pixel area × filter transmission / N². Pixel area is where the sensors differ most: OV2640 2.2 µm → 4.84 µm²; OVM7692 1.75 µm → 3.06 µm² (0.63× the OV2640); HM01B0 3.6 µm → 12.96 µm² (2.7×), and with no Bayer filter each pixel gets roughly three times the photons again, so the monochrome Himax collects on the order of ten times more light per pixel than the OVM7692. The OV2640's QVGA scaler adds its own factor: 25 input pixels per output pixel is an effective 11 µm pixel, which is why the stage-1 ring takes acceptable photos indoors. Typical illuminance: direct sun 10,000–100,000 lux, overcast 1,000, an office 300–500, a dim restaurant 50–100, candlelight ~10; from office to restaurant is −7 to −10 dB of SNR before the ISP compensates with longer exposure (motion blur on a hand-held camera) and higher gain (which amplifies noise and colour speckle). The aperture matters too: f/2.0 passes twice the light of f/2.8. And a tiny lens hits a physical limit, diffraction: the smallest spot it can form has an Airy-disk diameter of about 2.44·λ·N, which for green light (λ = 0.55 µm) at f/2.8 is 3.8 µm, larger than the OVM7692's 1.75 µm pixel, so the sensor is diffraction-limited and its 640 × 480 array carries only QVGA-class real detail. The practical advice for the wearer follows: point at the lit side of the object, hold still through the capture, and expect the model to ask for another photo in dim light.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [Cambridge in Colour tutorials](https://www.cambridgeincolour.com/) | article (site) | 1.5 h | Image noise, sensor size, pixel size and diffraction (Airy disk) tutorials with calculators; the whole of this section in more depth |
| [OV2640 datasheet (Waveshare copy)](https://files.waveshare.com/wiki/common/OV2640DS_en.pdf) | datasheet (PDF) | 20 min | Sensitivity, dynamic range and SNR figures for the stage-1 sensor; the frame-rate drop in low light |
| [OmniVision OVM7692 product brief](https://www.ovt.com/wp-content/uploads/2026/04/OVM7692-PB-v1.9-WEB.pdf) | datasheet (PDF) | 15 min | Pixel size and lens parameters for the stage-2 arithmetic above |
| [Branch Education: How do Smartphone Cameras Work?](https://www.youtube.com/watch?v=GU3ABAWA-Jk) | video | 20 min | Why phones stack frames and use big pixels for night shots; the ring can do neither |

**Check yourself.**

1. Compute the pixel-area ratios OV2640 : OVM7692 : HM01B0 and express the HM01B0's advantage over the OVM7692 in dB (area only).
2. A scene drops from 400 lux to 40 lux. If AEC compensates with 10× longer exposure, what happens to shot-noise SNR, and what else goes wrong on a ring?
3. Compute the Airy-disk diameter at f/2.4 and f/4 for λ = 0.55 µm, and say which pixel pitches each can resolve.
4. Why does averaging 5 × 5 pixels help SNR but not help a diffraction-limited sensor's real resolution?

<details><summary>Answers</summary>

1. 4.84 : 3.06 : 12.96 → 1 : 0.63 : 2.68. HM01B0 vs OVM7692: 12.96 / 3.06 = 4.2× area, 10·log10(4.2) ≈ +6 dB in signal, about +3 dB in shot-noise SNR (SNR scales with √signal); the missing colour filter adds roughly another factor of 3 in photons.
2. Same photon count, so the same SNR as before, but a 10× longer exposure (say 30 → 300 ms) on a hand means motion blur, and if the sensor cannot expose that long it raises gain instead, which does lower SNR.
3. 2.44 × 0.55 × 2.4 = 3.2 µm; at f/4, 5.4 µm. The 3.2 µm spot roughly matches a 2.2 µm pitch at two pixels per spot; 5.4 µm needs ~3 µm pixels (the HM01B0's 3.6 µm is fine, the OVM7692's 1.75 µm is oversampling blur).
4. Averaging reduces random noise (√N) but cannot recover detail the lens never formed; the blur is deterministic and already larger than the pixel.

</details>

## 5.8 Choosing the sensor: OV2640 versus HM01B0 versus OVM7692

**Why it matters in mcring.** `docs/research/01-camera-modules.md` §7 is the master comparison and §9 the recommended path; `docs/03` turns it into the stage table (OV2640 FPC head or HM01B0 lensed module for stage 1, OVM7692 in a 4–5 mm pod for stage 2); `hardware/cad/mcring_stage1.py --lens-d 3.5` is the HM01B0 variant of the shell; `firmware/ring-nrf52840` has the camera HAL stubbed because the sensor choice is still open. The report's loudest warning is that the famous 0.65 mm OVM6948 is analog and needs a 6 × 6 mm bridge chip: wrong part for a BLE ring.

**The concepts.** The decision is four trade-offs. Interface and pins: all three are DVP-class, but only the OV2640 and OVM7692 need the full 8-bit bus; the HM01B0 can run 1-bit serial over four lines (D0, PCLK, HSYNC, VSYNC), which is what makes it plausible on an MCU without a camera peripheral. Compression: the OV2640 produces JPEG in hardware, so the MCU never touches pixels and a QVGA photo is 8–15 KB; the HM01B0 and OVM7692 deliver raw frames, so either the MCU encodes (expensive on an nRF52840) or the radio carries raw bytes (160 × 120 × 1 = 19.2 KB grayscale, 320 × 320 × 1 = 102 KB for a full HM01B0 frame, versus a ~10 KB JPEG). Power: the HM01B0 runs QVGA at 30 fps under 2 mW and sleeps at 200 µW; the OVM7692 is ~120 mW active and 23 µA in standby; the OV2640 on the XIAO is part of a 300–370 mA peak when the whole board captures (`docs/03`), which is the number that bans the ESP32-S3 from a 16–24 mAh stage-2 cell. Size and buyability: OV2640 heads are 21 × 12.5 mm boards with an 8–9 mm lens head, cheap and everywhere; the lensed HM01B0 module is 20 × 12.5 × 3.4 mm at ~$12; the OVM7692 is 2.8 × 3.2 × 2.6 mm, DigiKey-stocked, but a 25-ball 0.4 mm-pitch CSP with no breakout board, so it only exists for you once you have a custom flex and an assembly house. Colour versus mono is the last axis: the model identifies a flower better in colour, but mono buys low-light performance and bandwidth. Energy per photo puts it in perspective: `hardware/power-budget.txt` books 154 µAh per ESP32-S3 + OV2640 shot, dominated by the radio and the MCU, not the sensor; an HM01B0 frame at 2 mW for 100 ms is about 0.02 µAh, and an OVM7692 capture at 120 mW for 300 ms is 120 mW / 2.8 V × 0.3 s ≈ 3.6 µAh. The verdict in the research report stands: OV2640 for stage 0/1 because the pipeline exists, HM01B0 if you want to learn low-power capture now, OVM7692 as the only realistic digital stage-2 part, OVM6211 if stock ever appears, and read the IRIS paper (linked from `docs/research/01` §0) before designing the stage-2 pod.

**Learn it.**

| Resource | Type | Time | Why this one |
|---|---|---|---|
| [OmniVision OVM7692 product page](https://www.ovt.com/products/ovm7692/) | datasheet | 15 min | The stage-2 part's official specs; compare them line by line with `docs/research/01` §7 |
| [OmniVision OVM7692 product brief](https://www.ovt.com/wp-content/uploads/2026/04/OVM7692-PB-v1.9-WEB.pdf) | datasheet (PDF) | 20 min | Package drawing (2.8 × 3.2 × 2.6 mm), interfaces, power; what the custom flex has to land |
| [Arducam: OV2640 overview](https://www.arducam.com/blog/ov2640/) | article | 20 min | The stage-0/1 part: module variants, lens heads, FPC pinouts |
| [espressif/esp32-camera (GitHub)](https://github.com/espressif/esp32-camera) | code | 30 min | The supported-sensor list tells you what works unmodified on the ESP32-S3 (OV2640, OV3660, HM0360...) and what does not (HM01B0) |
| [ArduCAM/RPI-Pico-Cam (GitHub)](https://github.com/ArduCAM/RPI-Pico-Cam) | code | 1 h | HM01B0 on an RP2040: the cheapest way to try the low-power mono path the research report recommends for learning |

**Check yourself.**

1. How long does a 19.2 KB QQVGA grayscale frame take over iOS BLE (~11 KB/s) compared with a 10 KB QVGA JPEG, and why does that favour on-sensor JPEG even when the MCU is idle?
2. Compute the energy of a 300 ms OVM7692 capture at 120 mW from a 2.8 V rail, and compare it with the 154 µAh per shot in `hardware/power-budget.txt`.
3. Which of the three sensors can an nRF52840 read with four GPIOs, and what resolution and format would you get?
4. Why is the OVM6948 "a trap", in one sentence?

<details><summary>Answers</summary>

1. 19,200 / 11,000 ≈ 1.75 s versus 0.9 s. Transfer time is radio-on time, i.e. energy: compression on the sensor saves battery as well as seconds.
2. 120 mW / 2.8 V = 43 mA; × 0.3 s = 12.9 mA·s = 3.6 µAh, about 2% of the stage-1 shot, which is why the stage-2 budget is about the radio and the MCU, not the camera.
3. The HM01B0 in 1-bit serial mode: D0, PCLK, HSYNC, VSYNC plus I²C. Raw 8-bit monochrome, 320 × 320 or binned 160 × 120 (19.2 KB), no JPEG.
4. Its output is an analog proprietary signal that needs OmniVision's 6 × 6 mm OV426 bridge chip to become DVP, so the "0.65 mm camera" is really a 6 mm camera that costs $115–$550.

</details>
