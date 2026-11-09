"""Toolhead layout and centre of mass. Plain Python (no rCAD), so it runs on its own:

    python3 cad/toolhead.py          # prints the mass table and where the centre of mass is

build.py uses layout() for the geometry, so the model and this check always agree.

The toolhead is laid out in its own frame:
  origin  the beam cross: the yoke centre, where the two MGN9 rail lines cross
  u       along the diagonal from the cross to the filament axis
  v       across it (u, v, z right-handed)
  z       world z (0 = top plate underside)
The Part Studios for the toolhead plate, Beacon bracket and toolhead detail are drawn in this
frame and placed rotated by `rot` degrees about z.

Why: the filament has to drop past both beams, so the nozzle sits in an open quadrant, (18, 25)
from the cross. If the extruder, motor, hotend and Beacon all sit around the nozzle, the centre of
mass is off both rail lines and every acceleration twists the MGN9 carriages. So everything heavy
is arranged along that diagonal: the hotend and the Sherpa-style gearbox on the nozzle side, and
the extruder motor across the cross as the counterweight, driving the gearbox's pinion through a
coupling and a short jackshaft. The motor position is set so the centre of mass lands on the cross.
"""
import math

RHO = {"7075": 2.81e-3, "steel": 7.85e-3, "print": 1.45e-3}    # g/mm3 (PPS-CF about 1.45)


def layout(P):
    TH, G = P["toolhead"], P["gantry"]
    FX, FY = TH["offset"]
    FU = math.hypot(FX, FY)                       # nozzle distance from the cross, along u
    rot = math.degrees(math.atan2(FY, FX))
    PT = P["frame"]["plate_t"]
    Y_CAR_FACE, X_CAR_FACE = G["y_beam_bot"] - 10, G["x_beam_bot"] - 10
    YOKE_T = 6
    TP_TOP = TH["body_top"]
    TP_T = 6.0
    TP_BOT = TP_TOP - TP_T
    NOZ = TP_TOP - TH["height"]
    NECK_TOP = Y_CAR_FACE - YOKE_T
    MF = TH["motor_face_u"]                       # extruder motor mounting face, u
    L = {"FU": FU, "rot": rot, "TP_TOP": TP_TOP, "TP_BOT": TP_BOT, "TP_T": TP_T, "NOZ": NOZ, "MF": MF}

    # Sherpa-style gearbox around the filament: drive shafts along u, drive gears either side of
    # the filament, the big gear on the cross side. Its 10T pinion sits on the jackshaft axis.
    GB = (FU - 14, FU + 10, -19.5, 16.0, TP_BOT - 38, TP_BOT)          # u0 u1 v0 v1 z0 z1
    JS_Z = TP_BOT - 30                                                 # jackshaft / motor axis z
    L.update(GB=GB, JS_Z=JS_Z)
    # motor (36 mm square, 20 mm body) on the cross side; its face on the plate's flange
    FL_T = 5.0                                                         # motor flange thickness
    MOT = (MF - 20, MF, -18, 18, JS_Z - 18, JS_Z + 18)
    CPL = (MF + FL_T + 2, MF + FL_T + 20)                              # flexible coupling, u range, D14
    JSH = (CPL[0] + 9, GB[0] + 10)                                     # 5 mm jackshaft, u range (into the gearbox bearings)
    L.update(FL_T=FL_T, MOT=MOT, CPL=CPL, JSH=JSH)

    # toolhead plate (7075, 6 mm): a band along the diagonal, the neck footprint, and the motor
    # flange with two side cheeks hanging under it (milled from the bottom)
    BAND = (MF - 22, FU + 12, -28.0, 23.0)
    FLANGE = (MF, MF + FL_T, -22.5, 22.5, JS_Z - 21, TP_BOT)
    CHEEKS = [(MF - 20, MF, s0, s1, JS_Z, TP_BOT) for s0, s1 in ((-22.5, -18.5), (18.5, 22.5))]
    L.update(BAND=BAND, FLANGE=FLANGE, CHEEKS=CHEEKS)
    # neck screws (world frame, in the neck wall ends): chosen clear of the gearbox, flange, duct and Beacon bracket
    L["TPN_W"] = [[-19.5, 19.0], [19.5, -19.0], [19.5, 0.0], [-19.5, -19.0]]
    # air outlet from the hollow neck into the duct plenum (inside the neck's pocket)
    L["AIR"] = (-2.0, 11.0, -5.0, 9.0)

    # part-cooling duct: plenum under the plate, riser beside the jackshaft, feed into a ring at the nozzle
    L["PLEN"] = (-5.0, 14.0, -8.0, 21.0, TP_BOT - 6, TP_BOT)
    L["RISER"] = (2.0, 14.0, 8.0, 20.0, NOZ + 4, TP_BOT - 6)
    L["FEED"] = (8.0, FU - 6, 6.0, 16.0, NOZ + 2, NOZ + 8)
    L["RING"] = (14.0, 7.0, NOZ + 2, NOZ + 8)                          # outer r, bore r, z0, z1 (at the nozzle)
    L["DUCT_H"] = [[-3.5, -6.5], [12.5, -6.5], [4.0, 19.5]]          # countersunk from the plate top, inside the neck pocket

    # Beacon on the cross side of the nozzle, on a printed C bracket
    L["BEACON"] = (-9.0, 17.0, -22.0, -8.0, NOZ + 3, NOZ + 15)
    L["BB_TOP"] = (8.0, 20.0, -27.0, -20.0, TP_BOT - 5, TP_BOT)
    L["BB_WEB"] = (8.0, 20.0, -27.0, -24.0, NOZ + 15, TP_BOT - 5)
    L["BB_BOT"] = (-9.0, 20.0, -27.0, -12.0, NOZ + 15, NOZ + 19)
    L["BB_H"] = [[11.0, -24.0], [17.0, -24.0]]                       # bracket to plate, countersunk from the top
    L["BCN_H"] = [[-4.0, -15.0], [12.0, -15.0]]                      # Beacon to bracket
    L["EXT_H"] = [[GB[0] + 5, 13.0], [GB[1] - 3, 13.0], [GB[0] + 5, -16.0], [GB[1] - 3, -16.0]]
    L["MOT_H"] = [[sv * 13, JS_Z + sz * 13] for sv in (-1, 1) for sz in (-1, 1)]   # NEMA14 36 mm, 26 mm square
    L["CHUBE"] = (11.0, NOZ + 12, GB[4])
    L["NOZZLE"] = (3.5, NOZ, NOZ + 12)

    # world-frame things that move with the yoke (symmetric about the cross unless noted)
    L["Y_CAR_FACE"], L["X_CAR_FACE"], L["NECK_TOP"], L["YOKE_T"] = Y_CAR_FACE, X_CAR_FACE, NECK_TOP, YOKE_T
    return L


