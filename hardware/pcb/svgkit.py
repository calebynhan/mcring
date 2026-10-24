"""Tiny dependency-free SVG writer shared by floorplan.py and wiring_stage0.py.

Coordinates are SVG user units (px). Every drawing helper returns nothing and
appends to the internal list; `save()` writes the .svg and (via cairosvg) a .png.
"""
from __future__ import annotations

import html
import math
import os

FONT = "Helvetica, Arial, 'DejaVu Sans', sans-serif"
MONO = "Menlo, Consolas, 'DejaVu Sans Mono', monospace"


class SVG:
    def __init__(self, width: float, height: float, bg: str = "#ffffff"):
        self.w, self.h = width, height
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.bg = bg

    # -- primitives ---------------------------------------------------------
    def add(self, s: str) -> None:
        self.parts.append(s)

    def group(self, inner: list[str], **attrs) -> None:
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        self.parts.append(f"<g {a}>" + "".join(inner) + "</g>")

    def rect(self, x, y, w, h, fill="none", stroke="#000", sw=1.0, rx=0.0,
             dash=None, opacity=None, title=None, **extra) -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        e = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in extra.items())
        t = f"<title>{html.escape(title)}</title>" if title else ""
        if t:
            self.parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx:.2f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{o} {e}>{t}</rect>')
        else:
            self.parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx:.2f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{o} {e}/>')

    def circle(self, cx, cy, r, fill="none", stroke="#000", sw=1.0, dash=None, opacity=None) -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{d}{o}/>')

    def line(self, x1, y1, x2, y2, stroke="#000", sw=1.0, dash=None, marker=None, opacity=None) -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#{marker})"' if marker else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round"{d}{m}{o}/>')

    def polyline(self, pts, stroke="#000", sw=1.0, fill="none", dash=None, marker=None, opacity=None,
                 linejoin="round") -> None:
        p = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#{marker})"' if marker else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(
            f'<polyline points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="{linejoin}" stroke-linecap="round"{d}{m}{o}/>')

    def polygon(self, pts, fill="none", stroke="#000", sw=1.0, opacity=None) -> None:
        p = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{o}/>')

    def path(self, d, fill="none", stroke="#000", sw=1.0, dash=None, opacity=None) -> None:
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}{o}/>')

    def text(self, x, y, s, size=10, fill="#111", anchor="start", weight="normal", rotate=None,
             mono=False, italic=False, baseline="middle", opacity=None) -> None:
        tr = f' transform="rotate({rotate:.1f} {x:.2f} {y:.2f})"' if rotate else ""
        fam = MONO if mono else FONT
        st = " font-style='italic'" if italic else ""
        o = f' opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="{fam}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" dominant-baseline="{baseline}"{st}{tr}{o}>'
            f'{html.escape(s)}</text>')

    def multiline(self, x, y, lines, size=10, lh=None, **kw) -> float:
        lh = lh or size * 1.35
        for i, s in enumerate(lines):
            self.text(x, y + i * lh, s, size=size, **kw)
        return y + len(lines) * lh

    # -- compound helpers ---------------------------------------------------
    def arrow_marker(self, name="arrow", color="#333", size=6) -> None:
        self.defs.append(
            f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="{size}" '
            f'markerHeight="{size}" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>')

    def hatch(self, name="hatch", color="#2a7", spacing=5, sw=0.8, angle=45) -> None:
        self.defs.append(
            f'<pattern id="{name}" patternUnits="userSpaceOnUse" width="{spacing}" height="{spacing}" '
            f'patternTransform="rotate({angle})">'
            f'<line x1="0" y1="0" x2="0" y2="{spacing}" stroke="{color}" stroke-width="{sw}"/></pattern>')

    def dim_h(self, x1, x2, y, label, size=9, color="#333", offset=0, above=True) -> None:
        """Horizontal dimension line between x1..x2 at height y."""
        self.line(x1, y, x2, y, stroke=color, sw=0.8, marker="dim")
        self.line(x2, y, x1, y, stroke=color, sw=0.8, marker="dim")
        ty = y - 8 if above else y + size + 1
        self.text((x1 + x2) / 2, ty, label, size=size, fill=color, anchor="middle")

    def dim_v(self, y1, y2, x, label, size=9, color="#333", left=True) -> None:
        self.line(x, y1, x, y2, stroke=color, sw=0.8, marker="dim")
        self.line(x, y2, x, y1, stroke=color, sw=0.8, marker="dim")
        tx = x - 9 if left else x + 9
        self.text(tx, (y1 + y2) / 2, label, size=size, fill=color, anchor="middle", rotate=-90)

    # -- output --------------------------------------------------------------
    def to_string(self) -> str:
        defs = "<defs>" + "".join(self.defs) + "</defs>"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">{defs}'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="{self.bg}"/>'
                + "".join(self.parts) + "</svg>")

    def save(self, path_svg: str, png_scale: float = 2.0) -> tuple[str, str]:
        os.makedirs(os.path.dirname(path_svg), exist_ok=True)
        s = self.to_string()
        with open(path_svg, "w", encoding="utf-8") as f:
            f.write(s)
        path_png = os.path.splitext(path_svg)[0] + ".png"
        import cairosvg  # local import so the module stays importable without it
        cairosvg.svg2png(bytestring=s.encode("utf-8"), write_to=path_png, scale=png_scale,
                         background_color="white")
        return path_svg, path_png


def rounded_rect_path(x, y, w, h, r) -> str:
    return (f"M {x + r:.2f} {y:.2f} H {x + w - r:.2f} A {r} {r} 0 0 1 {x + w:.2f} {y + r:.2f} "
            f"V {y + h - r:.2f} A {r} {r} 0 0 1 {x + w - r:.2f} {y + h:.2f} H {x + r:.2f} "
            f"A {r} {r} 0 0 1 {x:.2f} {y + h - r:.2f} V {y + r:.2f} A {r} {r} 0 0 1 {x + r:.2f} {y:.2f} Z")
