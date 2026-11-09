"""Render close-ups from a saved build without rebuilding.

    python3 cad/closeup.py path/to/rcad out name x0 y0 z0 x1 y1 z1 [view] [hide-substring ...]

Opens out/CroXY.json, optionally hides instances whose name contains any hide-substring,
and writes out/render-<name>.png framed on the box.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rc import RCad

exe, out, name = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]
box = [float(v) for v in sys.argv[4:10]]
view = sys.argv[10] if len(sys.argv) > 10 else "iso_front_left"
hide = sys.argv[11:]
r = RCad(exe, cwd=out)
r("open_document", path="CroXY.json")
info = r("assembly_info", assembly=0)
for i in info["instances"]:
    if any(h in (i["name"] or "") for h in hide):
        r("assembly_move", assembly=0, instance=i["id"], hidden=True)
r("render_assembly", assembly=0, view=view, width=1400, height=1050,
  fit_box=[box[:3], box[3:]], path=f"render-{name}.png")
r.close() if hasattr(r, "close") else None
print("wrote", f"render-{name}.png")
