"""
Bill of Quantities + cost estimate for the rubble-mound breakwater.

Volumes are taken from the validated cross-section geometry produced by
`coastal.breakwater_section_geometry` (nested core / filter / armour
trapezoids, m² per metre run) multiplied by the breakwater length.

Unit rates are planning-level placeholders (USD) — adjust to the project's
own schedule of rates. This module never alters the engineering numbers; it
only consumes them.
"""

from __future__ import annotations


def _poly_area(points) -> float:
    """Shoelace area of a closed polygon (absolute, m²)."""
    n = len(points)
    a = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


# planning-level unit rates
RATES = {
    "armour":   {"unit": "t",  "rate": 38.0, "label": "Primary armour stone"},
    "filter":   {"unit": "t",  "rate": 26.0, "label": "Secondary / filter stone"},
    "core":     {"unit": "t",  "rate": 18.0, "label": "Quarry-run core"},
    "concrete": {"unit": "m³", "rate": 165.0, "label": "Crest capping concrete"},
    "geotextile": {"unit": "m²", "rate": 6.5, "label": "Geotextile separator"},
}


def bill_of_quantities(breakwater: dict, section_geometry: dict,
                       length_m: float = 600.0,
                       gamma_r: float = 2.65) -> dict:
    """Quantities & cost for a breakwater of the given length.

    Net cross-sectional areas come from the nested section trapezoids:
        armour_net = A(armour) - A(filter)
        filter_net = A(filter) - A(core)
        core_net   = A(core)
    """
    polys = {s["layer"]: s["points"]
             for s in section_geometry["shapes"]
             if s.get("kind") == "polyline" and s.get("closed")}

    a_armour = _poly_area(polys["ARMOUR"]) if "ARMOUR" in polys else 0.0
    a_filter = _poly_area(polys["FILTER"]) if "FILTER" in polys else 0.0
    a_core = _poly_area(polys["CORE"]) if "CORE" in polys else 0.0

    armour_net = max(0.0, a_armour - a_filter)
    filter_net = max(0.0, a_filter - a_core)
    core_net = max(0.0, a_core)

    # volumes (m³) over the full length
    v_armour = armour_net * length_m
    v_filter = filter_net * length_m
    v_core = core_net * length_m

    # masses (t) — rock unit weight = gamma_r (t/m³)
    m_armour = v_armour * gamma_r
    m_filter = v_filter * gamma_r
    m_core = v_core * gamma_r

    # crest capping concrete: crest width * 1.0 m cap * length
    crest_w = breakwater.get("crest_width_m", 0.0)
    v_concrete = crest_w * 1.0 * length_m

    # geotextile under the structure ~ base width * length
    a_geo = breakwater.get("base_width_m", 0.0) * length_m

    rows = [
        _row("core", m_core),
        _row("filter", m_filter),
        _row("armour", m_armour),
        _row("concrete", v_concrete),
        _row("geotextile", a_geo),
    ]
    total = sum(r["amount"] for r in rows)

    return {
        "length_m": round(length_m, 1),
        "section_areas_m2": {
            "armour_net": round(armour_net, 2),
            "filter_net": round(filter_net, 2),
            "core_net": round(core_net, 2),
        },
        "items": rows,
        "total_cost": round(total, 0),
        "currency": "USD",
        "note": "Planning-level BOQ. Quantities from the validated section; "
                "unit rates are placeholders — replace with project rates.",
    }


def _row(key: str, qty: float) -> dict:
    r = RATES[key]
    amount = qty * r["rate"]
    return {
        "item": r["label"],
        "qty": round(qty, 1),
        "unit": r["unit"],
        "rate": r["rate"],
        "amount": round(amount, 0),
    }
