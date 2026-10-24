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

int main(int, char **) {
  UNITY_BEGIN();
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
