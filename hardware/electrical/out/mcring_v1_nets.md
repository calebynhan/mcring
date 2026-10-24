# mcring v1 (stage 1) — net listing

75 parts (74 populated), 265 pins, 53 nets, 251 nodes, 8 power nets.

## Nets

| Net | Power | Nodes | Connections |
|---|---|---|---|
| `3V3` | yes | 24 | U1.3 (3V3), C4.1 (1), C5.1 (1), R1.1 (1), R2.1 (1), R3.1 (1), R4.1 (1), TP6.1 (1), R19.1 (1), L1.2 (2), U8.8 (VOS), C2.1 (1), C3.1 (1), U2.A1 (VIN), C9.1 (1), U5.6 (VDD), C15.1 (1), U6.9 (VDD), U6.10 (VDD_IO), U6.2 (CS), C17.1 (1), C18.1 (1), MK1.1 (VDD), C19.1 (1) |
| `CAM_1V2` | yes | 3 | U4.2 (VOUT), C12.1 (1), FPC1.10 (DVDD) |
| `CAM_2V8` | yes | 4 | U3.2 (VOUT), C11.1 (1), C13.1 (1), FPC1.4 (AVDD) |
| `CAM_3V3` | yes | 9 | U2.A2 (VOUT), C10.1 (1), C24.1 (1), U3.3 (VIN), U4.3 (VIN), FPC1.11 (DOVDD), R5.1 (1), R6.1 (1), R16.1 (1) |
| `CHG_IN` | yes | 4 | PAD1.1 (PAD), D2.1 (K), U7.A1 (IN), C7.1 (1) |
| `GND` | yes | 85 | U1.1 (GND), U1.2 (GND), U1.43 (GND), U1.44 (GND), U1.46 (GND), U1.47 (GND), U1.48 (GND), U1.49 (GND), U1.50 (GND), U1.51 (GND), U1.52 (GND), U1.53 (GND), U1.54 (GND), U1.55 (GND), U1.56 (GND), U1.57 (GND), U1.58 (GND), U1.59 (GND), U1.60 (GND), U1.61 (GND), U1.62 (GND), U1.63 (GND), U1.64 (GND), U1.65 (GND), C4.2 (2), C5.2 (2), C6.2 (2), TP5.1 (1), R17.2 (2), R18.2 (2), SW2.2 (2), J1.2 (BAT-), PAD2.1 (PAD), D2.2 (A), U7.C2 (VSS), C7.2 (2), C8.2 (2), R10.2 (2), R11.2 (2), U8.2 (GND), U8.5 (STOP), U8.6 (MODE), C1.2 (2), C2.2 (2), C3.2 (2), R12.2 (2), R9.2 (2), C23.2 (2), U2.B2 (GND), C9.2 (2), C10.2 (2), C24.2 (2), C11.2 (2), C13.2 (2), C12.2 (2), C14.2 (2), U3.1 (VSS), U4.1 (VSS), FPC1.2 (AGND), FPC1.15 (DGND), FPC1.8 (PWDN), U5.7 (GND), U5.4 (IN/TRIG), C15.2 (2), C16.2 (2), U6.5 (RES), U6.6 (GND), U6.7 (GND), U6.8 (GND), U6.3 (SA0/SDO), C17.2 (2), C18.2 (2), MK1.2 (GND), MK1.6 (GND), MK1.5 (SELECT), C19.2 (2), SW1.2 (2), C22.2 (2), U9.B2 (GND), C21.2 (2), C20.2 (2), D1.3 (GND), BZ1.2 (2), Q1.2 (S), R14.2 (2) |
| `VBAT` | yes | 10 | J1.1 (BAT+), U7.A2 (OUT), C8.1 (1), U8.3 (VIN), U8.4 (EN), C1.1 (1), TP8.1 (1), R8.1 (1), U9.A1 (VIN), J2.1 (VBAT) |
| `VLED` | yes | 4 | U9.A2 (VOUT), C21.1 (1), C20.1 (1), D1.1 (VDD) |
| `AUX_DRAIN` |  | 2 | Q1.3 (D), J2.2 (DRAIN) |
| `AUX_EN` |  | 3 | U1.13 (IO9), Q1.1 (G), R14.1 (1) |
| `BAT_SENSE` |  | 4 | R8.2 (2), R9.1 (1), C23.1 (1), U1.5 (IO1) |
| `BUTTON` |  | 3 | SW1.1 (1), C22.1 (1), U1.6 (IO2) |
| `BUZZER` |  | 2 | U1.8 (IO4), R15.1 (1) |
| `BUZZ_DRV` |  | 2 | R15.2 (2), BZ1.1 (1) |
| `CAM_HREF` |  | 2 | FPC1.9 (HREF), U1.41 (IO47) |
| `CAM_PCLK` |  | 2 | FPC1.17 (PCLK), U1.17 (IO13) |
| `CAM_PWR_EN` |  | 3 | U1.25 (IO21), R17.1 (1), U2.B1 (ON) |
| `CAM_RESET` |  | 3 | FPC1.6 (RESET), R16.2 (2), C14.1 (1) |
| `CAM_SIOC` |  | 3 | FPC1.5 (SIOC), R6.2 (2), U1.33 (IO39) |
| `CAM_SIOD` |  | 3 | FPC1.3 (SIOD), R5.2 (2), U1.34 (IO40) |
| `CAM_VSYNC` |  | 2 | FPC1.7 (VSYNC), U1.32 (IO38) |
| `CAM_XCLK` |  | 2 | FPC1.13 (XCLK), U1.14 (IO10) |
| `CAM_Y2` |  | 2 | FPC1.19 (Y2), U1.19 (IO15) |
| `CAM_Y3` |  | 2 | FPC1.21 (Y3), U1.21 (IO17) |
| `CAM_Y4` |  | 2 | FPC1.22 (Y4), U1.22 (IO18) |
| `CAM_Y5` |  | 2 | FPC1.20 (Y5), U1.20 (IO16) |
| `CAM_Y6` |  | 2 | FPC1.18 (Y6), U1.18 (IO14) |
| `CAM_Y7` |  | 2 | FPC1.16 (Y7), U1.16 (IO12) |
| `CAM_Y8` |  | 2 | FPC1.14 (Y8), U1.15 (IO11) |
| `CAM_Y9` |  | 2 | FPC1.12 (Y9), U1.42 (IO48) |
| `DRV_REG` |  | 2 | U5.1 (REG), C16.1 (1) |
| `HAPTIC_EN` |  | 2 | U5.5 (EN), U1.7 (IO3) |
| `IMU_INT1` |  | 2 | U6.12 (INT1), U1.11 (IO7) |
| `IO0` |  | 4 | U1.4 (IO0), R2.2 (2), TP1.1 (1), SW2.1 (1) |
| `ISET` |  | 2 | U7.C1 (ISET), R10.1 (1) |
| `LED_PWR_EN` |  | 3 | U1.38 (RXD0/IO44), R18.1 (1), U9.B1 (ON) |
| `LRA_N` |  | 2 | U5.8 (OUT-), M1.2 (-) |
| `LRA_P` |  | 2 | U5.9 (OUT+), M1.1 (+) |
| `MCU_EN` |  | 4 | U1.45 (EN), R1.2 (2), C6.1 (1), TP2.1 (1) |
| `PDM_CLK` |  | 2 | MK1.3 (CLK), U1.36 (IO42) |
| `PDM_DATA` |  | 2 | MK1.4 (DATA), U1.35 (IO41) |
| `PRETERM` |  | 2 | U7.B2 (PRE_TERM), R11.1 (1) |
| `RGB_DATA` |  | 2 | U1.37 (TXD0/IO43), R7.1 (1) |
| `RGB_DIN` |  | 2 | R7.2 (2), D1.4 (DIN) |
| `SCL` |  | 4 | U1.10 (IO6), R4.2 (2), U5.2 (SCL), U6.1 (SCL/SPC) |
| `SDA` |  | 4 | U1.9 (IO5), R3.2 (2), U5.3 (SDA), U6.4 (SDA/SDI/SDO) |
| `SW_NODE` |  | 2 | U8.1 (SW), L1.1 (1) |
| `TOUCH` |  | 2 | R13.1 (1), U1.12 (IO8) |
| `TOUCH_PAD` |  | 2 | R13.2 (2), TPAD1.1 (PAD) |
| `USB_DM` |  | 2 | U1.23 (IO19), TP3.1 (1) |
| `USB_DP` |  | 2 | U1.24 (IO20), TP4.1 (1) |
| `VSET` |  | 2 | U8.7 (VSET), R12.1 (1) |
| `nCHG` |  | 3 | U7.B1 (nCHG), R19.2 (2), TP7.1 (1) |

