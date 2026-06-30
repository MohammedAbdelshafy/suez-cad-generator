"""
Engineering report generator — Coastal Structures Studio (CSS v1.0).

Renders a self-contained, print-ready HTML report (open in a browser and
"Print → Save as PDF") from the validated design package. Consumes the
engineering outputs verbatim; it does not compute or alter any value.
"""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path

LOGO = Path(__file__).resolve().parent.parent / "static" / "img" / "aast_logo.png"


def _logo_data_uri() -> str:
    try:
        return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    except Exception:
        return ""


def _table(headers, rows) -> str:
    h = "".join(f"<th>{c}</th>" for c in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"


def build_report(pkg: dict, project: dict | None = None,
                 boq: dict | None = None) -> str:
    project = project or {}
    meta = pkg.get("meta", {})
    wind = pkg["wind"]
    tide = pkg["tides"]
    wave = pkg["waves"]
    bw = pkg["breakwater"]

    pname = project.get("name", "Coastal Port — Concept Design")
    eng = project.get("engineer", "Mohamed Abdelshafy")

    wind_rows = [[r["dir"], r["sum"], r["v_avg"], f'{r["pct_of_total"]}%']
                 for r in wind["rows"]]

    tide_rows = [[k, f'{v:+.2f} m'] for k, v in tide["levels"].items()]

    wave_rows = [
        ["Deep-water length L0 = 1.56 T²", f'{wave["L0"]} m'],
        ["Length at depth L (dispersion)", f'{wave["L"]} m'],
        ["Shoaling coefficient Ks", wave["Ks"]],
        ["Refraction coefficient Kr", wave["Kr"]],
        ["Diffraction coefficient Kd", wave["Kd"]],
        ["Design wave height H = Ks·Kr·Kd·H0", f'<b>{wave["H"]} m</b>'],
        ["Breaking limit Hb ≈ 0.78 d", f'{wave["Hb_limit"]} m'],
    ]

    bw_rows = [
        ["Stability coefficient KD (Hudson)", bw["KD"]],
        ["Specific gravity Sr = γr/γw", bw["Sr"]],
        ["Armour unit weight W", f'<b>{bw["armour_W_t"]} t</b>'],
        ["Armour nominal size Dn", f'{bw["armour_Dn_m"]} m'],
        ["Filter stone weight", f'{bw["filter_W_t"]} t'],
        ["Core stone weight", f'{bw["core_W_t"]} t'],
        ["Armour layer thickness", f'{bw["layer_thickness_m"]} m'],
        ["Crest width B", f'{bw["crest_width_m"]} m'],
        ["Crest level", f'{bw["crest_level_m"]:+.2f} m'],
        ["Structure height", f'{bw["structure_height_m"]} m'],
        ["Base width", f'{bw["base_width_m"]} m'],
        ["Seaward slope", bw["slope"]],
    ]

    boq_html = ""
    if boq:
        boq_rows = [[i["item"], f'{i["qty"]:,}', i["unit"],
                     f'${i["rate"]:,.0f}', f'${i["amount"]:,.0f}'] for i in boq["items"]]
        boq_html = f"""
        <h2>6 · Bill of Quantities &amp; Cost Estimate</h2>
        <p>Breakwater length: {boq['length_m']} m. {boq['note']}</p>
        {_table(["Item", "Quantity", "Unit", "Rate", "Amount"], boq_rows)}
        <p class="total">Estimated total: <b>${boq['total_cost']:,.0f} {boq['currency']}</b></p>
        """

    logo = _logo_data_uri()
    logo_img = f'<img src="{logo}" alt="AASTMT" class="logo">' if logo else ""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>{pname} — Engineering Report</title>
<style>
 @page {{ margin: 18mm; }}
 body {{ font-family: "Segoe UI", Arial, sans-serif; color:#16202c; line-height:1.5;
        max-width: 900px; margin: 0 auto; padding: 24px; }}
 .head {{ display:flex; align-items:center; gap:18px; border-bottom:3px solid #0a4d68;
         padding-bottom:14px; margin-bottom:8px; }}
 .logo {{ height:74px; }}
 .head h1 {{ font-size:20px; margin:0; color:#0a4d68; }}
 .head .sub {{ font-size:12.5px; color:#456; margin-top:2px; }}
 .meta {{ display:flex; flex-wrap:wrap; gap:6px 28px; font-size:12.5px; color:#33485c;
         margin:10px 0 22px; }}
 .meta b {{ color:#0a4d68; }}
 h2 {{ color:#0a4d68; font-size:15px; border-left:4px solid #1b9aaa; padding-left:9px;
      margin-top:26px; }}
 table {{ border-collapse:collapse; width:100%; font-size:12.5px; margin:8px 0; }}
 th, td {{ border:1px solid #cdd9e3; padding:5px 9px; text-align:left; }}
 th {{ background:#0a4d68; color:#fff; font-weight:600; }}
 tr:nth-child(even) td {{ background:#f1f6f9; }}
 .eq {{ background:#f1f6f9; border:1px solid #cdd9e3; border-radius:6px; padding:9px 12px;
       font-family:Consolas,monospace; font-size:13px; margin:8px 0; }}
 .total {{ font-size:14px; margin-top:10px; }}
 .foot {{ margin-top:34px; border-top:1px solid #cdd9e3; padding-top:10px; font-size:11px;
        color:#6a7c8c; }}
 .badge {{ display:inline-block; background:#1b9aaa; color:#fff; border-radius:4px;
          padding:1px 8px; font-size:11px; letter-spacing:.5px; }}
</style></head><body>
<div class="head">{logo_img}
  <div><h1>{pname}</h1>
  <div class="sub">Engineering Design Report &nbsp;·&nbsp; <span class="badge">CSS v1.0</span> Coastal Structures Studio</div></div>
</div>
<div class="meta">
  <span><b>Course:</b> {meta.get('course','ECB 3802')}</span>
  <span><b>Lecturer:</b> {meta.get('lecturer','Dr. Waleed Elemary')}</span>
  <span><b>Institution:</b> {meta.get('institution','AASTMT')}</span>
  <span><b>Engineer:</b> {eng}</span>
  <span><b>Date:</b> {date.today().isoformat()}</span>
</div>

<h2>1 · Wind Analysis &amp; Wind Rose</h2>
<p>Prevailing wind: <b>{wind['prevailing']['dir']}</b>
   ({wind['prevailing']['hours']:,} h/yr, mean {wind['prevailing']['v_avg']} kn).
   The major breakwater is oriented perpendicular to the prevailing wind
   ({wind['breakwater_normal_deg']}°).</p>
<div class="eq">V_avg = Σ(count·V) / Σcount &nbsp;·&nbsp; %DVi = countᵢ / Σcolumn × 100</div>
{_table(["Direction", "Hours", "V_avg (kn)", "% of total"], wind_rows)}

<h2>2 · Tides &amp; Water Levels</h2>
<p>Classification: <b>{tide['classification']}</b> ·
   spring range {tide['spring_range']} m · neap range {tide['neap_range']} m.</p>
{_table(["Datum", "Level"], tide_rows)}

<h2>3 · Wave Transformation</h2>
<p>Refracted/shoaled/diffracted design wave from H0 = {wave['input']['H0']} m,
   T = {wave['input']['T']} s at depth d = {wave['input']['d']} m.</p>
<div class="eq">H = Ks · Kr · Kd · H0 &nbsp;·&nbsp; L0 = 1.56 T² &nbsp;·&nbsp; L = L0·tanh(2πd/L)</div>
{_table(["Quantity", "Value"], wave_rows)}

<h2>4 · Rubble-Mound Breakwater (Hudson)</h2>
<div class="eq">W = γr · H³ / [ KD · (Sr − 1)³ · cotθ ]</div>
<p>Designed for H = {bw['input']['H']} m,
   {'breaking' if bw['input']['breaking'] else 'non-breaking'} waves,
   slope {bw['slope']}, {bw['input']['armour']} armour.</p>
{_table(["Parameter", "Value"], bw_rows)}

<h2>5 · Masterplan &amp; CAD</h2>
<p>Harbour layout and breakwater cross-section are generated as editable
   AutoCAD DXF and SVG drawings (layers, dimensions, title block, north arrow,
   {meta.get('institution','AASTMT')} title block). See the CAD Generator module.</p>
{boq_html}

<div class="foot">
  Generated by <b>Coastal Structures Studio (CSS v1.0)</b> — AI Engineering Platform.
  All calculations follow the {meta.get('course','ECB 3802')} lecture methods of
  {meta.get('lecturer','Dr. Waleed Elemary')}, {meta.get('institution','AASTMT')}.
  Planning / teaching level — verify against full design codes and site surveys
  before construction. The engineer remains responsible for all final decisions.
</div>
</body></html>"""
