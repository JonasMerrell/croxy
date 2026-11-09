"""Toolhead layout, centre of mass and fit checks. Plain Python (no rCAD), so it runs on its own:

    python3 cad/toolhead.py          # mass table, centre of mass, solved frame and motor position, fit checks

build.py uses layout() for the geometry, so the model and these checks always agree.

Layout (Jonas, 2026-11-09): the extruder rides ABOVE the plate, in the cool gantry bay, under the yoke.
Only a slim column (the hotend and the part-cooling duct riser) drops through the shutter and the plate
cutout to the nozzle. The gearbox sits round the filament; the extruder motor sits across the beam
cross as the counterweight and turns the gearbox pinion through a coupling and a jackshaft that runs
under the yoke. The motor position and the frame angle are solved so the centre of mass of everything
the two MGN9H carriages carry lands on the beam cross (both rail lines).

Frame: origin at the beam cross; u along the gearbox drive shafts (rotated `rot` degrees from world x),
v across, z world (0 = top plate underside). The filament axis is at (Fu, Fv) in this frame.
"""
import copy
import math

RHO = {"7075": 2.81e-3, "steel": 7.85e-3, "print": 1.45e-3}    # g/mm3 (PPS-CF about 1.45)


def _rot(deg):
    return math.cos(math.radians(deg)), math.sin(math.radians(deg))


def to_world(L, u, v):
    c, s = _rot(L["rot"])
    return [c * u - s * v, s * u + c * v]


def to_local(L, x, y):
    c, s = _rot(L["rot"])
    return [c * x + s * y, -s * x + c * y]


def gantry_z(P):
    """World z of the gantry stack the toolhead hangs in."""
    G, F = P["gantry"], P["frame"]
    PT = F["plate_t"]
    Y_CAR_FACE, X_CAR_FACE = G["y_beam_bot"] - 10, G["x_beam_bot"] - 10
    YOKE_T = 6
    return {"PT": PT, "SHUTTER_TOP": PT + F["shutter_h"], "Y_CAR_FACE": Y_CAR_FACE, "X_CAR_FACE": X_CAR_FACE,
            "YOKE_T": YOKE_T, "YOKE_BOT": Y_CAR_FACE - YOKE_T}


def layout(P, rot=None, mf=None):
    TH = P["toolhead"]
    gz = gantry_z(P)
    FX, FY = TH["offset"]
    L = dict(gz)
    L["rot"] = TH["frame_rot"] if rot is None else rot
    MF = TH["motor_face_u"] if mf is None else mf
    Fu, Fv = to_local(L, FX, FY)
    NOZ = TH["nozzle_z"]
    CP_TOP = gz["YOKE_BOT"]                     # carrier plate bolts under the yoke
    CP_T = 6.0
    CP_BOT = CP_TOP - CP_T
    Z0 = gz["SHUTTER_TOP"] + 1.0                # lowest point of anything above the shutter
    AX = Z0 + 18.0                              # motor, jackshaft and gearbox drive shaft axis height
    assert CP_BOT >= Z0 + 36, "no room for the 36 mm motor between the shutter and the yoke: raise the beams"
    L.update(Fu=Fu, Fv=Fv, MF=MF, NOZ=NOZ, CP_TOP=CP_TOP, CP_BOT=CP_BOT, CP_T=CP_T, Z0=Z0, AX=AX)
    # Sherpa-style gearbox: drive shafts along u, the main drive gear at v = Fv - 5.5, its 50T gear meshing the
    # 10T pinion on the jackshaft 15 mm across at v = Fv + 9.5 (same height)
    VM = Fv + 9.5
    GB = (Fu - 14, Fu + 7, Fv - 20, Fv + 14, Z0, CP_BOT)        # u kept short of the end-block bases at full travel
    L.update(VM=VM, GB=GB)
    FL_T = 5.0
    MOT = (MF - 20, MF, VM - 18, VM + 18, AX - 18, AX + 18)
    CPL = (MF + FL_T + 0.5, GB[0] - 0.5)                               # flexible coupling, D12, fills the gap
    assert CPL[1] - CPL[0] >= 10, "no room for the coupling between the motor flange and the gearbox"
    JSH = ((CPL[0] + CPL[1]) / 2, GB[0] + 10)                          # 5 mm jackshaft into the gearbox bearings
    FLANGE = (MF, MF + FL_T, VM - 22.5, VM + 22.5, Z0 + 0.5, CP_BOT)
    CHEEKS = [(MF - 20, MF, VM + s0, VM + s1, AX, CP_BOT) for s0, s1 in ((-22.5, -18.5), (18.5, 22.5))]
    L.update(FL_T=FL_T, MOT=MOT, CPL=CPL, JSH=JSH, FLANGE=FLANGE, CHEEKS=CHEEKS)
    # carrier plate: the yoke footprint plus a band over the gearbox and the motor flange
    L["BAND"] = (MF - 22, GB[1] + 2, min(GB[2], VM - 22.5) - 2, max(GB[3], VM + 22.5) + 2)
    # hotend column through the shutter and the plate
    L["CHUBE"] = (11.0, NOZ + 12, Z0)
    L["NOZZLE"] = (3.5, NOZ, NOZ + 12)
    L["RISER"] = (max(Fu - 27, MF + FL_T + 1), GB[0] - 1, Fv - 6, Fv + 6, NOZ + 4, Z0 + 10)    # duct riser, cross side of the hotend
    L["BARB"] = (L["RISER"][0] + 6.5, Fv - 6, Z0 + 5)                    # hose barb on the riser's -v face, (u, v face, z)
    L["FEED"] = (Fu - 22, Fu - 6, Fv - 5, Fv + 5, NOZ + 2, NOZ + 8)
    L["RING"] = (14.0, 7.0, NOZ + 2, NOZ + 8)
    # Beacon on a printed pad from the riser, on the cross side, fully under the plate
    L["BEACON"] = (Fu - 54, Fu - 28, Fv - 7, Fv + 7, NOZ + 2, NOZ + 14)
    L["BPAD"] = (Fu - 54, Fu - 14, Fv - 9, Fv + 9, NOZ + 14, -2.0)
    L["BCN_H"] = [[Fu - 49, Fv], [Fu - 33, Fv]]
    # gearbox through-bolts (from its underside into the carrier) and motor screws
    L["EXT_H"] = [[GB[0] + 3, GB[2] + 3], [GB[1] - 3, GB[2] + 3], [GB[1] - 3, GB[3] - 3]]
    L["YK_SCR"] = carrier_screws(L, P)
    L["MOT_H"] = [[VM + sv * 13, AX + sz * 13] for sv in (-1, 1) for sz in (-1, 1)]
    return L


