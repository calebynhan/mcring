# mcring v1 (stage 1) — ERC

Checked 92 parts / 313 pins / 65 nets / 299 nodes.

* 1 warning(s) total, 0 unexplained, 1 explained.

**Result: CLEAN**

## Explained (intentional) warnings

| Warning | Why it is intentional |
|---|---|
| [single-node] net ANT_RF has 1 node(s): [('ANT1', '1')] | ANT1's RF lead mates with the u.FL receptacle on the ESP32-S3-MINI-1U module, which is not one of the module's 65 pads, so the net has no second node |

## Checks performed

1. every pin not marked NC or spare is on a net (off-board parts included);
2. no net has fewer than two nodes;
3. every pin declared as a power pin sits on a power-named net;
4. every IC supply pin (non-ground) has at least one populated capacitor on its net;
5. (while building) no pin is on two nets, every NC pin that is connected is reported.

