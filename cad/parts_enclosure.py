# Enclosure, door, shutter, heater, back module and toolhead detail, designed for how each part is made.
# exec'd from build.py (shares its globals). Sheet parts are SCS laser cut and bent (5052-H32 aluminium,
# modelled with 6061 density), insulation boards are cut to size and held captive between the frame and
# the skin, printed parts print without supports.

AL = "Aluminium 6061"
BY0, BY1 = OW, OW + BM["depth"]           # back module
SPL = BM["split_z"]
FL_W = 15.0                                   # sheet flange width
RIV_L = 6.0
S_RIV = studio("Blind rivet 4 mm")
res = cyl(0, 0, 4, -1.2, 0, "new", "Head")
riv_body = new_body(res)
cyl(0, 0, 2, 0, RIV_L, "add", "Body")
name_part(riv_body, "Blind rivet 4.0 x 8, aluminium, open end", AL, "#b8bec4", "satin", method="buy")
RIV = (S_RIV, riv_body)

def sbox(sx, xa, xb, y0, y1, z0, z1, op="new", name=None):
    """box mirrored in x by sx (xa, xb given for the left side)."""
    a_, b_ = sorted((-sx * xa, -sx * xb))
    return box(a_, b_, y0, y1, z0, z1, op, name)


def drill(keys, bb, tf=None, name="Fastener holes"):
    """Cut clearance holes for every screw / rivet shank in JOINTS[keys] that crosses the box bb
    ((x0, x1), (y0, y1), (z0, z1)) of the current studio. tf maps a world joint point/dir into the studio frame."""
    AX = {"x": 0, "y": 1, "z": 2}
    for key in keys:
        for std, size, L, p, d, label in JOINTS.get(key, []):
            if isinstance(std, tuple):
                if std[1] != RIV: continue
                dia, L = 4.1, RIV_L
            elif std in SCREWS:
                dia = CLR[size]
            else:
                continue
            p_, d_ = (tf(p, d) if tf else (p, d))
            a = AX[d_[1]]; sgn = 1 if d_[0] == "+" else -1
            s0, s1 = sorted((p_[a] - sgn * 1.5, p_[a] + sgn * L))
            lo, hi = max(s0, bb[a][0]), min(s1, bb[a][1])
            if hi - lo <= 0.05: continue
            if any(not (bb[k][0] - dia / 2 < p_[k] < bb[k][1] + dia / 2) for k in range(3) if k != a): continue
            if a == 0: cyl_x(p_[1], p_[2], dia / 2, lo, hi, "remove", name)
            elif a == 1: cyl_y(p_[0], p_[2], dia / 2, lo, hi, "remove", name)
            else: cyl(p_[0], p_[1], dia / 2, lo, hi, "remove", name)

# ---------------------------------------------------------------- insulation (cut boards, captive)
S_HOT = studio("Hot-face insulation")
res = box(-W / 2 - HL, -W / 2, -W / 2, W / 2, FI[0], PT, "new", "Left")
hot_body = new_body(res)
box(-W / 2 - HL, W / 2 + HL, W / 2, W / 2 + HL, FI[0], PT, "add", "Back")
box(W / 2, W / 2 + HL, -W / 2, W / 2, FI[0], PT, "add", "Right")
box(-W / 2, W / 2, -W / 2, W / 2, FLOOR[0] - HL, FLOOR[0], "add", "Floor")
cut_through(floor_holes, FLOOR[0], "Floor pass-throughs")
for dx in (-120, 130):
    cyl_y(dx, DUCT_Z, 20.5, W / 2, W / 2 + HL, "remove", "Duct hole")
name_part(hot_body, f"Hot-face insulation {HL} mm (mineral wool board)", None, "#d9d2bf", "matte", method="cut",
          notes="rated >= 250 C board, cut with a knife to fit between the frame and the PIR; held captive, no fixings")

S_PIR = studio("PIR insulation")
o = W / 2 + HL
res = box(-o - PIR, -o, -W / 2, o + PIR, FI[0], PT, "new", "Left")
pir_body = new_body(res)
box(-o, o, o, o + PIR, FI[0], PT, "add", "Back")
box(o, o + PIR, -W / 2, o + PIR, FI[0], PT, "add", "Right")
for dx in (-120, 130):
    cyl_y(dx, DUCT_Z, 20.5, o, o + PIR, "remove", "Duct hole")
res = box(-W / 2, W / 2, -W / 2, W / 2, FI[0], FLOOR[0] - HL, "new", "Floor")
pirf_body = new_body(res)
cut_through(floor_holes, FLOOR[0] - HL, "Floor pass-throughs")
for b_, n_ in ((pir_body, "walls"), (pirf_body, "floor")):
    name_part(b_, f"PIR insulation {n_} {PIR} mm", None, "#e2c75a", "matte", method="cut",
              notes="foil-faced PIR board, cut with a saw; held captive between the hot-face layer and the skin")

