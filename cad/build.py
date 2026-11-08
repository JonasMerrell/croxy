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
SH, Z, BD = P["shell"], P["z"], P["bed"]

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
TH_TOP = TH["body_top"]                   # toolhead body hangs below the plate
NECK_TOP = Y_CAR_FACE - YOKE_T            # underside of the yoke
FX, FY = TH["offset"]                     # nozzle / filament axis relative to the beam cross
NOZ = TH_TOP - TH["height"]
MOTOR_PLATE = (XB_TOP + 1, XB_TOP + 7)    # motor plate clears the X beam
MOTOR_FACE = MOTOR_PLATE[1]
assert BLK_BOT[0] > CARR_FACE - 10 and NECK_TOP > PT + F["shutter_h"] and TH_TOP < 0, "stack does not fit"

layout = {"drive_FL": D_FL, "idler_FL": I_FL, "pulley_z": [PUL_Z0, PUL_Z1], "belt_z": BZ,
          "x_beam": [XB_BOT, XB_TOP], "y_beam": [YB_BOT, YB_TOP], "motor_face": MOTOR_FACE,
          "toolhead_top": TH_TOP, "nozzle_z": NOZ, "nozzle_offset": [FX, FY],
          "build_centre": [FX, FY]}

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
for sy in (-1, 1):   # pockets for the shutter's Y-cover spring rollers, just outside the cutout edges
    box(-(CUT - 2), CUT - 2, min(sy * (CUT + 1), sy * (CUT + 11)), max(sy * (CUT + 1), sy * (CUT + 11)), 2, T, "remove", "Roller pocket")
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
name_part(xend_body, "X-end tower", "Aluminium 7075", "#c0c6cc", "metal")

# ---- 3. Y-end tower (local = world for the right end with the Y beam at y = 0)
S_YEND = studio("Y-end tower")
res = box(RO - 13.5, RO + 13.5, -22.7, 22.7, CARR_FACE, CARR_FACE + BASE_T, "new", "Base")
yend_body = new_body(res)
box(RO - 13.5, B + 2, -17.5, 17.5, CARR_FACE + BASE_T, YB_BOT, "add", "Upright")
box(inner - 1.2, inner + 1.2, -17.5, 17.5, BZ - BW / 2 - 0.5, BZ + BW / 2 + 0.5, "remove", "Belt clamp slot")
name_part(yend_body, "Y-end tower", "Aluminium 7075", "#c0c6cc", "metal")

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
yw, ylen = 22.0, BWD / 2 + 9
leg_in, leg_out = BWD / 2 + 3, BWD / 2 + 9
res = box(-yw, yw, -ylen, ylen, X_CAR_FACE - YOKE_T, X_CAR_FACE, "new", "Top plate")
yoke_body = new_body(res)
box(-yw, yw, leg_in, leg_out, Y_CAR_FACE, X_CAR_FACE - YOKE_T, "add", "Back leg")
box(-yw, yw, -leg_out, -leg_in, Y_CAR_FACE, X_CAR_FACE - YOKE_T, "add", "Front leg")
box(-yw, yw, -ylen, ylen, Y_CAR_FACE - YOKE_T, Y_CAR_FACE, "add", "Bottom plate")
name_part(yoke_body, "Toolhead yoke", "Aluminium 7075", "#c0c6cc", "metal")

# ---- 6. Toolhead neck (yoke down through the cutout) and envelope (Chube Conduction + Sherpa Heavy, stand-in)
S_NECK = studio("Toolhead neck")
nx, ny = TH["neck"]
res = box(-nx / 2, nx / 2, -ny / 2, ny / 2, TH_TOP, NECK_TOP, "new", "Neck")
neck_body = new_body(res)
box(-nx / 2 + 4, nx / 2 - 4, -ny / 2 + 4, ny / 2 - 4, TH_TOP, NECK_TOP, "remove", "Lightening")
name_part(neck_body, "Toolhead neck", "Aluminium 7075", "#c0c6cc", "metal")

S_TOOL = studio("Toolhead envelope")
ex, ey = TH["envelope"]
res = box(FX - ex / 2, FX + ex / 2, FY - ey / 2, FY + ey / 2, NOZ + 12, TH_TOP, "new", "Envelope")
tool_body = new_body(res)
cyl(FX, FY, 4, NOZ, NOZ + 12, "add", "Nozzle")
name_part(tool_body, "Toolhead envelope (stand-in)", None, "#c4572a", "satin")

S_TUBE = studio("Filament tube")
res = cyl(FX, FY, 2, TH_TOP, TH["filament_top"], "new", "PTFE tube")
tube_body = new_body(res)
name_part(tube_body, "PTFE filament tube 4 mm", None, "#e8e4d8", "satin")

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


# ================================================================ Frame, Z and bed
CH = F["chamber_h"]
SPI = PC - 15                       # inner face of the posts
SPF = SPI - SH["shear_t"]           # inner face of the shear plates
FLOOR = (-CH - SH["floor_t"], -CH)
EN, SHU, HT, BM = P["enclosure"], P["shutter"], P["heater"], P["back_module"]
HL, PIR, SK = EN["hot_layer"], EN["pir"], EN["skin"]
WT = HL + PIR + SK                   # wall build-up outside the frame
OW = W / 2 + WT                      # outer half width
FI = (FLOOR[0] - HL - PIR, FLOOR[0])  # floor insulation under the floor plate
BAY = (FI[0] - EN["bay_h"], FI[0])    # cool bay
BASE = (BAY[0] - EN["base_t"], BAY[0])
LID = EN["lid_z"]
BX, BY = FX, FY                      # build / bed centre (the toolhead's nozzle offset)
Z_TOP = NOZ - 0.5                    # bed top at Z = 0 (just under the nozzle)
Z_BOT = NOZ - P["build"]["z"]        # bed top at Z = 180
RAILV = [[0, 0, 1], [0, -1, 0], [1, 0, 0]]     # part X -> world Z, part Z -> inward (column frame X)
RY90 = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]      # part Z -> column X
# the three Z columns: origin on the shear plate face, column X points into the chamber
COLS = [("Z1", [-SPF, Z["z12_y"], 0], Rz(0)), ("Z2", [SPF, Z["z12_y"], 0], Rz(180)), ("Z3", [Z["z3_x"], SPF, 0], Rz(-90))]
def col_world(col, p):
    _, o, Rc = col
    return [o[i] + sum(Rc[i][k] * p[k] for k in range(3)) for i in range(3)]
