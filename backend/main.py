"""
Coastal-Structures Design Engine — ECB 3802
"Design and Construction of Coastal Structures" · Dr. Waleed Elemary
Arab Academy for Science, Technology & Maritime Transport (AASTMT).

FastAPI backend: serves the front-end, the lecture-based calculation API
(wind rose, tides, wave transformation, rubble-mound breakwater) and the
CAD (DXF) / SVG exports of the breakwater section & harbour layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import coastal
import calculations
import boq as boq_mod
import report as report_mod
from cad_export import geometry_to_dxf, geometry_to_svg, META

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Coastal Structures Studio (CSS v1.0)", version="1.0")


# ------------------------------------------------------------------ requests --
class WindReq(BaseModel):
    data: Optional[dict] = None
    speeds: Optional[list] = None
    calm_hours: float = Field(60.0, ge=0)
    error_hours: float = Field(0.0, ge=0)


class TideReq(BaseModel):
    mhws: float = 0.65
    mhwn: float = 0.45
    mlwn: float = -0.40
    mlws: float = -0.60
    chart_datum: float = 0.0


class WaveReq(BaseModel):
    H0: float = Field(2.5, gt=0)
    T: float = Field(8.0, gt=0)
    d: float = Field(8.0, gt=0)
    phi0_deg: float = Field(0.0, ge=0, le=89)
    Kd: float = Field(1.0, gt=0, le=1.5)


class DiffReq(BaseModel):
    T: float = Field(8.0, gt=0)
    d: float = Field(8.0, gt=0)
    gap_b: float = Field(130.0, gt=0)
    X: float = 400.0
    Y: float = 200.0


class BreakwaterReq(BaseModel):
    H: float = Field(2.5, gt=0)
    armour: Literal["rough_quarry_2", "smooth_round_2", "tetrapod", "dolos", "cube"] = "rough_quarry_2"
    breaking: bool = True
    cot_theta: float = Field(2.0, ge=1, le=5)
    gamma_r: float = Field(2.65, gt=1)
    gamma_w: float = Field(1.025, gt=1)
    n_layers: int = Field(2, ge=2, le=3)
    design_water_level: float = 0.65
    seabed_level: float = -8.0
    freeboard: float = Field(1.0, ge=0)


class DesignReq(BaseModel):
    wind: Optional[WindReq] = None
    tide: Optional[TideReq] = None
    wave: Optional[WaveReq] = None
    breakwater: Optional[BreakwaterReq] = None


class VesselReq(BaseModel):
    vessel_type: str = "container"
    loa: float = Field(366.0, gt=0)
    beam: float = Field(51.0, gt=0)
    draft: float = Field(15.5, gt=0)
    dwt: float = Field(0.0, ge=0)
    speed_kn: float = Field(6.0, gt=0)
    exposure: Literal["sheltered", "moderate", "exposed"] = "moderate"
    channel_type: Literal["one-way", "two-way"] = "two-way"
    maneuver_aids: Literal["none", "tugs", "thrusters"] = "tugs"
    num_berths: int = Field(2, ge=1, le=20)


class BoqReq(BaseModel):
    design: Optional[DesignReq] = None
    length_m: float = Field(600.0, gt=0)


class ReportReq(BaseModel):
    design: Optional[DesignReq] = None
    project_name: str = "Coastal Port — Concept Design"
    engineer: str = "Mohamed Abdelshafy"
    length_m: float = Field(600.0, gt=0)
    include_boq: bool = True


# ------------------------------------------------------------------- modules --
@app.get("/api/meta")
def meta():
    return {
        **META,
        "app": "Coastal Structures Studio",
        "abbr": "CSS v1.0",
        "tagline": "AI That Engineers Your Infrastructure.",
        "vessel_presets": calculations.VESSEL_PRESETS,
    }


@app.post("/api/vessel")
def api_vessel(req: VesselReq):
    """Navigation channel, turning basin, berths & anchorage from the design
    vessel (PIANC/UNCTAD concept method)."""
    return calculations.compute(calculations.VesselInput(**req.model_dump()))


@app.get("/api/presets")
def api_presets():
    return calculations.VESSEL_PRESETS


@app.post("/api/calculate")
def api_calculate(req: VesselReq):
    return api_vessel(req)


@app.post("/api/export.dxf")
def api_export_dxf(req: VesselReq):
    payload = calculations.compute(calculations.VesselInput(**req.model_dump()))
    return _file(geometry_to_dxf(payload["geometry"], "Harbour Layout"),
                 "application/dxf", "harbour_layout.dxf")


@app.post("/api/export.svg")
def api_export_svg(req: VesselReq):
    payload = calculations.compute(calculations.VesselInput(**req.model_dump()))
    return _file(geometry_to_svg(payload["geometry"], "Harbour Layout"),
                 "image/svg+xml", "harbour_layout.svg")


@app.post("/api/wind")
def api_wind(req: WindReq):
    return coastal.wind_rose(**req.model_dump(exclude_none=False))


@app.post("/api/tides")
def api_tides(req: TideReq):
    return coastal.tides(**req.model_dump())


@app.post("/api/waves")
def api_waves(req: WaveReq):
    return coastal.wave_transformation(**req.model_dump())


@app.post("/api/diffraction")
def api_diffraction(req: DiffReq):
    return coastal.diffraction_geometry(**req.model_dump())


@app.post("/api/breakwater")
def api_breakwater(req: BreakwaterReq):
    return coastal.breakwater(**req.model_dump())


def _package(req: DesignReq) -> dict:
    return coastal.design_port(
        wind=req.wind.model_dump() if req.wind else None,
        tide=req.tide.model_dump() if req.tide else None,
        wave=req.wave.model_dump() if req.wave else None,
        bw=req.breakwater.model_dump() if req.breakwater else None,
    )


@app.post("/api/design")
def api_design(req: DesignReq):
    pkg = _package(req)
    pkg["section_geometry"] = coastal.breakwater_section_geometry(pkg["breakwater"], pkg["tides"])
    pkg["plan_geometry"] = coastal.harbour_layout_geometry(pkg["wind"], pkg["breakwater"])
    return pkg


def _boq(design: Optional[DesignReq], length_m: float) -> dict:
    pkg = _package(design or DesignReq())
    section = coastal.breakwater_section_geometry(pkg["breakwater"], pkg["tides"])
    g_r = pkg["breakwater"]["input"]["gamma_r"]
    return boq_mod.bill_of_quantities(pkg["breakwater"], section,
                                      length_m=length_m, gamma_r=g_r)


@app.post("/api/boq")
def api_boq(req: BoqReq):
    return _boq(req.design, req.length_m)


@app.post("/api/report")
def api_report(req: ReportReq):
    pkg = _package(req.design or DesignReq())
    boq = _boq(req.design, req.length_m) if req.include_boq else None
    html = report_mod.build_report(
        pkg, project={"name": req.project_name, "engineer": req.engineer}, boq=boq)
    return Response(content=html, media_type="text/html")


# ------------------------------------------------------------------- exports --
def _geoms(req: DesignReq):
    pkg = _package(req)
    section = coastal.breakwater_section_geometry(pkg["breakwater"], pkg["tides"])
    plan = coastal.harbour_layout_geometry(pkg["wind"], pkg["breakwater"])
    return section, plan


def _file(content, media, name):
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/export/section.dxf")
def export_section_dxf(req: DesignReq):
    section, _ = _geoms(req)
    return _file(geometry_to_dxf(section, "Breakwater Cross-Section"),
                 "application/dxf", "breakwater_section.dxf")


@app.post("/api/export/section.svg")
def export_section_svg(req: DesignReq):
    section, _ = _geoms(req)
    return _file(geometry_to_svg(section, "Breakwater Cross-Section"),
                 "image/svg+xml", "breakwater_section.svg")


@app.post("/api/export/plan.dxf")
def export_plan_dxf(req: DesignReq):
    _, plan = _geoms(req)
    return _file(geometry_to_dxf(plan, "Harbour Layout"),
                 "application/dxf", "harbour_layout.dxf")


@app.post("/api/export/plan.svg")
def export_plan_svg(req: DesignReq):
    _, plan = _geoms(req)
    return _file(geometry_to_svg(plan, "Harbour Layout"),
                 "image/svg+xml", "harbour_layout.svg")


# --------------------------------------------------------------------- pages --
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
