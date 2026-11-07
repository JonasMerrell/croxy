"""Build the CroXY rCAD document from params.yaml.

    python3 cad/build.py [path/to/rcad] [out_dir]

Writes out/CroXY.json (open it in rCAD), STEP of the assembly, renders and a
clearance report that moves the gantry through its travel.
"""
import json, math, os, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rc import RCad

RCAD = sys.argv[1] if len(sys.argv) > 1 else "rcad"
OUT = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "out"))
os.makedirs(OUT, exist_ok=True)
P = yaml.safe_load(open(os.path.join(HERE, "params.yaml")))
F, XY, G, TH = P["frame"], P["xy"], P["gantry"], P["toolhead"]

r = RCad(RCAD, cwd=OUT, log=open(os.path.join(OUT, "build.log"), "w"))
r("new_document", units="mm")

# ---------------------------------------------------------------- helpers
studios = []          # names, index = studio index
first_studio = [True]

def studio(name):
    if first_studio[0]:
        first_studio[0] = False
    else:
        r("new_part_studio", name=name)
    studios.append(name)
    return len(studios) - 1

def plane(z):
    if z == 0:
        return "top"
    f = r("add_feature", kind="plane", name=f"Plane z={z:g}",
          params={"mode": "offset", "base": {"kind": "origin_plane", "plane": "Top"}, "offset": str(z)})
    return {"kind": "feature_plane", "feature": f["feature_id"]}

def sketch(pl, items, name=None):
    s = r("create_sketch", plane=pl, **({"name": name} if name else {}))
    sid = s["sketch_id"]
    r("sketch_add", sketch_id=sid, items=items)
    return sid

def extrude(sid, depth, op="new", name=None, opposite=False, end="blind"):
    params = {"profiles": [{"sketch": sid}], "depth": str(depth), "op": op, "end": end}
    if opposite:
        params["opposite"] = True
    return r("add_feature", kind="extrude", params=params, **({"name": name} if name else {}))

def box(x0, x1, y0, y1, z0, z1, op="new", name=None):
    """Axis-aligned block from z0 up to z1."""
    sid = sketch(plane(z0), [{"type": "rect", "corner1": [x0, y0], "corner2": [x1, y1]}], name)
    return extrude(sid, z1 - z0, op, name)

def cyl(cx, cy, rad, z0, z1, op="new", name=None):
    sid = sketch(plane(z0), [{"type": "circle", "center": [cx, cy], "radius": rad}], name)
    return extrude(sid, z1 - z0, op, name)

def cut_through(items, z_top, name):
    """Cut sketch items straight down through everything below z_top."""
    sid = sketch(plane(z_top), items, name)
    return r("add_feature", kind="extrude", name=name,
             params={"profiles": [{"sketch": sid, "all": True}], "op": "remove", "end": "through_all", "opposite": True})

def new_body(res):
    return [res["feature_id"], 0]

def name_part(body, name, material=None, color=None, finish=None):
    a = {"body": body, "name": name}
    if material: a["material"] = material
    if color: a["color"] = color
    if finish: a["finish"] = finish
    r("set_part", **a)

def rot_z(deg, p):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [round(c * p[0] - s * p[1], 6), round(s * p[0] + c * p[1], 6)]