def _inside(L, b, x, y, pad):
    u, v = to_local(L, x, y)
    return b[0] - pad <= u <= b[1] + pad and b[2] - pad <= v <= b[3] + pad


def carrier_screws(L, P):
    """Four carrier-to-yoke screws (world xy): inside the yoke footprint, clear of the MGN9H carriage screw heads,
    the filament and everything hanging under the carrier (so they can be reached from below)."""
    yx, yy = _yoke_xy(P)
    car9 = [[sx * 8, sy * 7.5] for sx in (-1, 1) for sy in (-1, 1)]
    FX, FY = P["toolhead"]["offset"]
    under = [L["GB"], L["MOT"], L["FLANGE"], (L["CPL"][0], L["CPL"][1], L["VM"] - 6, L["VM"] + 6, 0, 0)] + L["CHEEKS"]
    ok = []
    for i in range(-40, 41):
        for j in range(-48, 49):
            x, y = i * 0.5, j * 0.5
            if abs(x) > yx - 4 or abs(y) > yy - 4:
                continue
            if any(math.hypot(x - a, y - b) < 7 for a, b in car9) or math.hypot(x - FX, y - FY) < 7:
                continue
            if any(_inside(L, b, x, y, 4.0) for b in under):
                continue
            ok.append((x, y))
    picks = []
    for cx, cy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        best = max(ok, key=lambda p: cx * p[0] + cy * p[1])
        picks.append([best[0], best[1]])
    return picks


def column_world(L, pad=0.0):
    """World xy bounds (relative to the cross) of what passes through the shutter and the plate."""
    pts = []
    r = L["CHUBE"][0]
    for a in range(0, 360, 10):
        pts.append(to_world(L, L["Fu"] + r * math.cos(math.radians(a)), L["Fv"] + r * math.sin(math.radians(a))))
    R = L["RISER"]
    for u in R[:2]:
        for v in R[2:4]:
            pts.append(to_world(L, u, v))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)