# ---------------------------------------------------------------- outer skin: SCS cut and bent 2 mm sheet
SKY1 = BY1 + SK                               # skin back face (behind the back module)
JX = OW - SK                                  # inner face of the side skins
FX_ = JX - FL_W / 2                           # x of every fastener in a side-panel flange (left side, sign by sx)
DW = JX - FL_W                                # door half width: the side flanges form the door jambs
TB_FANS = [[-120, 100], [120, 100]]           # top bay fans (x, z)
EPY = (OW + 4, OW + 6)                        # electronics backplate
# skin and module fasteners (world). Rivets: p = head face, d = into the joint.
for sx in (-1, 1):
    sd = "+x" if sx < 0 else "-x"
    for zz in (BAY[0] + 40, -300, -170 - 40, -60, 60, LID - 40):            # back wall side flange to side skin
        J("skin", ("studio", RIV), None, [sx * OW, OW + FL_W / 2, zz], sd, label="rivet")
    for zz in (PT + 40, LID - 40, BAY[0] + 20, FI[0] - 20):                 # front strips to the jambs
        J("skin", ("studio", RIV), None, [sx * FX_, -OW, zz], "+y", label="rivet")
    for yy in (OW + 40, BY1 - 40):                                          # divider flanges
        J("skin", ("studio", RIV), None, [sx * OW, yy, SPL - 1 - FL_W / 2], sd, label="rivet")
    for yy in (-200, -60, 80, 220, OW + 50):                                 # side skins to the base plate
        J("skin", "ISO 7380", "M4", [sx * FX_, yy, BAY[0] + SK], "-z", L=8, label="base screw")
    for yy in (-150, 0, 150, OW + 50):                                       # lid to the side top flanges
        J("skin", "ISO 7380", "M4", [sx * FX_, yy, LID + SK], "-z", L=10, label="lid screw")
        J("skin", "ISO 4032", "M4", [sx * FX_, yy, LID - SK - 3.2], "+z", label="rivnut")
    for zz in (SPL + 40, LID - 40, BAY[0] + 30, SPL - 30):                   # covers into rivnuts in the back flanges
        J("skin", "ISO 7380", "M4", [sx * FX_, SKY1, zz], "-y", L=10, label="cover screw")
        J("skin", "ISO 4032", "M4", [sx * FX_, BY1 - SK, zz], "-y", label="rivnut")
for xx in (-150, 0, 150):
    J("skin", "ISO 7380", "M4", [xx, OW + FL_W / 2, LID + SK], "-z", L=10, label="lid screw")
    J("skin", "ISO 4032", "M4", [xx, OW + FL_W / 2, LID - SK - 3.2], "+z", label="rivnut")
    J("skin", "ISO 7380", "M4", [xx, -JX + FL_W / 2, LID + SK], "-z", L=10, label="lid screw")
    J("skin", "ISO 4032", "M4", [xx, -JX + FL_W / 2, LID - SK - 3.2], "+z", label="rivnut")
    J("skin", "ISO 7380", "M4", [xx, OW + FL_W / 2, BAY[0] + SK], "-z", L=8, label="base screw")
for xx in (-150, 150):
    J("skin", "ISO 7380", "M4", [xx, EPY[1] + FL_W / 2, BAY[0] + 2 * SK], "-z", L=10, label="base screw")

def skin_side(sx):
    nm = "left" if sx < 0 else "right"
    st = studio(f"Skin side {nm}")
    res = sbox(sx, -OW, -JX, -OW, SKY1, BAY[0], LID, "new", "Panel")
    b = new_body(res)
    for y0_, y1_ in ((-JX, OW - SK), (OW + FL_W, BY1)):          # relieved where the back wall's flanges pass
        sbox(sx, -JX, -JX + FL_W, y0_, y1_, BAY[0], BAY[0] + SK, "add", "Bottom flange")
        sbox(sx, -JX, -JX + FL_W, y0_, y1_, LID - SK, LID, "add", "Top flange")
    sbox(sx, -JX, -JX + FL_W, -JX, -JX + SK, BAY[0], LID, "add", "Front flange (door jamb)")
    sbox(sx, -JX, -JX + FL_W, BY1 - SK, BY1, BAY[0], LID, "add", "Back flange")
    name_part(b, f"Skin side {nm}", AL, "#56636f", "satin", method="SCS",
              notes="2 mm 5052-H32, SCS laser cut with all holes, 4 flanges bent in (corner reliefs), powder coat")
    return st, b
S_SKL, skl_body = skin_side(-1)
S_SKR, skr_body = skin_side(1)

S_SKB = studio("Skin back wall")
res = box(-JX, JX, OW - SK, OW, BAY[0], LID, "new", "Panel")
skb_body = new_body(res)
for sx in (-1, 1):
    sbox(sx, -JX, -JX + SK, OW, OW + FL_W, BAY[0], LID, "add", "Side flange")
box(-JX + FL_W, JX - FL_W, OW, OW + FL_W, BAY[0], BAY[0] + SK, "add", "Bottom flange")
box(-JX + FL_W, JX - FL_W, OW, OW + FL_W, LID - SK, LID, "add", "Top flange")
holes_y([circ([dx, DUCT_Z], 41.0) for dx in (-120, 130)] + [circ(p, 76.0) for p in TB_FANS], OW - SK, SK, +1, "Duct and fan openings")
name_part(skb_body, "Skin back wall (between the chamber and the back module)", AL, "#56636f", "satin", method="SCS",
          notes="2 mm 5052, SCS cut and bent: flanges point back into the module so all fixings sit outside the insulation")

