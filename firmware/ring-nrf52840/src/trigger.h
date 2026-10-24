#pragma once
#include <stdbool.h>
int  trigger_init(void);
bool trigger_poll_capture(void);   /* true once per button press / double-tap */