# where each arm meets the bed, in the column frame (distance from the plate face)
hb = BD["size"] / 2
ARM_REACH = {k: round(SPF - v, 3) for k, v in {"Z1": abs(BX - hb) - BD["arm_inset"],
                                               "Z2": (BX + hb) - BD["arm_inset"],
                                               "Z3": (BY + hb) - BD["arm_inset"]}.items()}

S_SIDE = studio("Side shear plate")
res = box(-SPI, -SPF, -SPI, SPI, -CH, 0, "new", "Plate")
side_body = new_body(res)
name_part(side_body, "Side shear plate", "Steel", "#58626b", "metal")

S_BACK = studio("Back shear plate")
res = box(-SPF, SPF, SPF, SPI, -CH, 0, "new", "Plate")
back_body = new_body(res)
name_part(back_body, "Back shear plate", "Steel", "#58626b", "metal")

S_FLOOR = studio("Floor plate")
res = box(-W / 2, W / 2, -W / 2, W / 2, FLOOR[0], FLOOR[1], "new", "Plate")
floor_body = new_body(res)
slots = []
for col in COLS:
    a = col_world(col, [Z["belt_x"] - 10, Z["belt_offset"] - 15, 0]); b = col_world(col, [Z["belt_x"] + 10, Z["belt_offset"] + 15, 0])
    slots.append({"type": "rect", "corner1": a[:2], "corner2": b[:2]})
cut_through(slots, FLOOR[1], "Z belt slots")
name_part(floor_body, "Floor plate", "Steel", "#58626b", "metal")

zc_span = Z["idler_z"] - Z["motor_z"]
S_ZBELT = studio("Z belt")
def stadium_z(rad, h):
    return [{"type": "line", "from": [-h, -rad], "to": [h, -rad]},
            {"type": "arc", "center": [h, 0], "start": [h, -rad], "end": [h, rad]},
            {"type": "line", "from": [h, rad], "to": [-h, rad]},
            {"type": "arc", "center": [-h, 0], "start": [-h, rad], "end": [-h, -rad]}]
sid = sketch("top", stadium_z(XY["pitch_r"] + XY["belt_t"] / 2, zc_span / 2) + stadium_z(XY["pitch_r"] - XY["belt_t"] / 2, zc_span / 2), "Z belt")
res = r("add_feature", kind="extrude", name="Z belt", params={"profiles": [{"sketch": sid}], "depth": str(BW), "op": "new"})
zbelt_body = new_body(res)
name_part(zbelt_body, "Gates EPDM GT2 12 mm Z belt", None, "#22262a", "satin")

# Z drive with a 1:3 belt reduction, in the column frame: the jackshaft J carries the 20T Z drive
# pulley inboard and a 60T pulley outboard; the NEMA17 sits inboard of the mount at J + (0, C, 0)
# and drives the 60T with a 20T through a closed 6 mm GT2 loop.
mz = Z["motor_z"]
RD = Z["reduction"]
R60, R20 = RD["big_t"] * 2 / (2 * math.pi), RD["small_t"] * 2 / (2 * math.pi)
JY, MY = Z["belt_offset"], Z["belt_offset"] + RD["centre"]
RX0 = -6 - 10 - 8                     # outboard face of the reduction pulleys (plate 6, bearing boss 10, pulley 8)
S_ZMOUNT = studio("Z motor mount")
res = box(-6, 0, JY - 21, MY + 21, mz - 21, FI[0], "new", "Plate")
zmount_body = new_body(res)
box(-16, -6, JY - 14, JY + 14, mz - 14, mz + 14, "add", "Bearing boss")   # two 608s for the jackshaft
name_part(zmount_body, "Z motor mount (motor holes slotted for reduction belt tension)", "Steel", "#7a8691", "metal")

S_P60 = studio("GT2 pulley 60T 6 mm")
res = cyl(0, 0, R60 + 1.4, 0, 0.75, "new", "Flange"); cyl(0, 0, R60 - 0.4, 0.75, 7.25, "add"); cyl(0, 0, R60 + 1.4, 7.25, 8, "add")
p60_body = new_body(res); name_part(p60_body, f"GT2 {RD['big_t']}T pulley, 6 mm belt, 8 mm bore", "Aluminium 6061", "#b8bec4", "satin")
S_P20 = studio("GT2 pulley 20T 6 mm")
res = cyl(0, 0, 8, 0, 0.75, "new", "Flange"); cyl(0, 0, R20 - 0.4, 0.75, 7.25, "add"); cyl(0, 0, 8, 7.25, 8, "add")
p20_body = new_body(res); name_part(p20_body, f"GT2 {RD['small_t']}T pulley, 6 mm belt, 5 mm bore", "Aluminium 6061", "#b8bec4", "satin")

