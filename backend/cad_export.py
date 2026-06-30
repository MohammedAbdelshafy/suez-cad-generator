"""
Render coastal-structure geometry (breakwater cross-section / harbour layout)
to downloadable CAD artefacts:

  * DXF — AutoCAD-compatible (ezdxf), 1 unit = 1 m, one layer per feature,
          with a title block (institution / course / lecturer).
  * SVG — self-contained vector drawing with the AASTMT logo embedded.

ECB 3802 — Design and Construction of Coastal Structures · Dr. Waleed Elemary
Arab Academy for Science, Technology & Maritime Transport (AASTMT).
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

import ezdxf

LOGO = Path(__file__).resolve().parent.parent / "static" / "img" / "aast_logo.png"

META = {
    "institution": "Arab Academy for Science, Technology & Maritime Transport",
    "course": "ECB 3802 - Design and Construction of Coastal Structures",
    "lecturer": "Dr. Waleed Elemary",
}

# layer -> (AutoCAD color index, svg stroke, svg fill)
STYLE = {
    "ARMOUR":     (30, "#ffb454", "rgba(255,180,84,0.12)"),
    "FILTER":     (4,  "#5ef0ff", "rgba(94,240,255,0.10)"),
    "CORE":       (8,  "#83b4ab", "rgba(131,180,171,0.10)"),
    "SEABED":     (43, "#b08d57", "none"),
    "WATER":      (5,  "#19f0c8", "none"),
    "DIM":        (7,  "#d6f2ec", "none"),
    "SHORE":      (30, "#ffb454", "none"),
    "BREAKWATER": (3,  "#19f0c8", "rgba(25,240,200,0.12)"),
    "BASIN":      (4,  "#5ef0ff", "rgba(94,240,255,0.04)"),
    "WIND":       (6,  "#7a5cff", "none"),
}


def _rect_pts(s):
    x, y, w, h = s["x"], s["y"], s["w"], s["h"]
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _bbox(geo):
    if "extent" in geo:
        ex, ey = geo["extent"]["x"], geo["extent"]["y"]
        return min(ex), min(ey), max(ex), max(ey)
    xs, ys = [], []
    for s in geo["shapes"]:
        if s["kind"] == "circle":
            xs += [s["cx"] - s["r"], s["cx"] + s["r"]]; ys += [s["cy"] - s["r"], s["cy"] + s["r"]]
        elif s["kind"] == "rect":
            xs += [s["x"], s["x"] + s["w"]]; ys += [s["y"], s["y"] + s["h"]]
        elif s["kind"] in ("line", "arrow", "dim"):
            xs += [s["p1"][0], s["p2"][0]]; ys += [s["p1"][1], s["p2"][1]]
        else:
            xs += [p[0] for p in s["points"]]; ys += [p[1] for p in s["points"]]
    return min(xs), min(ys), max(xs), max(ys)


def _extent(geo):
    a, b, c, d = _bbox(geo)
    return max(c - a, d - b, 1.0)


def _centroid(s):
    if s["kind"] == "circle":
        return s["cx"], s["cy"]
    if s["kind"] == "rect":
        return s["x"] + s["w"] / 2, s["y"] + s["h"] / 2
    if s["kind"] in ("line", "arrow", "dim"):
        return (s["p1"][0] + s["p2"][0]) / 2, (s["p1"][1] + s["p2"][1]) / 2
    xs = [p[0] for p in s["points"]]; ys = [p[1] for p in s["points"]]
    return sum(xs) / len(xs), sum(ys) / len(ys)


# --------------------------------------------------------------------- DXF ---
def geometry_to_dxf(geo: dict, title: str = "") -> str:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    for name, (aci, _, _) in STYLE.items():
        if name not in doc.layers:
            doc.layers.add(name, color=aci)
    h = max(_extent(geo) * 0.018, 0.6)

    for s in geo["shapes"]:
        layer = s["layer"]
        k = s["kind"]
        if k == "circle":
            msp.add_circle((s["cx"], s["cy"]), s["r"], dxfattribs={"layer": layer})
        elif k == "rect":
            msp.add_lwpolyline(_rect_pts(s), close=True, dxfattribs={"layer": layer})
        elif k in ("line", "dim"):
            msp.add_line(s["p1"], s["p2"], dxfattribs={"layer": layer})
        elif k == "arrow":
            msp.add_line(s["p1"], s["p2"], dxfattribs={"layer": layer})
        else:
            msp.add_lwpolyline(s["points"], close=s.get("closed", False),
                               dxfattribs={"layer": layer})
        if s.get("label"):
            cx, cy = _centroid(s)
            t = msp.add_text(s["label"], dxfattribs={"layer": layer, "height": h})
            t.set_placement((cx, cy))

    _dxf_titleblock(msp, geo, title, h)
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()


def _dxf_titleblock(msp, geo, title, h):
    minx, miny, maxx, maxy = _bbox(geo)
    y = miny - _extent(geo) * 0.10
    lines = [
        f"{META['institution']}",
        f"{META['course']}",
        f"Lecturer: {META['lecturer']}",
        f"Drawing: {title or geo.get('view', '').title()}",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} - "
        f"CONCEPT / TEACHING - NOT FOR CONSTRUCTION",
    ]
    for i, ln in enumerate(lines):
        t = msp.add_text(ln, dxfattribs={"height": h, "layer": "DIM"})
        t.set_placement((minx, y - i * h * 1.8))


# --------------------------------------------------------------------- SVG ---
def _logo_data_uri() -> str | None:
    try:
        b = LOGO.read_bytes()
        return "data:image/png;base64," + base64.b64encode(b).decode()
    except Exception:
        return None


def geometry_to_svg(geo: dict, title: str = "", px: int = 980) -> str:
    minx, miny, maxx, maxy = _bbox(geo)
    pad = _extent(geo) * 0.08
    minx -= pad; miny -= pad; maxx += pad; maxy += pad
    wm, hm = maxx - minx, maxy - miny
    scale = px / max(wm, hm)
    W, H = wm * scale, hm * scale + 86          # +titleblock band

    def X(x): return (x - minx) * scale
    def Y(y): return (maxy - y) * scale + 64     # +header band

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
        f'viewBox="0 0 {W:.0f} {H:.0f}" font-family="monospace">',
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="#05090f"/>',
    ]
    # header band with logo + title block
    out.append(f'<rect width="{W:.0f}" height="58" fill="#0b141e"/>')
    logo = _logo_data_uri()
    if logo:
        out.append(f'<image href="{logo}" x="8" y="6" width="46" height="46"/>')
    out.append(_t(META["institution"], 66, 20, 12, "#d6f2ec", anchor="start"))
    out.append(_t(f'{META["course"]}  ·  {META["lecturer"]}', 66, 38, 11,
                  "#83b4ab", anchor="start"))
    out.append(_t((title or geo.get("view", "")).upper(), W - 12, 30, 14,
                  "#19f0c8", anchor="end", bold=True))

    # grid
    out.append(_grid(minx, miny, maxx, maxy, scale, X, Y, W))

    for s in geo["shapes"]:
        _, stroke, fill = STYLE.get(s["layer"], STYLE["DIM"])
        k = s["kind"]
        dash = ' stroke-dasharray="6 5"' if s.get("dashed") else ""
        if k == "circle":
            out.append(f'<circle cx="{X(s["cx"]):.1f}" cy="{Y(s["cy"]):.1f}" '
                       f'r="{s["r"]*scale:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        elif k == "rect":
            f = "none" if s.get("ghost") else fill
            d = ' stroke-dasharray="4 4"' if s.get("ghost") else ""
            out.append(f'<rect x="{X(s["x"]):.1f}" y="{Y(s["y"]+s["h"]):.1f}" '
                       f'width="{s["w"]*scale:.1f}" height="{s["h"]*scale:.1f}" '
                       f'fill="{f}" stroke="{stroke}" stroke-width="1.5"{d}/>')
        elif k in ("line", "dim"):
            out.append(f'<line x1="{X(s["p1"][0]):.1f}" y1="{Y(s["p1"][1]):.1f}" '
                       f'x2="{X(s["p2"][0]):.1f}" y2="{Y(s["p2"][1]):.1f}" '
                       f'stroke="{stroke}" stroke-width="1.8"{dash}/>')
        elif k == "arrow":
            out.append(_arrow(X(s["p1"][0]), Y(s["p1"][1]), X(s["p2"][0]), Y(s["p2"][1]), stroke))
        else:
            pts = " ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in s["points"])
            close = "Z" if s.get("closed") else ""
            d = "M " + " L ".join(pts.split(" ")) + " " + close
            out.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
        if s.get("label"):
            cx, cy = _centroid(s)
            out.append(_t(s["label"], X(cx), Y(cy), 12, stroke, halo=True))

    out.append(_scalebar(scale, W, H))
    out.append(_t("CONCEPT / TEACHING — NOT FOR CONSTRUCTION", W/2, H-10, 10,
                  "#6f9e95", anchor="middle"))
    out.append("</svg>")
    return "\n".join(out)


def _t(s, x, y, size, color, anchor="middle", bold=False, halo=False):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    w = ' font-weight="bold"' if bold else ""
    h = ' paint-order="stroke" stroke="#05090f" stroke-width="3"' if halo else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="{size}" '
            f'text-anchor="{anchor}"{w}{h}>{s}</text>')


def _arrow(x1, y1, x2, y2, color):
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    s = 12
    p1 = (x2 - s*math.cos(a - 0.4), y2 - s*math.sin(a - 0.4))
    p2 = (x2 - s*math.cos(a + 0.4), y2 - s*math.sin(a + 0.4))
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="2.4"/>'
            f'<polygon points="{x2:.1f},{y2:.1f} {p1[0]:.1f},{p1[1]:.1f} '
            f'{p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/>')


def _grid(minx, miny, maxx, maxy, scale, X, Y, W):
    import math
    raw = (maxx - minx) / 9
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = next((m*mag for m in (1, 2, 5, 10) if raw <= m*mag), 10*mag)
    o = ['<g stroke="rgba(25,240,200,0.08)" stroke-width="1">']
    x = step * math.ceil(minx / step)
    while x <= maxx:
        o.append(f'<line x1="{X(x):.1f}" y1="58" x2="{X(x):.1f}" y2="{Y(miny):.1f}"/>'); x += step
    y = step * math.ceil(miny / step)
    while y <= maxy:
        o.append(f'<line x1="0" y1="{Y(y):.1f}" x2="{W:.0f}" y2="{Y(y):.1f}"/>'); y += step
    o.append("</g>")
    return "\n".join(o)


def _scalebar(scale, W, H):
    import math
    raw = (W / scale) / 6
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    bar_m = next((m*mag for m in (1, 2, 5, 10) if raw <= m*mag), 10*mag)
    bp = bar_m * scale
    x0, y0 = 18, H - 30
    return (f'<g stroke="#d6f2ec" stroke-width="2" fill="#d6f2ec">'
            f'<line x1="{x0}" y1="{y0}" x2="{x0+bp:.1f}" y2="{y0}"/>'
            f'<line x1="{x0}" y1="{y0-5}" x2="{x0}" y2="{y0+5}"/>'
            f'<line x1="{x0+bp:.1f}" y1="{y0-5}" x2="{x0+bp:.1f}" y2="{y0+5}"/>'
            f'<text x="{x0}" y="{y0-9}" font-size="12" stroke="none">{bar_m:g} m</text></g>')
