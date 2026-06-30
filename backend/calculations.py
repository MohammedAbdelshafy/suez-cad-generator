"""
Port dimensioning engine.

Computes the principal geometric dimensions of a port/harbour from a
"design vessel" using concept-design rules of thumb drawn from PIANC
WG121 (approach channels), UNCTAD and standard maritime engineering
practice. These are planning-level figures: final design must be
verified by a qualified coastal/maritime engineer with a real
manoeuvring/simulation study.

It also derives a to-scale schematic *plan geometry* (metres) of the
resulting port — channel, turning basin, quay/berths and anchorage —
which is the single source of truth shared by the on-screen plan, the
SVG export and the DXF (CAD) export.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import pi


# Block coefficient (fullness of hull) by vessel family — used for squat.
BLOCK_COEFFICIENT = {
    "container": 0.65,
    "tanker": 0.82,
    "bulk": 0.85,
    "general": 0.70,
    "cruise": 0.62,
    "lng": 0.74,
    "roro": 0.68,
}

# Exposure presets feed under-keel clearance, wave allowance and channel width.
EXPOSURE = {
    "sheltered": {"ukc_frac": 0.07, "wave_m": 0.0, "width_add": 0.6, "label": "Sheltered"},
    "moderate":  {"ukc_frac": 0.10, "wave_m": 0.5, "width_add": 1.3, "label": "Moderate"},
    "exposed":   {"ukc_frac": 0.15, "wave_m": 1.0, "width_add": 2.2, "label": "Exposed"},
}

# Turning-circle multiplier on LOA by available manoeuvring aids.
TURNING_FACTOR = {
    "none":      2.0,
    "tugs":      1.6,
    "thrusters": 1.5,
}

# Quick-fill particulars for well-known design vessels (planning-level typicals).
VESSEL_PRESETS = {
    "neopanamax": {
        "label": "Neo-Panamax container",
        "vessel_type": "container", "loa": 366, "beam": 49, "draft": 15.2,
        "dwt": 120000, "speed_kn": 6, "channel_type": "two-way",
    },
    "ulcv": {
        "label": "ULCV (24k TEU)",
        "vessel_type": "container", "loa": 400, "beam": 61.5, "draft": 16.5,
        "dwt": 220000, "speed_kn": 6, "exposure": "exposed", "channel_type": "two-way",
    },
    "feeder": {
        "label": "Container feeder",
        "vessel_type": "container", "loa": 200, "beam": 30, "draft": 11,
        "dwt": 30000, "speed_kn": 7, "channel_type": "one-way", "num_berths": 1,
    },
    "suezmax": {
        "label": "Suezmax tanker",
        "vessel_type": "tanker", "loa": 275, "beam": 48, "draft": 16.2,
        "dwt": 160000, "speed_kn": 5, "maneuver_aids": "tugs",
    },
    "vlcc": {
        "label": "VLCC tanker",
        "vessel_type": "tanker", "loa": 333, "beam": 60, "draft": 22.5,
        "dwt": 320000, "speed_kn": 5, "exposure": "exposed", "maneuver_aids": "tugs",
    },
    "capesize": {
        "label": "Capesize bulk carrier",
        "vessel_type": "bulk", "loa": 292, "beam": 45, "draft": 18.2,
        "dwt": 180000, "speed_kn": 5, "maneuver_aids": "tugs",
    },
    "qmax_lng": {
        "label": "Q-Max LNG carrier",
        "vessel_type": "lng", "loa": 345, "beam": 53.8, "draft": 12,
        "dwt": 130000, "speed_kn": 6, "maneuver_aids": "thrusters",
    },
    "oasis_cruise": {
        "label": "Oasis-class cruise",
        "vessel_type": "cruise", "loa": 362, "beam": 47, "draft": 9.3,
        "dwt": 100000, "speed_kn": 6, "maneuver_aids": "thrusters",
    },
}


@dataclass
class VesselInput:
    vessel_type: str = "container"
    loa: float = 366.0        # length overall [m]
    beam: float = 51.0        # moulded beam [m]
    draft: float = 15.5       # max design draft [m]
    dwt: float = 0.0          # deadweight [t] (optional, informational)
    speed_kn: float = 6.0     # transit speed in channel [knots]
    exposure: str = "moderate"
    channel_type: str = "two-way"   # "one-way" | "two-way"
    maneuver_aids: str = "tugs"      # "none" | "tugs" | "thrusters"
    num_berths: int = 2


@dataclass
class Result:
    label: str
    value: float
    unit: str
    note: str = ""
    formula: str = ""      # symbolic basis, e.g. "d = T + UKC + squat + wave"
    working: str = ""      # the same with the actual numbers substituted


def _round(x: float, n: int = 1) -> float:
    return round(float(x), n)


def squat(cb: float, speed_kn: float) -> float:
    """Barrass-II simplified maximum squat (open water), metres."""
    return cb * (speed_kn ** 2) / 100.0


def _build_geometry(v: VesselInput, d: dict) -> dict:
    """Derive a to-scale schematic port plan (metres, y-up, quay at y=0).

    Layout, water side below the quay:
        land (y > 0)  ───── QUAY ─────  (y = 0)
        berthed vessels alongside       (0 .. -beam)
        turning basin (circle)
        approach channel (rectangle, leads to sea)
    """
    B, LOA = v.beam, v.loa
    quay_len = d["quay_length"]
    clr = d["clearance"]
    n = d["num_berths"]
    turn_d = d["turning_diameter"]
    chan_w = d["channel_width"]
    chan_depth = d.get("channel_depth", 0.0)
    berth_depth = d.get("berth_depth", 0.0)

    cx = quay_len / 2.0
    gap = max(clr, 0.5 * B)
    o = max(quay_len, turn_d) * 0.05      # dimension offset (m) — scales with drawing

    shapes = []

    # Quay wall (land/water boundary).
    shapes.append({
        "kind": "polyline", "layer": "QUAY", "label": "Quay wall",
        "points": [[0.0, 0.0], [quay_len, 0.0]], "closed": False,
    })

    # Berthed design vessels alongside the quay.
    for i in range(n):
        x0 = clr + i * (LOA + clr)
        shapes.append({
            "kind": "rect", "layer": "BERTH",
            "label": f"Berth {i + 1}",
            "x": _round(x0, 2), "y": _round(-B, 2),
            "w": _round(LOA, 2), "h": _round(B, 2),
        })

    # Turning basin (clear of berthed vessels).
    basin_cy = -(B + gap + turn_d / 2.0)
    shapes.append({
        "kind": "circle", "layer": "TURNING", "label": "Turning basin",
        "cx": _round(cx, 2), "cy": _round(basin_cy, 2), "r": _round(turn_d / 2.0, 2),
    })

    # Approach channel — representative reach toward the sea (length schematic).
    basin_bottom = basin_cy - turn_d / 2.0
    chan_len = max(turn_d, 1.5 * chan_w)
    chan_top = basin_bottom + gap
    chan_y = chan_top - chan_len
    shapes.append({
        "kind": "rect", "layer": "CHANNEL", "label": "Approach channel",
        "x": _round(cx - chan_w / 2.0, 2), "y": _round(chan_y, 2),
        "w": _round(chan_w, 2), "h": _round(chan_len, 2),
        "note": "reach length schematic",
    })

    # Breakwater / training-mole stubs flanking the channel mouth (sea end).
    mouth = chan_y
    stub = max(chan_w * 0.6, gap)
    for sgn in (-1, 1):
        ex = cx + sgn * chan_w / 2.0
        shapes.append({
            "kind": "polyline", "layer": "STRUCT", "closed": False,
            "points": [[_round(ex + sgn * stub, 2), _round(mouth - stub, 2)],
                       [_round(ex, 2), _round(mouth, 2)]],
        })
    shapes.append({
        "kind": "note", "layer": "STRUCT", "text": "Breakwater heads",
        "x": _round(cx, 2), "y": _round(mouth - stub * 1.15, 2), "anchor": "middle",
    })

    # ---- Dimension lines (extension lines + ticked dim line + value text) ----
    def dim(p1, p2, off, text):
        shapes.append({"kind": "dimension", "layer": "DIM",
                       "p1": [_round(p1[0], 2), _round(p1[1], 2)],
                       "p2": [_round(p2[0], 2), _round(p2[1], 2)],
                       "off": _round(off, 2), "text": text})

    # Total quay length — dimensioned on the land side (above the quay).
    dim([0.0, 0.0], [quay_len, 0.0], o, f"Quay L = {quay_len:.0f} m")
    # First berth: LOA (below) and beam (to the left).
    dim([clr, -B], [clr + LOA, -B], -o, f"LOA = {LOA:.0f} m")
    dim([clr, 0.0], [clr, -B], -o, f"B = {B:.0f} m")
    if n >= 2:                                   # inter-berth clearance
        dim([clr + LOA, -B], [2 * clr + LOA, -B], -o * 0.6, f"c = {clr:.0f} m")
    # Turning basin diameter (horizontal through the centre).
    dim([cx - turn_d / 2.0, basin_cy], [cx + turn_d / 2.0, basin_cy], 0.0,
        f"Ø {turn_d:.0f} m")
    # Channel width (across the mouth).
    dim([cx - chan_w / 2.0, mouth], [cx + chan_w / 2.0, mouth], -o, f"W = {chan_w:.0f} m")

    # ---- Depth call-outs (depths aren't visible in plan view) ----
    shapes.append({
        "kind": "note", "layer": "DIM", "anchor": "middle",
        "x": _round(cx, 2), "y": _round((chan_y + chan_top) / 2.0, 2),
        "text": f"Dredge depth {chan_depth:.1f} m CD",
    })
    shapes.append({
        "kind": "note", "layer": "DIM", "anchor": "middle",
        "x": _round(cx, 2), "y": _round(-B / 2.0, 2),
        "text": f"Berth pocket {berth_depth:.1f} m CD",
    })

    return {"units": "m", "shapes": shapes, "north": True}


def compute(v: VesselInput) -> dict:
    cb = BLOCK_COEFFICIENT.get(v.vessel_type, 0.70)
    exp = EXPOSURE.get(v.exposure, EXPOSURE["moderate"])
    B, T, LOA = v.beam, v.draft, v.loa

    # --- Approach channel depth ---------------------------------------
    s = squat(cb, v.speed_kn)
    net_ukc = max(0.05 * T, 0.5)            # manoeuvrability / bottom margin
    wave_allow = exp["wave_m"]
    channel_depth = T + net_ukc + s + wave_allow

    # --- Berth pocket depth (lower speed -> less squat) ---------------
    berth_depth = T + max(0.07 * T, 0.5)

    # --- Channel width (PIANC concept method) -------------------------
    w_bm = 1.5 * B                          # basic manoeuvring lane
    w_add = exp["width_add"] * B            # wind/current/aids/visibility
    w_bank = 0.5 * B                        # bank clearance per side
    if v.channel_type == "two-way":
        w_pass = 1.6 * B                    # passing distance
        channel_width = 2 * w_bm + 2 * w_add + w_pass + 2 * w_bank
    else:
        channel_width = w_bm + w_add + 2 * w_bank

    # --- Turning circle ----------------------------------------------
    turn_factor = TURNING_FACTOR.get(v.maneuver_aids, 2.0)
    turning_diameter = turn_factor * LOA
    turning_area = pi * (turning_diameter / 2) ** 2

    # --- Berth / quay length -----------------------------------------
    clearance = max(0.10 * LOA, 15.0)
    n = max(1, int(v.num_berths))
    quay_length = n * LOA + (n + 1) * clearance

    # Channel-width formula/working depend on the channel type (PIANC concept).
    a = exp["width_add"]
    if v.channel_type == "two-way":
        width_formula = "W = 2·(1.5B) + 2·(a·B) + 1.6B + 2·(0.5B)"
        width_working = (f"2×{w_bm:.0f} + 2×{w_add:.0f} + {w_pass:.0f} + 2×{w_bank:.0f} "
                         f"= {channel_width:.0f} m   (B={B:.0f}, a={a:.1f})")
    else:
        width_formula = "W = 1.5B + a·B + 2·(0.5B)"
        width_working = (f"{w_bm:.0f} + {w_add:.0f} + 2×{w_bank:.0f} "
                         f"= {channel_width:.0f} m   (B={B:.0f}, a={a:.1f})")

    results = [
        Result("Approach Channel Depth", _round(channel_depth), "m",
                f"draft {T:.1f} + squat {s:.2f} + wave {wave_allow:.1f} + UKC {net_ukc:.2f}",
                formula="d = T + UKC + squat + wave",
                working=f"{T:.1f} + {net_ukc:.2f} + {s:.2f} + {wave_allow:.1f} = {channel_depth:.2f} m"),
        Result("Approach Channel Width", _round(channel_width), "m",
                f"{v.channel_type} channel, {exp['label'].lower()} exposure",
                formula=width_formula, working=width_working),
        Result("Turning Circle Diameter", _round(turning_diameter), "m",
                f"{turn_factor:.1f} x LOA ({v.maneuver_aids})",
                formula="D = f · LOA",
                working=f"{turn_factor:.1f} × {LOA:.0f} = {turning_diameter:.0f} m   (f for {v.maneuver_aids})"),
        Result("Turning Basin Area", _round(turning_area / 10000, 2), "ha",
                "water area swept for turning",
                formula="A = π·(D/2)²",
                working=f"π × ({turning_diameter:.0f}/2)² = {turning_area:,.0f} m² = {turning_area/10000:.2f} ha"),
        Result("Berth Pocket Depth", _round(berth_depth), "m",
                "alongside, reduced squat",
                formula="d_b = T + max(0.07·T, 0.5)",
                working=f"{T:.1f} + {max(0.07*T, 0.5):.2f} = {berth_depth:.2f} m"),
        Result("Total Quay Length", _round(quay_length), "m",
                f"{n} berth(s) + {clearance:.0f} m clearances",
                formula="L = n·LOA + (n+1)·c",
                working=f"{n}×{LOA:.0f} + {n + 1}×{clearance:.0f} = {quay_length:.0f} m   (c={clearance:.0f} m)"),
    ]

    summary = {
        "vessel_class": _vessel_class(v),
        "block_coefficient": cb,
        "squat_m": _round(s, 2),
    }

    # Dimensions reused by the plan geometry (full precision, not rounded).
    dims = {
        "quay_length": quay_length,
        "clearance": clearance,
        "num_berths": n,
        "turning_diameter": turning_diameter,
        "channel_width": channel_width,
        "channel_depth": channel_depth,
        "berth_depth": berth_depth,
    }

    return {
        "input": asdict(v),
        "summary": summary,
        "results": [asdict(r) for r in results],
        "geometry": _build_geometry(v, dims),
        "disclaimer": (
            "Planning-level concept figures (PIANC/UNCTAD rules of thumb). "
            "Not for construction. Verify with a manoeuvring simulation and "
            "a qualified maritime engineer."
        ),
    }


def _vessel_class(v: VesselInput) -> str:
    """Loose size-class label for context."""
    loa = v.loa
    if v.vessel_type == "container":
        if loa >= 397: return "ULCV (Ultra Large Container Vessel)"
        if loa >= 366: return "New-Panamax / Neo-Panamax"
        if loa >= 294: return "Post-Panamax"
        return "Panamax / Feeder"
    if v.vessel_type in ("tanker", "bulk"):
        if loa >= 330: return "VLCC / Capesize class"
        if loa >= 245: return "Suezmax / Panamax class"
        return "Aframax / Handymax class"
    return f"{v.vessel_type.title()} vessel"