S_SKF = studio("Skin front strips")
res = box(-JX, JX, -OW, -JX, PT, LID, "new", "Top strip")
skft_body = new_body(res)
box(-JX + FL_W, JX - FL_W, -JX, -JX + FL_W, LID - SK, LID, "add", "Top flange")
res = box(-JX, JX, -OW, -JX, BAY[0], FI[0], "new", "Bay strip")
skfb_body = new_body(res)
for b_, n_ in ((skft_body, "Skin front strip, top bay"), (skfb_body, "Skin front strip, Z bay")):
    name_part(b_, n_, AL, "#56636f", "satin", method="SCS", notes="2 mm 5052, SCS cut (and bent), riveted to the side jambs")

S_LID = studio("Lid")
res = box(-OW, OW, -OW, SKY1, LID, LID + SK, "new", "Lid")
lid_body = new_body(res)
name_part(lid_body, "Lid (removable)", AL, "#56636f", "satin", method="SCS", notes="2 mm 5052 flat, SCS cut; M4 screws into rivnuts")

S_BCOV = studio("Back module covers")
res = box(-JX, JX, BY1, SKY1, SPL, LID, "new", "Upper cover")
bcov_up = new_body(res)
res = box(-JX, JX, BY1, SKY1, BAY[0], SPL - 0.5, "new", "Lower cover")
bcov_lo = new_body(res)
EL_FANS = [[-160, BAY[0] + 56], [-70, BAY[0] + 56]]   # bay floor up, so they follow the chamber height
holes_y([circ(p, 76.0) for p in EL_FANS], BY1, SK, +1, "Fan openings")
holes_y([{"type": "rect", "corner1": [x_ - 3, z_ - 30], "corner2": [x_ + 3, z_ + 30]} for x_ in range(-200, 201, 16) for z_ in (-90, 120)],
        BY1, SK, +1, "Vent slots")
name_part(bcov_up, "Back cover, filter bay (vented)", AL, "#66737f", "satin", method="SCS", notes="2 mm 5052, SCS cut with vent slots")
name_part(bcov_lo, "Back cover, electronics bay", AL, "#66737f", "satin", method="SCS", notes="2 mm 5052, SCS cut with fan openings")

S_DIV = studio("Module divider")
res = box(-JX + SK, JX - SK, OW, BY1 - SK, SPL - 1, SPL + 1, "new", "Divider")
div_body = new_body(res)
for sx in (-1, 1):
    sbox(sx, -JX, -JX + SK, OW + 20, BY1 - SK - 5, SPL - 1 - FL_W, SPL - 1, "add", "Flange")
name_part(div_body, "Module divider (filter bay over electronics)", AL, "#66737f", "satin", method="SCS",
          notes="2 mm 5052, SCS cut and bent, riveted to the side skins")

S_EPL = studio("Electronics backplate")
res = box(-JX + FL_W + 1, JX - FL_W - 1, EPY[0], EPY[1], BAY[0] + SK, SPL - 1 - FL_W - 1, "new", "Plate")
epl_body = new_body(res)
box(-JX + FL_W + 1, JX - FL_W - 1, EPY[1], EPY[1] + FL_W, BAY[0] + SK, BAY[0] + 2 * SK, "add", "Bottom flange")
name_part(epl_body, "Electronics backplate", AL, "#66737f", "satin", method="SCS", notes="2 mm 5052, SCS cut with all holes and bent")

# ---------------------------------------------------------------- base plate and feet (extends under the back module)
S_BASE = studio("Base plate")
res = box(-OW, OW, -OW, SKY1, BASE[0], BASE[1], "new", "Base")
base_body = new_body(res)
FEET = [[sx * (OW - 30), yy] for sx in (-1, 1) for yy in (-OW + 30, SKY1 - 30)]
HM_H = [[HSX + sx * 20, HSY + sy * 20] for sx in (-1, 1) for sy in (-1, 1)]
base_h = [circ([sx * PC, sy * PC], CLR["M8"]) for sx in (-1, 1) for sy in (-1, 1)] + [circ(p, CLR["M6"]) for p in FEET]
base_h += [circ(p, CLR["M4"]) for p in HM_H]
base_h += [circ([sx * FX_, yy], TAP["M4"]) for sx in (-1, 1) for yy in (-200, -60, 80, 220, OW + 50)]
base_h += [circ([xx, OW + FL_W / 2], TAP["M4"]) for xx in (-150, 0, 150)]
base_h += [circ([xx, EPY[1] + FL_W / 2], TAP["M4"]) for xx in (-150, 150)]
cut_through(base_h, BASE[1], "Holes")
name_part(base_body, "Base plate", AL, "#3a434c", "satin", method="SCS", notes="6 mm 6061, SCS laser cut with holes; hand-tap the M4 skin holes")
S_FOOT = studio("Rubber foot")
res = cyl(0, 0, 15, 0, EN["feet_h"], "new", "Foot")
foot_body = new_body(res)
name_part(foot_body, "Rubber foot 30 x 15, M6 insert", None, "#1d1d1d", "satin", method="buy")
for p in FEET:
    J("feet", "ISO 4762", "M6", [p[0], p[1], BASE[1]], "-z", L=16, label="foot screw")

