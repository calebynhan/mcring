// Host unit tests for the shared C libraries: `pio test -e native`
#include <unity.h>
#include <string.h>
#include "mcring_morse.h"
#include "mcring_proto.h"
#include "mcring_adpcm.h"

void test_morse_sos(void) {
  uint8_t out[64]; int tr = 0;
  size_t n = mc_morse_encode("SOS", NULL, out, sizeof out, &tr);
  const uint8_t exp[] = {1,1,1,1,1,3,3,1,3,1,3,3,1,1,1,1,1};
  TEST_ASSERT_EQUAL_UINT32(sizeof exp, n);
  TEST_ASSERT_EQUAL_UINT8_ARRAY(exp, out, n);
  TEST_ASSERT_EQUAL_INT(0, tr);
}

void test_morse_word_gap_and_unknown(void) {
  uint8_t out[64]; int tr = 0;
  size_t n = mc_morse_encode("  e #  e ", NULL, out, sizeof out, &tr);
  const uint8_t exp[] = {1, 7, 1};
  TEST_ASSERT_EQUAL_UINT32(3, n);
  TEST_ASSERT_EQUAL_UINT8_ARRAY(exp, out, n);
}

void test_morse_truncate_whole_char(void) {
  uint8_t out[8]; int tr = 0;
  size_t n = mc_morse_encode("SOS", NULL, out, 8, &tr);
  TEST_ASSERT_EQUAL_UINT32(5, n);
  TEST_ASSERT_EQUAL_INT(1, tr);
}

void test_farnsworth(void) {
  mc_morse_spacing_t sp; mc_morse_spacing_farnsworth(&sp, 15, 8);
  TEST_ASSERT_EQUAL_UINT8(1, sp.dot);
  TEST_ASSERT_EQUAL_UINT8(3, sp.dash);
  TEST_ASSERT_TRUE(sp.char_gap > 3);
  TEST_ASSERT_TRUE(sp.word_gap > 7);
  mc_morse_spacing_farnsworth(&sp, 10, 15);   // overall >= char → standard
  TEST_ASSERT_EQUAL_UINT8(3, sp.char_gap);
  TEST_ASSERT_EQUAL_UINT16(80, mc_morse_unit_ms(15));
}

void test_crc32(void) {
  TEST_ASSERT_EQUAL_HEX32(0xCBF43926, mc_crc32((const uint8_t *)"123456789", 9));
  TEST_ASSERT_EQUAL_HEX32(0x00000000, mc_crc32((const uint8_t *)"", 0));
}

void test_status_encoding(void) {
  mc_status_t s = {1, MC_STATE_TRANSFERRING, 3812, 77, 0x22, 1234, 0, 1};
  uint8_t b[12];
  TEST_ASSERT_EQUAL_UINT32(12, mc_encode_status(&s, b));
  const uint8_t exp[] = {1, 2, 0xE4, 0x0E, 77, 0x22, 0xD2, 0x04, 0, 0, 0, 1};
  TEST_ASSERT_EQUAL_UINT8_ARRAY(exp, b, 12);
}

void test_xfer_start_encoding(void) {
  mc_xfer_start_t x = {MC_XFER_JPEG, 5, 10240, 178, 58, 0xDEADBEEF, 320, 240, 1};
  uint8_t b[20];
  TEST_ASSERT_EQUAL_UINT32(20, mc_encode_xfer_start(&x, b));
  TEST_ASSERT_EQUAL_UINT8(1, b[0]);
  TEST_ASSERT_EQUAL_UINT16(5, mc_get_u16(b + 1));
  TEST_ASSERT_EQUAL_UINT32(10240, mc_get_u32(b + 3));
  TEST_ASSERT_EQUAL_UINT16(178, mc_get_u16(b + 7));
  TEST_ASSERT_EQUAL_UINT16(58, mc_get_u16(b + 9));
  TEST_ASSERT_EQUAL_HEX32(0xDEADBEEF, mc_get_u32(b + 11));
  TEST_ASSERT_EQUAL_UINT16(320, mc_get_u16(b + 15));
  TEST_ASSERT_EQUAL_UINT16(240, mc_get_u16(b + 17));
  TEST_ASSERT_EQUAL_UINT8(1, b[19]);
}

