# Top plate and XY gantry, designed for how each part is made. exec'd from build.py (shares its globals).
# Methods: "mill" = Jonas's 3-axis mill, "SCS" = Send Cut Send laser cut (and bend), "print" = FDM,
# supportless (PPS-CF in the hot zone, PET-CF outside), "buy" = bought part.

def holes_z(items, z_top, name="Holes"):
    if items:
        cut_through(items, z_top, name)

def circ(c, d):
    return {"type": "circle", "center": [c[0], c[1]], "radius": d / 2}

def pocket_z(items, z_top, depth, name="Pocket"):
    """Blind pocket from z_top down."""
    sid = sketch(plane(z_top - depth), items, name)
    return r("add_feature", kind="extrude", name=name, params={"profiles": [{"sketch": sid, "all": True}], "depth": str(depth), "op": "remove"})

def pocket_up(items, z_bot, depth, name="Pocket"):
    """Blind pocket from z_bot up."""
    sid = sketch(plane(z_bot), items, name)
    return r("add_feature", kind="extrude", name=name, params={"profiles": [{"sketch": sid, "all": True}], "depth": str(depth), "op": "remove"})

def holes_y(items_xz, y_face, depth, towards, name="Holes"):
    """Holes along y, sketched at y_face as (x, z) circles, cut depth mm towards +1 / -1."""
    if towards > 0:
        sid = sketch(plane_y(y_face + depth), items_xz, name)
    else:
        sid = sketch(plane_y(y_face), items_xz, name)
    return r("add_feature", kind="extrude", name=name, params={"profiles": [{"sketch": sid, "all": True}], "depth": str(depth), "op": "remove"})

def holes_x(items_yz, x_face, depth, towards, name="Holes"):
    if towards > 0:
        sid = sketch(plane_x(x_face), items_yz, name)
    else:
        sid = sketch(plane_x(x_face - depth), items_yz, name)
    return r("add_feature", kind="extrude", name=name, params={"profiles": [{"sketch": sid, "all": True}], "depth": str(depth), "op": "remove"})

def plane_y(y):
    f = r("add_feature", kind="plane", name=f"Plane y={y:g}",
          params={"mode": "offset", "base": {"kind": "origin_plane", "plane": "Front"}, "offset": str(-y)})
    return {"kind": "feature_plane", "feature": f["feature_id"]}

def plane_x(x):
    f = r("add_feature", kind="plane", name=f"Plane x={x:g}",
          params={"mode": "offset", "base": {"kind": "origin_plane", "plane": "Right"}, "offset": str(x)})
    return {"kind": "feature_plane", "feature": f["feature_id"]}