S_SUP = studio("Floor support block")
res = box(-SUP / 2, SUP / 2, -SUP / 2, SUP / 2, FI[0], FLOOR[0], "new", "Block")
sup_body = new_body(res)
cut_through([circ([0, 0], CLR["M8"])], FLOOR[0], "Tie rod bore")
name_part(sup_body, "Floor support block (G10, thermal break)", None, "#c9c27a", "satin", method="buy + mill",
          notes="G10/FR4 30 mm square bar, cut to 50 mm, faced and drilled Ø9 on the mill (2 setups)")

# ---------------------------------------------------------------- door (built flat: local x across, local y = world z,
# local z = thickness, 0 at the chamber side). Pan + inner sheet riveted together, boards inside, both panes bonded.
S_DOOR = studio("Door")
win = EN["window"]
wx0, wx1 = BX - win["w"] / 2, BX + win["w"] / 2
wz0, wz1 = win["cz"] - win["h"] / 2, win["cz"] + win["h"] / 2
DZ = (FI[0], PT)
gt = EN["glass_t"]
res = box(-DW, DW, DZ[0], DZ[1], WT - SK, WT, "new", "Face")
door_pan = new_body(res)
box(-DW, -DW + SK, DZ[0], DZ[1], 0, WT - SK, "add", "Wall")
box(DW - SK, DW, DZ[0], DZ[1], 0, WT - SK, "add", "Wall")
box(-DW + SK, DW - SK, DZ[0], DZ[0] + SK, 0, WT - SK, "add", "Wall")
box(-DW + SK, DW - SK, DZ[1] - SK, DZ[1], 0, WT - SK, "add", "Wall")
cut_through([{"type": "rect", "corner1": [wx0, wz0], "corner2": [wx1, wz1]}], WT, "Window")
name_part(door_pan, "Door outer pan", AL, "#4b5865", "satin", method="SCS",
          notes="2 mm 5052, SCS laser cut and bent into a tray (4 bends, corner reliefs), window cut out")
S_DINNER = studio("Door inner sheet")
res = box(-DW + SK, DW - SK, DZ[0] + SK, DZ[1] - SK, 0, 1, "new", "Sheet")
door_inner = new_body(res)
box(-DW + SK, -DW + SK + 1, DZ[0] + SK, DZ[1] - SK, 1, 16, "add", "Flange")
box(DW - SK - 1, DW - SK, DZ[0] + SK, DZ[1] - SK, 1, 16, "add", "Flange")
box(-DW + SK + 1, DW - SK - 1, DZ[0] + SK, DZ[0] + SK + 1, 1, 16, "add", "Flange")
box(-DW + SK + 1, DW - SK - 1, DZ[1] - SK - 1, DZ[1] - SK, 1, 16, "add", "Flange")
cut_through([{"type": "rect", "corner1": [wx0, wz0], "corner2": [wx1, wz1]}], 16, "Window")
name_part(door_inner, "Door inner sheet (hot face)", "Stainless steel", "#a7adb3", "satin", method="SCS",
          notes="1 mm 304 stainless, SCS laser cut and bent, riveted to the pan walls")
CI = (-DW + SK + 1, DW - SK - 1, DZ[0] + SK + 1, DZ[1] - SK - 1)
GM = 10.0
S_DCORE = studio("Door core")
res = box(CI[0], CI[1], CI[2], CI[3], 1, 1 + HL, "new", "Core hot")
door_core_h = new_body(res)
res = box(CI[0], CI[1], CI[2], CI[3], 1 + HL, WT - SK, "new", "Core PIR")
door_core_p = new_body(res)
cut_through([{"type": "rect", "corner1": [wx0 - GM - 2, wz0 - GM - 2], "corner2": [wx1 + GM + 2, wz1 + GM + 2]}], WT, "Window")
name_part(door_core_h, "Door core, hot-face board", None, "#d9d2bf", "matte", method="cut")
name_part(door_core_p, "Door core, PIR board", None, "#e2c75a", "matte", method="cut")
S_GLASS = studio("Door glass")
res = box(wx0 - GM, wx1 + GM, wz0 - GM, wz1 + GM, 1, 1 + gt, "new", "Inner pane")
glass_in = new_body(res)
res = box(wx0 - GM, wx1 + GM, wz0 - GM, wz1 + GM, WT - SK - gt, WT - SK, "new", "Outer pane")
glass_out = new_body(res)
name_part(glass_in, "Door glass, inner (borosilicate)", None, "#9fc3d6", "glass", method="buy",
          notes="cut to size, bonded to the inner sheet with high-temperature RTV silicone")
name_part(glass_out, "Door glass, outer (tempered)", None, "#9fc3d6", "glass", method="buy",
          notes="cut to size, bonded behind the pan face with RTV silicone")