# open belt around two pulleys of different radius: big at the origin, small at (C, 0)
def open_belt(Rb, rs, C):
    a = math.acos((Rb - rs) / C)
    pt = lambda cx, rr, ang: [cx + rr * math.cos(ang), rr * math.sin(ang)]
    return [{"type": "line", "from": pt(0, Rb, a), "to": pt(C, rs, a)},
            {"type": "arc", "center": [C, 0], "start": pt(C, rs, -a), "end": pt(C, rs, a)},
            {"type": "line", "from": pt(C, rs, -a), "to": pt(0, Rb, -a)},
            {"type": "arc", "center": [0, 0], "start": pt(0, Rb, a), "end": pt(0, Rb, -a)}]
S_RBELT = studio("Z reduction belt")
sid = sketch("top", open_belt(R60 + bt / 2, R20 + bt / 2, RD["centre"]) + open_belt(R60 - bt / 2, R20 - bt / 2, RD["centre"]), "Belt")
res = r("add_feature", kind="extrude", name="Belt", params={"profiles": [{"sketch": sid}], "depth": "6", "op": "new"})
rbelt_body = new_body(res); name_part(rbelt_body, f"GT2 6 mm closed loop {RD['loop']}", None, "#22262a", "satin")

S_MIC6 = studio("Bed")
res = box(BX - hb, BX + hb, BY - hb, BY + hb, -BD["t"], 0, "new", "MIC6")
bed_body = new_body(res)
name_part(bed_body, "Bed, MIC6 200 x 200 x 8", "Aluminium 6061", "#b9c0c6", "metal")
S_HEATER = studio("Bed heater")
res = box(BX - hb + 5, BX + hb - 5, BY - hb + 5, BY + hb - 5, -BD["t"] - BD["heater_t"], -BD["t"], "new", "Heater")
heater_body = new_body(res)
name_part(heater_body, "Silicone bed heater", None, "#b5482b", "matte")

# bed arms, one Part Studio each, in their column's frame with the bed top at z = 0
arm_s = {}
aw = BD["arm"]
zd = Z["carriage_drop"]
under = -BD["t"] - BD["heater_t"]
for nm, _, _ in COLS:
    st = studio(f"Bed arm {nm}")
    L = ARM_REACH[nm]
    res = box(13, 19, -13.5, 13.5, -zd - 22.7, -zd + 22.7, "new", "Carriage plate")
    b = new_body(res)
    box(19, L + aw / 2, -aw / 2, aw / 2, under - aw, under, "add", "Arm")
    # belt clamp tab reaching the inner strand
    yb = Z["belt_offset"] + XY["pitch_r"]
    res2 = box(Z["belt_x"] - 8, 19, yb - 4.5, -13.5, -zd - 10, -zd + 10, "add", "Belt clamp")
    name_part(b, f"Bed arm {nm}", "Steel", "#8a96a1", "metal")
    arm_s[nm] = (st, b)

# ================================================================ Enclosure, shutter, heater, back module, toolhead detail
def plane_y(y):
    """Sketch plane at world y; sketch (u, v) = (x, z); a positive extrude goes towards -y."""
    f = r("add_feature", kind="plane", name=f"Plane y={y:g}",
          params={"mode": "offset", "base": {"kind": "origin_plane", "plane": "Front"}, "offset": str(-y)})
    return {"kind": "feature_plane", "feature": f["feature_id"]}

def plane_x(x):
    """Sketch plane at world x; sketch (u, v) = (y, z); a positive extrude goes towards +x."""
    f = r("add_feature", kind="plane", name=f"Plane x={x:g}",
          params={"mode": "offset", "base": {"kind": "origin_plane", "plane": "Right"}, "offset": str(x)})
    return {"kind": "feature_plane", "feature": f["feature_id"]}

def cyl_y(cx, cz, rad, y0, y1, op="new", name=None):
    sid = sketch(plane_y(y1), [{"type": "circle", "center": [cx, cz], "radius": rad}], name)
    return extrude(sid, y1 - y0, op, name)

def cyl_x(cy, cz, rad, x0, x1, op="new", name=None):
    sid = sketch(plane_x(x0), [{"type": "circle", "center": [cy, cz], "radius": rad}], name)
    return extrude(sid, x1 - x0, op, name)

def rect_world(col, a, b):
    pa, pb = col_world(col, a), col_world(col, b)
    return {"type": "rect", "corner1": pa[:2], "corner2": pb[:2]}

# holes through the floor insulation: G10 supports, Z hangers, Z belt slots, heater shaft
SUP = EN["support"]
SUP_C = W / 2 - SUP / 2 - 3
HSX, HSY = (HT["x"][0] + HT["x"][1]) / 2, (HT["y"][0] + HT["y"][1]) / 2
floor_holes = [{"type": "rect", "corner1": [sx * SUP_C - SUP / 2, sy * SUP_C - SUP / 2],
                "corner2": [sx * SUP_C + SUP / 2, sy * SUP_C + SUP / 2]} for sx in (-1, 1) for sy in (-1, 1)]
floor_holes += [rect_world(col, [-6, JY - 21, 0], [0, MY + 21, 0]) for col in COLS]
floor_holes += slots
floor_holes.append({"type": "circle", "center": [HSX, HSY], "radius": 6})