## Parts

| Ref | Value | MPN | Footprint | Pins | Sheet |
|---|---|---|---|---|---|
| BZ1 | PKMCS0909E4000-R1 | PKMCS0909E4000-R1 | `mcring:Murata_PKMCS0909_9x9mm` | 2 | Outputs |
| C1 | 10u | GRM188R60J106ME47 | `Capacitor_SMD:C_0603_1608Metric` | 2 | Power |
| C2 | 10u | GRM188R60J106ME47 | `Capacitor_SMD:C_0603_1608Metric` | 2 | Power |
| C3 | 100u | GRM31CR60J107ME39 | `Capacitor_SMD:C_1206_3216Metric` | 2 | Power |
| C4 | 10u | GRM188R60J106ME47 | `Capacitor_SMD:C_0603_1608Metric` | 2 | MCU |
| C5 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | MCU |
| C6 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | MCU |
| C7 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Power |
| C8 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Power |
| C9 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| C10 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| C11 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| C12 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| C13 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| C14 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| C15 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Sensors |
| C16 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Sensors |
| C17 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Sensors |
| C18 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Sensors |
| C19 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Sensors |
| C20 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Outputs |
| C21 | 1u | GRM155R61A105KE15 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Outputs |
| C22 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Sensors |
| C23 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Power |
| C24 | 100n | GRM155R71C104KA88 | `Capacitor_SMD:C_0402_1005Metric` | 2 | Camera |
| D1 | WS2812B-2020 | WS2812B-2020 | `LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm` | 4 | Outputs |
| D2 | PESD5V0S1UB | PESD5V0S1UB,115 | `Diode_SMD:D_SOD-523` | 2 | Power |
| FPC1 | FPC-24-0.5mm | FH12-24S-0.5SH(55) / F32R-1A7H1-11024 | `Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal` | 24 | Camera |
| J1 | BM02B-SRSS-TB | BM02B-SRSS-TB(LF)(SN) | `Connector_JST:JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical` | 2 | Power |
| J2 | AUX |  | `mcring:PAD_Aux_1x2` | 2 | Outputs |
| L1 | 2.2uH | DFE201610E-2R2M=P2 | `Inductor_SMD:L_0806_2016Metric` | 2 | Power |
| M1 | LRA0825BC-0167F | LRA0825BC-0167F | `mcring:LRA_8mm_2pad` | 2 | Sensors |
| MK1 | T3902 | T3902 | `mcring:MIC_TDK_T3902_3.5x2.65mm` | 6 | Sensors |
| PAD1 | CHG+ |  | `mcring:PAD_Charge_3.0x2.0mm` | 1 | Power |
| PAD2 | CHG- |  | `mcring:PAD_Charge_3.0x2.0mm` | 1 | Power |
| Q1 | AO3400A | AO3400A | `Package_TO_SOT_SMD:SOT-23` | 3 | Outputs |
| R1 | 10k | RC0402FR-0710KL | `Resistor_SMD:R_0402_1005Metric` | 2 | MCU |
| R2 | 10k | RC0402FR-0710KL | `Resistor_SMD:R_0402_1005Metric` | 2 | MCU |
| R3 | 4.7k | RC0402FR-074K7L | `Resistor_SMD:R_0402_1005Metric` | 2 | MCU |
| R4 | 4.7k | RC0402FR-074K7L | `Resistor_SMD:R_0402_1005Metric` | 2 | MCU |
| R5 | 4.7k | RC0402FR-074K7L | `Resistor_SMD:R_0402_1005Metric` | 2 | Camera |
| R6 | 4.7k | RC0402FR-074K7L | `Resistor_SMD:R_0402_1005Metric` | 2 | Camera |
| R7 | 100 | RC0402FR-07100RL | `Resistor_SMD:R_0402_1005Metric` | 2 | Outputs |
| R8 | 100k | RC0402FR-07100KL | `Resistor_SMD:R_0402_1005Metric` | 2 | Power |
| R9 | 100k | RC0402FR-07100KL | `Resistor_SMD:R_0402_1005Metric` | 2 | Power |
| R10 | 9.1k | RC0402FR-079K1L | `Resistor_SMD:R_0402_1005Metric` | 2 | Power |
| R11 | 11.5k | RC0402FR-0711K5L | `Resistor_SMD:R_0402_1005Metric` | 2 | Power |
| R12 | VSET-3V3 | RC0402FR-07xxxL | `Resistor_SMD:R_0402_1005Metric` | 2 | Power |
| R13 | 1k | RC0402FR-071KL | `Resistor_SMD:R_0402_1005Metric` | 2 | Sensors |
| R14 | 100k | RC0402FR-07100KL | `Resistor_SMD:R_0402_1005Metric` | 2 | Outputs |
| R15 | 100 | RC0402FR-07100RL | `Resistor_SMD:R_0402_1005Metric` | 2 | Outputs |
| R16 | 10k | RC0402FR-0710KL | `Resistor_SMD:R_0402_1005Metric` | 2 | Camera |
| R17 | 100k | RC0402FR-07100KL | `Resistor_SMD:R_0402_1005Metric` | 2 | MCU |
| R18 | 4.7k | RC0402FR-074K7L | `Resistor_SMD:R_0402_1005Metric` | 2 | MCU |
| R19 | 100k | RC0402FR-07100KL | `Resistor_SMD:R_0402_1005Metric` | 2 | Power |
| SW1 | B3U-3000P | B3U-3000P | `mcring:SW_Omron_B3U-3000P` | 2 | Sensors |
| SW2 (DNP) | B3U-1000P | B3U-1000P | `mcring:SW_Omron_B3U-1000P` | 2 | MCU |
| TP1 | TP_IO0 |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | MCU |
| TP2 | TP_EN |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | MCU |
| TP3 | TP_USB_DM |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | MCU |
| TP4 | TP_USB_DP |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | MCU |
| TP5 | TP_GND |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | MCU |
| TP6 | TP_3V3 |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | MCU |
| TP7 | TP_nCHG |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | Power |
| TP8 | TP_VBAT |  | `TestPoint:TestPoint_Pad_D1.0mm` | 1 | Power |
| TPAD1 | TOUCH |  | `mcring:PAD_Touch_3x4mm` | 1 | Sensors |
| U1 | ESP32-S3-MINI-1U-N4R2 | ESP32-S3-MINI-1U-N4R2 | `RF_Module:ESP32-S3-MINI-1U` | 65 | MCU |
| U2 | TPS22916CYFPR | TPS22916CYFPR | `mcring:TPS22916_DSBGA-4_YFP` | 4 | Camera |
| U3 | XC6206P282MR | XC6206P282MR | `Package_TO_SOT_SMD:SOT-23` | 3 | Camera |
| U4 | XC6206P122MR | XC6206P122MR | `Package_TO_SOT_SMD:SOT-23` | 3 | Camera |
| U5 | DRV2605LDGS | DRV2605LDGSR | `Package_SO:VSSOP-10_3x3mm_P0.5mm` | 10 | Sensors |
| U6 | LIS2DW12TR | LIS2DW12TR | `Package_LGA:LGA-12_2x2mm_P0.5mm` | 12 | Sensors |
| U7 | BQ25100AYFPR | BQ25100AYFPR | `mcring:BQ25100_DSBGA-6_YFP` | 6 | Power |
| U8 | TPS62840DLCR | TPS62840DLCR | `Package_TO_SOT_SMD:SOT-583-8` | 8 | Power |
| U9 | TPS22916CYFPR | TPS22916CYFPR | `mcring:TPS22916_DSBGA-4_YFP` | 4 | Outputs |

