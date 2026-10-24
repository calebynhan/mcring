# mcring v1 (stage 1) — ERC

Checked 75 parts / 265 pins / 53 nets / 251 nodes.

* 0 warning(s) total, 0 unexplained, 0 explained.

**Result: CLEAN**

## Checks performed

1. every pin not marked NC is on a net;
2. no net has fewer than two nodes;
3. every pin declared as a power pin sits on a power-named net;
4. every IC supply pin (non-ground) has at least one populated capacitor on its net;
5. (while building) no pin is on two nets, every NC pin that is connected is reported.