# clearance and tapped (modelled at nominal) diameters
CLR = {"M2.5": 2.9, "M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6, "M8": 9.0}
TAP = {"M2.5": 2.5, "M3": 3.0, "M4": 4.0, "M5": 5.0, "M6": 6.0, "M8": 8.0}
CB = {"M3": (6.5, 3.3), "M4": (8.0, 4.4), "M5": (9.5, 5.4), "M6": (11.0, 6.5), "M8": (14.0, 8.6)}  # cbore dia, depth

# ---- small bought parts as studios (spacers, G10 tubes, shims, inserts)
_tube_cache = {}
def tube(od, idd, L, name, material=None, color="#9aa3ab", method="buy", notes=""):
    k = (od, idd, L, name)
    if k not in _tube_cache:
        st = studio(name)
        res = cyl(0, 0, od / 2, 0, L, "new", name)
        b = new_body(res)
        if idd:
            cyl(0, 0, idd / 2, 0, L, "remove", "Bore")
        name_part(b, name, material, color, "satin", method=method, notes=notes)
        _tube_cache[k] = (st, b)
    return _tube_cache[k]

# ================================================================ 0. Top plate (waterjet, finish-milled)
S_PLATE = studio("Top plate")
r("set_variable", name="plate_w", expr=str(W))
r("set_variable", name="plate_t", expr=str(T))
sid = sketch("top", [{"type": "center_rect", "center": [0, 0], "corner": [W / 2, W / 2],
                      "dims": {"width": "plate_w", "height": "plate_w"}}], "Plate outline")
res = r("add_feature", kind="extrude", name="Plate", params={"profiles": [{"sketch": sid}], "depth": "plate_t", "op": "new"})
plate_body = new_body(res)
S_PTS = [[-155.5, -140], [-140, -155.5], [-127.5, -127.5], [-155.5, -155.5]]   # corner stack rods (FL frame)
holes = [{"type": "rect", "corner1": [-CUT, -CUT], "corner2": [CUT, CUT]}]   # toolhead cutout
for k in range(4):
    a = 90 * k
    for p in S_PTS:
        holes.append(circ(rot_z(a, p), TAP["M5"]))                      # M5 tapped through, corner stack rods
    holes.append(circ(rot_z(a, [-PC, -PC]), CLR["M8"]))                 # M8 tie rod through the post
    for n in range(-4, 5):
        holes.append(circ(rot_z(a, [n * 25, -RO]), TAP["M3"]))           # MGN12 rail screws, M3 tapped
ANG_PTS = []                                  # M5 tapped from below for the shear plate angles (outside the shear plates)
for s_ in (-125, -40, 40, 125):
    ANG_PTS += [[-PC, s_], [PC, s_], [s_, PC]]
holes += [circ(p, TAP["M5"]) for p in ANG_PTS]
cut_through(holes, T, "Cutout and holes")
for sy in (-1, 1):   # pockets for the shutter's Y-cover spring rollers, just outside the cutout edges
    box(-(CUT - 2), CUT - 2, min(sy * (CUT + 1), sy * (CUT + 11)), max(sy * (CUT + 1), sy * (CUT + 11)), 2, T, "remove", "Roller pocket")
name_part(plate_body, "Top plate", "Steel", "#5b6670", "metal", method="waterjet + mill",
          notes="12 mm mild steel, waterjet blank (cutout, holes undersize), stress relieve, face both sides, drill/tap M3/M5, mill roller pockets. 1 setup per face")

# ================================================================ 1. Corner pulley block: two milled steel plates on a rod stack
x0, x1 = -158.0, -123.0
I_MID = [I_FL[0], I_FL[1] - TT / 2]          # idler modelled at mid tension
PT_T = 8.0
# Idler tensioner: a steel slider on the upper plate carries the top of the M8 idler axle and is pushed by two M5
# jack screws in a tab bolted to a tongue on the upper plate; the M8 axle then clamps slider, both plates and nut.
TAB_X, TAB_Y = (I_FL[0] - 10, I_FL[0] + 10), (-120.0, -114.0)
TAB_SCR = [[I_FL[0] - 8, -117], [I_FL[0] + 8, -117]]
JACK_X = [I_FL[0] - 3.5, I_FL[0] + 3.5]
SL_HL = 6.0                                    # slider half length along the slot
def block_plate(nm, seat_top):
    st = studio(nm)
    res = box(x0, x1, x0, x1, 0, PT_T, "new", "Plate")
    b = new_body(res)
    for c in (D_FL, I_FL, [I_FL[0], I_FL[1] - TT]):
        cyl(c[0], c[1], BOSS_R, 0, PT_T, "add", "Boss")
    items = [circ(D_FL, 10.0), {"type": "rect", "corner1": [I_FL[0] - 4.25, I_FL[1] - TT], "corner2": [I_FL[0] + 4.25, I_FL[1]]},
             circ(I_FL, 8.5), circ([I_FL[0], I_FL[1] - TT], 8.5)] + [circ(p, CLR["M5"]) for p in S_PTS]
    if not seat_top:
        box(TAB_X[0], TAB_X[1], x1 - 1, TAB_Y[1], 0, PT_T, "add", "Tension tongue")
        items += [circ(p, TAP["M4"]) for p in TAB_SCR]   # tension tab screws
    cut_through(items, PT_T, "Shaft, idler slot, rods")
    if seat_top:
        pocket_z([circ(D_FL, 22.0)], PT_T, 7, "608 seat")
    else:
        pocket_up([circ(D_FL, 22.0)], 0, 7, "608 seat")
    name_part(b, nm, "Steel", "#7a8691", "metal", method="mill",
              notes="8 mm mild steel plate. 2D contour, Ø10 shaft hole, 8.5 mm idler slot, Ø5.5 rod holes, Ø22 x 7 608 seat " +
                    ("from the top face (1 setup)" if seat_top else "from the bottom face, M4 tapped tab holes on the tongue (flip once)"))
    return st, b
S_BLKL, blkl_body = block_plate("Corner block plate, lower", True)
S_BLKU, blku_body = block_plate("Corner block plate, upper", False)

S_TAB = studio("Tension tab")
res = box(TAB_X[0], TAB_X[1], TAB_Y[0], TAB_Y[1], BLK_TOP[1], BLK_TOP[1] + 10, "new", "Tab")
tab_body = new_body(res)
cut_through([circ(p, CLR["M4"]) for p in TAB_SCR], BLK_TOP[1] + 10, "Screw holes")
holes_y([circ([x, BLK_TOP[1] + 4], TAP["M5"]) for x in JACK_X], TAB_Y[0], 6, +1, "M5 jack screws")
name_part(tab_body, "Tension tab", "Steel", "#7a8691", "metal", method="mill",
          notes="20 x 6 x 10 steel bar. 2 drilled holes from the top, 2 M5 tapped holes from the side (2 setups)")
S_SLIDE = studio("Tension slider")
res = box(I_FL[0] - 7, I_FL[0] + 7, I_MID[1] - SL_HL, I_MID[1] + SL_HL, BLK_TOP[1], BLK_TOP[1] + 8, "new", "Slider")
slide_body = new_body(res)
cut_through([circ(I_MID, CLR["M8"])], BLK_TOP[1] + 8, "Axle hole")
name_part(slide_body, "Tension slider", "Steel", "#7a8691", "metal", method="mill",
          notes="14 x 12 x 8 steel block, Ø9 drilled from the top (1 setup)")

# ---- motor plate on the stack (replaces the tower walls)
S_MTOWER = studio("Motor plate")
mh = 28.2
res = box(-161, D_FL[0] + mh, D_FL[1] - mh, D_FL[1] + mh, MOTOR_PLATE[0], MOTOR_PLATE[1], "new", "Motor plate")
mtower_body = new_body(res)
NEMA23_H = [[D_FL[0] + sx * 23.57, D_FL[1] + sy * 23.57] for sx in (-1, 1) for sy in (-1, 1)]
cut_through([circ(D_FL, 38.6)] + [circ(p, TAP["M5"]) for p in NEMA23_H] + [circ(p, TAP["M5"]) for p in S_PTS],
            MOTOR_PLATE[1], "Pilot bore, motor and rod holes")
name_part(mtower_body, "Motor plate", "Steel", "#7a8691", "metal", method="SCS + mill",
          notes="6 mm mild steel, SCS laser blank, bore the Ø38.6 pilot and tap M5 on the mill (1 setup)")

# corner joints (FL frame, world z)
SP_LO = tube(8, 5.3, BLK_BOT[0] - PT, "Spacer 8 x 5.3 x 9", "Steel", method="buy", notes="steel round spacer")
SP_MID = tube(8, 5.3, BLK_TOP[0] - BLK_BOT[1], "Spacer 8 x 5.3 x 20", "Steel", method="buy", notes="steel round spacer")
G10_TOP = MOTOR_PLATE[0] - 4.7 - BLK_TOP[1]
SP_G10 = tube(10, 5.3, G10_TOP, f"G10 tube 10 x 5.3 x {G10_TOP:.1f}", None, "#c9c27a", method="buy", notes="G10/FR4 tube, thermal break under the motor")
SHIM = tube(14, 8.2, 2, "Shim 8 x 14 x 2", "Steel", method="buy", notes="DIN 988 shim washer")
for p in S_PTS:
    J("corner", "Shaft", "Ø5", [p[0], p[1], 2], "+z", L=MOTOR_PLATE[1] - 2, label="M5 threaded rod")
    J("corner", ("studio", SP_LO), None, [p[0], p[1], PT], "+z", label="spacer")
    J("corner", ("studio", SP_MID), None, [p[0], p[1], BLK_BOT[1]], "+z", label="spacer")
    J("corner", ("studio", SP_G10), None, [p[0], p[1], BLK_TOP[1]], "+z", label="G10 tube")
    J("corner", "ISO 4032", "M5", [p[0], p[1], MOTOR_PLATE[0] - 4.7], "+z", label="nut")
for zz in (BLK_BOT[1], PUL_Z1):
    J("corner", ("studio", SHIM), None, [D_FL[0], D_FL[1], zz], "+z", label="shim")
J("corner", "ISO 4762", "M8", [I_MID[0], I_MID[1], BLK_TOP[1] + 8], "-z", L=50, label="idler axle")
J("corner", "ISO 7089", "M8", [I_MID[0], I_MID[1], BLK_BOT[1]], "+z", label="washer")
J("corner", "ISO 7089", "M8", [I_MID[0], I_MID[1], BLK_TOP[0] - 1.6], "+z", label="washer")
J("corner", "ISO 4035", "M8", [I_MID[0], I_MID[1], BLK_BOT[0] - 4], "+z", label="thin nut")
for p in TAB_SCR:
    J("corner", "ISO 4762", "M4", [p[0], p[1], BLK_TOP[1] + 10], "-z", L=16, label="tab screw")
for x in JACK_X:
    J("corner", "ISO 4026", "M5", [x, TAB_Y[1], BLK_TOP[1] + 4], "-y", L=10, label="tension jack screw")
for p in NEMA23_H:
    J("corner", "ISO 4762", "M5", [p[0], p[1], MOTOR_FACE + 6], "-z", L=12, label="NEMA23 motor screw")

# ================================================================ 2. End blocks: one 7075 part each, 3-axis milled
# Each block bolts to its MGN12H carriage and carries a beam end between two cheeks (high-tension 12 mm GT2).
# The block anchors the OUTER strand on its own line: the strand runs along the upright's outer face, which has
# GT2 tooth grooves milled into it (both belt ends meet at the block centre), and a 7075 clamp plate per end with four
# M4 countersunk screws (two above, two below the belt) presses the belt into the teeth. No wrap, no deep slots.
# Local frame: X-end block, u = x along the rail, v = y towards the outside.
pr_, bt_ = XY["pitch_r"], XY["belt_t"]
UP0 = B - pr_ + bt_ / 2 + 1.0                  # upright inner face: 1 mm outside the passing inner strand
UP1 = B + pr_ - bt_ / 2                        # upright outer face = toothed clamp face on the outer strand
UPM = (UP0 + UP1) / 2                          # beam cross screws: through the flanges into the tower cheeks
CHK_Z = 14.0                                   # cross screw height above the beam bottom
CP_U = (1.0, 22.7)                             # clamp plate along u (one per belt end)
CP_Z = (CARR_FACE + 0.5, BZ + BW / 2 + 7.5)
CP_T = 5.0
CP_V = (UP1 + bt_, UP1 + bt_ + CP_T)
CP_SCR = [((CP_U[0] + CP_U[1]) / 2 + du, z) for du in (-6.25, 6.25) for z in (29.0, 49.0)]
TEETH_U = [1.5 + 2 * k for k in range(11)]     # GT2 tooth grooves 1.2 wide, 0.75 deep (Ø1 end mill from the side)
HW = 22.7                                      # block half width along the rail
CAR12 = [[sx * 10, sy * 10] for sx in (-1, 1) for sy in (-1, 1)]

def end_block(swap, top_z, seat, nm):
    """swap=False: X-end frame (u = x along the rail, v = y towards the outside). swap=True: Y-end (u = y, v = x)."""
    def bx(u0, u1, v0, v1, z0, z1, op, name):
        return box(v0, v1, u0, u1, z0, z1, op, name) if swap else box(u0, u1, v0, v1, z0, z1, op, name)
    def pt(u, v):
        return [v, u] if swap else [u, v]
    res = bx(-HW, HW, RO - 13.5, UP1, CARR_FACE, CARR_FACE + BASE_T, "new", "Base")
    body = new_body(res)
    bx(-HW, HW, UP0, UP1, CARR_FACE + BASE_T, top_z, "add", "Upright")
    seat()
    for su in (-1, 1):
        for tu in TEETH_U:
            bx(su * tu - 0.6, su * tu + 0.6, UP1 - 0.75, UP1 + 1, BZ - BW / 2 - 0.5, BZ + BW / 2 + 0.5, "remove", "Tooth groove")
    taps = [circ([su * u, z], TAP["M4"]) for su in (-1, 1) for u, z in CP_SCR]
    if swap:
        holes_x(taps, UP1, 8, -1, "Clamp plate taps M4")
    else:
        holes_y(taps, UP1 - 8, 8, +1, "Clamp plate taps M4")
    ch = [pt(c[0], RO + c[1]) for c in CAR12]
    pocket_z([circ(p, CB["M3"][0]) for p in ch], CARR_FACE + BASE_T, CB["M3"][1], "Cbores")
    cut_through([circ(p, CLR["M3"]) for p in ch], CARR_FACE + BASE_T, "Carriage screws")
    return body, ch

# ---- belt clamp plate, centred on u = 0 in the X-end frame (placed at u = +-CP_UC; Rz(-90) for the Y-end blocks)
CP_UC = (CP_U[0] + CP_U[1]) / 2
CP_HW = (CP_U[1] - CP_U[0]) / 2
S_BCLP = studio("Belt clamp plate")
res = box(-CP_HW, CP_HW, CP_V[0], CP_V[1], CP_Z[0], CP_Z[1], "new", "Plate")
bclp_body = new_body(res)
sid = sketch(plane_y(CP_V[1]), [circ([u - CP_UC, z], CLR["M4"]) for u, z in CP_SCR], "Screw holes")
r("add_feature", kind="extrude", name="Screw holes", params={"profiles": [{"sketch": sid, "all": True}], "depth": str(CP_T), "op": "remove"})
sid = sketch(plane_y(CP_V[1]), [circ([u - CP_UC, z], 8.0) for u, z in CP_SCR], "Countersinks")
r("add_feature", kind="extrude", name="Countersinks", params={"profiles": [{"sketch": sid, "all": True}], "depth": "2.2", "op": "remove"})
name_part(bclp_body, "Belt clamp plate", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="21.7 x 27 x 5 7075 bar, 4 drilled and countersunk holes from the outer face (1 setup). 8 per printer")

# ---- X-end block: the upright rises to the X beam, which drops into a slot between two cheeks
S_XEND = studio("X-end block")
def _xseat():
    for sx in (-1, 1):
        x0_, x1_ = sorted((sx * (BWD / 2), sx * HW))
        box(x0_, x1_, UP0, UP1, XB_BOT, XB_BOT + 20, "add", "Cheek")
    holes_x([circ([UPM, XB_BOT + CHK_Z], TAP["M4"])], BWD / 2, HW - BWD / 2, +1, "Cheek tap")
    holes_x([circ([UPM, XB_BOT + CHK_Z], TAP["M4"])], -BWD / 2, HW - BWD / 2, -1, "Cheek tap")
    pocket_z([circ([sx * 6, B - 1.5], TAP["M4"]) for sx in (-1, 1)], XB_BOT, 10, "Beam screws M4")
xend_body, xc_h = end_block(False, XB_BOT, _xseat, "X")
name_part(xend_body, "X-end block", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="One part from 7075 bar 45.4 x 19.2 x 85. Setup 1, bottom face down: profile, step down to the base, carriage cbores, beam screw taps M4. "
                "Setup 2, on each side: cheek taps M4 through. Setup 3, outer face up: 2 x 11 GT2 tooth grooves (Ø1 end mill, 0.75 deep) and 8 clamp plate taps M4 (3 setups)")
for c in xc_h:
    J("xend", "ISO 4762", "M3", [c[0], c[1], CARR_FACE + BASE_T - CB["M3"][1]], "-z", L=8, label="carriage screw")
for sx in (-1, 1):
    J("xend", "ISO 4762", "M4", [sx * 6, B - 1.5, XB_BOT + BT], "-z", L=12, label="beam screw")
    for u, z in CP_SCR:
        J("xend", "ISO 10642", "M4", [sx * u, CP_V[1], z], "-y", L=12, label="belt clamp screw")

# ---- Y-end block (local: right block, Y beam at y = 0): the beam sits in a seat between the two ears
S_YEND = studio("Y-end block")
EAR_Z = YB_BOT + 21
def _yseat():
    box(UP0, UP1, -BWD / 2, BWD / 2, YB_BOT, EAR_Z, "remove", "Beam seat")
    holes_y([circ([UPM, YB_BOT + CHK_Z], TAP["M4"])], BWD / 2, HW - BWD / 2, +1, "Cheek tap")
    holes_y([circ([UPM, YB_BOT + CHK_Z], TAP["M4"])], -BWD / 2, HW - BWD / 2, -1, "Cheek tap")
    pocket_z([circ([B - 1.5, sy * 6], TAP["M4"]) for sy in (-1, 1)], YB_BOT, 10, "Beam screws M4")
yend_body, yc_h = end_block(True, EAR_Z, _yseat, "Y")
name_part(yend_body, "Y-end block", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="One part from 7075 bar 19.2 x 45.4 x 43. Setup 1, bottom face down: profile, step down to the base, "
                "beam seat slot, carriage cbores, beam screw taps M4. "
                "Setup 2, on each side: ear taps M4 through. Setup 3, outer face up: 2 x 11 GT2 tooth grooves (Ø1 end mill, 0.75 deep) and 8 clamp plate taps M4 (3 setups)")
for c in yc_h:
    J("yend", "ISO 4762", "M3", [c[0], c[1], CARR_FACE + BASE_T - CB["M3"][1]], "-z", L=8, label="carriage screw")
for sy in (-1, 1):
    J("yend", "ISO 4762", "M4", [B - 1.5, sy * 6, YB_BOT + BT], "-z", L=12, label="beam screw")
    for u, z in CP_SCR:
        J("yend", "ISO 10642", "M4", [CP_V[1], sy * u, z], "-x", L=12, label="belt clamp screw")

# ================================================================ 4. Beam backer: SCS bent U channel, web at the bottom
S_BEAM = studio("Beam backer")
r("set_variable", name="beam_len", expr=str(BL))
sid = sketch("right", [{"type": "polyline", "closed": True, "points": [
    [-BWD / 2, 0], [BWD / 2, 0], [BWD / 2, BH], [BWD / 2 - BT, BH], [BWD / 2 - BT, BT],
    [-BWD / 2 + BT, BT], [-BWD / 2 + BT, BH], [-BWD / 2, BH]]}], "Channel section")
res = r("add_feature", kind="extrude", name="Channel", params={"profiles": [{"sketch": sid}], "depth": "beam_len", "op": "new", "end": "symmetric"})
beam_body = new_body(res)
RAIL9_X = [x * 20 for x in range(-6, 7)]
cut_through([circ([x, 0], CLR["M3"]) for x in RAIL9_X] + [circ([sx * (B - 1.5), sy * 6], CLR["M4"]) for sx in (-1, 1) for sy in (-1, 1)],
            BT, "Rail and tower holes")
holes_y([circ([sx * UPM, CHK_Z], CLR["M4"]) for sx in (-1, 1)], -BWD / 2, BWD, +1, "Flange cross holes")
name_part(beam_body, "Beam backer (U channel)", "Steel", "#6d7a86", "metal", method="SCS + mill",
          notes="3 mm mild steel or 4130, SCS laser cut with holes and bent to a 25 x 25 U. Mill the rail face flat (1 setup, long vise or fixture)")
for sx in (-1, 1):
    for sy in (-1, 1):
        J("beam", "ISO 4762", "M4", [sx * UPM, sy * (BWD / 2 - BT), CHK_Z], "+y" if sy > 0 else "-y", L=8, label="beam cross screw")
for x in RAIL9_X:
    J("beam", "ISO 4762", "M3", [x, 0, -3.0], "+z", L=8, label="MGN9 rail screw")
    J("beam", "ISO 4032", "M3", [x, 0, BT], "+z", label="nut")

# ================================================================ 5. Toolhead yoke: U (bottom plate + legs) and a top plate, both 7075
CAR9 = [[sx * 8, sy * 7.5] for sx in (-1, 1) for sy in (-1, 1)]        # MGN9H holes (along x 16, across 15)
yw = 22.0
YK_Y = BWD / 2 + 9
LEG_IN = BWD / 2 + 3
LEG_H = [[sx * 17, sy * 18.5] for sx in (-1, 1) for sy in (-1, 1)]
NECK_SCR = [[sx * 14, sy * 13] for sx in (-1, 1) for sy in (-1, 1)]
S_YOKE = studio("Yoke U")
res = box(-yw, yw, -YK_Y, YK_Y, Y_CAR_FACE - YOKE_T, Y_CAR_FACE, "new", "Bottom plate")
yoke_body = new_body(res)
box(-yw, yw, LEG_IN, YK_Y, Y_CAR_FACE, X_CAR_FACE - YOKE_T, "add", "Back leg")
box(-yw, yw, -YK_Y, -LEG_IN, Y_CAR_FACE, X_CAR_FACE - YOKE_T, "add", "Front leg")
cut_through([circ(p, CLR["M3"]) for p in CAR9] + [circ(p, TAP["M3"]) for p in NECK_SCR], Y_CAR_FACE, "Carriage and neck holes")
pocket_z([circ(p, TAP["M3"]) for p in LEG_H], X_CAR_FACE - YOKE_T, 10, "Leg screws M3")
name_part(yoke_body, "Yoke U", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="7075 block 44 x 43 x 43. U profile contoured standing on end; holes from the bottom and the top (3 setups)")
S_YTOP = studio("Yoke top plate")
res = box(-yw, yw, -YK_Y, YK_Y, X_CAR_FACE - YOKE_T, X_CAR_FACE, "new", "Top plate")
ytop_body = new_body(res)
CARX9 = [[sx * 7.5, sy * 8] for sx in (-1, 1) for sy in (-1, 1)]      # X beam carriage, rotated
pocket_up([circ(p, CB["M3"][0]) for p in CARX9], X_CAR_FACE - YOKE_T, CB["M3"][1], "Cbores from below")
cut_through([circ(p, CLR["M3"]) for p in CARX9 + LEG_H], X_CAR_FACE, "Holes")
name_part(ytop_body, "Yoke top plate", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="6 mm 7075 plate: contour and holes from the top, cbores from the bottom (2 setups)")
for p in CARX9:
    J("yoke", "ISO 4762", "M3", [p[0], p[1], X_CAR_FACE - YOKE_T + CB["M3"][1]], "+z", L=6, label="X carriage screw")
for p in LEG_H:
    J("yoke", "ISO 4762", "M3", [p[0], p[1], X_CAR_FACE], "-z", L=10, label="leg screw")
for p in CAR9:
    J("yoke", "ISO 4762", "M3", [p[0], p[1], Y_CAR_FACE - YOKE_T], "+z", L=10, label="Y carriage screw")

# ---- 6. Toolhead neck: 7075 tube pocketed from the bottom (closed top web), air window on +y
nx, ny = TH["neck"]
NW = 5.0                                     # wall
WEB = 4.0
TP_T = 6.0                                    # toolhead plate under the neck
TP_TOP = TH_TOP                               # plate top (the neck bottom)
TP_BOT = TH_TOP - TP_T
S_NECK = studio("Toolhead neck")
res = box(-nx / 2, nx / 2, -ny / 2, ny / 2, TP_TOP, NECK_TOP, "new", "Neck")
neck_body = new_body(res)
pocket_up([{"type": "rect", "corner1": [-nx / 2 + NW, -ny / 2 + NW], "corner2": [nx / 2 - NW, ny / 2 - NW]}], TP_TOP, NECK_TOP - WEB - TP_TOP, "Air channel")
cut_through([circ(p, CLR["M3"]) for p in NECK_SCR] + [circ(p, 7.0) for p in CAR9], NECK_TOP, "Web holes")
AD_T = 10.0                                   # air adapter thickness
WIN = (-12, 4, 20, 27)                        # x0, x1, z0, z1 of the air window in the +y wall
sid = sketch(plane_y(ny / 2), [{"type": "rect", "corner1": [WIN[0], WIN[2]], "corner2": [WIN[1], WIN[3]]}], "Air window")
r("add_feature", kind="extrude", name="Air window", params={"profiles": [{"sketch": sid}], "depth": str(NW), "op": "remove"})
AD_SCR = [[-19.5, 23.5], [9, 23.5]]
holes_y([circ(p, TAP["M3"]) for p in AD_SCR], ny / 2 - NW, NW, +1, "Adapter screws M3")
TPN = THL["TPN_W"]                            # toolhead plate screws into the wall ends (clear of the gearbox, flange, duct and Beacon bracket)
pocket_up([circ(p, TAP["M3"]) for p in TPN], TP_TOP, 8, "Plate screws M3")
name_part(neck_body, "Toolhead neck", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="7075 block 44 x 43 x 33. From the bottom: pocket the air channel leaving a 4 mm top web, tap M3 in the wall ends; "
                "from the top: web holes; from +y: air window and M3 (3 setups)")

# ---- Toolhead plate, drawn in the toolhead frame (cad/toolhead.py: u from the beam cross towards the nozzle,
# v across) and placed rotated by THL["rot"] about z. Everything heavy sits on that diagonal so the centre of mass
# lands on the cross: hotend and gearbox on the nozzle side, the extruder motor on a flange past the cross.
def loc(p):
    return THM.to_local(THL, p[0], p[1])
FU, MF, FL_T, JS_Z = THL["FU"], THL["MF"], THL["FL_T"], THL["JS_Z"]
S_TPL = studio("Toolhead plate")
BAND = THL["BAND"]
res = box(BAND[0], BAND[1], BAND[2], BAND[3], TP_BOT, TP_TOP, "new", "Diagonal band")
tpl_body = new_body(res)
nsq = [loc(c) for c in ((-nx / 2, -ny / 2), (nx / 2, -ny / 2), (nx / 2, ny / 2), (-nx / 2, ny / 2))]
sid = sketch(plane(TP_BOT), [{"type": "polyline", "closed": True, "points": [[round(a, 4), round(b, 4)] for a, b in nsq]}], "Neck footprint")
extrude(sid, TP_T, "add", "Neck footprint")
box(*THL["FLANGE"], "add", "Motor flange")
for c in THL["CHEEKS"]:
    box(*c, "add", "Motor cheek")
TPN_L = [loc(p) for p in TPN]
EXT_H, BB_H, DUCT_H, MOT_H = THL["EXT_H"], THL["BB_H"], THL["DUCT_H"], THL["MOT_H"]
AIR = THL["AIR"]
cut_through([{"type": "rect", "corner1": [AIR[0], AIR[2]], "corner2": [AIR[1], AIR[3]]}, circ([FU, 0], 4.5)]
            + [circ(p, CLR["M3"]) for p in TPN_L + EXT_H + BB_H + DUCT_H], TP_TOP, "Holes")
pocket_up([circ(p, CB["M3"][0]) for p in TPN_L], TP_BOT, CB["M3"][1], "Cbores from below")
pocket_z([circ(p, 6.6) for p in EXT_H + BB_H + DUCT_H], TP_TOP, 1.7, "Countersinks")
holes_x([circ([0, JS_Z], 23.0)] + [circ(p, CLR["M3"]) for p in MOT_H], MF, FL_T, +1, "Motor pilot and screws")
name_part(tpl_body, "Toolhead plate", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="7075 block 82 x 61 x 57, machined in its own (diagonal) frame. From the bottom: motor flange and cheeks, "
                "cbores; from the top: contour, air outlet, filament hole, holes and countersinks; from the flange face: "
                "motor pilot and M3 holes (3 setups)")
for p in NECK_SCR:
    J("neck", "ISO 4762", "M3", [p[0], p[1], NECK_TOP - WEB], "+z", L=8, label="neck screw")
for p in TPN:
    J("neck", "ISO 4762", "M3", [p[0], p[1], TP_BOT + CB["M3"][1]], "+z", L=10, label="plate screw")
# toolhead-frame fasteners: joint list "th", placed rotated with the toolhead
for p in EXT_H:
    J("th", "ISO 10642", "M3", [p[0], p[1], TP_TOP], "-z", L=10, label="extruder screw")
for p in BB_H:
    J("th", "ISO 10642", "M3", [p[0], p[1], TP_TOP], "-z", L=10, label="Beacon bracket screw")
for p in DUCT_H:
    J("th", "ISO 10642", "M3", [p[0], p[1], TP_TOP], "-z", L=10, label="duct screw")
for p in MOT_H:
    J("th", "ISO 4762", "M3", [MF + FL_T, p[0], p[1]], "-x", L=8, label="extruder motor screw")
for p in AD_SCR:
    J("neck", "ISO 4762", "M3", [p[0], ny / 2 + AD_T, p[1]], "-y", L=14, label="adapter screw")

# air adapter on the neck's +y face (PPS-CF, printed standing on its mounting face; teardrop channel)
S_ADAPT = studio("Neck air adapter")
res = box(-nx / 2, 12, ny / 2, ny / 2 + AD_T, WIN[2] - 1, WIN[3] + 3, "new", "Adapter")
adapt_body = new_body(res)
cyl(-4, ny / 2 + 5.5, 4.5, WIN[3] + 3, WIN[3] + 13, "add", "Hose barb")
pocket_z([circ([-4, ny / 2 + 5.5], 6)], WIN[3] + 13, 11, "Barb bore")
box(WIN[0], WIN[1], ny / 2, ny / 2 + 7, WIN[2], WIN[3] + 2, "remove", "Air cavity")
holes_y([circ(p, CLR["M3"]) for p in AD_SCR], ny / 2, AD_T, +1, "Screw holes")
name_part(adapt_body, "Neck air adapter", "PPS-CF", "#3c3f44", "satin", method="print",
          notes="PPS-CF, printed standing on the mounting face; internal channel teardrop-shaped, no supports")

# PTFE filament tube (bought)
S_TUBE = studio("Filament tube")
res = cyl(FX, FY, 2, TH_TOP, TH["filament_top"], "new", "PTFE tube")
tube_body = new_body(res)
name_part(tube_body, "PTFE filament tube 4 mm", None, "#e8e4d8", "satin", method="buy")

# rail screws (rail frame: holes along local x, rail top at local z = h)
for n in range(-4, 5):
    J("rail12", "ISO 4762", "M3", [n * 25, 0, 8 - 4.5], "-z", L=8, label="MGN12 rail screw")

