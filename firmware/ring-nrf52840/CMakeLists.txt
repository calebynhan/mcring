# mcring stage-2 firmware skeleton — nRF52840 / Zephyr (nRF Connect SDK)
#   west build -b xiao_ble -p auto firmware/ring-nrf52840      (Seeed XIAO nRF52840 Sense)
#   west build -b nrf52840dk/nrf52840 firmware/ring-nrf52840
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(mcring_ring_nrf52840)

set(MCRING_LIB ${CMAKE_CURRENT_SOURCE_DIR}/../ring-esp32s3/lib)

target_sources(app PRIVATE
  src/main.c
  src/ble_svc.c
  src/transfer.c
  src/feedback.c
  src/camera_hal.c
  src/trigger.c
  ${MCRING_LIB}/mcring_proto/mcring_proto.c
  ${MCRING_LIB}/mcring_morse/mcring_morse.c
  ${MCRING_LIB}/mcring_adpcm/mcring_adpcm.c
)
target_include_directories(app PRIVATE
  src
  ${MCRING_LIB}/mcring_proto
  ${MCRING_LIB}/mcring_morse
  ${MCRING_LIB}/mcring_adpcm
)