# ---- hot-face layer: walls (left, back, right) and floor, one body
S_HOT = studio("Hot-face insulation")
res = box(-W / 2 - HL, -W / 2, -W / 2, W / 2, FI[0], PT, "new", "Left")
hot_body = new_body(res)
box(-W / 2 - HL, W / 2 + HL, W / 2, W / 2 + HL, FI[0], PT, "add", "Back")
box(W / 2, W / 2 + HL, -W / 2, W / 2, FI[0], PT, "add", "Right")
box(-W / 2, W / 2, -W / 2, W / 2, FLOOR[0] - HL, FLOOR[0], "add", "Floor")
cut_through(floor_holes, FLOOR[0], "Floor pass-throughs")
name_part(hot_body, f"Hot-face insulation {HL} mm (aerogel blanket / mineral wool board)", None, "#d9d2bf", "matte")

# ---- PIR board: walls and floor
S_PIR = studio("PIR insulation")
o = W / 2 + HL
res = box(-o - PIR, -o, -W / 2, o + PIR, FI[0], PT, "new", "Left")
pir_body = new_body(res)
box(-o, o, o, o + PIR, FI[0], PT, "add", "Back")
box(o, o + PIR, -W / 2, o + PIR, FI[0], PT, "add", "Right")
res = box(-W / 2, W / 2, -W / 2, W / 2, FI[0], FLOOR[0] - HL, "new", "Floor")
pirf_body = new_body(res)
cut_through(floor_holes, FLOOR[0] - HL, "Floor pass-throughs")
name_part(pir_body, f"PIR insulation walls {PIR} mm", None, "#e2c75a", "matte")
name_part(pirf_body, f"PIR insulation floor {PIR} mm", None, "#e2c75a", "matte")

# ---- outer skin: sides, back, front above and below the door, lid
S_SKIN = studio("Outer skin")
res = box(-OW, -OW + SK, -OW, OW, BAY[0], LID, "new", "Left")
skin_body = new_body(res)
box(-OW + SK, OW - SK, OW - SK, OW, BAY[0], LID, "add", "Back")
box(OW - SK, OW, -OW, OW, BAY[0], LID, "add", "Right")
box(-OW + SK, OW - SK, -OW, -OW + SK, PT, LID, "add", "Front top")
box(-OW + SK, OW - SK, -OW, -OW + SK, BAY[0], FI[0], "add", "Front bay")
box(-OW, OW, -OW, OW, LID, LID + SK, "add", "Lid")
name_part(skin_body, "Outer skin (aluminium sheet, powder coated)", "Aluminium 6061", "#56636f", "satin")

S_BASE = studio("Base plate")
res = box(-OW, OW, -OW, OW, BASE[0], BASE[1], "new", "Base")
base_body = new_body(res)
for sx in (-1, 1):
    for sy in (-1, 1):
        cyl(sx * (OW - 30), sy * (OW - 30), 15, BASE[0] - EN["feet_h"], BASE[0], "add", "Foot")
name_part(base_body, "Base plate with feet", "Aluminium 6061", "#3a434c", "satin")

S_SUP = studio("Floor support block")
res = box(-SUP / 2, SUP / 2, -SUP / 2, SUP / 2, FI[0], FLOOR[0], "new", "Block")
sup_body = new_body(res)
name_part(sup_body, "Floor support block (G10, thermal break)", None, "#c9c27a", "satin")

S_ZHANG = studio("Z mount hanger")
res = box(-6, 0, JY - 21, MY + 21, FI[0], FLOOR[0], "new", "Hanger")
zhang_body = new_body(res)
name_part(zhang_body, "Z mount hanger (G10, thermal break)", None, "#c9c27a", "satin")

# ---- door: built flat (local x across, local y = world z, local z = thickness outwards)
DW = OW - SK
S_DOOR = studio("Door")
res = box(-DW, DW, FI[0], PT, 0, WT, "new", "Door")
door_body = new_body(res)
win = EN["window"]
wx0, wx1 = BX - win["w"] / 2, BX + win["w"] / 2
wz0, wz1 = win["cz"] - win["h"] / 2, win["cz"] + win["h"] / 2
cut_through([{"type": "rect", "corner1": [wx0, wz0], "corner2": [wx1, wz1]}], WT, "Window")
name_part(door_body, "Front door (insulated: hot layer + PIR + skins)", None, "#4b5865", "satin")
S_GLASS = studio("Door glass")
gt = EN["glass_t"]
res = box(wx0, wx1, wz0, wz1, 3, 3 + gt, "new", "Inner pane")
glass_in = new_body(res)
res = box(wx0, wx1, wz0, wz1, WT - 3 - gt, WT - 3, "new", "Outer pane")
glass_out = new_body(res)
name_part(glass_in, "Door glass, inner (borosilicate)", None, "#9fc3d6", "glass")
name_part(glass_out, "Door glass, outer (tempered)", None, "#9fc3d6", "glass")
S_HW = studio("Door hardware")
res = cyl(-DW + 6, -OW - 6, 6, FI[0] + 40, FI[0] + 100, "new", "Hinge low")
hinge_lo = new_body(res)
res = cyl(-DW + 6, -OW - 6, 6, PT - 100, PT - 40, "new", "Hinge high")
hinge_hi = new_body(res)
res = box(DW - 40, DW - 25, -OW - 30, -OW - 22, -230, -110, "new", "Handle bar")
handle_body = new_body(res)
box(DW - 40, DW - 25, -OW - 22, -OW, -230, -220, "add", "Handle foot low")
box(DW - 40, DW - 25, -OW - 22, -OW, -120, -110, "add", "Handle foot high")
for b_, n_ in ((hinge_lo, "Door hinge, lower"), (hinge_hi, "Door hinge, upper")):
    name_part(b_, n_, "Stainless steel", "#a7adb3", "metal")
name_part(handle_body, "Door handle and latch", "Stainless steel", "#a7adb3", "metal")

