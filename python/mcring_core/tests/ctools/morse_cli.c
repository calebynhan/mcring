/* Host test helper: prints C Morse encoding as comma-separated units.
 * usage: morse_cli <char_wpm> <overall_wpm> "<text>"  (overall 0 = standard spacing)
 *        morse_cli crc | adpcm (stdin)  |  event <ev> <arg> <t_ms>  |  mkstart <rate> <codec> <vol>  |  start <hex> */
#include <stdio.h>
#include <stdlib.h>
#include "mcring_morse.h"
#include "mcring_proto.h"
#include "mcring_adpcm.h"

int main(int argc, char **argv) {
  if (argc >= 2 && argv[1][0] == 'c') {           /* crc32 of stdin */
    unsigned char buf[1 << 16]; size_t n; uint32_t crc = 0;
    while ((n = fread(buf, 1, sizeof buf, stdin)) > 0) crc = mc_crc32_update(crc, buf, n);
    printf("%08x\n", crc); return 0;
  }
  if (argc >= 2 && argv[1][0] == 'a') {           /* adpcm encode raw s16le from stdin -> stdout */
    static int16_t pcm[1 << 18]; size_t n = fread(pcm, 2, sizeof(pcm) / 2, stdin);
    static uint8_t out[1 << 17]; size_t w = mc_adpcm_encode(pcm, n, out);
    fwrite(out, 1, w, stdout); return 0;
  }
  if (argc >= 5 && argv[1][0] == 'e') {           /* event <ev> <arg> <t_ms> -> hex */
    uint8_t b[MC_EVENT_LEN]; size_t n = mc_encode_event((uint8_t)atoi(argv[2]), (uint8_t)atoi(argv[3]), (uint32_t)strtoul(argv[4], NULL, 10), b);
    for (size_t i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n"); return 0;
  }
  if (argc >= 5 && argv[1][0] == 'm') {           /* mkstart <rate> <codec> <vol> -> hex */
    uint8_t b[MC_AUDIO_START_LEN]; size_t n = mc_encode_audio_start((uint16_t)atoi(argv[2]), (uint8_t)atoi(argv[3]), (uint8_t)atoi(argv[4]), b);
    for (size_t i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n"); return 0;
  }
  if (argc >= 3 && argv[1][0] == 's') {           /* start <hex> -> "rate codec vol" or "err" */
    uint8_t b[64]; size_t n = 0; const char *h = argv[2];
    while (h[0] && h[1] && n < sizeof b) { unsigned v; if (sscanf(h, "%2x", &v) != 1) break; b[n++] = (uint8_t)v; h += 2; }
    mc_audio_start_t st;
    if (mc_decode_audio_start(b, n, &st) != 0) { printf("err\n"); return 0; }
    printf("%u %u %u\n", (unsigned)st.sample_rate_div100 * 100u, st.codec, st.volume); return 0;
  }
  if (argc < 4) return 2;
  mc_morse_spacing_t sp; int cw = atoi(argv[1]), ow = atoi(argv[2]);
  if (ow > 0) mc_morse_spacing_farnsworth(&sp, (uint8_t)cw, (uint8_t)ow); else mc_morse_spacing_default(&sp);
  uint8_t out[4096]; int trunc = 0;
  size_t n = mc_morse_encode(argv[3], &sp, out, sizeof out, &trunc);
  for (size_t i = 0; i < n; i++) printf("%s%u", i ? "," : "", out[i]);
  printf("\n%d\n", trunc);
  return 0;
}
