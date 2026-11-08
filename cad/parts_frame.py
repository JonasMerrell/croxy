# Frame, Z drives and bed arms, designed for how each part is made. exec'd from build.py (shares its globals).
# Everything in the frame is steel so it grows with the steel top plate and rails at 150 C.

ANG = 30.0                                   # bought steel angle 30 x 30 x 3
ANG_T = 3.0
ANG_L = 2 * SPI - 1                          # fits between the posts
S_ANG = [-125, -40, 40, 125]                 # screw stations along every angle (symmetric, so one part fits all)

# rail screw world points for a column (MGN12 rail on the shear plate face)
def zrail_pts(col):
    R = mm(col[2], RAILV)
    o = col_world(col, [0, 0, rail_mid])
    return [[a + b for a, b in zip(o, mvec(R, [n * 25, 0, 0]))] for n in range(-4, 5)]

def zidler_pt(col):
    return col_world(col, [0, Z["belt_offset"], Z["idler_z"]])

# ---- side shear plates (one studio each: the Z rails sit at the same y on both sides)
def side_plate(sx):
    nm = "left" if sx < 0 else "right"
    st = studio(f"Side shear plate {nm}")
    x0_, x1_ = sorted((sx * SPI, sx * SPF))
    res = box(x0_, x1_, -SPI, SPI, -CH, 0, "new", "Plate")
    b = new_body(res)
    col = COLS[0] if sx < 0 else COLS[1]
    items = [circ([p[1], p[2]], TAP["M3"]) for p in zrail_pts(col)]
    ip = zidler_pt(col)
    items.append({"type": "rect", "corner1": [ip[1] - 4.1, ip[2] - 7], "corner2": [ip[1] + 4.1, ip[2] + 7]})
    items += [circ([s, zz], CLR["M5"]) for s in S_ANG for zz in (-ANG / 2, -CH + ANG / 2)]
    holes_x(items, x0_, SH["shear_t"], +1, "Rail, idler slot and angle holes")
    name_part(b, f"Side shear plate {nm}", "Steel", "#58626b", "metal", method="SCS",
              notes="6 mm mild steel, SCS laser cut with all holes; hand-tap the M3 rail holes. Idler slot 8.2 x 14 for Z belt tension")
    return st, b
S_SIDEL, sidel_body = side_plate(-1)
S_SIDER, sider_body = side_plate(1)

S_BACK = studio("Back shear plate")
res = box(-SPF, SPF, SPF, SPI, -CH, 0, "new", "Plate")
back_body = new_body(res)
col = COLS[2]
DUCT_Z = -55                                    # filter ducts pass through the back plate here
items = [circ([p[0], p[2]], TAP["M3"]) for p in zrail_pts(col)] + [circ([dx, DUCT_Z], 41.0) for dx in (-120, 130)]
ip = zidler_pt(col)
items.append({"type": "rect", "corner1": [ip[0] - 4.1, ip[2] - 7], "corner2": [ip[0] + 4.1, ip[2] + 7]})
items += [circ([s, zz], CLR["M5"]) for s in S_ANG for zz in (-ANG / 2, -CH + ANG / 2)]
holes_y(items, SPF, SH["shear_t"], +1, "Rail, idler slot and angle holes")
name_part(back_body, "Back shear plate", "Steel", "#58626b", "metal", method="SCS",
          notes="6 mm mild steel, SCS laser cut with all holes; hand-tap the M3 rail holes")

# ---- bought steel angles, top and bottom of each shear plate, outside it (between the posts)
S_ANGLE = studio("Steel angle 30 x 30 x 3")
res = box(-ANG_L / 2, ANG_L / 2, 0, ANG, 0, ANG_T, "new", "Flat leg")
angle_body = new_body(res)
box(-ANG_L / 2, ANG_L / 2, 0, ANG_T, ANG_T, ANG, "add", "Upright leg")
cut_through([circ([s, ANG / 2], CLR["M5"]) for s in S_ANG], ANG_T, "Flat leg holes")
holes_y([circ([s, ANG / 2], CLR["M5"]) for s in S_ANG], 0, ANG_T, +1, "Upright leg holes")
name_part(angle_body, f"Steel angle 30 x 30 x 3 x {ANG_L:.0f}", "Steel", "#6d7a86", "metal", method="buy + drill",
          notes="bought mild steel angle, cut to length, 8 holes drilled on the mill with a stop (1 setup per leg)")