void test_chunk_len(void) {
  TEST_ASSERT_EQUAL_UINT16(178, mc_chunk_len_for_mtu(185));
  TEST_ASSERT_EQUAL_UINT16(510, mc_chunk_len_for_mtu(517));
  TEST_ASSERT_EQUAL_UINT16(16, mc_chunk_len_for_mtu(23));
}

void test_adpcm_roundtrip(void) {
  int16_t pcm[MC_ADPCM_BLOCK_SAMPLES * 2];
  for (int i = 0; i < MC_ADPCM_BLOCK_SAMPLES * 2; i++) pcm[i] = (int16_t)(8000 * ((i / 20) % 2 ? 1 : -1));
  uint8_t enc[MC_ADPCM_BLOCK_BYTES * 2];
  size_t w = mc_adpcm_encode(pcm, MC_ADPCM_BLOCK_SAMPLES * 2, enc);
  TEST_ASSERT_EQUAL_UINT32(2 * MC_ADPCM_BLOCK_BYTES, w);
  int16_t dec[MC_ADPCM_BLOCK_SAMPLES];
  mc_adpcm_decode_block(enc + MC_ADPCM_BLOCK_BYTES, dec);
  // Second block's first sample is stored verbatim
  TEST_ASSERT_EQUAL_INT16(pcm[MC_ADPCM_BLOCK_SAMPLES], dec[0]);
}

// ---- voice-first additions ------------------------------------------------------------------

void test_event_encoding(void) {
  uint8_t b[MC_EVENT_LEN];
  TEST_ASSERT_EQUAL_UINT32(6, mc_encode_event(MC_EV_BUTTON_UP, 23, 0x01020304u, b));
  const uint8_t exp[] = {2, 23, 0x04, 0x03, 0x02, 0x01};   // matches python tests/test_proto.py
  TEST_ASSERT_EQUAL_UINT8_ARRAY(exp, b, 6);
  mc_event_t e;
  TEST_ASSERT_EQUAL_INT(0, mc_decode_event(b, 6, &e));
  TEST_ASSERT_EQUAL_UINT8(MC_EV_BUTTON_UP, e.event);
  TEST_ASSERT_EQUAL_UINT8(23, e.arg);
  TEST_ASSERT_EQUAL_HEX32(0x01020304u, e.t_ms);
  TEST_ASSERT_EQUAL_INT(-1, mc_decode_event(b, 5, &e));
  TEST_ASSERT_EQUAL_UINT8(11, MC_EV_AUDIO_DONE);
}

void test_audio_start_encoding(void) {
  uint8_t b[MC_AUDIO_START_LEN];
  TEST_ASSERT_EQUAL_UINT32(5, mc_encode_audio_start(16000, MC_AUDIO_CODEC_ADPCM, 200, b));
  const uint8_t exp[] = {0x20, 0xA0, 0x00, 0x02, 200};
  TEST_ASSERT_EQUAL_UINT8_ARRAY(exp, b, 5);
  mc_audio_start_t st;
  TEST_ASSERT_EQUAL_INT(0, mc_decode_audio_start(b, 5, &st));
  TEST_ASSERT_EQUAL_UINT16(160, st.sample_rate_div100);
  TEST_ASSERT_EQUAL_UINT8(2, st.codec);
  TEST_ASSERT_EQUAL_UINT8(200, st.volume);
  const uint8_t end[] = {MC_AO_END, 0, 0, 0, 0};
  TEST_ASSERT_EQUAL_INT(-1, mc_decode_audio_start(end, 5, &st));   // wrong opcode
  TEST_ASSERT_EQUAL_INT(-1, mc_decode_audio_start(b, 4, &st));     // too short
}