## Pin-by-pin

### D1 — WS2812B-2020

| Pin | Name | Net |
|---|---|---|
| 1 | VDD | VLED |
| 2 | DOUT | NC |
| 3 | GND | GND |
| 4 | DIN | RGB_DIN |

### FPC1 — FPC-24-0.5mm

| Pin | Name | Net |
|---|---|---|
| 1 | NC | NC |
| 2 | AGND | GND |
| 3 | SIOD | CAM_SIOD |
| 4 | AVDD | CAM_2V8 |
| 5 | SIOC | CAM_SIOC |
| 6 | RESET | CAM_RESET |
| 7 | VSYNC | CAM_VSYNC |
| 8 | PWDN | GND |
| 9 | HREF | CAM_HREF |
| 10 | DVDD | CAM_1V2 |
| 11 | DOVDD | CAM_3V3 |
| 12 | Y9 | CAM_Y9 |
| 13 | XCLK | CAM_XCLK |
| 14 | Y8 | CAM_Y8 |
| 15 | DGND | GND |
| 16 | Y7 | CAM_Y7 |
| 17 | PCLK | CAM_PCLK |
| 18 | Y6 | CAM_Y6 |
| 19 | Y2 | CAM_Y2 |
| 20 | Y5 | CAM_Y5 |
| 21 | Y3 | CAM_Y3 |
| 22 | Y4 | CAM_Y4 |
| 23 | Y1 | NC |
| 24 | Y0 | NC |