# angle frame: length along x, flat leg in +y, upright leg in +z. Rb turns local +y outwards; the top ones are
# flipped about local y so the flat leg sits under the top plate with the upright hanging down.
RY180 = [[-1, 0, 0], [0, 1, 0], [0, 0, -1]]
ANGLES = []
for nm_, Rb, d in (("left", Rz(90), [-SPI, 0]), ("right", Rz(-90), [SPI, 0]), ("back", Rz(0), [0, SPI])):
    ANGLES.append((f"{nm_} top", "angle_top", mm(Rb, RY180), [d[0], d[1], 0]))
    ANGLES.append((f"{nm_} bottom", "angle_bot", Rb, [d[0], d[1], FLOOR[1]]))
for s_ in S_ANG:
    J("angle_top", "ISO 4762", "M5", [s_, ANG / 2, ANG_T], "-z", L=12, label="angle screw")    # up into the top plate
    J("angle_bot", "ISO 4762", "M5", [s_, ANG / 2, ANG_T], "-z", L=8, label="angle screw")     # down into the floor plate

# shear plate to angle screws are written in world by side below (they go through the plate and the upright leg)
def plate_angle_joints():
    out = []
    for s in S_ANG:
        for zz in (-ANG / 2, -CH + ANG / 2):
            out.append(("left", [-SPF, s, zz], "-x"))
            out.append(("right", [SPF, s, zz], "+x"))
            out.append(("back", [s, SPF, zz], "+y"))
    return out
for nm_, p, d in plate_angle_joints():
    J("shear", "ISO 4762", "M5", p, d, L=16, label="shear plate screw")
    q = list(p)
    ax = {"-x": (0, -1), "+x": (0, 1), "+y": (1, 1)}[d]
    q[ax[0]] += ax[1] * (SH["shear_t"] + ANG_T)
    J("shear", "ISO 4032", "M5", q, d, label="nut")

# ---- posts: bought steel square tube, clamped between the plates by an M8 tie rod that runs on into the bay leg
S_POST = studio("Post")
res = box(-15, 15, -15, 15, 0, CH, "new", "Tube")
post_body = new_body(res)
box(-12, 12, -12, 12, 0, CH, "remove", "Bore")
name_part(post_body, f"Post, steel square tube 30 x 30 x 3 x {CH:.0f}", "Steel", "#6d7a86", "metal", method="buy + mill",
          notes="bought mild steel tube, cut and both ends faced square to length on the mill (1 setup per end)")
TIE_BOT = FI[0] - 20
TIE_TOP = PT + 1.6 + 6.8 + 1.5
J("post", "Shaft", "Ø8", [-PC, -PC, TIE_BOT], "+z", L=round(TIE_TOP - TIE_BOT, 1), label="M8 tie rod")
J("post", "ISO 7089", "M8", [-PC, -PC, PT], "+z", label="washer")
J("post", "ISO 4032", "M8", [-PC, -PC, PT + 1.6], "+z", label="nut")
J("post", "ISO 4762", "M8", [-PC, -PC, BASE[0]], "+z", L=16, label="leg screw")

S_FLOOR = studio("Floor plate")
res = box(-W / 2, W / 2, -W / 2, W / 2, FLOOR[0], FLOOR[1], "new", "Plate")
floor_body = new_body(res)
slots = []
for col in COLS:
    a = col_world(col, [Z["belt_x"] - 10, Z["belt_offset"] - 15, 0]); b = col_world(col, [Z["belt_x"] + 10, Z["belt_offset"] + 15, 0])
    slots.append({"type": "rect", "corner1": a[:2], "corner2": b[:2]})
ZSO = [[35, JY - 5], [35, 10], [35, MY + 14]]          # Z bracket standoffs, column frame (x inward, y)
zso_w = [col_world(col, [p[0], p[1], 0])[:2] for col in COLS for p in ZSO]
cut_through(slots + [circ(p, CLR["M5"]) for p in zso_w] + [circ(p, TAP["M5"]) for p in ANG_PTS]
            + [circ([sx * PC, sy * PC], CLR["M8"]) for sx in (-1, 1) for sy in (-1, 1)], FLOOR[1], "Holes")
name_part(floor_body, "Floor plate", "Steel", "#58626b", "metal", method="SCS",
          notes="6 mm mild steel, SCS laser cut with all holes; hand-tap the M5 angle holes")