# door rivets (door frame): pan walls to the inner sheet flanges
for yy in (DZ[0] + 40, (DZ[0] + DZ[1]) / 2, DZ[1] - 40):
    J("door", ("studio", RIV), None, [-DW, yy, 8], "+x", label="rivet")
    J("door", ("studio", RIV), None, [DW, yy, 8], "-x", label="rivet")
for xx in (-150, 0, 150):
    J("door", ("studio", RIV), None, [xx, DZ[0], 8], "+y", label="rivet")
    J("door", ("studio", RIV), None, [xx, DZ[1], 8], "-y", label="rivet")

# hinges (bought, lift-off, stainless) and handle, in world
S_HW = studio("Door hardware")
hinges = []
HZ = (DZ[0] + 50, DZ[1] - 50)
for hz in HZ:
    res = cyl(-DW, -OW - 4, 3, hz - 25, hz + 25, "new", "Knuckle")
    h_ = new_body(res)
    box(-DW, -DW + 30, -OW - 2, -OW, hz - 25, hz + 25, "add", "Door leaf")
    box(-DW - 3, -DW, -OW - 7, -OW - 2, hz - 25, hz + 25, "add", "Neck")
    box(-JX, -DW - 1, -OW - 7, -OW - 5, hz - 25, hz + 25, "add", "Jamb leaf")
    box(-JX, -DW - 1, -OW - 5, -JX, hz - 25, hz + 25, "add", "Jamb pad")
    name_part(h_, "Door hinge, lift-off, stainless", "Stainless steel", "#a7adb3", "metal", method="buy")
    hinges.append(h_)
    for dz in (-15, 15):
        J("doorhw", "ISO 7380", "M4", [-DW + 20, -OW - 2, hz + dz], "+y", L=8, label="hinge screw")
        J("doorhw", "ISO 4032", "M4", [-DW + 20, -OW + SK, hz + dz], "+y", label="hinge nut")
        J("doorhw", "ISO 7380", "M4", [-JX + FL_W / 2 - 1, -OW - 7, hz + dz], "+y", L=16, label="jamb screw")
        J("doorhw", "ISO 4032", "M4", [-JX + FL_W / 2 - 1, -JX + SK, hz + dz], "+y", label="jamb nut")
res = box(DW - 40, DW - 25, -OW - 30, -OW - 22, -230, -110, "new", "Handle bar")
handle_body = new_body(res)
box(DW - 40, DW - 25, -OW - 22, -OW, -230, -220, "add", "Handle foot low")
box(DW - 40, DW - 25, -OW - 22, -OW, -120, -110, "add", "Handle foot high")
name_part(handle_body, "Door handle with roller catch", "Stainless steel", "#a7adb3", "metal", method="buy")
for zz in (-225, -115):
    J("doorhw", "ISO 4762", "M5", [DW - 32.5, -OW + SK, zz], "-y", L=12, label="handle screw")

# ---------------------------------------------------------------- shutter over the cutout
ST = SHU["strip_t"]
SZ0 = PT + 0.5
SXE = CUT + 6                          # strip ends overlap the plate by 6 mm and slide on PTFE pads
COL = THM.column_world(THL)            # the hotend column (hotend + duct riser) that drops through the shutter
S_STRIP = studio("Shutter strip")
SB0, SB1 = COL[2] - 8, COL[3] + 6      # band around the column
res = box(-SXE, SXE, SB0, SB1, SZ0, SZ0 + ST, "new", "Strip")
strip_body = new_body(res)
cut_through([{"type": "rect", "corner1": [-G["travel"] + COL[0] - 2, COL[2] - 1.5],
              "corner2": [G["travel"] + COL[1] + 2, COL[3] + 1.5]}], SZ0 + ST, "Column slot")
rr = SHU["roller_r"]
for sx in (-1, 1):   # reels just outside the cutout edge, clear of the column at full travel
    sid = sketch(plane_y(SB1 - 2), [{"type": "circle", "center": [sx * (CUT + 2), SZ0 + ST + rr], "radius": rr}], "X cover roller")
    extrude(sid, SB1 - SB0 - 4, "add", "X cover roller")
name_part(strip_body, "Shutter strip with X-cover spring reels (moves in Y)", "PPS-CF", "#8c6f4e", "satin", method="print",
          notes="PPS-CF printed flat (2 mm plate, supportless); the two bought spring-tape reels clip into it")
S_NPLATE = studio("Shutter column plate")
res = box(COL[0] - 1.5, COL[1] + 1.5, COL[2] - 6, COL[3] + 6, SZ0 + ST + 0.5, SZ0 + ST + 2, "new", "Plate")
nplate_body = new_body(res)
box(COL[0] - 0.5, COL[1] + 0.5, COL[2] - 0.5, COL[3] + 0.5, SZ0 + ST + 0.5, SZ0 + ST + 2, "remove", "Column hole")
name_part(nplate_body, "Shutter column plate (X covers attach here)", AL, "#c0c6cc", "metal", method="SCS",
          notes="1.5 mm aluminium, SCS cut; rides on the strip, pushed by the hotend column, X tapes bonded to it")