### MK1 — T3902

| Pin | Name | Net |
|---|---|---|
| 1 | VDD | 3V3 |
| 2 | GND | GND |
| 3 | CLK | PDM_CLK |
| 4 | DATA | PDM_DATA |
| 5 | SELECT | GND |
| 6 | GND | GND |

### Q1 — AO3400A

| Pin | Name | Net |
|---|---|---|
| 1 | G | AUX_EN |
| 2 | S | GND |
| 3 | D | AUX_DRAIN |

### U1 — ESP32-S3-MINI-1U-N4R2

| Pin | Name | Net |
|---|---|---|
| 1 | GND | GND |
| 2 | GND | GND |
| 3 | 3V3 | 3V3 |
| 4 | IO0 | IO0 |
| 5 | IO1 | BAT_SENSE |
| 6 | IO2 | BUTTON |
| 7 | IO3 | HAPTIC_EN |
| 8 | IO4 | BUZZER |
| 9 | IO5 | SDA |
| 10 | IO6 | SCL |
| 11 | IO7 | IMU_INT1 |
| 12 | IO8 | TOUCH |
| 13 | IO9 | AUX_EN |
| 14 | IO10 | CAM_XCLK |
| 15 | IO11 | CAM_Y8 |
| 16 | IO12 | CAM_Y7 |
| 17 | IO13 | CAM_PCLK |
| 18 | IO14 | CAM_Y6 |
| 19 | IO15 | CAM_Y2 |
| 20 | IO16 | CAM_Y5 |
| 21 | IO17 | CAM_Y3 |
| 22 | IO18 | CAM_Y4 |
| 23 | IO19 | USB_DM |
| 24 | IO20 | USB_DP |
| 25 | IO21 | CAM_PWR_EN |
| 26 | IO26 | NC |
| 27 | IO33 | NC |
| 28 | IO34 | NC |
| 29 | IO35 | NC |
| 30 | IO36 | NC |
| 31 | IO37 | NC |
| 32 | IO38 | CAM_VSYNC |
| 33 | IO39 | CAM_SIOC |
| 34 | IO40 | CAM_SIOD |
| 35 | IO41 | PDM_DATA |
| 36 | IO42 | PDM_CLK |
| 37 | TXD0/IO43 | RGB_DATA |
| 38 | RXD0/IO44 | LED_PWR_EN |
| 39 | IO45 | NC |
| 40 | IO46 | NC |
| 41 | IO47 | CAM_HREF |
| 42 | IO48 | CAM_Y9 |
| 43 | GND | GND |
| 44 | GND | GND |
| 45 | EN | MCU_EN |
| 46 | GND | GND |
| 47 | GND | GND |
| 48 | GND | GND |
| 49 | GND | GND |
| 50 | GND | GND |
| 51 | GND | GND |
| 52 | GND | GND |
| 53 | GND | GND |
| 54 | GND | GND |
| 55 | GND | GND |
| 56 | GND | GND |
| 57 | GND | GND |
| 58 | GND | GND |
| 59 | GND | GND |
| 60 | GND | GND |
| 61 | GND | GND |
| 62 | GND | GND |
| 63 | GND | GND |
| 64 | GND | GND |
| 65 | GND | GND |