# ---- Z drive bracket: SCS laser cut and bent 5 mm steel, web on the column axis, flange inboard on top.
# It hangs from the floor plate on three G10 tubes (thermal break) through the floor insulation.
ZB_T = 5.0
ZB_Y = (JY - 21, MY + 21)
ZB_Z0 = mz - 21
ZF = (FI[0] - ZB_T, FI[0])                   # flange
S_ZMOUNT = studio("Z drive bracket")
res = box(-ZB_T, 0, ZB_Y[0], ZB_Y[1], ZB_Z0, ZF[1], "new", "Web")
zmount_body = new_body(res)
box(0, 50, ZB_Y[0], ZB_Y[1], ZF[0], ZF[1], "add", "Flange")
BRG_H = [[JY + sy * 10, mz + sz * 10] for sy in (-1, 1) for sz in (-1, 1)]
N17 = 15.5
N17_H = [[MY + sy * N17, mz + sz * N17] for sy in (-1, 1) for sz in (-1, 1)]
TT_Z = 3.0                                    # motor slot travel for the reduction belt tension
web_items = [circ([JY, mz], 12.0)] + [circ(p, CLR["M4"]) for p in BRG_H]
web_items.append({"type": "rect", "corner1": [MY - 11.5 - TT_Z, mz - 11.5], "corner2": [MY + 11.5 + TT_Z, mz + 11.5]})
web_items += [{"type": "rect", "corner1": [p[0] - 1.7 - TT_Z, p[1] - 1.7], "corner2": [p[0] + 1.7 + TT_Z, p[1] + 1.7]} for p in N17_H]
holes_x(web_items, -ZB_T, ZB_T, +1, "Web holes")
cut_through([{"type": "rect", "corner1": [Z["belt_x"] - 10, JY - 15], "corner2": [Z["belt_x"] + 10, JY + 15]}]
            + [circ(p, TAP["M5"]) for p in ZSO], ZF[1], "Flange holes")
name_part(zmount_body, "Z drive bracket", "Steel", "#7a8691", "metal", method="SCS",
          notes="5 mm mild steel, SCS laser cut and bent 90 deg; motor holes slotted for the reduction belt tension; hand-tap the 3 M5 flange holes")

def bearing_block(nm, tapped):
    st = studio(nm)
    res = box(-14, 14, -14, 14, 0, 10, "new", "Block")          # local: y across, x up the bracket, z out of the web
    b = new_body(res)
    pocket_up([circ([0, 0], 22.0)], 0, 7, "608 seat")
    cut_through([circ([0, 0], 12.0)] + [circ([sy * 10, sz * 10], TAP["M4"] if tapped else CLR["M4"]) for sy in (-1, 1) for sz in (-1, 1)], 10, "Holes")
    name_part(b, nm, "Steel", "#7a8691", "metal", method="mill",
              notes="10 mm steel plate: contour, Ø22 x 7 seat and holes from one side" + (", M4 tapped" if tapped else "") + " (1 setup)")
    return st, b
S_ZBO, zbo_body = bearing_block("Z bearing block, outboard", False)
S_ZBI, zbi_body = bearing_block("Z bearing block, inboard", True)
# bearing block local (u, v, w) -> column (y, z, x): outboard faces -x, inboard +x
R_ZBI = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
R_ZBO = [[0, 0, -1], [1, 0, 0], [0, -1, 0]]

G10_L = FLOOR[0] - ZF[1]
SO_G10 = tube(10, 5.3, G10_L, f"G10 tube 10 x 5.3 x {G10_L:.0f}", None, "#c9c27a", method="buy", notes="G10/FR4 tube, thermal break")
for p in ZSO:
    J("zcol", ("studio", SO_G10), None, [p[0], p[1], ZF[1]], "+z", label="G10 standoff")
    J("zcol", "ISO 4762", "M5", [p[0], p[1], FLOOR[1]], "-z", L=60, label="bracket screw")
for p in BRG_H:
    J("zcol", "ISO 4762", "M4", [-ZB_T - 10, p[0], p[1]], "+x", L=20, label="bearing block screw")
for p in N17_H:
    J("zcol", "ISO 4762", "M3", [-ZB_T, p[0], p[1]], "+x", L=8, label="NEMA17 screw")