S_YROLL = studio("Shutter Y roller")
yr = SHU["y_roller_r"]
res = cyl_x(0, 7, yr, -(CUT - 3), CUT - 3, "new", "Roller")
yroll_body = new_body(res)
name_part(yroll_body, "Y-cover spring reel, stainless tape (in a plate pocket)", None, "#8c6f4e", "satin", method="buy")
YROLL_Y = CUT + 6

# ---------------------------------------------------------------- chamber heater: PTC block + blower, motor in the bay
S_HEAT = studio("Chamber heater")
res = box(HT["x"][0], HT["x"][1], HT["y"][0], HT["y"][1], FLOOR[1], HT["top"], "new", "Housing")
cheat_body = new_body(res)
name_part(cheat_body, f"Chamber heater: 2 x PTC, {HT['power_w']} W + blower wheel (stand-in)", None, "#8d8f91", "metal", method="buy")
for p in HEAT_H:
    J("heat", "ISO 4762", "M4", [p[0], p[1], FLOOR[1] + 8], "-z", L=12, label="heater screw")
S_HMOT = studio("Heater fan motor")
res = box(HSX - 25, HSX + 25, HSY - 25, HSY + 25, BAY[0] + 8, BAY[0] + 48, "new", "Motor")
hmot_body = new_body(res)
box(HSX - 25, HSX + 25, HSY - 25, HSY + 25, BAY[0], BAY[0] + 8, "add", "Foot plate")
name_part(hmot_body, "Heater blower motor (BLDC, foot-mounted, in the cool bay)", None, "#2b2b2b", "satin", method="buy")
for p in HM_H:
    J("heat", "ISO 4762", "M4", [p[0], p[1], BASE[0]], "+z", L=12, label="heater motor screw")

# ---------------------------------------------------------------- back module contents
FZ = (SPL + 5, PT + 40)                # filter parts stand on printed cradles on the divider
S_FILT = studio("Filter loop")
fparts, cradles = [], []
FILT = ((-175, -65, BY0 + 6, BY1 - 6, "Air-to-air cooler (finned, ambient side vented)", "#9aa3ab"),
        (-60, -20, BY0 + 10, BY1 - 10, "HEPA H13 filter", "#e9e6dc"),
        (-15, 65, BY0 + 10, BY1 - 10, "Activated carbon filter", "#3b3b3b"),
        (80, 180, BY0 + 8, BY0 + 42, "Filter loop blower (radial 97 mm)", "#2b2b2b"))
for x0_, x1_, y0_, y1_, nm_, col_ in FILT:
    res = box(x0_, x1_, y0_, y1_, FZ[0], FZ[1], "new", nm_)
    b_ = new_body(res); name_part(b_, nm_, None, col_, "satin", method="buy"); fparts.append((b_, nm_))
S_CRAD = studio("Filter cradles")
for k, (x0_, x1_, y0_, y1_, nm_, _) in enumerate(FILT):
    y0c, y1c = max(y0_ - 2.4, OW + 1), min(y1_ + 2.4, BY1 - SK - 1)
    res = box(x0_ - 2.4, x1_ + 2.4, y0c, y1c, SPL + 1, FZ[0] + 15, "new", f"Cradle {k}")
    b_ = new_body(res)
    box(x0_, x1_, y0_, y1_, FZ[0], FZ[0] + 15, "remove", "Pocket")
    cut_through([circ([(x0_ + x1_) / 2 + sx * ((x1_ - x0_) / 2 - 8), (y0_ + y1_) / 2], CLR["M4"]) for sx in (-1, 1)], FZ[0], "Screw holes")
    name_part(b_, f"Cradle for {nm_.split(' (')[0]}", "PET-CF", "#3c3f44", "satin", method="print",
              notes="PET-CF, printed as it sits (open tray, no overhangs)")
    cradles.append((b_, f"Filter cradle {k + 1}"))
    for sx in (-1, 1):
        px = (x0_ + x1_) / 2 + sx * ((x1_ - x0_) / 2 - 8)
        J("module", "ISO 4762", "M4", [px, (y0_ + y1_) / 2, FZ[0] - 0.01], "-z", L=10, label="cradle screw")
        J("module", "ISO 4032", "M4", [px, (y0_ + y1_) / 2, SPL - 1 - 3.2], "+z", label="cradle nut")

S_DUCT = studio("Filter ducts")
res = cyl_y(-120, DUCT_Z, 20, SPF, BY0 + 6, "new", "Outlet")
duct_out = new_body(res)
res = cyl_y(130, DUCT_Z, 20, SPF, BY0 + 8, "new", "Return")
duct_ret = new_body(res)
cyl_y(-120, DUCT_Z, 18.5, SPF, BY0 + 6, "remove", "Outlet bore")
cyl_y(130, DUCT_Z, 18.5, SPF, BY0 + 8, "remove", "Return bore")
for b_, n_ in ((duct_out, "outlet"), (duct_ret, "return")):
    name_part(b_, f"Filter duct, chamber {n_} (stainless tube 40 x 1.5)", "Stainless steel", "#a7adb3", "metal", method="buy",
              notes="bought tube cut to length; slip-fit through the back wall, sealed with high-temp silicone")

