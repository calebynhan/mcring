"""Rebuild docs/ring-anatomy.html (the interactive 3D ring viewer) from the CadQuery model.

    python3 tools/ring-viz/export_mesh.py

Tessellates the shell, lid, key and every fit-check placeholder from hardware/cad/mcring_stage1.py
and embeds the meshes in page_template.html.
"""
import sys, json, base64, struct, time, math
import os
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'hardware', 'cad'))
import mcring_stage1 as M
t0 = time.time()
p = M.default_params(); bp = M.load_board_params(M.PARAMS_JSON)
m = M.Model(p, bp); m.build_shell(); m.build_lid(); m.build_key(); m.build_placeholders()
parts = {"shell": m.shell, "lid": m.lid}
parts.update({k: v for k, v in m.placeholders.items()})
out = {"units": "mm", "parts": {}}
total = 0
for name, shp in parts.items():
    s = shp if hasattr(shp, "tessellate") else shp.val()
    tol = 0.04 if name in ("shell", "lid") else 0.03
    verts, tris = s.tessellate(tol, 0.25)
    va = [c for v in verts for c in (v.x, v.y, v.z)]
    ia = [i for t in tris for i in t]
    bb = s.BoundingBox()
    vb = struct.pack(f"<{len(va)}f", *va); ib = struct.pack(f"<{len(ia)}I", *ia)
    out["parts"][name] = {"v": base64.b64encode(vb).decode(), "i": base64.b64encode(ib).decode(),
                          "nv": len(verts), "nt": len(tris),
                          "bb": [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
                          "vol": round(s.Volume(), 2)}
    total += len(vb) + len(ib)
    print(f"{name:14} {len(verts):6} v {len(tris):6} t  bb x[{bb.xmin:.1f},{bb.xmax:.1f}] y[{bb.ymin:.1f},{bb.ymax:.1f}] z[{bb.zmin:.1f},{bb.zmax:.1f}] vol {s.Volume():.1f}")
mesh = json.dumps(out)
tpl = open(os.path.join(HERE, "page_template.html")).read()
page = tpl.replace("__MESH__", mesh.replace("</", "<\\/"))
dst = os.path.join(REPO, "docs", "ring-anatomy.html")
open(dst, "w").write(page)
print(f"raw {total/1e6:.2f} MB, page {len(page)/1e6:.2f} MB -> {dst}, {time.time()-t0:.1f}s")
print("inner_d", p["inner_d"], "board", bp["board_length_mm"], bp["board_width_mm"])