# ---- shutter over the cutout
ST = SHU["strip_t"]
SZ0 = PT + 0.5
SXE = CUT + 4                          # strip ends overlap the plate by 4 mm and slide on PTFE pads
S_STRIP = studio("Shutter strip")
SB0, SB1 = -(ny / 2 + 6.5), FY + 7.5          # band around the neck and the filament tube
res = box(-SXE, SXE, SB0, SB1, SZ0, SZ0 + ST, "new", "Strip")
strip_body = new_body(res)
cut_through([{"type": "rect", "corner1": [-(G["travel"] + nx / 2 + 2), -(ny / 2 + 1.5)],
              "corner2": [G["travel"] + nx / 2 + 2, FY + 3.5]}], SZ0 + ST, "Neck and tube slot")
rr = SHU["roller_r"]
for sx in (-1, 1):
    sid = sketch(plane_y(SB1 - 2), [{"type": "circle", "center": [sx * (CUT - rr), SZ0 + ST + rr], "radius": rr}], "X cover roller")
    extrude(sid, SB1 - SB0 - 4, "add", "X cover roller")
name_part(strip_body, "Shutter strip with X-cover spring rollers (moves in Y)", None, "#8c6f4e", "satin")
S_NPLATE = studio("Shutter neck plate")
res = box(-nx / 2 - 2, nx / 2 + 2, -ny / 2 - 6, FY + 6, SZ0 + ST + 0.5, SZ0 + ST + 2, "new", "Plate")
nplate_body = new_body(res)
box(-nx / 2, nx / 2, -ny / 2, ny / 2, SZ0 + ST + 0.5, SZ0 + ST + 2, "remove", "Neck hole")
cyl(FX, FY, 3, SZ0 + ST + 0.5, SZ0 + ST + 2, "remove", "Filament tube hole")
name_part(nplate_body, "Shutter neck plate (X covers attach here)", "Aluminium 6061", "#c0c6cc", "metal")
S_YROLL = studio("Shutter Y roller")
yr = SHU["y_roller_r"]
res = cyl_x(0, 7, yr, -(CUT - 3), CUT - 3, "new", "Roller")
yroll_body = new_body(res)
name_part(yroll_body, "Y-cover spring roller, stainless tape (in a plate pocket)", None, "#8c6f4e", "satin")
YROLL_Y = CUT + 6

# ---- chamber heater: PTC block + blower on the floor, motor in the cool bay
S_HEAT = studio("Chamber heater")
res = box(HT["x"][0], HT["x"][1], HT["y"][0], HT["y"][1], FLOOR[1], HT["top"], "new", "Housing")
cheat_body = new_body(res)
name_part(cheat_body, f"Chamber heater: 2 x PTC, {HT['power_w']} W + blower wheel (stand-in)", None, "#8d8f91", "metal")
S_HMOT = studio("Heater fan motor")
res = box(HSX - 25, HSX + 25, HSY - 25, HSY + 25, BAY[0] + 8, BAY[0] + 48, "new", "Motor")
hmot_body = new_body(res)
name_part(hmot_body, "Heater blower motor (BLDC, in the cool bay)", None, "#2b2b2b", "satin")

# ---- back module: filter loop above, electronics below, rear covers
BY0, BY1 = OW, OW + BM["depth"]
SPL = BM["split_z"]
S_BMOD = studio("Back module housing")
res = box(-OW, OW, BY0, BY1, BAY[0], PT, "new", "Housing")
bmod_body = new_body(res)
box(-OW + 2, OW - 2, BY0, BY1, BAY[0] + 2, PT - 2, "remove", "Inside")
box(-OW + 2, OW - 2, BY0, BY1, SPL - 1, SPL + 1, "add", "Divider")
name_part(bmod_body, "Back module housing", "Aluminium 6061", "#56636f", "satin")
S_BCOV = studio("Back module covers")
res = box(-OW, OW, BY1, BY1 + 2, SPL, PT, "new", "Upper cover")
bcov_up = new_body(res)
res = box(-OW, OW, BY1, BY1 + 2, BAY[0], SPL - 0.5, "new", "Lower cover")
bcov_lo = new_body(res)
name_part(bcov_up, "Filter bay cover (filter change)", "Aluminium 6061", "#66737f", "satin")
name_part(bcov_lo, "Electronics bay cover (hinged)", "Aluminium 6061", "#66737f", "satin")

FZ = (SPL + 15, PT - 20)              # filter parts height
S_FILT = studio("Filter loop")
fparts = []
for x0_, x1_, y0_, y1_, nm_, col_ in ((-175, -65, BY0 + 6, BY1 - 6, "Air-to-air cooler (finned, ambient side vented)", "#9aa3ab"),
                                      (-60, -20, BY0 + 10, BY1 - 10, "HEPA H13 filter", "#e9e6dc"),
                                      (-15, 65, BY0 + 10, BY1 - 10, "Activated carbon filter", "#3b3b3b"),
                                      (80, 180, BY0 + 8, BY0 + 42, "Filter loop blower (radial 97 mm)", "#2b2b2b")):
    res = box(x0_, x1_, y0_, y1_, FZ[0], FZ[1], "new", nm_)
    b_ = new_body(res); name_part(b_, nm_, None, col_, "satin"); fparts.append((b_, nm_))