def mat_to_axis_angle(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    ang = math.degrees(math.acos(max(-1, min(1, (tr - 1) / 2))))
    if abs(ang) < 1e-9:
        return {"axis": [0, 0, 1], "angle": 0}
    if abs(ang - 180) < 1e-6:
        # axis from the diagonal of (M + I) / 2
        xx, yy, zz = [math.sqrt(max(0, (m[i][i] + 1) / 2)) for i in range(3)]
        ax = [xx, yy, zz]
        i = max(range(3), key=lambda k: ax[k])
        for j in range(3):
            if j != i:
                ax[j] = math.copysign(ax[j], m[i][j] + m[j][i])
        return {"axis": ax, "angle": 180}
    s = 2 * math.sin(math.radians(ang))
    ax = [(m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s]
    return {"axis": ax, "angle": ang}

def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def Rz(d):
    c, s = round(math.cos(math.radians(d)), 12), round(math.sin(math.radians(d)), 12)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]

RX180 = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

# ---------------------------------------------------------------- derived layout
# Everything that moves in XY sits ON TOP of the plate, out of the hot chamber. The toolhead
# hangs from the beams down through a central cutout in the plate.
W, T = F["plate_w"], F["plate_t"]
PT = T                                    # plate top face
B, PP, TT = XY["belt_line"], XY["pulley_pos"], XY["tension_travel"]
BZ, BW = XY["belt_z"], XY["belt_w"]
RO, RL = XY["rail_off"], XY["rail_len"]
PC = F["post_center"]
CUT = F["cutout"] / 2
# FL corner of the pinwheel; the other three are this rotated by 90, 180, 270 degrees about Z
D_FL = [-PP, -B]          # X-front belt drive
I_FL = [-B, -PP]          # Y-left belt idler (tension moves it towards -Y)
PUL_Z0, PUL_Z1 = BZ - 8, BZ + 8           # pulley with flanges
BLK_BOT = (PUL_Z0 - 10, PUL_Z0 - 2)       # corner block bottom plate (clears the MGN12 carriages)
BLK_TOP = (PUL_Z1 + 2, PUL_Z1 + 10)       # corner block top plate
BOSS_R = 12.5
SEAT_R = 11.0                             # 608 bearing seat
CARR_FACE = PT + 13                       # MGN12H carriage mounting face (rail on the plate)
BASE_T = 6                                # tower base plate on the carriage
BH, BWD, BT, BL = G["beam_h"], G["beam_w"], G["beam_t"], G["beam_len"]
YB_BOT, XB_BOT = G["y_beam_bot"], G["x_beam_bot"]
YB_TOP, XB_TOP = YB_BOT + BH, XB_BOT + BH
X_CAR_FACE = XB_BOT - 10                  # MGN9H face under the X beam
Y_CAR_FACE = YB_BOT - 10                  # MGN9H face under the Y beam
YOKE_T = 6
TH_TOP = Y_CAR_FACE - YOKE_T              # top of the toolhead, under the yoke
NOZ = TH_TOP - TH["height"]
MOTOR_PLATE = (XB_TOP + 1, XB_TOP + 7)    # motor plate clears the X beam
MOTOR_FACE = MOTOR_PLATE[1]
assert BLK_BOT[0] > CARR_FACE - 10 and TH_TOP > PT + F["shutter_h"], "stack does not fit"

layout = {"drive_FL": D_FL, "idler_FL": I_FL, "pulley_z": [PUL_Z0, PUL_Z1], "belt_z": BZ,
          "x_beam": [XB_BOT, XB_TOP], "y_beam": [YB_BOT, YB_TOP], "motor_face": MOTOR_FACE,
          "toolhead_top": TH_TOP, "nozzle_z": NOZ}

# ================================================================ Part Studios
# ---- 0. Top plate
S_PLATE = studio("Top plate")
r("set_variable", name="plate_w", expr=str(W))
r("set_variable", name="plate_t", expr=str(T))
sid = sketch("top", [{"type": "center_rect", "center": [0, 0], "corner": [W / 2, W / 2],
                      "dims": {"width": "plate_w", "height": "plate_w"}}], "Plate outline")
res = r("add_feature", kind="extrude", name="Plate", params={"profiles": [{"sketch": sid}], "depth": "plate_t", "op": "new"})
plate_body = new_body(res)

holes = [{"type": "rect", "corner1": [-CUT, -CUT], "corner2": [CUT, CUT]}]   # toolhead cutout
for k in range(4):
    a = 90 * k
    for p in ([-155.5, -140], [-140, -155.5], [-125.5, -125.5], [-155.5, -155.5]):    # corner block screws
        holes.append({"type": "circle", "center": rot_z(a, p), "radius": 2.75})
    holes.append({"type": "circle", "center": rot_z(a, [-PC, -PC]), "radius": 4.25})  # corner post bolt
    for n in range(-4, 5):                                                              # MGN12 rail screws, M3 tapped
        holes.append({"type": "circle", "center": rot_z(a, [n * 25, -RO]), "radius": 1.25})
cut_through(holes, T, "Cutout and holes")
name_part(plate_body, "Top plate", "Steel", "#5b6670", "metal")

# ---- 1. Corner pulley block (one design, pinwheeled), standing on the plate
S_BLOCK = studio("Corner pulley block")
x0, x1 = -158.0, -123.0
for zz, nm in ((BLK_BOT, "bottom"), (BLK_TOP, "top")):
    res = box(x0, x1, x0, x1, zz[0], zz[1], "new" if nm == "bottom" else "add", f"Block {nm} plate")
    if nm == "bottom":
        block_body = new_body(res)
    cyl(D_FL[0], D_FL[1], BOSS_R, zz[0], zz[1], "add", f"Drive boss {nm}")
    cyl(I_FL[0], I_FL[1], BOSS_R, zz[0], zz[1], "add", f"Idler boss {nm}")
    cyl(I_FL[0], I_FL[1] - TT, BOSS_R, zz[0], zz[1], "add", f"Idler boss tensioned {nm}")
box(x0, x1, x0, x0 + 5, PT, BLK_TOP[1], "add", "Wall front")
box(x0, x0 + 5, x0, x1, PT, BLK_TOP[1], "add", "Wall left")
box(-128, -123, -128, -123, PT, BLK_TOP[1], "add", "Inner post")
sid = sketch(plane(BLK_TOP[0]), [{"type": "circle", "center": D_FL, "radius": SEAT_R}], "Top bearing seat")
r("add_feature", kind="extrude", name="Top bearing seat", params={"profiles": [{"sketch": sid}], "depth": "7", "op": "remove"})
sid = sketch(plane(BLK_BOT[1]), [{"type": "circle", "center": D_FL, "radius": SEAT_R}], "Bottom bearing seat")
r("add_feature", kind="extrude", name="Bottom bearing seat", params={"profiles": [{"sketch": sid}], "depth": "7", "op": "remove", "opposite": True})
cut_through([{"type": "circle", "center": D_FL, "radius": 5.0},
             {"type": "rect", "corner1": [I_FL[0] - 4.25, I_FL[1] - TT], "corner2": [I_FL[0] + 4.25, I_FL[1]]},
             {"type": "circle", "center": I_FL, "radius": 4.25},
             {"type": "circle", "center": [I_FL[0], I_FL[1] - TT], "radius": 4.25}], BLK_TOP[1], "Shaft and idler slot")
sid = sketch(plane(PT), [{"type": "circle", "center": p, "radius": 2.1} for p in
                         ([-155.5, -140], [-140, -155.5], [-125.5, -125.5], [-155.5, -155.5])], "M5 tapped holes")
r("add_feature", kind="extrude", name="M5 tapped holes", params={"profiles": [{"sketch": sid}], "depth": "12", "op": "remove"})
name_part(block_body, "Corner pulley block", "Steel", "#7a8691", "metal")

# ---- 1b. Motor tower: L-shaped walls on the block's outer edges, motor plate above the X beam
S_MTOWER = studio("Motor tower")
mh = 57.0 / 2
res = box(D_FL[0] - mh, D_FL[0] + mh, D_FL[1] - mh, D_FL[1] + mh, MOTOR_PLATE[0], MOTOR_PLATE[1], "new", "Motor plate")
mtower_body = new_body(res)
box(x0, x0 + 5, x0, x1, BLK_TOP[1], MOTOR_PLATE[0], "add", "Wall left")
box(x0, D_FL[0] + mh, x0, x0 + 5, BLK_TOP[1], MOTOR_PLATE[0], "add", "Wall front")
cut_through([{"type": "circle", "center": D_FL, "radius": 19.3}], MOTOR_PLATE[1], "Pilot bore")
name_part(mtower_body, "Motor tower", "Steel", "#7a8691", "metal")

# ---- 2. X-end tower (local = world for the back end with the X beam at x = 0): stands on the MGN12H,
#         clamps the inner strand of the X belt, carries the X beam on top
S_XEND = studio("X-end tower")
inner = B - XY["pitch_r"]           # inner belt strand, clamped by the tower
res = box(-22.7, 22.7, RO - 13.5, RO + 13.5, CARR_FACE, CARR_FACE + BASE_T, "new", "Base")
xend_body = new_body(res)
box(-17.5, 17.5, RO - 13.5, B + 2, CARR_FACE + BASE_T, XB_BOT, "add", "Upright")
box(-17.5, 17.5, inner - 1.2, inner + 1.2, BZ - BW / 2 - 0.5, BZ + BW / 2 + 0.5, "remove", "Belt clamp slot")
name_part(xend_body, "X-end tower", "Steel", "#8a96a1", "metal")

# ---- 3. Y-end tower (local = world for the right end with the Y beam at y = 0)
S_YEND = studio("Y-end tower")
res = box(RO - 13.5, RO + 13.5, -22.7, 22.7, CARR_FACE, CARR_FACE + BASE_T, "new", "Base")
yend_body = new_body(res)
box(RO - 13.5, B + 2, -17.5, 17.5, CARR_FACE + BASE_T, YB_BOT, "add", "Upright")
box(inner - 1.2, inner + 1.2, -17.5, 17.5, BZ - BW / 2 - 0.5, BZ + BW / 2 + 0.5, "remove", "Belt clamp slot")
name_part(yend_body, "Y-end tower", "Steel", "#8a96a1", "metal")

# ---- 4. Beam backer: bent U channel along X, web at the bottom (z 0..t), flanges up
S_BEAM = studio("Beam backer")
r("set_variable", name="beam_len", expr=str(BL))
sid = sketch("right", [{"type": "polyline", "closed": True, "points": [
    [-BWD / 2, 0], [BWD / 2, 0], [BWD / 2, BH], [BWD / 2 - BT, BH], [BWD / 2 - BT, BT],
    [-BWD / 2 + BT, BT], [-BWD / 2 + BT, BH], [-BWD / 2, BH]]}], "Channel section")
res = r("add_feature", kind="extrude", name="Channel", params={"profiles": [{"sketch": sid}], "depth": "beam_len", "op": "new", "end": "symmetric"})
beam_body = new_body(res)
name_part(beam_body, "Beam backer (U channel)", "Steel", "#6d7a86", "metal")

# ---- 5. Toolhead yoke (carries both MGN9H carriages, wraps the Y beam)
S_YOKE = studio("Toolhead yoke")
yw, ylen = 22.0, 30.0
leg_in, leg_out = BWD / 2 + 3, BWD / 2 + 9
res = box(-yw, yw, -ylen, ylen, X_CAR_FACE - YOKE_T, X_CAR_FACE, "new", "Top plate")
yoke_body = new_body(res)
box(-yw, yw, leg_in, leg_out, Y_CAR_FACE, X_CAR_FACE - YOKE_T, "add", "Back leg")
box(-yw, yw, -leg_out, -leg_in, Y_CAR_FACE, X_CAR_FACE - YOKE_T, "add", "Front leg")
box(-yw, yw, -ylen, ylen, Y_CAR_FACE - YOKE_T, Y_CAR_FACE, "add", "Bottom plate")
name_part(yoke_body, "Toolhead yoke", "Aluminium 7075", "#c0c6cc", "metal")

# ---- 6. Toolhead envelope (Chube Conduction + Sherpa Heavy, stand-in)
S_TOOL = studio("Toolhead envelope")
ex, ey = TH["envelope"]
res = box(-ex / 2, ex / 2, -ey / 2, ey / 2, NOZ + 12, TH_TOP, "new", "Envelope")
tool_body = new_body(res)
cyl(0, 0, 4, NOZ, NOZ + 12, "add", "Nozzle")
name_part(tool_body, "Toolhead envelope (stand-in)", None, "#c4572a", "satin")

# ---- 7. Bought parts (stand-ins), one Part Studio each, modelled in their own frames
buy = {}
def bought(key, res, name, color, material=None):
    b = new_body(res); buy[key] = (len(studios) - 1, b); name_part(b, name, material, color, "satin")

studio("MGN12 rail")
bought("mgn12_rail", box(-RL / 2, RL / 2, -6, 6, 0, 8, "new", "MGN12 rail"), f"MGN12 rail {RL}", "#9aa3ab", "Steel")
studio("MGN12H carriage")
res = box(-22.7, 22.7, -13.5, 13.5, 8.5, 13, "new", "MGN12H block")
box(-22.7, 22.7, -13.5, -6.5, 3, 8.5, "add"); box(-22.7, 22.7, 6.5, 13.5, 3, 8.5, "add")
bought("mgn12h", res, "MGN12H carriage", "#3d4a57", "Steel")
bl9 = G["beam_rail_len"]
studio("MGN9 rail")
bought("mgn9_rail", box(-bl9 / 2, bl9 / 2, -4.5, 4.5, 0, 6.5, "new", "MGN9 rail"), f"MGN9 rail {bl9}", "#9aa3ab", "Steel")
studio("MGN9H carriage")
res = box(-19.95, 19.95, -10, 10, 7, 10, "new", "MGN9H block")
box(-19.95, 19.95, -10, -5, 2, 7, "add"); box(-19.95, 19.95, 5, 10, 2, 7, "add")
bought("mgn9h", res, "MGN9H carriage", "#3d4a57", "Steel")
studio("GT2 pulley 20T")
res = cyl(0, 0, 9, 0, 1.5, "new", "Pulley"); cyl(0, 0, 6.1, 1.5, 14.5, "add"); cyl(0, 0, 9, 14.5, 16, "add")
bought("pulley", res, "GT2 20T pulley, 12 mm belt", "#b8bec4", "Aluminium 6061")
studio("GT2 idler 20T")
res = cyl(0, 0, 9, 0, 1.5, "new", "Idler"); cyl(0, 0, 6.1, 1.5, 14.5, "add"); cyl(0, 0, 9, 14.5, 16, "add")
bought("idler", res, "GT2 20T toothed idler, 12 mm belt", "#b8bec4", "Steel")
# belt loop: pulley centres 2*PP apart along X, pitch radius pr, thickness bt, z = 0..BW
pr, bt = XY["pitch_r"], XY["belt_t"]
def stadium(rad):
    return [{"type": "line", "from": [-PP, -rad], "to": [PP, -rad]},
            {"type": "arc", "center": [PP, 0], "start": [PP, -rad], "end": [PP, rad]},
            {"type": "line", "from": [PP, rad], "to": [-PP, rad]},
            {"type": "arc", "center": [-PP, 0], "start": [-PP, rad], "end": [-PP, -rad]}]
studio("Belt")
sid = sketch("top", stadium(pr + bt / 2) + stadium(pr - bt / 2), "Belt")
res = r("add_feature", kind="extrude", name="Belt", params={"profiles": [{"sketch": sid}], "depth": str(BW), "op": "new"})
bought("belt", res, "Gates EPDM GT2 12 mm belt", "#22262a")
studio("Shaft coupling")
bought("coupling", cyl(0, 0, 12.5, 0, 25, "new", "Coupling"), "Shaft coupling 6.35-8", "#b8bec4", "Aluminium 6061")

# ================================================================ Assembly
A = r("create_assembly", name="CroXY")["assembly"]
inst = []
def place(studio_i, body, pos, R=I3, name=None, fixed=True):
    a = {"assembly": A, "studio": studio_i, "body": body, "position": [round(v, 4) for v in pos], "fixed": fixed}
    aa = mat_to_axis_angle(R)
    if aa["angle"]:
        a["rotate"] = aa
    if name: a["name"] = name
    i = r("assembly_insert", **a)["instance"]
    inst.append({"id": i, "name": name})
    return i

def place_std(standard, size, pos, R=I3, length=None, name=None):
    a = {"assembly": A, "standard": standard, "size": size, "position": [round(v, 4) for v in pos], "fixed": True}
    if length: a["length"] = length
    aa = mat_to_axis_angle(R)
    if aa["angle"]:
        a["rotate"] = aa
    if name: a["name"] = name
    i = r("insert_standard_part", **a)["instance"]
    inst.append({"id": i, "name": name})
    return i

place(S_PLATE, plate_body, [0, 0, 0], name="Top plate")
for k in range(4):
    a = 90 * k
    R = Rz(a)
    corner = ["FL", "FR", "BR", "BL"][k]
    place(S_BLOCK, block_body, [0, 0, 0], R, name=f"Corner block {corner}")
    place(S_MTOWER, mtower_body, [0, 0, 0], R, name=f"Motor tower {corner}")
    d, i_ = rot_z(a, D_FL), rot_z(a, I_FL)
    place(*buy["pulley"], [d[0], d[1], PUL_Z0], name=f"Drive pulley {corner}")
    place(*buy["idler"], [i_[0], i_[1], PUL_Z0], name=f"Idler {corner}")
    shaft_top = MOTOR_FACE - 27
    place_std("Shaft", "Ø8", [d[0], d[1], BLK_BOT[0]], length=round(shaft_top - BLK_BOT[0], 1), name=f"Drive shaft {corner}")
    for zb in (BLK_TOP[0], BLK_BOT[1] - 7):
        place_std("Bearing", "608", [d[0], d[1], zb], name=f"608 {corner}")
    place(*buy["coupling"], [d[0], d[1], MOTOR_PLATE[0] - 25], name=f"Coupling {corner}")
    place_std("NEMA", "NEMA 23", [d[0], d[1], MOTOR_FACE], RX180, length=XY["motor_len"], name=f"NEMA23 {corner}")
    pc = rot_z(a, [-PC, -PC])
    place_std("Extrusion", "3030", [pc[0], pc[1], -F["chamber_h"]], length=F["chamber_h"], name=f"Post {corner}")

# perimeter rails on the plate: X rails along X at y = +-RO, Y rails along Y at x = +-RO
for k, (pos, R) in enumerate([([0, -RO, PT], I3), ([0, RO, PT], I3), ([-RO, 0, PT], Rz(90)), ([RO, 0, PT], Rz(90))]):
    place(*buy["mgn12_rail"], pos, R, name=["X rail front", "X rail back", "Y rail left", "Y rail right"][k])

# belts: X belts along X at y = +-B, Y belts along Y at x = +-B
for nm, pos, R in [("X belt front", [0, -B, BZ - BW / 2], I3), ("X belt back", [0, B, BZ - BW / 2], I3),
                   ("Y belt left", [-B, 0, BZ - BW / 2], Rz(90)), ("Y belt right", [B, 0, BZ - BW / 2], Rz(90))]:
    place(*buy["belt"], pos, R, name=nm)

# moving gantry at (tx, ty): (key, studio/body, position fn, rotation, name)
def gantry_parts():
    g = []
    for sgn, nm in ((1, "back"), (-1, "front")):
        R = I3 if sgn > 0 else Rz(180)
        g.append((f"xcar_{nm}", buy["mgn12h"], lambda tx, ty, s=sgn: [tx, s * RO, PT], I3, f"MGN12H X {nm}"))
        g.append((f"xend_{nm}", (S_XEND, xend_body), lambda tx, ty: [tx, 0, 0], R, f"X-end tower {nm}"))
    for sgn, nm in ((1, "right"), (-1, "left")):
        R = I3 if sgn > 0 else Rz(180)
        g.append((f"ycar_{nm}", buy["mgn12h"], lambda tx, ty, s=sgn: [s * RO, ty, PT], Rz(90), f"MGN12H Y {nm}"))
        g.append((f"yend_{nm}", (S_YEND, yend_body), lambda tx, ty: [0, ty, 0], R, f"Y-end tower {nm}"))
    g += [("xbeam", (S_BEAM, beam_body), lambda tx, ty: [tx, 0, XB_BOT], Rz(90), "X beam"),
          ("xrail", buy["mgn9_rail"], lambda tx, ty: [tx, 0, XB_BOT], mm(Rz(90), RX180), "MGN9 rail X beam"),
          ("ybeam", (S_BEAM, beam_body), lambda tx, ty: [0, ty, YB_BOT], I3, "Y beam"),
          ("yrail", buy["mgn9_rail"], lambda tx, ty: [0, ty, YB_BOT], RX180, "MGN9 rail Y beam"),
          ("xcar9", buy["mgn9h"], lambda tx, ty: [tx, ty, XB_BOT], mm(Rz(90), RX180), "MGN9H on X beam"),
          ("ycar9", buy["mgn9h"], lambda tx, ty: [tx, ty, YB_BOT], RX180, "MGN9H on Y beam"),
          ("yoke", (S_YOKE, yoke_body), lambda tx, ty: [tx, ty, 0], I3, "Toolhead yoke"),
          ("tool", (S_TOOL, tool_body), lambda tx, ty: [tx, ty, 0], I3, "Toolhead envelope")]
    return g

GP = gantry_parts()
TX0, TY0 = 40, -30
moving = {k: place(st, bd, f(TX0, TY0), R, name=nm) for k, (st, bd), f, R, nm in GP}

def pose(tx, ty):
    for k, _, f, _, _ in GP:
        r("assembly_move", assembly=A, instance=moving[k], position=[round(v, 4) for v in f(tx, ty)])

# stand-in pairs that overlap on purpose (no bores in the stand-ins, belt on the pulley pitch line)
EXPECTED = ("Drive pulley", "Idler", "Drive shaft", "Coupling", "NEMA23", "608", "belt")
def unexpected(info):
    names = {i["id"]: i["name"] for i in info["instances"]}
    bad = []
    for x in info["interference"]:
        na, nb = names[x["a"]], names[x["b"]]
        if any(e in na for e in EXPECTED) and any(e in nb for e in EXPECTED):
            continue
        bad.append([na, nb, round(x["volume_mm3"], 2)])
    return bad

T_ = G["travel"]
sweep = []
for tx, ty in [(0, 0), (-T_, -T_), (T_, -T_), (T_, T_), (-T_, T_), (-T_, 0), (T_, 0), (0, -T_), (0, T_)]:
    pose(tx, ty)
    bad = unexpected(r("assembly_info", assembly=A, interference=True))
    sweep.append({"pose": [tx, ty], "clashes": bad})
pose(TX0, TY0)
json.dump(sweep, open(os.path.join(OUT, "clearance-sweep.json"), "w"), indent=1)

r("save_document", path="CroXY.json")
# rename the first Part Studio (scripts cannot name it)
doc = json.load(open(os.path.join(OUT, "CroXY.json")))
doc["studios"][0]["name"] = studios[0]
json.dump(doc, open(os.path.join(OUT, "CroXY.json"), "w"), indent=1)

json.dump({"studios": studios, "layout": layout, "moving": moving, "start": [TX0, TY0], "sweep": sweep},
          open(os.path.join(OUT, "build-info.json"), "w"), indent=1)

for view in ("iso_front_left", "top", "front"):
    r("render_assembly", assembly=A, view=view, width=1400, height=1050, path=f"render-{view}.png")
# the gantry from below, close up
r("render_assembly", assembly=A, view="iso_front_left", width=1400, height=1050,
  fit_box=[[-W / 2, -W / 2, NOZ - 5], [W / 2, W / 2, MOTOR_FACE + 80]], path="render-gantry.png")
r("render_assembly", assembly=A, view="iso_front_left_below", width=1400, height=1050,
  fit_box=[[-W / 2, -W / 2, NOZ - 5], [W / 2, W / 2, 0]], path="render-below.png")
r("export", format="step", assembly=A, path="CroXY-xy.step")
info = r("assembly_info", assembly=A, interference=True)
json.dump(info, open(os.path.join(OUT, "assembly-info.json"), "w"), indent=1)
r.close()
print("ok", len(inst), "instances")
