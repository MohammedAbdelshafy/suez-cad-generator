"""
Coastal-structures engineering engine — ECB 3802
"Design and Construction of Coastal Structures", Dr. Waleed Elemary
Arab Academy for Science, Technology & Maritime Transport (AASTMT).

Implements the lecture formulas directly:

  * Wind & Wind Rose  (Lectures 2 / 2A)
  * Tides & water levels (Lecture 3)
  * Wave transformation — shoaling Ks, refraction Kr, diffraction Kd (Lecture 4)
  * Rubble-mound breakwater design — Hudson (Lecture 5)

Planning / teaching level. Verify against full design codes and site surveys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import pi, sin, cos, tan, atan, asin, radians, degrees, sinh, tanh, sqrt

KNOT_KMH = 1.852          # 1 knot = 1.852 km/h  (Lecture 2)
G = 9.81                  # m/s^2


def _r(x, n=2):
    return round(float(x), n)


# ======================================================================== WIND
# 12 compass directions used in the lectures' wind-rose tables.
WIND_DIRS = ["N", "30", "60", "E", "120", "150", "S", "210", "240", "W", "300", "330"]
DIR_DEG = {"N": 0, "30": 30, "60": 60, "E": 90, "120": 120, "150": 150,
           "S": 180, "210": 210, "240": 240, "W": 270, "300": 300, "330": 330}

# Default recorded wind data (hours) from the lecture worked example
# (Lecture 2 slide 23 / Lecture 2A). Speed classes V1..V4.
WIND_SPEEDS = [5, 15, 25, 35]            # representative speed of each class [knots]
WIND_DATA = {
    "N":   [1459, 518, 84, 49],
    "30":  [535, 149, 15, 34],
    "60":  [330, 52, 19, 19],
    "E":   [230, 56, 10, 14],
    "120": [254, 24, 18, 15],
    "150": [180, 30, 12, 8],
    "S":   [140, 54, 11, 15],
    "210": [240, 225, 24, 18],
    "240": [115, 279, 15, 18],
    "W":   [210, 225, 16, 10],
    "300": [587, 790, 24, 31],
    "330": [1075, 409, 31, 11],
}
TOTAL_HOURS_YEAR = 8760                  # 365 * 24


def wind_rose(data: dict | None = None, speeds: list | None = None,
              calm_hours: float = 60.0, error_hours: float = 0.0) -> dict:
    """Analyse a directional wind table the way Lectures 2 / 2A do.

    Per direction:
      sum D            = Σ counts
      V_avg            = Σ(count_i · V_i) / Σ counts          (Polygon method)
      percentage DVi%  = count_i / (column total of V_i) · 100  (Percentage method)
    Prevailing wind direction = the direction blowing the largest time.
    """
    data = data or WIND_DATA
    speeds = speeds or WIND_SPEEDS
    dirs = [d for d in WIND_DIRS if d in data]

    col_tot = [sum(data[d][i] for d in dirs) for i in range(len(speeds))]
    grand = sum(col_tot)

    rows = []
    for d in dirs:
        counts = data[d]
        s = sum(counts)
        v_avg = sum(c * v for c, v in zip(counts, speeds)) / s if s else 0.0
        pct = [(_r(c / col_tot[i] * 100, 2) if col_tot[i] else 0.0)
               for i, c in enumerate(counts)]
        rows.append({
            "dir": d, "deg": DIR_DEG[d], "counts": counts,
            "sum": s, "pct_of_total": _r(s / grand * 100, 2) if grand else 0,
            "v_avg": _r(v_avg, 2), "pct": pct,
        })

    prevailing = max(rows, key=lambda r: r["sum"])
    recorded = TOTAL_HOURS_YEAR - calm_hours - error_hours

    return {
        "speeds": speeds,
        "rows": rows,
        "column_totals": col_tot,
        "grand_total": grand,
        "total_hours_year": TOTAL_HOURS_YEAR,
        "calm_hours": calm_hours,
        "error_hours": error_hours,
        "recorded_hours": recorded,
        "prevailing": {
            "dir": prevailing["dir"], "deg": prevailing["deg"],
            "hours": prevailing["sum"], "v_avg": prevailing["v_avg"],
        },
        # the major breakwater is set perpendicular to the prevailing wind
        "breakwater_normal_deg": (prevailing["deg"] + 180) % 360,
        "note": "Major breakwater oriented perpendicular to the prevailing "
                "wind direction (Lecture 2A).",
    }


# ======================================================================= TIDES
def tides(mhws: float = 0.65, mhwn: float = 0.45, mlwn: float = -0.40,
          mlws: float = -0.60, chart_datum: float = 0.0) -> dict:
    """Tidal datums & ranges (Lecture 3).

    Inputs are water levels (m) relative to mean sea level:
      MHWS mean high water springs, MHWN neap, MLWN, MLWS.
    """
    spring_range = mhws - mlws
    neap_range = mhwn - mlwn
    msl = (mhws + mhwn + mlwn + mlws) / 4.0
    # simple harmonic-style form factor is data-dependent; classify by ranges
    classification = ("Macrotidal" if spring_range >= 4 else
                      "Mesotidal" if spring_range >= 2 else "Microtidal")
    return {
        "levels": {
            "MHWS": _r(mhws), "MHWN": _r(mhwn), "MSL": _r(msl),
            "MLWN": _r(mlwn), "MLWS": _r(mlws), "chart_datum": _r(chart_datum),
        },
        "spring_range": _r(spring_range),
        "neap_range": _r(neap_range),
        "mean_range": _r((spring_range + neap_range) / 2),
        "classification": classification,
        "note": "Spring range at new/full moon (max); neap range at "
                "quarter moon (min). Lecture 3.",
    }


# ======================================================================= WAVES
def wavelength(T: float, d: float) -> dict:
    """Deep-water length L0 = 1.56 T^2 and length L at depth d via the
    linear dispersion relation L = L0 · tanh(2πd/L) (Lecture 4 tables)."""
    L0 = 1.56 * T * T
    L = L0
    for _ in range(100):                       # fixed-point iteration
        L_new = L0 * tanh(2 * pi * d / L)
        if abs(L_new - L) < 1e-6:
            L = L_new
            break
        L = L_new
    return {"L0": L0, "L": L, "d_over_L0": d / L0, "d_over_L": d / L}


def _shoaling(T: float, d: float, L0: float, L: float) -> float:
    k = 2 * pi / L
    n = 0.5 * (1 + 2 * k * d / sinh(2 * k * d))
    C = L / T
    C0 = L0 / T
    Cg = n * C
    Cg0 = 0.5 * C0
    return sqrt(Cg0 / Cg)


def wave_transformation(H0: float = 2.5, T: float = 8.0, d: float = 8.0,
                        phi0_deg: float = 0.0, Kd: float = 1.0) -> dict:
    """Wave transformation H = Ks · Kr · Kd · H0 (Lecture 4).

      Shoaling   Ks = √(Cg0 / Cg)
      Refraction Kr = √(cos φ0 / cos φ),   sin φ = (L/L0)·sin φ0   (Snell)
      Diffraction Kd  read from Wiegel chart/table → supplied as input.
    """
    wl = wavelength(T, d)
    L0, L = wl["L0"], wl["L"]
    Ks = _shoaling(T, d, L0, L)

    phi0 = radians(phi0_deg)
    sin_phi = (L / L0) * sin(phi0)
    sin_phi = max(-1.0, min(1.0, sin_phi))
    phi = asin(sin_phi)
    Kr = sqrt(cos(phi0) / cos(phi)) if cos(phi) > 0 else 1.0

    H = Ks * Kr * Kd * H0

    # depth-limited breaking check (McCowan / SPM): Hb ≈ 0.78 d
    Hb = 0.78 * d
    breaks = H > Hb

    return {
        "input": {"H0": _r(H0), "T": _r(T), "d": _r(d),
                  "phi0_deg": _r(phi0_deg), "Kd": _r(Kd, 3)},
        "L0": _r(L0), "L": _r(L),
        "d_over_L0": _r(wl["d_over_L0"], 4), "d_over_L": _r(wl["d_over_L"], 4),
        "Ks": _r(Ks, 3), "Kr": _r(Kr, 3), "Kd": _r(Kd, 3),
        "phi_deg": _r(degrees(phi), 2),
        "H": _r(H, 3),
        "Hb_limit": _r(Hb, 2),
        "breaking": breaks,
        "note": "H = Ks·Kr·Kd·H0. Kd from Wiegel diffraction chart/table "
                "(Lecture 4).",
    }


def diffraction_geometry(T: float, d: float, gap_b: float,
                         X: float, Y: float) -> dict:
    """Helper geometry for the diffraction chart lookup (Lecture 4 example):
    classify single vs double breakwater by b/L and give X/L, Y/L."""
    L = wavelength(T, d)["L"]
    b_L = gap_b / L
    kind = "Double breakwater (gap)" if b_L < 5 else "Single breakwater"
    return {
        "L": _r(L), "b_over_L": _r(b_L, 2),
        "X_over_L": _r(X / L, 2), "Y_over_L": _r(Y / L, 2),
        "type": kind,
        "note": "b/L < 5 → diffraction through a gap (double); "
                "b/L ≥ 5 → behaves as a single breakwater.",
    }


# ================================================================== BREAKWATER
# Hudson stability coefficient KD (SPM): {armour: (breaking, non-breaking)}
HUDSON_KD = {
    "rough_quarry_2": (2.0, 4.0),     # rough angular quarrystone, 2 layers
    "smooth_round_2": (1.2, 2.4),     # smooth rounded stone
    "tetrapod": (7.0, 8.0),
    "dolos": (15.8, 31.8),
    "cube": (6.5, 7.5),
}
# layer / packing coefficients (SPM): {armour: (kΔ, porosity P, n-per-layer)}
LAYER_K = {
    "rough_quarry_2": (1.15, 0.37),
    "smooth_round_2": (1.02, 0.38),
    "tetrapod": (1.04, 0.50),
    "dolos": (0.94, 0.56),
    "cube": (1.10, 0.47),
}


def breakwater(H: float = 2.5, armour: str = "rough_quarry_2",
               breaking: bool = True, cot_theta: float = 2.0,
               gamma_r: float = 2.65, gamma_w: float = 1.025,
               n_layers: int = 2, design_water_level: float = 0.65,
               seabed_level: float = -8.0, freeboard: float = 1.0) -> dict:
    """Rubble-mound armour design — Hudson formula (Lecture 5).

        W = (γr · H³) / (KD · (Sr − 1)³ · cotθ),   Sr = γr / γw

    Plus layer thickness, crest width and section levels.
    """
    kd_pair = HUDSON_KD.get(armour, HUDSON_KD["rough_quarry_2"])
    KD = kd_pair[0] if breaking else kd_pair[1]
    kdelta, P = LAYER_K.get(armour, LAYER_K["rough_quarry_2"])

    Sr = gamma_r / gamma_w
    W = (gamma_r * H ** 3) / (KD * (Sr - 1) ** 3 * cot_theta)   # tonnes

    # equivalent cube size of one armour unit
    Dn = (W / gamma_r) ** (1 / 3.0)
    layer_thk = n_layers * kdelta * Dn
    crest_width = max(3, n_layers) * kdelta * Dn               # ≥ 3 units

    # secondary layers (rule-of-thumb from Hudson practice)
    filter_W = W / 10.0
    core_W = W / 200.0

    # levels
    crest_level = design_water_level + freeboard
    height = crest_level - seabed_level
    base_width = crest_width + 2 * cot_theta * height          # symmetric slopes

    # number of armour units per 100 m² (SPM placement formula)
    Na_per_100 = 100 * n_layers * kdelta * (1 - P / 100.0 if P > 1 else 1 - P) \
        * (gamma_r / W) ** (2 / 3.0)

    return {
        "input": {"H": _r(H), "armour": armour, "breaking": breaking,
                  "cot_theta": _r(cot_theta), "gamma_r": _r(gamma_r),
                  "gamma_w": _r(gamma_w), "n_layers": n_layers},
        "KD": KD, "Sr": _r(Sr, 3),
        "armour_W_t": _r(W, 2),
        "armour_Dn_m": _r(Dn, 2),
        "filter_W_t": _r(filter_W, 2),
        "core_W_t": _r(core_W, 3),
        "layer_thickness_m": _r(layer_thk, 2),
        "crest_width_m": _r(crest_width, 2),
        "crest_level_m": _r(crest_level),
        "seabed_level_m": _r(seabed_level),
        "structure_height_m": _r(height, 2),
        "base_width_m": _r(base_width, 2),
        "units_per_100m2": _r(Na_per_100, 1),
        "slope": f"1 : {cot_theta:g}",
        "note": "Hudson W = γr·H³ / (KD·(Sr−1)³·cotθ). SPM coefficients. "
                "Lecture 5.",
    }


# ===================================================================== summary
def design_port(wind=None, tide=None, wave=None, bw=None) -> dict:
    """Run the full lecture workflow and return a combined design package."""
    w = wind_rose(**(wind or {}))
    t = tides(**(tide or {}))
    v = wave_transformation(**(wave or {}))
    # by default design the breakwater for the transformed wave height
    bw = dict(bw or {})
    bw.setdefault("H", v["H"])
    bw.setdefault("design_water_level", t["levels"]["MHWS"])
    b = breakwater(**bw)
    return {"wind": w, "tides": t, "waves": v, "breakwater": b,
            "meta": {
                "course": "ECB 3802 — Design and Construction of Coastal Structures",
                "lecturer": "Dr. Waleed Elemary",
                "institution": "Arab Academy for Science, Technology & "
                               "Maritime Transport (AASTMT)",
            }}


# ================================================================== GEOMETRY ==
def breakwater_section_geometry(bw: dict, tide: dict) -> dict:
    """Rubble-mound cross-section (elevation, metres): nested core / filter /
    armour trapezoids with water levels and key dimensions (Lecture 5)."""
    cot = bw["input"]["cot_theta"]
    cl = bw["crest_level_m"]
    sb = bw["seabed_level_m"]
    B = bw["crest_width_m"]
    ta = bw["layer_thickness_m"]
    tf = ta * 0.7
    H = cl - sb

    def trapezoid(crest_y, half_crest, toe_x):
        return [[-toe_x, sb], [-half_crest, crest_y],
                [half_crest, crest_y], [toe_x, sb]]

    toe = B / 2 + cot * H
    shapes = []
    # core (innermost)
    shapes.append({"kind": "polyline", "layer": "CORE", "label": "Core",
                   "points": trapezoid(cl - ta - tf, max(0.5, B / 2 - ta - tf),
                                       toe - ta - tf), "closed": True})
    # filter
    shapes.append({"kind": "polyline", "layer": "FILTER", "label": "Filter layer",
                   "points": trapezoid(cl - ta, B / 2 - ta, toe - ta),
                   "closed": True})
    # armour (outer)
    shapes.append({"kind": "polyline", "layer": "ARMOUR", "label": "Armour layer",
                   "points": trapezoid(cl, B / 2, toe), "closed": True})
    # seabed
    shapes.append({"kind": "line", "layer": "SEABED", "label": "Seabed",
                   "p1": [-toe - 6, sb], "p2": [toe + 6, sb]})
    # water levels
    for lvl_name in ("MHWS", "MLWS"):
        y = tide["levels"][lvl_name]
        shapes.append({"kind": "line", "layer": "WATER", "label": f"{lvl_name} {y:+.2f}",
                       "p1": [-toe - 6, y], "p2": [toe + 6, y], "dashed": True})
    # crest dimension
    shapes.append({"kind": "dim", "layer": "DIM", "label": f"crest B = {B:g} m",
                   "p1": [-B / 2, cl], "p2": [B / 2, cl]})
    return {"units": "m", "view": "section", "shapes": shapes,
            "extent": {"x": [-toe - 6, toe + 6], "y": [sb, cl + 2]}}


def harbour_layout_geometry(wind: dict, bw: dict) -> dict:
    """Schematic harbour plan (metres): shoreline, main breakwater set
    perpendicular to the prevailing wind, a lee breakwater forming the
    entrance gap, the protected basin, and a prevailing-wind arrow."""
    base = bw["base_width_m"]
    Lmain = max(400.0, 12 * base)          # representative breakwater length
    gap = max(120.0, 3 * base)             # entrance width
    w = base                                # plan footprint width of mound

    pwd = wind["prevailing"]["deg"]
    shapes = []
    # shoreline along y = 0 (land y>0, sea y<0)
    shapes.append({"kind": "line", "layer": "SHORE", "label": "Shoreline",
                   "p1": [-900, 0], "p2": [900, 0]})
    # main breakwater: from shore extending seaward (down), slight dogleg
    shapes.append({"kind": "rect", "layer": "BREAKWATER", "label": "Main breakwater",
                   "x": -Lmain * 0.55, "y": -Lmain, "w": w, "h": Lmain})
    # lee breakwater on the other side, leaving the entrance gap
    shapes.append({"kind": "rect", "layer": "BREAKWATER", "label": "Lee breakwater",
                   "x": -Lmain * 0.55 + w + gap, "y": -Lmain * 0.6,
                   "w": w, "h": Lmain * 0.6})
    # protected basin
    shapes.append({"kind": "rect", "layer": "BASIN", "label": "Protected basin",
                   "x": -Lmain * 0.5, "y": -Lmain * 0.85, "w": Lmain * 0.95,
                   "h": Lmain * 0.8, "ghost": True})
    # prevailing-wind arrow pointing toward the harbour
    import math
    ax, ay = 600, -700
    dx, dy = math.sin(math.radians(pwd)) * 260, math.cos(math.radians(pwd)) * 260
    shapes.append({"kind": "arrow", "layer": "WIND",
                   "label": f"Prevailing wind {wind['prevailing']['dir']} ({pwd:g}°)",
                   "p1": [ax + dx, ay + dy], "p2": [ax, ay]})
    return {"units": "m", "view": "plan", "shapes": shapes,
            "extent": {"x": [-900, 900], "y": [-Lmain - 40, 80]}}


# ===================================================== self-test vs lectures ==
if __name__ == "__main__":
    print("== Wind rose (Lecture 2A) ==")
    wr = wind_rose()
    north = next(r for r in wr["rows"] if r["dir"] == "N")
    print(f"  North V_avg = {north['v_avg']}  (lecture 8.95)")
    print(f"  North DV1%  = {north['pct'][0]}  (lecture 27.25)")
    print(f"  Prevailing  = {wr['prevailing']['dir']} "
          f"({wr['prevailing']['hours']} h)")

    print("== Wave (Lecture 4 example: T=8, d=8) ==")
    wl = wavelength(8, 8)
    print(f"  L0 = {wl['L0']:.1f} (lecture 100)   L = {wl['L']:.1f} (lecture 65)")
    print(f"  d/L = {wl['d_over_L']:.4f} (lecture 0.1232)")
    dg = diffraction_geometry(8, 8, 130, 400, 200)
    print(f"  gap 130 -> b/L={dg['b_over_L']} ({dg['type']})  "
          f"X/L={dg['X_over_L']} Y/L={dg['Y_over_L']}")

    print("== Breakwater (Hudson) ==")
    b = breakwater(H=2.5)
    print(f"  armour W = {b['armour_W_t']} t  crest = {b['crest_width_m']} m  "
          f"thk = {b['layer_thickness_m']} m")

    print("== Full design package ==")
    pkg = design_port()
    print("  keys:", list(pkg.keys()))