def to_world(L, u, v):
    c, s = math.cos(math.radians(L["rot"])), math.sin(math.radians(L["rot"]))
    return [c * u - s * v, s * u + c * v]


def to_local(L, x, y):
    c, s = math.cos(math.radians(L["rot"])), math.sin(math.radians(L["rot"]))
    return [c * x + s * y, -s * x + c * y]


def _box(b):
    u0, u1, v0, v1, z0, z1 = b
    return (u1 - u0) * (v1 - v0) * (z1 - z0), [(u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2]


def _plate(L, P):
    """Toolhead plate volume and centroid: band + neck footprint (sampled on a 0.5 mm grid), less the holes, plus flange and cheeks."""
    nx, ny = P["toolhead"]["neck"]
    BAND, h = L["BAND"], 0.5
    a = m_u = m_v = 0.0
    lo, hi = -60.0, 60.0
    n = int((hi - lo) / h)
    for i in range(n):
        u = lo + (i + 0.5) * h
        for j in range(n):
            v = lo + (j + 0.5) * h
            x, y = to_world(L, u, v)
            inside = (BAND[0] <= u <= BAND[1] and BAND[2] <= v <= BAND[3]) or (abs(x) <= nx / 2 and abs(y) <= ny / 2)
            if not inside:
                continue
            ax = L["AIR"]
            if ax[0] <= u <= ax[1] and ax[2] <= v <= ax[3]:
                continue
            a += h * h; m_u += u * h * h; m_v += v * h * h
    vol = a * L["TP_T"]
    parts = [(vol, [m_u / a, m_v / a, (L["TP_TOP"] + L["TP_BOT"]) / 2])]
    for b in [L["FLANGE"]] + L["CHEEKS"]:
        parts.append(_box(b))
    # motor pilot hole in the flange
    fl = L["FLANGE"]
    parts.append((-math.pi * 11.5 ** 2 * L["FL_T"], [(fl[0] + fl[1]) / 2, 0, L["JS_Z"]]))
    V = sum(p[0] for p in parts)
    c = [sum(p[0] * p[1][k] for p in parts) / V for k in range(3)]
    return V, c


def masses(P):
    """[(name, grams, [u, v, z])] for everything the two MGN9H carriages carry."""
    L = layout(P)
    TH = P["toolhead"]
    MG = TH["mass_g"]
    nx, ny = TH["neck"]
    out = []
    # yoke, neck and carriages: centred on the cross
    yw, YK_Y, LEG_IN = 22.0, 12.5 + 9, 12.5 + 3
    yc, xc, YT = L["Y_CAR_FACE"], L["X_CAR_FACE"], L["YOKE_T"]
    vU = 2 * yw * 2 * YK_Y * YT + 2 * (2 * yw * (YK_Y - LEG_IN) * (xc - YT - yc))
    out.append(("Yoke U (7075)", vU * RHO["7075"], [0, 0, (yc - YT + xc - YT) / 2]))
    out.append(("Yoke top plate (7075)", 2 * yw * 2 * YK_Y * YT * RHO["7075"], [0, 0, xc - YT / 2]))
    hN = L["NECK_TOP"] - L["TP_TOP"]
    vN = nx * ny * hN - (nx - 10) * (ny - 10) * (hN - 4)
    out.append(("Toolhead neck (7075)", vN * RHO["7075"], [0, 0, (L["NECK_TOP"] + L["TP_TOP"]) / 2]))
    out.append(("MGN9H carriage, Y beam", MG["mgn9h"], [0, 0, yc + 5]))
    out.append(("MGN9H carriage, X beam", MG["mgn9h"], [0, 0, xc + 5]))
    ad = to_local(L, -5.0, ny / 2 + 5)
    out.append(("Neck air adapter (PPS-CF)", MG["air_adapter"], [ad[0], ad[1], 20.0]))
    # toolhead
    V, c = _plate(L, P)
    out.append(("Toolhead plate with motor flange (7075)", V * RHO["7075"], c))
    out.append(("Extruder motor (LDO high-temp, 36 mm)", MG["motor"], _box(L["MOT"])[1]))
    out.append(("Shaft coupling", MG["coupling"], [(L["CPL"][0] + L["CPL"][1]) / 2, 0, L["JS_Z"]]))
    js = L["JSH"]
    out.append(("Jackshaft 5 mm", math.pi * 2.5 ** 2 * (js[1] - js[0]) * RHO["steel"], [(js[0] + js[1]) / 2, 0, L["JS_Z"]]))
    out.append(("Extruder gearbox (Sherpa-style, with gears and bearings)", MG["gearbox"], _box(L["GB"])[1]))
    out.append(("Chube Conduction hotend with nozzle", MG["hotend"], [L["FU"], 0, (L["NOZZLE"][1] + L["CHUBE"][2]) / 2]))
    out.append(("Beacon3D", MG["beacon"], _box(L["BEACON"])[1]))
    vb = [_box(L[k]) for k in ("BB_TOP", "BB_WEB", "BB_BOT")]
    Vb = sum(x[0] for x in vb)
    out.append(("Beacon bracket (PPS-CF)", Vb * RHO["print"],
                [sum(x[0] * x[1][k] for x in vb) / Vb for k in range(3)]))
    Vd, cd = _duct(L)
    out.append(("Part-cooling duct (PPS-CF)", Vd * RHO["print"], cd))
    out.append(("Wiring and sleeving to the toolhead", MG["wiring"], [L["FU"] / 2, 0, L["TP_BOT"] - 10]))
    return L, out


def _duct(L):
    """Duct volume (outer shapes less the plenum, riser and feed channels) and centroid."""
    PL, RS, FD = L["PLEN"], L["RISER"], L["FEED"]
    parts = [_box(PL), _box(RS), _box(FD)]
    ro, ri, z0, z1 = L["RING"]
    parts.append((math.pi * (ro ** 2 - ri ** 2) * (z1 - z0), [L["FU"], 0, (z0 + z1) / 2]))
    for b in [(PL[0] + 3, PL[1] - 3, PL[2] + 3, PL[3] - 3, PL[4] + 2, PL[5]),
              (RS[0] + 2, RS[1] - 2, RS[2] + 2, RS[3] - 2, FD[4] + 2, PL[4] + 2),
              (FD[0], FD[1], FD[2] + 2, FD[3] - 2, FD[4] + 2, FD[5] - 2)]:
        v, c = _box(b)
        parts.append((-v, c))
    V = sum(p[0] for p in parts)
    return V, [sum(p[0] * p[1][k] for p in parts) / V for k in range(3)]


def com(P):
    L, ms = masses(P)
    M = sum(m for _, m, _ in ms)
    cu = [sum(m * p[k] for _, m, p in ms) / M for k in range(3)]
    return L, ms, M, cu


def report(P):
    L, ms, M, c = com(P)
    w = to_world(L, c[0], c[1])
    lines = [f"{'part':58s} {'g':>6s} {'u':>7s} {'v':>7s} {'z':>7s}"]
    for n, m, p in ms:
        lines.append(f"{n:58s} {m:6.1f} {p[0]:7.1f} {p[1]:7.1f} {p[2]:7.1f}")
    lines.append(f"{'total carried by the two MGN9H carriages':58s} {M:6.1f}")
    lines.append(f"centre of mass: u {c[0]:.2f}  v {c[1]:.2f}  ->  x {w[0]:.2f}  y {w[1]:.2f} from the beam cross; z {c[2]:.1f}")
    lines.append(f"rail planes: Y-beam MGN9H face z {L['Y_CAR_FACE']:.0f}, X-beam MGN9H face z {L['X_CAR_FACE']:.0f}")
    return "\n".join(lines), (w[0], w[1], c[2]), M


def solve_motor_face(P):
    """motor_face_u that puts the centre of mass on the cross (bisection on u)."""
    import copy
    Q = copy.deepcopy(P)
    lo, hi = -40.0, 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        Q["toolhead"]["motor_face_u"] = mid
        if com(Q)[3][0] > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


if __name__ == "__main__":
    import os, yaml
    P = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.yaml")))
    print(report(P)[0])
    print(f"motor_face_u for zero offset along the diagonal: {solve_motor_face(P):.1f}")