EZ = (BAY[0] + 10, SPL - 10)
S_ELEC = studio("Electronics")
eparts = []
ELEC = ((-200, -40, BY0 + 6, BY0 + 26, BAY[0] + 106, BAY[0] + 206, "BTT Kraken (on standoffs)", "#1d5c3a"),
        (-20, 195, BY0 + 6, BY0 + 36, BAY[0] + 136, BAY[0] + 251, "PSU 48 V (LRS-350-48 class)", "#a7adb3"),
        (-20, 195, BY0 + 6, BY0 + 36, BAY[0] + 16, BAY[0] + 116, "PSU 24 V (LRS-350-24 class)", "#a7adb3"),
        (-200, -120, BY1 - 27, BY1 - 2, BAY[0] + 16, BAY[0] + 96, "Electronics fan 80 mm, intake", "#2b2b2b"),
        (-110, -30, BY1 - 27, BY1 - 2, BAY[0] + 16, BAY[0] + 96, "Electronics fan 80 mm, exhaust", "#2b2b2b"),
        (-200, -130, BY0 + 6, BY0 + 46, BAY[0] + 214, BAY[0] + 256, "Raspberry Pi / host + relays", "#1d5c3a"))
for x0_, x1_, y0_, y1_, z0_, z1_, nm_, col_ in ELEC:
    res = box(x0_, x1_, y0_, y1_, z0_, z1_, "new", nm_)
    b_ = new_body(res); name_part(b_, nm_, None, col_, "satin", method="buy"); eparts.append((b_, nm_))
    if y0_ == BY0 + 6:                       # on the backplate
        for sx in (-1, 1):
            for sz in (-1, 1):
                J("module", "ISO 4762", "M3", [(x0_ + x1_) / 2 + sx * ((x1_ - x0_) / 2 - 6), EPY[0], (z0_ + z1_) / 2 + sz * ((z1_ - z0_) / 2 - 6)],
                  "+y", L=10, label="electronics screw")
    else:                                    # fans on the lower cover
        cx_, cz_ = (x0_ + x1_) / 2, (z0_ + z1_) / 2
        for sx in (-1, 1):
            for sz in (-1, 1):
                J("module", "ISO 4762", "M4", [cx_ + sx * 36, SKY1, cz_ + sz * 36], "-y", L=12, label="fan screw")

# ---------------------------------------------------------------- top bay: fans in the back wall, part-cooling blower
S_TBAY = studio("Top bay")
tparts = []
for (cx_, cz_), nm_ in zip(TB_FANS, ("Top bay fan 80 mm, intake", "Top bay fan 80 mm, exhaust")):
    res = box(cx_ - 40, cx_ + 40, OW - SK - 25, OW - SK, cz_ - 40, cz_ + 40, "new", nm_)
    b_ = new_body(res); name_part(b_, nm_, None, "#2b2b2b", "satin", method="buy"); tparts.append((b_, nm_))
    for sx in (-1, 1):
        for sz in (-1, 1):
            J("module", "ISO 4762", "M4", [cx_ + sx * 36, OW, cz_ + sz * 36], "-y", L=12, label="fan screw")
res = box(-40, 57, OW - SK - 33, OW - SK, 120, 205, "new", "Part-cooling blower")
b_ = new_body(res); name_part(b_, "Part-cooling blower (server type, hose to the toolhead duct)", None, "#2b2b2b", "satin", method="buy")
tparts.append((b_, "Part-cooling blower (server type, hose to the toolhead duct)"))
for p in ((-30, 130), (47, 130), (-30, 195), (47, 195)):
    J("module", "ISO 4762", "M4", [p[0], OW, p[1]], "-y", L=12, label="blower screw")

# ---------------------------------------------------------------- toolhead detail, in the toolhead frame
# (cad/toolhead.py: u along the gearbox drive shafts, v across; placed rotated by THL["rot"]). Above the shutter,
# under the extruder carrier: the gearbox round the filament and the motor across the beam cross, joined by a
# coupling and a jackshaft. Through the shutter: the hotend and the duct riser. Under the plate: the nozzle,
# the duct ring and the Beacon on a pad of the duct.
NOZ_ = THL["NOZ"]
S_TDET = studio("Toolhead")
tdet = []
def tpart(nm_, res, color, material=None, method="buy", notes=""):
    b_ = new_body(res); name_part(b_, nm_, material, color, "satin", method=method, notes=notes); tdet.append((b_, nm_))
def tbox(b, op="new", name=None):
    return box(b[0], b[1], b[2], b[3], b[4], b[5], op, name)