def _box(b):
    u0, u1, v0, v1, z0, z1 = b
    return (u1 - u0) * (v1 - v0) * (z1 - z0), [(u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2]


def _yoke_xy(P):
    G = P["gantry"]
    return 22.0, G["beam_w"] / 2 + 12          # yoke half widths in x and y


def _carrier(L, P, h=0.5):
    """Carrier plate volume and centroid: band + yoke footprint on a grid, plus flange and cheeks, less the pilot hole."""
    yx, yy = _yoke_xy(P)
    B = L["BAND"]
    a = mu = mv = 0.0
    lo, hi = -80.0, 80.0
    n = int((hi - lo) / h)
    for i in range(n):
        u = lo + (i + 0.5) * h
        for j in range(n):
            v = lo + (j + 0.5) * h
            x, y = to_world(L, u, v)
            if (B[0] <= u <= B[1] and B[2] <= v <= B[3]) or (abs(x) <= yx and abs(y) <= yy):
                a += h * h; mu += u * h * h; mv += v * h * h
    parts = [(a * L["CP_T"], [mu / a, mv / a, (L["CP_TOP"] + L["CP_BOT"]) / 2])]
    for b in [L["FLANGE"]] + L["CHEEKS"]:
        parts.append(_box(b))
    fl = L["FLANGE"]
    parts.append((-math.pi * 11.5 ** 2 * L["FL_T"], [(fl[0] + fl[1]) / 2, L["VM"], L["AX"]]))
    V = sum(p[0] for p in parts)
    return V, [sum(p[0] * p[1][k] for p in parts) / V for k in range(3)]


def _duct(L):
    R, FD = L["RISER"], L["FEED"]
    ro, ri, z0, z1 = L["RING"]
    parts = [_box(R), _box(FD), _box(L["BPAD"]),
             (math.pi * (ro ** 2 - ri ** 2) * (z1 - z0), [L["Fu"], L["Fv"], (z0 + z1) / 2])]
    for b in [(R[0] + 2, R[1] - 2, R[2] + 2, R[3] - 2, FD[4] + 2, R[5] - 2),
              (FD[0], FD[1], FD[2] + 2, FD[3] - 2, FD[4] + 2, FD[5] - 2)]:
        v, c = _box(b)
        parts.append((-v, c))
    V = sum(p[0] for p in parts)
    return V, [sum(p[0] * p[1][k] for p in parts) / V for k in range(3)]


def masses(P, rot=None, mf=None):
    """[(name, grams, [u, v, z])] for everything the two MGN9H carriages carry."""
    L = layout(P, rot, mf)
    MG = P["toolhead"]["mass_g"]
    yx, yy = _yoke_xy(P)
    LEG_IN = yy - 6
    yc, xc, YT = L["Y_CAR_FACE"], L["X_CAR_FACE"], L["YOKE_T"]
    out = []
    vU = 2 * yx * 2 * yy * YT + 2 * (2 * yx * (yy - LEG_IN) * (xc - YT - yc))
    out.append(("Yoke U (7075)", vU * RHO["7075"], [0, 0, (yc - YT + xc - YT) / 2]))
    out.append(("Yoke top plate (7075)", 2 * yx * 2 * yy * YT * RHO["7075"], [0, 0, xc - YT / 2]))
    out.append(("MGN9H carriage, Y beam", MG["mgn9h"], [0, 0, yc + 5]))
    out.append(("MGN9H carriage, X beam", MG["mgn9h"], [0, 0, xc + 5]))
    V, c = _carrier(L, P)
    out.append(("Carrier plate with motor flange (7075)", V * RHO["7075"], c))
    out.append(("Extruder motor (36 mm)", MG["motor"], _box(L["MOT"])[1]))
    out.append(("Shaft coupling", MG["coupling"], [(L["CPL"][0] + L["CPL"][1]) / 2, L["VM"], L["AX"]]))
    js = L["JSH"]
    out.append(("Jackshaft 5 mm", math.pi * 2.5 ** 2 * (js[1] - js[0]) * RHO["steel"], [(js[0] + js[1]) / 2, L["VM"], L["AX"]]))
    out.append(("Extruder gearbox (Sherpa-style, with gears and bearings)", MG["gearbox"], _box(L["GB"])[1]))
    out.append(("Chube Conduction hotend with nozzle", MG["hotend"], [L["Fu"], L["Fv"], (L["NOZZLE"][1] + L["CHUBE"][2]) / 2]))
    out.append(("Beacon3D", MG["beacon"], _box(L["BEACON"])[1]))
    Vd, cd = _duct(L)
    out.append(("Part-cooling duct with Beacon pad (PPS-CF)", Vd * RHO["print"], cd))
    out.append(("Wiring and sleeving to the toolhead", MG["wiring"], [L["Fu"] / 2, L["Fv"], L["AX"]]))
    return L, out


def com(P, rot=None, mf=None):
    L, ms = masses(P, rot, mf)
    M = sum(m for _, m, _ in ms)
    c = [sum(m * p[k] for _, m, p in ms) / M for k in range(3)]
    return L, ms, M, c


def solve(P):
    """frame_rot and motor_face_u that put the centre of mass on the cross (Newton on the two unknowns)."""
    rot, mf = P["toolhead"]["frame_rot"], P["toolhead"]["motor_face_u"]
    for _ in range(30):
        def f(r_, m_):
            L, _, _, c = com(P, r_, m_)
            return to_world(L, c[0], c[1])
        f0 = f(rot, mf)
        if math.hypot(*f0) < 1e-3:
            break
        fr, fm = f(rot + 0.5, mf), f(rot, mf + 0.5)
        J = [[(fr[0] - f0[0]) / 0.5, (fm[0] - f0[0]) / 0.5], [(fr[1] - f0[1]) / 0.5, (fm[1] - f0[1]) / 0.5]]
        det = J[0][0] * J[1][1] - J[0][1] * J[1][0]
        d_rot = (J[1][1] * f0[0] - J[0][1] * f0[1]) / det
        d_mf = (-J[1][0] * f0[0] + J[0][0] * f0[1]) / det
        rot, mf = rot - d_rot, mf - d_mf
    return rot, mf


def fit_problems(P, L):
    """Rough envelope checks against what closes in at full travel (the rCAD sweep is the real check)."""
    T, G, XY = P["gantry"]["travel"], P["gantry"], P["xy"]
    cut = P["frame"]["cutout"] / 2
    belt_in = XY["belt_line"] - XY["pitch_r"] - XY["belt_t"] / 2          # inner belt strands
    bad = []
    col = column_world(L)
    if max(abs(col[0]), abs(col[1]), abs(col[2]), abs(col[3])) + T > cut - 1:
        bad.append(f"column {col} reaches the cutout edge at full travel")
    above = [L["GB"], L["MOT"], L["FLANGE"]] + L["CHEEKS"]
    for b in above:
        for u in b[:2]:
            for v in b[2:4]:
                x, y = to_world(L, u, v)
                if max(abs(x), abs(y)) + T > belt_in - 1 and b[4] < 46:
                    bad.append(f"{b} corner ({x:.1f}, {y:.1f}) reaches the inner belt strands")
                if min(abs(x), abs(y)) + T > 123 - 1 and b[4] < 57:
                    bad.append(f"{b} corner ({x:.1f}, {y:.1f}) reaches a corner block")
                for a, o in ((x, y), (y, x)):                                    # beam end blocks ride with the toolhead
                    if abs(o) < 22.7 and b[4] < 31 and abs(a) + T > 129.5 - 1:
                        bad.append(f"{b} corner ({x:.1f}, {y:.1f}) reaches an end-block base")
                    if abs(o) < 22.7 and abs(a) + T > 138.3 - 1:
                        bad.append(f"{b} corner ({x:.1f}, {y:.1f}) reaches an end-block upright")
    return bad


def report(P):
    L, ms, M, c = com(P)
    w = to_world(L, c[0], c[1])
    lines = [f"{'part':58s} {'g':>6s} {'u':>7s} {'v':>7s} {'z':>7s}"]
    for n, m, p in ms:
        lines.append(f"{n:58s} {m:6.1f} {p[0]:7.1f} {p[1]:7.1f} {p[2]:7.1f}")
    lines.append(f"{'total carried by the two MGN9H carriages':58s} {M:6.1f}")
    lines.append(f"centre of mass: x {w[0]:.2f}  y {w[1]:.2f} from the beam cross; z {c[2]:.1f}")
    lines.append(f"rail planes: Y-beam MGN9H face z {L['Y_CAR_FACE']:.0f}, X-beam MGN9H face z {L['X_CAR_FACE']:.0f}; nozzle z {L['NOZ']:.0f}")
    lines.append(f"column through the plate (x0, x1, y0, y1): {tuple(round(v, 1) for v in column_world(L))}")
    return "\n".join(lines), (w[0], w[1], c[2]), M


if __name__ == "__main__":
    import os, yaml
    P = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.yaml")))
    print(report(P)[0])
    r_, m_ = solve(P)
    print(f"solved: frame_rot {r_:.2f}, motor_face_u {m_:.2f}")
    for b in fit_problems(P, layout(P)):
        print("FIT:", b)