DUCT_Z = -45
S_DUCT = studio("Filter ducts")
res = cyl_y(-120, DUCT_Z, 20, SPF, BY0 + 6, "new", "Outlet")
duct_out = new_body(res)
res = cyl_y(130, DUCT_Z, 20, SPF, BY0 + 8, "new", "Return")
duct_ret = new_body(res)
cyl_y(-120, DUCT_Z, 18.5, SPF, BY0 + 6, "remove", "Outlet bore")
cyl_y(130, DUCT_Z, 18.5, SPF, BY0 + 8, "remove", "Return bore")
name_part(duct_out, "Filter duct, chamber outlet (stainless)", "Stainless steel", "#a7adb3", "metal")
name_part(duct_ret, "Filter duct, chamber return (stainless)", "Stainless steel", "#a7adb3", "metal")

EZ = (BAY[0] + 10, SPL - 10)
S_ELEC = studio("Electronics")
eparts = []
for x0_, x1_, y0_, y1_, z0_, z1_, nm_, col_ in (
        (-200, -40, BY0 + 6, BY0 + 26, -330, -230, "BTT Kraken (on standoffs)", "#1d5c3a"),
        (-20, 195, BY0 + 6, BY0 + 36, -300, -185, "PSU 48 V (LRS-350-48 class)", "#a7adb3"),
        (-20, 195, BY0 + 6, BY0 + 36, -420, -320, "PSU 24 V (LRS-350-24 class)", "#a7adb3"),
        (-200, -120, BY1 - 27, BY1 - 2, -420, -340, "Electronics fan 80 mm, intake", "#2b2b2b"),
        (-110, -30, BY1 - 27, BY1 - 2, -420, -340, "Electronics fan 80 mm, exhaust", "#2b2b2b"),
        (-200, -130, BY0 + 6, BY0 + 46, -222, -180, "Raspberry Pi / host + relays", "#1d5c3a")):
    res = box(x0_, x1_, y0_, y1_, z0_, z1_, "new", nm_)
    b_ = new_body(res); name_part(b_, nm_, None, col_, "satin"); eparts.append((b_, nm_))

# ---- top bay: fans in the back skin, part-cooling blower (fixed, hose to the neck)
S_TBAY = studio("Top bay")
tparts = []
for x0_, x1_, y0_, y1_, z0_, z1_, nm_ in ((-160, -80, OW - SK - 25, OW - SK, 60, 140, "Top bay fan 80 mm, intake"),
                                          (80, 160, OW - SK - 25, OW - SK, 60, 140, "Top bay fan 80 mm, exhaust"),
                                          (-40, 57, OW - SK - 40, OW - SK - 7, 120, 205, "Part-cooling blower (server type, hose to the neck)")):
    res = box(x0_, x1_, y0_, y1_, z0_, z1_, "new", nm_)
    b_ = new_body(res); name_part(b_, nm_, None, "#2b2b2b", "satin"); tparts.append((b_, nm_))

# ---- toolhead detail (inside the 60 x 60 envelope), relative to the neck centre
S_TDET = studio("Toolhead")
tdet = []
def tpart(nm_, res, color, material=None):
    b_ = new_body(res); name_part(b_, nm_, material, color, "satin"); tdet.append((b_, nm_))
res = box(FX - 30, FX - 21, FY - 30, FY + 10, NOZ + 4, TH_TOP, "new", "Duct riser")
cyl(FX, FY, 14, NOZ + 2, NOZ + 8, "add", "Duct ring")
box(FX - 21, FX - 8, FY - 5, FY + 5, NOZ + 2, NOZ + 8, "add", "Duct feed")
cyl(FX, FY, 7, NOZ + 2, NOZ + 8, "remove", "Ring bore")
tpart("Part-cooling duct (fed through the hollow neck)", res, "#3c3f44", "PPS-CF")
tpart("Extruder (Sherpa Heavy style)", box(FX - 20, FX + 20, FY - 14, FY + 10, -42, TH_TOP, "new", "Extruder"), "#c4572a")
tpart("Extruder motor (LDO high-temp)", box(FX - 18, FX + 18, FY + 10, FY + 30, -40, -4, "new", "Extruder motor"), "#2b2b2b")
res = cyl(FX, FY, 11, NOZ + 12, -42, "new", "Chube")
tpart("Chube Conduction hotend", res, "#b8bec4")
tpart("Nozzle", cyl(FX, FY, 3.5, NOZ, NOZ + 12, "new", "Nozzle"), "#c9a227", "Brass")
tpart("Beacon3D probe", box(FX + 16, FX + 30, FY - 27, FY - 1, NOZ + 3, NOZ + 15, "new", "Beacon"), "#1d1d1d")

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


# frame shell
place(S_SIDE, side_body, [0, 0, 0], I3, name="Shear plate left")
place(S_SIDE, side_body, [0, 0, 0], Rz(180), name="Shear plate right")
place(S_BACK, back_body, [0, 0, 0], I3, name="Shear plate back")
place(S_FLOOR, floor_body, [0, 0, 0], I3, name="Floor plate")

# Z columns: rail, top idler, belt, drive pulley, NEMA17 and its mount
def place_col(col, studio_body, p, Rl, name, std=None, **kw):
    _, o, Rc = col
    pos = col_world(col, p)
    R = mm(Rc, Rl)
    if std:
        return place_std(std[0], std[1], pos, R, name=name, **kw)
    return place(*studio_body, pos, R, name=name)

