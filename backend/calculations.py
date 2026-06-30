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
        anchorage (circle, sea end)
    """
    B, LOA = v.beam, v.loa
    quay_len = d["quay_length"]
    clr = d["clearance"]
    n = d["num_berths"]
    turn_d = d["turning_diameter"]
    chan_w = d["channel_width"]
    anch_r = d["anchorage_radius"]

    cx = quay_len / 2.0
    gap = max(clr, 0.5 * B)

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

    # Anchorage swing circle at the sea end of the channel.
    anch_cy = chan_y - gap - anch_r
    shapes.append({
        "kind": "circle", "layer": "ANCHORAGE", "label": "Anchorage",
        "cx": _round(cx, 2), "cy": _round(anch_cy, 2), "r": _round(anch_r, 2),
    })

    return {"units": "m", "shapes": shapes}


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

    # --- Stopping distance & anchorage --------------------------------
    stopping_distance = 7.0 * LOA
    anchorage_radius = LOA + 6.0 * channel_depth + 30.0
    anchorage_area = pi * anchorage_radius ** 2

    results = [
        Result("Approach Channel Depth", _round(channel_depth), "m",
                f"draft {T:.1f} + squat {s:.2f} + wave {wave_allow:.1f} + UKC {net_ukc:.2f}"),
        Result("Approach Channel Width", _round(channel_width), "m",
                f"{v.channel_type} channel, {exp['label'].lower()} exposure"),
        Result("Turning Circle Diameter", _round(turning_diameter), "m",
                f"{turn_factor:.1f} x LOA ({v.maneuver_aids})"),
        Result("Turning Basin Area", _round(turning_area / 10000, 2), "ha",
                "water area swept for turning"),
        Result("Berth Pocket Depth", _round(berth_depth), "m",
                "alongside, reduced squat"),
        Result("Total Quay Length", _round(quay_length), "m",
                f"{n} berth(s) + {clearance:.0f} m clearances"),
        Result("Design Stopping Distance", _round(stopping_distance), "m",
                "~7 x LOA, loaded, emergency stop"),
        Result("Anchorage Swing Radius", _round(anchorage_radius), "m",
                "single-point swing mooring"),
        Result("Anchorage Area", _round(anchorage_area / 10000, 1), "ha",
                "per swinging vessel"),
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
        "anchorage_radius": anchorage_radius,
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
