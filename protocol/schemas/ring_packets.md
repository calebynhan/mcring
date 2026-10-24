# Ring packet quick reference (binary, little-endian)

See `../ble-gatt.md` for semantics. Byte layouts, for implementers:

```
--- Control 0002 (phone -> ring) -------------------------------------------------------
CAPTURE        01 qq ff                      qq=quality(1..63|0) ff=frame_size(0..5)
ACK_TRANSFER   02 ii ii ss nn nn [mm mm]*    ii=xfer_id ss=status nn=n_missing mm=idx
SET_CONFIG     03 kk vv vv vv vv             kk=key(1..11) vv=int32
PING           04
ABORT          05
RECORD_AUDIO   06 ss                         ss=seconds (1..8)
SLEEP          07
GET_STATUS     08
RECORD_START   09                            ring-mic recording until RECORD_STOP / 8 s
RECORD_STOP    0A

--- Status 0003 (ring -> phone) --------------------------------------------------------
STATUS         01 st bb bb pp fl uu uu uu uu ee qq
               st=state bb=batt_mv pp=batt_pct fl=flags uu=uptime_s ee=last_err qq=queued
               fl: b0 charging b1 camera b2 imu b3 mic b4 haptic b5 queued b6 speaker

--- Transfer 0004 / 0005 (ring -> phone) -----------------------------------------------
XFER_START     tt ii ii ll ll ll ll cc cc nn nn rr rr rr rr ww ww hh hh sf
               tt=type(1 jpeg,2 adpcm) ii=xfer_id ll=total_len cc=chunk_len nn=n_chunks
               rr=crc32 ww=width hh=height sf=seq_flags
XFER_DATA      ii ii dd dd <payload>         dd=idx
XFER_END       FF ii ii

--- Feedback 0006 (phone -> ring) ------------------------------------------------------
MORSE_TEXT     10 ww cc ll <text>            ww=wpm cc=channels ll=len         (legacy)
PATTERN        11 uu cc nn <units u8[nn]>    uu=unit_ms cc=channels
STOP           12
RGB            13 rr gg bb mm mm             mm=ms
MORSE_UNITS    14 uu cc nn nn <units...>     nn=u16 count; may be continued with (legacy)
MORSE_UNITS_CONT 15 oo oo <units...>         oo=u16 offset into the units array
CUE            16 cc                         cc=1 listening, 2 answer_ready, 3 error, 4 ok

--- Events 0007 (ring -> phone), 6 bytes -----------------------------------------------
EVENT          ev aa tt tt tt tt             ev=event id aa=arg tt=u32 uptime ms
               ev: 1 BUTTON_DOWN 2 BUTTON_UP(aa=floor(held_ms/100); <=6 short, >=7 long) 3 DOUBLE_TAP 4 TOUCH
                   5 CAPTURE_STARTED 6 CAPTURE_DONE(aa=queued) 7 REC_STARTED(aa=max s)
                   8 REC_STOPPED(aa=tenths) 9 LOW_BATTERY(aa=pct) 10 AUDIO_UNDERRUN
                   11 AUDIO_DONE(aa=0 drained, 1 stopped)

--- Audio out 0008 (phone -> ring) -----------------------------------------------------
AUDIO_START    20 rr rr cc vv                rr=sample_rate/100 (160) cc=codec(2 adpcm) vv=volume
AUDIO_DATA     21 qq qq <132-byte blocks>*   qq=u16 seq; 1..N whole mcring-ADPCM blocks
AUDIO_END      22
AUDIO_STOP     23

mcring-ADPCM block (132 bytes = 256 samples @ 16 kHz = 16 ms):
               pp pp si 00 <128 bytes: 255 nibbles, low nibble first, padded>
               pp=int16 first sample  si=step index (0..88)
```