rail_mid = (Z_TOP - zd + Z_BOT - zd) / 2
for col in COLS:
    nm = col[0]
    place_col(col, buy["mgn12_rail"], [0, 0, rail_mid], RAILV, f"{nm} rail")
    place_col(col, buy["idler"], [Z["belt_x"] - 8, Z["belt_offset"], Z["idler_z"]], RY90, f"{nm} Z idler")
    place_col(col, buy["pulley"], [Z["belt_x"] - 8, Z["belt_offset"], Z["motor_z"]], RY90, f"{nm} Z drive pulley")
    place_col(col, (S_ZBELT, zbelt_body), [Z["belt_x"] - BW / 2, Z["belt_offset"], (Z["idler_z"] + Z["motor_z"]) / 2], RAILV, f"{nm} Z belt")
    place_col(col, (S_ZMOUNT, zmount_body), [0, 0, 0], I3, f"{nm} Z motor mount")
    # 1:3 reduction: jackshaft in two 608s, 60T outboard, NEMA17 inboard of the mount driving a 20T
    place_col(col, None, [RX0 - 2, JY, mz], RY90, f"{nm} Z jackshaft", std=("Shaft", "Ø8"), length=round(Z["belt_x"] + 10 - (RX0 - 2), 1))
    for xb in (-16, -9):
        place_col(col, None, [xb, JY, mz], RY90, f"{nm} Z 608 {xb}", std=("Bearing", "608"))
    place_col(col, (S_P60, p60_body), [RX0, JY, mz], RY90, f"{nm} Z reduction 60T")
    place_col(col, (S_P20, p20_body), [RX0, MY, mz], RY90, f"{nm} Z reduction 20T")
    place_col(col, (S_RBELT, rbelt_body), [RX0 + 1, JY, mz], [[0, 0, 1], [1, 0, 0], [0, 1, 0]], f"{nm} Z reduction belt")
    place_col(col, None, [0, MY, mz], mm(RY90, RX180), f"{nm} NEMA17", std=("NEMA", "NEMA 17"), length=40)

# enclosure and the rest of the static machine; ENC = instances hidden for the inside renders
ENC = []
def penc(*a, **kw):
    i = place(*a, **kw); ENC.append(i); return i
penc(S_HOT, hot_body, [0, 0, 0], name="Hot-face insulation")
penc(S_PIR, pir_body, [0, 0, 0], name="PIR insulation walls")
penc(S_PIR, pirf_body, [0, 0, 0], name="PIR insulation floor")
penc(S_SKIN, skin_body, [0, 0, 0], name="Outer skin")
RDOOR = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]          # local y -> world z, local z -> world -y
penc(S_DOOR, door_body, [0, -W / 2, 0], RDOOR, name="Front door")
penc(S_GLASS, glass_in, [0, -W / 2, 0], RDOOR, name="Door glass inner")
penc(S_GLASS, glass_out, [0, -W / 2, 0], RDOOR, name="Door glass outer")
penc(S_HW, hinge_lo, [0, 0, 0], name="Door hinge lower")
penc(S_HW, hinge_hi, [0, 0, 0], name="Door hinge upper")
penc(S_HW, handle_body, [0, 0, 0], name="Door handle")
penc(S_BCOV, bcov_up, [0, 0, 0], name="Filter bay cover")
penc(S_BCOV, bcov_lo, [0, 0, 0], name="Electronics bay cover")
place(S_BASE, base_body, [0, 0, 0], name="Base plate")
for sx in (-1, 1):
    for sy in (-1, 1):
        place(S_SUP, sup_body, [sx * SUP_C, sy * SUP_C, 0], name="Floor support G10")
        place_std("Extrusion", "3030", [sx * SUP_C, sy * SUP_C, BAY[0]], length=EN["bay_h"], name="Bay leg 3030")
for col in COLS:
    place_col(col, (S_ZHANG, zhang_body), [0, 0, 0], I3, f"{col[0]} Z mount hanger")
for (yy, nm_) in ((YROLL_Y, "back"), (-YROLL_Y, "front")):
    place(S_YROLL, yroll_body, [0, yy, 0], name=f"Shutter Y roller {nm_}")
place(S_HEAT, cheat_body, [0, 0, 0], name="Chamber heater")
place(S_HMOT, hmot_body, [0, 0, 0], name="Heater fan motor")
place_std("Shaft", "Ø8", [HSX, HSY, BAY[0] + 48], length=round(FLOOR[1] + 20 - (BAY[0] + 48), 1), name="Heater shaft")
place(S_BMOD, bmod_body, [0, 0, 0], name="Back module housing")
for st_, parts_ in ((S_FILT, fparts), (S_ELEC, eparts), (S_TBAY, tparts)):
    for b_, nm_ in parts_:
        place(st_, b_, [0, 0, 0], name=nm_)
place(S_DUCT, duct_out, [0, 0, 0], name="Filter duct outlet")
place(S_DUCT, duct_ret, [0, 0, 0], name="Filter duct return")

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
          ("neck", (S_NECK, neck_body), lambda tx, ty: [tx, ty, 0], I3, "Toolhead neck"),
          ("strip", (S_STRIP, strip_body), lambda tx, ty: [0, ty, 0], I3, "Shutter strip"),
          ("nplate", (S_NPLATE, nplate_body), lambda tx, ty: [tx, ty, 0], I3, "Shutter neck plate"),
          ("tube", (S_TUBE, tube_body), lambda tx, ty: [tx, ty, 0], I3, "Filament tube")]
    g += [(f"tdet{k}", (S_TDET, b_), lambda tx, ty: [tx, ty, 0], I3, nm_) for k, (b_, nm_) in enumerate(tdet)]
    return g

GP = gantry_parts()
TX0, TY0 = 40, -30
moving = {k: place(st, bd, f(TX0, TY0), R, name=nm) for k, (st, bd), f, R, nm in GP}

# moving bed at bed-top height zt: bed, heater, arms and Z carriages
BEDP = [("bed", (S_MIC6, bed_body), lambda zt: [0, 0, zt], I3, "Bed"),
        ("heater", (S_HEATER, heater_body), lambda zt: [0, 0, zt], I3, "Bed heater")]
