# SUEZ · CAD & Masterplan Design AI Engineer

A **design-vessel port dimensioning** engine with a CAD/masterplan front-end.
Enter a design vessel's particulars (LOA, beam, draft, …) and it computes the
port's principal dimensions — approach channel depth & width, turning circle,
quay length, anchorage, and more — then draws and exports a to-scale masterplan.

> Planning-level concept figures (PIANC WG121 / UNCTAD rules of thumb).
> **Not for construction** — verify with a manoeuvring simulation and a
> qualified maritime engineer.

## Run

```powershell
cd suez-cad-generator
./run.ps1
```

Then open **http://127.0.0.1:8077**.

Manual alternative:

```powershell
uv venv .venv --python 3.12
uv pip install -r requirements.txt --python .venv\Scripts\python.exe
.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --port 8077 --reload
```

## What it computes

| Output | Basis |
|--------|-------|
| Approach channel depth | draft + net UKC + Barrass squat + wave allowance |
| Approach channel width | PIANC concept method (one/two-way, exposure) |
| Turning circle diameter | 1.5–2.0 × LOA by manoeuvre aids |
| Turning basin area | swept circle |
| Berth pocket depth | draft + alongside clearance |
| Total quay length | berths × LOA + clearances |
| Stopping distance | ~7 × LOA |
| Anchorage radius & area | swing mooring |

## What it draws (CAD)

From the same numbers the engine derives a **to-scale schematic plan**
(quay wall, berthed design vessels, turning basin, approach channel and
anchorage swing circle) rendered live in the browser and exportable:

| Format | Endpoint | Use |
|--------|----------|-----|
| **DXF** | `POST /api/export.dxf` | open in AutoCAD/QCAD/LibreCAD — 1 unit = 1 m, one layer per feature |
| **SVG** | `POST /api/export.svg` | print / drop into a report |
| **PNG** | client-side | quick share |
| **JSON** | client-side | the full result payload |

Quick-fill **vessel presets** (Neo-Panamax, ULCV, Suezmax, VLCC, Capesize,
Q-Max LNG, Oasis cruise, feeder) are served from `GET /api/presets`.

## Structure

```
backend/
  main.py          FastAPI app + /api/calculate, /api/presets, /api/export.{dxf,svg}
  calculations.py  the dimensioning engine + plan geometry (edit formulas here)
  cad_export.py    geometry -> DXF (ezdxf) and standalone SVG
static/
  index.html       UI
  css/style.css    sci-fi bioluminescent theme
  js/scene.js      procedural port survey backdrop + reactive point-field
  js/plan.js       geometry -> to-scale SVG port plan
  js/app.js        form -> API -> result cells + plan + exports
```

### Custom port photo (optional)
The animated background is fully procedural (no assets). To overlay a real
Suez photo, drop `port.jpg` into `static/img/` and add it as a low-opacity
CSS background on `body` in `style.css`.