# top idler on a cantilevered M8 through the shear plate slot
SP_ID = tube(12, 8.2, Z["belt_x"] - 8, f"Spacer 12 x 8.2 x {Z['belt_x'] - 8:.0f}", "Steel", method="buy", notes="steel round spacer")
J("zcol", "ISO 4762", "M8", [-SH["shear_t"], Z["belt_offset"], Z["idler_z"]], "+x", L=40, label="Z idler axle")
J("zcol", ("studio", SP_ID), None, [0, Z["belt_offset"], Z["idler_z"]], "+x", label="spacer")
J("zcol", "ISO 7089", "M8", [Z["belt_x"] + 8, Z["belt_offset"], Z["idler_z"]], "+x", label="washer")
J("zcol", "ISO 4032", "M8", [Z["belt_x"] + 9.6, Z["belt_offset"], Z["idler_z"]], "+x", label="nut")

# ---- bed arms: 7075, milled from the top and bottom (2.5D), carriage holes from the side, clamp holes from the -y side
AW, AH = 12.0, 24.0                    # arm section (narrow so the carriage screws stay reachable)
CPZ = (-zd - 22.7, -zd + 22.7)         # carriage plate z
ATZ = (under - AH, under)              # arm z
TAB = (13.0, 31.0)                     # belt clamp tab x
SF_IN = Z["belt_offset"] + XY["pitch_r"] + XY["belt_t"] / 2      # strand face nearest the rail
SF_OUT = SF_IN - XY["belt_t"]
CLT = 5.0
arm_s = {}
for nm, _, _ in COLS:
    st = studio(f"Bed arm {nm}")
    L = ARM_REACH[nm]
    res = box(13, 19, -13.5, 13.5, CPZ[0], CPZ[1], "new", "Carriage plate")
    b = new_body(res)
    box(19, L + 10, -AW / 2, AW / 2, ATZ[0], ATZ[1], "add", "Arm")
    box(TAB[0], TAB[1], SF_IN, -13.5, -zd - 10, -zd + 10, "add", "Clamp tab")
    holes_x([circ([c[1], -zd + c[0]], CLR["M3"]) for c in CAR12], 13, 6, +1, "Carriage holes")
    holes_x([circ([c[1], -zd + c[0]], CB["M3"][0]) for c in CAR12], 19 - CB["M3"][1], CB["M3"][1], +1, "Cbores")
    holes_y([circ([27, -zd + sz * 6], TAP["M3"]) for sz in (-1, 1)], SF_IN, -13.5 - SF_IN, +1, "Clamp screws M3")
    pocket_z([circ([L, 0], TAP["M4"])], under, 12, "Bed screw M4")
    name_part(b, f"Bed arm {nm}", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
              notes="7075 block. Top and bottom: 2.5D outline and steps, M4 bed tap; side: carriage holes and cbores; "
                    "-y side: 2 M3 clamp taps (4 setups, or drill the clamp holes with a jig)")
    arm_s[nm] = (st, b)
S_ZCL = studio("Z belt clamp plate")
res = box(TAB[0], TAB[1], SF_OUT - CLT, SF_OUT, -zd - 10, -zd + 10, "new", "Clamp")
zcl_body = new_body(res)
holes_y([circ([27, -zd + sz * 6], CLR["M3"]) for sz in (-1, 1)], SF_OUT - CLT, CLT, +1, "Screw holes")
name_part(zcl_body, "Z belt clamp plate", "Aluminium 7075", "#c0c6cc", "metal", method="mill",
          notes="5 mm 7075: contour, 2 holes, GT2 tooth grooves on the belt face (1 setup)")
# bed-arm joints in the column frame, bed top at z = 0 (move with the bed)
for c in CAR12:
    J("arm", "ISO 4762", "M3", [19 - CB["M3"][1], c[1], -zd + c[0]], "-x", L=8, label="Z carriage screw")
for sz in (-1, 1):
    J("arm", "ISO 4762", "M3", [27, SF_OUT - CLT, -zd + sz * 6], "+y", L=10, label="Z clamp screw")
BW_G10 = tube(12, 4.5, BD["heater_t"], "G10 washer 12 x 4.5 x 2", None, "#c9c27a", method="buy", notes="G10 washer, keeps the arm off the heater layer")
for nm, _, _ in COLS:
    L = ARM_REACH[nm]
    J(f"bed_{nm}", "ISO 10642", "M4", [L, 0, 0], "-z", L=20, label="bed screw")
    J(f"bed_{nm}", ("studio", BW_G10), None, [L, 0, under], "+z", label="G10 washer")