void test_audio_data_helpers(void) {
  uint8_t h[MC_AUDIO_DATA_HDR_LEN];
  TEST_ASSERT_EQUAL_UINT32(3, mc_encode_audio_data_hdr(0x1234, h));
  const uint8_t exp[] = {0x21, 0x34, 0x12};
  TEST_ASSERT_EQUAL_UINT8_ARRAY(exp, h, 3);
  TEST_ASSERT_EQUAL_UINT32(3, mc_audio_data_blocks(3 + 3 * MC_AUDIO_BLOCK_BYTES));
  TEST_ASSERT_EQUAL_UINT32(1, mc_audio_data_blocks(135));
  TEST_ASSERT_EQUAL_UINT32(0, mc_audio_data_blocks(3 + 100));     // partial block
  TEST_ASSERT_EQUAL_UINT32(0, mc_audio_data_blocks(2));           // too short
  TEST_ASSERT_EQUAL_UINT32(1, mc_audio_blocks_per_write(182));    // iOS: MTU 185
  TEST_ASSERT_EQUAL_UINT32(3, mc_audio_blocks_per_write(514));    // Android: MTU 517
  TEST_ASSERT_EQUAL_UINT32(1, mc_audio_blocks_per_write(20));     // never 0
  TEST_ASSERT_EQUAL_UINT32(MC_ADPCM_BLOCK_BYTES, MC_AUDIO_BLOCK_BYTES);
}

void test_new_constants(void) {
  TEST_ASSERT_EQUAL_HEX8(0x09, MC_OP_RECORD_START);
  TEST_ASSERT_EQUAL_HEX8(0x0A, MC_OP_RECORD_STOP);
  TEST_ASSERT_EQUAL_HEX8(0x16, MC_FB_CUE);
  TEST_ASSERT_EQUAL_HEX8(0x40, MC_FLAG_SPEAKER_OK);
  TEST_ASSERT_EQUAL_UINT8(9, MC_CFG_SPEAKER_VOLUME);
  TEST_ASSERT_EQUAL_UINT8(10, MC_CFG_CUES_MASK);
  TEST_ASSERT_EQUAL_UINT8(11, MC_CFG_MIC_SOURCE_HINT);
  TEST_ASSERT_EQUAL_STRING("7a3b0007-9c2e-4f3a-b1d4-6d6372696e67", MCRING_UUID_EVENTS);
  TEST_ASSERT_EQUAL_STRING("7a3b0008-9c2e-4f3a-b1d4-6d6372696e67", MCRING_UUID_AUDIO_OUT);
}

void test_adpcm_decode_block_roundtrip(void) {
  // The speaker path decodes blocks the phone encoded: encode → decode must stay close.
  int16_t pcm[MC_ADPCM_BLOCK_SAMPLES];
  for (int i = 0; i < MC_ADPCM_BLOCK_SAMPLES; i++) pcm[i] = (int16_t)(6000 * ((i / 16) % 2 ? 1 : -1));
  uint8_t enc[MC_ADPCM_BLOCK_BYTES];
  TEST_ASSERT_EQUAL_UINT32(MC_ADPCM_BLOCK_BYTES, mc_adpcm_encode_block(pcm, enc));
  int16_t dec[MC_ADPCM_BLOCK_SAMPLES];
  TEST_ASSERT_EQUAL_UINT32(MC_ADPCM_BLOCK_SAMPLES, mc_adpcm_decode_block(enc, dec));
  TEST_ASSERT_EQUAL_INT16(pcm[0], dec[0]);
  long err = 0;
  for (int i = 64; i < MC_ADPCM_BLOCK_SAMPLES; i++) { long d = (long)pcm[i] - dec[i]; err += d < 0 ? -d : d; }
  TEST_ASSERT_TRUE(err / (MC_ADPCM_BLOCK_SAMPLES - 64) < 1500);   // mean abs error after adaptation
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_event_encoding);
  RUN_TEST(test_audio_start_encoding);
  RUN_TEST(test_audio_data_helpers);
  RUN_TEST(test_new_constants);
  RUN_TEST(test_adpcm_decode_block_roundtrip);
  RUN_TEST(test_morse_sos);
  RUN_TEST(test_morse_word_gap_and_unknown);
  RUN_TEST(test_morse_truncate_whole_char);
  RUN_TEST(test_farnsworth);
  RUN_TEST(test_crc32);
  RUN_TEST(test_status_encoding);
  RUN_TEST(test_xfer_start_encoding);
  RUN_TEST(test_chunk_len);
  RUN_TEST(test_adpcm_roundtrip);
  return UNITY_END();
}