RS, FD, RG, BP = THL["RISER"], THL["FEED"], THL["RING"], THL["BPAD"]
res = tbox(RS, "new", "Duct riser")
tbox(FD, "add", "Duct feed")
tbox(BP, "add", "Beacon pad")
cyl(Fu, Fv, RG[0], RG[2], RG[3], "add", "Duct ring")
cyl(Fu, Fv, RG[1], RG[2], RG[3], "remove", "Ring bore")
BB_ = THL["BARB"]
sid = sketch(plane_y(BB_[1]), [{"type": "circle", "center": [BB_[0], BB_[2]], "radius": 4.5}], "Hose barb")
extrude(sid, 10, "add", "Hose barb")
sid = sketch(plane_y(BB_[1] + 2), [{"type": "circle", "center": [BB_[0], BB_[2]], "radius": 3.0}], "Barb bore")
extrude(sid, 12, "remove", "Barb bore")
box(RS[0] + 2, RS[1] - 2, RS[2] + 2, RS[3] - 2, FD[4] + 2, RS[5] - 2, "remove", "Riser channel")
box(FD[0], FD[1], FD[2] + 2, FD[3] - 2, FD[4] + 2, FD[5] - 2, "remove", "Feed channel")
pocket_up([circ(p, 4.0) for p in THL["BCN_H"]], BP[4], 3.5, "Beacon heat-set inserts")
tpart("Part-cooling duct with Beacon pad (riser through the shutter)", res, "#3c3f44", "PPS-CF", "print",
      "PPS-CF, printed standing on the riser top; feed and ring channel roofs are <= 6 mm bridges, Beacon pad prints flat off the riser, "
      "no supports; 2 M3 heat-set inserts for the Beacon; hose from the gantry-bay blower on the barb")
GB = THL["GB"]
tpart("Extruder gearbox (Sherpa Heavy style, pinion on the jackshaft)", tbox(GB, "new", "Extruder gearbox"), "#c4572a")
tpart("Extruder motor (36 mm, in the gantry bay)", tbox(THL["MOT"], "new", "Extruder motor"), "#2b2b2b")
CP_, JSH = THL["CPL"], THL["JSH"]
tpart("Extruder shaft coupling (5-5 flexible coupling D12)", cyl_x(VM, AX, 6, CP_[0], CP_[1], "new", "Coupling"), "#b8bec4", "Aluminium 6061")
tpart("Extruder jackshaft (5 mm ground, in two 685 bearings in the gearbox)", cyl_x(VM, AX, 2.5, JSH[0], JSH[1], "new", "Jackshaft"),
      "#9aa3ab", "Steel")
CH_ = THL["CHUBE"]
tpart("Chube Conduction hotend", cyl(Fu, Fv, CH_[0], CH_[1], CH_[2], "new", "Chube"), "#b8bec4")
NZ_ = THL["NOZZLE"]
tpart("Nozzle", cyl(Fu, Fv, NZ_[0], NZ_[1], NZ_[2], "new", "Nozzle"), "#c9a227", "Brass")
tpart("Beacon3D probe", tbox(THL["BEACON"], "new", "Beacon"), "#1d1d1d")
for p in THL["BCN_H"]:
    J("th", "ISO 4762", "M3", [p[0], p[1], NOZ_ + 2], "+z", L=16, label="Beacon screw")

# ---------------------------------------------------------------- holes for every sheet-metal fastener (drilled after
# all joint lists exist; SCS cuts them with the blanks)
def door_tf(p, d):
    q = [p[0], p[2], -(p[1] + W / 2)]
    dd = {"+x": "+x", "-x": "-x", "+y": "-z", "-y": "+z", "+z": "+y", "-z": "-y"}[d]
    return q, dd
SHEETS = [(S_SKL, ["skin", "doorhw"], ((-OW, -JX + FL_W), (-OW, SKY1), (BAY[0], LID)), None),
          (S_SKR, ["skin", "doorhw"], ((JX - FL_W, OW), (-OW, SKY1), (BAY[0], LID)), None),
          (S_SKB, ["skin", "module"], ((-JX, JX), (OW - SK, OW + FL_W), (BAY[0], LID)), None),
          (S_SKF, ["skin"], ((-JX, JX), (-OW, -JX + FL_W), (BAY[0], LID)), None),
          (S_LID, ["skin"], ((-OW, OW), (-OW, SKY1), (LID, LID + SK)), None),
          (S_BCOV, ["skin", "module"], ((-JX, JX), (BY1, SKY1), (BAY[0], LID)), None),
          (S_DIV, ["skin", "module"], ((-JX, JX), (OW, BY1), (SPL - 1 - FL_W, SPL + 1)), None),
          (S_EPL, ["skin", "module"], ((-JX, JX), (EPY[0], EPY[1] + FL_W), (BAY[0], SPL)), None),
          (S_DOOR, ["door", "doorhw"], ((-DW, DW), (DZ[0], DZ[1]), (0, WT)), "door"),
          (S_DINNER, ["door"], ((-DW, DW), (DZ[0], DZ[1]), (0, WT)), "door"),
          (S_HW, ["doorhw"], ((-OW, DW), (-OW - 10, -JX + SK), (DZ[0], DZ[1])), None)]
for st_, keys_, bb_, tf_ in SHEETS:
    r("switch_part_studio", index=st_)
    if tf_ == "door":
        drill(["door"], bb_)
        drill(["doorhw"], bb_, door_tf)
    else:
        drill(keys_, bb_)
