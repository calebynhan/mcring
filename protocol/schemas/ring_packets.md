# Ring packet quick reference (binary, little-endian)

See `../ble-gatt.md` for semantics. Byte layouts, for implementers:

```
CAPTURE        01 qq ff                      qq=quality(1..63|0) ff=frame_size(0..5)
ACK_TRANSFER   02 ii ii ss nn nn [mm mm]*    ii=xfer_id ss=status nn=n_missing mm=idx
SET_CONFIG     03 kk vv vv vv vv             kk=key vv=int32
PING           04
ABORT          05
RECORD_AUDIO   06 ss                         ss=seconds (1..8)
SLEEP          07
GET_STATUS     08

STATUS         01 st bb bb pp fl uu uu uu uu ee qq
               st=state bb=batt_mv pp=batt_pct fl=flags uu=uptime_s ee=last_err qq=queued

XFER_START     tt ii ii ll ll ll ll cc cc nn nn rr rr rr rr ww ww hh hh sf
               tt=type(1 jpeg,2 adpcm) ii=xfer_id ll=total_len cc=chunk_len nn=n_chunks
               rr=crc32 ww=width hh=height sf=seq_flags
XFER_DATA      ii ii dd dd <payload>         dd=idx
XFER_END       FF ii ii

MORSE_TEXT     10 ww cc ll <text>            ww=wpm cc=channels ll=len
PATTERN        11 uu cc nn <units u8[nn]>    uu=unit_ms cc=channels
STOP           12
RGB            13 rr gg bb mm mm             mm=ms
MORSE_UNITS    14 uu cc nn nn <units...>     nn=u16 count; may be continued with
MORSE_UNITS_CONT 15 oo oo <units...>         oo=u16 offset into the units array
```
