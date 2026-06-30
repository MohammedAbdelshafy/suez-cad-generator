"""
Batch-generate port-plan outputs for every built-in vessel preset.

Writes <preset>.dxf, <preset>.svg and <preset>.json into data/output/.
Run:  .venv\\Scripts\\python.exe backend\\generate_outputs.py
"""

from __future__ import annotations

import json
from pathlib import Path

from calculations import compute, VesselInput, VESSEL_PRESETS
from cad_export import geometry_to_dxf, geometry_to_svg

OUT = Path(__file__).resolve().parent.parent / "data" / "output"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for key, preset in VESSEL_PRESETS.items():
        fields = {k: v for k, v in preset.items() if k != "label"}
        payload = compute(VesselInput(**fields))

        (OUT / f"{key}.dxf").write_text(geometry_to_dxf(payload), encoding="utf-8")
        (OUT / f"{key}.svg").write_text(geometry_to_svg(payload), encoding="utf-8")
        (OUT / f"{key}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        made.append((preset["label"], key))

    print(f"Wrote {len(made) * 3} files for {len(made)} presets to {OUT}")
    for label, key in made:
        print(f"  - {key:14} {label}")


if __name__ == "__main__":
    main()