### U2 — TPS22916CYFPR

| Pin | Name | Net |
|---|---|---|
| A1 | VIN | 3V3 |
| A2 | VOUT | CAM_3V3 |
| B1 | ON | CAM_PWR_EN |
| B2 | GND | GND |

### U3 — XC6206P282MR

| Pin | Name | Net |
|---|---|---|
| 1 | VSS | GND |
| 2 | VOUT | CAM_2V8 |
| 3 | VIN | CAM_3V3 |

### U4 — XC6206P122MR

| Pin | Name | Net |
|---|---|---|
| 1 | VSS | GND |
| 2 | VOUT | CAM_1V2 |
| 3 | VIN | CAM_3V3 |

### U5 — DRV2605LDGS

| Pin | Name | Net |
|---|---|---|
| 1 | REG | DRV_REG |
| 2 | SCL | SCL |
| 3 | SDA | SDA |
| 4 | IN/TRIG | GND |
| 5 | EN | HAPTIC_EN |
| 6 | VDD | 3V3 |
| 7 | GND | GND |
| 8 | OUT- | LRA_N |
| 9 | OUT+ | LRA_P |
| 10 | NC | NC |

### U6 — LIS2DW12TR

| Pin | Name | Net |
|---|---|---|
| 1 | SCL/SPC | SCL |
| 2 | CS | 3V3 |
| 3 | SA0/SDO | GND |
| 4 | SDA/SDI/SDO | SDA |
| 5 | RES | GND |
| 6 | GND | GND |
| 7 | GND | GND |
| 8 | GND | GND |
| 9 | VDD | 3V3 |
| 10 | VDD_IO | 3V3 |
| 11 | INT2 | NC |
| 12 | INT1 | IMU_INT1 |

### U7 — BQ25100AYFPR

| Pin | Name | Net |
|---|---|---|
| A1 | IN | CHG_IN |
| A2 | OUT | VBAT |
| B1 | nCHG | nCHG |
| B2 | PRE_TERM | PRETERM |
| C1 | ISET | ISET |
| C2 | VSS | GND |

### U8 — TPS62840DLCR

| Pin | Name | Net |
|---|---|---|
| 1 | SW | SW_NODE |
| 2 | GND | GND |
| 3 | VIN | VBAT |
| 4 | EN | VBAT |
| 5 | STOP | GND |
| 6 | MODE | GND |
| 7 | VSET | VSET |
| 8 | VOS | 3V3 |

### U9 — TPS22916CYFPR

| Pin | Name | Net |
|---|---|---|
| A1 | VIN | VBAT |
| A2 | VOUT | VLED |
| B1 | ON | LED_PWR_EN |
| B2 | GND | GND |