for col in COLS:
    nm, o, Rc = col
    BEDP.append((f"arm_{nm}", arm_s[nm], lambda zt, c=col: col_world(c, [0, 0, zt]), Rc, f"Bed arm {nm}"))
    BEDP.append((f"zcar_{nm}", buy["mgn12h"], lambda zt, c=col: col_world(c, [0, 0, zt - zd]), mm(col[2], RAILV), f"{nm} MGN12H"))
ZT0 = (Z_TOP + Z_BOT) / 2
moving_bed = {k: place(st, bd, f(ZT0), R, name=nm) for k, (st, bd), f, R, nm in BEDP}
def pose_bed(zt):
    for k, _, f, _, _ in BEDP:
        r("assembly_move", assembly=A, instance=moving_bed[k], position=[round(v, 4) for v in f(zt)])


def pose(tx, ty):
    for k, _, f, _, _ in GP:
        r("assembly_move", assembly=A, instance=moving[k], position=[round(v, 4) for v in f(tx, ty)])

# stand-in pairs that overlap on purpose (no bores in the stand-ins, belt on the pulley pitch line)
EXPECTED = ("Drive pulley", "Idler", "Drive shaft", "Coupling", "NEMA23", "608", "belt", "Z idler", "Z drive pulley", "Z belt", "NEMA17", "Z motor mount", "Z jackshaft", "Z 608", "Z reduction")
PASS = [("Filter duct", "Shear plate back"), ("Filter duct", "insulation"), ("Filter duct", "Outer skin"),
        ("Filter duct", "Back module housing"), ("Heater shaft", "Floor plate"), ("Heater shaft", "Chamber heater"),
        ("Heater shaft", "Heater fan motor")]
def unexpected(info):
    names = {i["id"]: i["name"] for i in info["instances"]}
    bad = []
    for x in info["interference"]:
        na, nb = names[x["a"]], names[x["b"]]
        if any(e in na for e in EXPECTED) and any(e in nb for e in EXPECTED):
            continue
        # each Z belt's inner strand passes through its own arm's clamp
        if {na, nb} in ({f"{c} Z belt", f"Bed arm {c}"} for c in ("Z1", "Z2", "Z3")):
            continue
        # pass-throughs that are not cut in the stand-ins
        if any(a_ in na and b_ in nb or a_ in nb and b_ in na for a_, b_ in PASS):
            continue
        bad.append([na, nb, round(x["volume_mm3"], 2)])
    return bad

T_ = G["travel"]
sweep = []
for tx, ty in [(0, 0), (-T_, -T_), (T_, -T_), (T_, T_), (-T_, T_), (-T_, 0), (T_, 0), (0, -T_), (0, T_)]:
    pose(tx, ty)
    bad = unexpected(r("assembly_info", assembly=A, interference=True))
    sweep.append({"pose": [tx, ty], "clashes": bad})
for zt in (Z_TOP, Z_BOT):
    pose_bed(zt)
    for tx, ty in [(0, 0), (-T_, -T_), (T_, -T_), (T_, T_), (-T_, T_)]:
        pose(tx, ty)
        bad = unexpected(r("assembly_info", assembly=A, interference=True))
        sweep.append({"pose": [tx, ty], "bed_top": zt, "clashes": bad})
pose(TX0, TY0)
pose_bed(ZT0)
json.dump(sweep, open(os.path.join(OUT, "clearance-sweep.json"), "w"), indent=1)

r("save_document", path="CroXY.json")
# rename the first Part Studio (scripts cannot name it)
doc = json.load(open(os.path.join(OUT, "CroXY.json")))
doc["studios"][0]["name"] = studios[0]
json.dump(doc, open(os.path.join(OUT, "CroXY.json"), "w"), indent=1)

json.dump({"studios": studios, "layout": layout, "moving": moving, "start": [TX0, TY0], "sweep": sweep},
          open(os.path.join(OUT, "build-info.json"), "w"), indent=1)

# outside views, then hide the enclosure and render the inside
for view in ("iso_front_left", "iso_back_right"):
    r("render_assembly", assembly=A, view=view, width=1400, height=1050, path=f"render-closed-{view}.png")
for i in ENC:
    r("assembly_move", assembly=A, instance=i, hidden=True)
for view in ("iso_front_left", "top", "front", "right"):
    r("render_assembly", assembly=A, view=view, width=1400, height=1050, path=f"render-{view}.png")
# the gantry from below, close up
r("render_assembly", assembly=A, view="iso_front_left", width=1400, height=1050,
  fit_box=[[-W / 2, -W / 2, NOZ - 5], [W / 2, W / 2, MOTOR_FACE + 80]], path="render-gantry.png")
r("render_assembly", assembly=A, view="iso_front_left_below", width=1400, height=1050,
  fit_box=[[-W / 2, -W / 2, NOZ - 5], [W / 2, W / 2, 0]], path="render-below.png")
# one Z drive (Z1) close up: 1:3 reduction under the floor
r("render_assembly", assembly=A, view="iso_front_left_below", width=1400, height=1050,
  fit_box=[[-SPF - 30, Z["z12_y"] - 40, mz - 30], [-SPF + 45, Z["z12_y"] + MY + 25, FLOOR[1]]], path="render-zdrive.png")
for i in ENC:
    r("assembly_move", assembly=A, instance=i, hidden=False)
r("export", format="step", assembly=A, path="CroXY.step")
info = r("assembly_info", assembly=A, interference=True)
json.dump(info, open(os.path.join(OUT, "assembly-info.json"), "w"), indent=1)
r.close()
print("ok", len(inst), "instances")
