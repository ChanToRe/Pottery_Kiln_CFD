#!/usr/bin/env python3
import math
import os
import sys

SLOPE = math.radians(15.0)
W_MAX, H_MAX = 2.20, 1.10
W_RAMP, W_TAPER = 1.00, 0.80
L_COMB = 1.60
APRON = 1.30
W_STOKE, H_STOKE = 0.95, 0.70
W_COMB, H_COMB = 1.25, 0.95
FLUE_W, FLUE_H, FLUE_ANG = 0.55, 0.48, 68.0
D_BURIAL = 1.60
FLUE_RISE = D_BURIAL / math.sin(math.radians(FLUE_ANG))
EPS = 1e-3
N_EXP = 2.4
N_ARCH, N_FLOOR = 48, 16
N_RING = N_ARCH + N_FLOOR
DS = 0.02
STEP_DZ = 0.12
STEP_FRACS = (0.40, 0.70)

TYPES = {"A": (0.0, 0.0), "B": (0.35, 0.0), "C": (0.35, 0.55)}


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, s):
    return (a[0] * s, a[1] * s)


def norm(a):
    return math.hypot(a[0], a[1])


def unit(a):
    n = norm(a)
    return (a[0] / n, a[1] / n) if n else (0.0, 0.0)


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            d = xs[i] - xs[i - 1]
            t = 0.0 if d == 0 else (x - xs[i - 1]) / d
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def section_ring(width, height):
    a, b = width / 2.0, height
    pts = []
    for i in range(N_ARCH):
        phi = math.pi * i / N_ARCH
        c, s = math.cos(phi), math.sin(phi)
        u = a * (1 if c >= 0 else -1) * abs(c) ** (2.0 / N_EXP)
        v = b * abs(s) ** (2.0 / N_EXP)
        pts.append((u, v))
    for i in range(1, N_FLOOR + 1):
        t = i / (N_FLOOR + 1)
        pts.append((-a + 2 * a * t, 0.0))
    return pts


def fillet_path(pts, radii):
    segs = []
    cur = pts[0]
    for i in range(1, len(pts) - 1):
        A, B, C = pts[i - 1], pts[i], pts[i + 1]
        R = radii[i - 1] if i - 1 < len(radii) else 0.0
        u = unit(sub(A, B))
        v = unit(sub(C, B))
        cosang = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
        th = math.acos(cosang)
        if th > math.pi - 1e-6 or R <= 0:
            continue
        t = R / math.tan(th / 2.0)
        T1, T2 = add(B, mul(u, t)), add(B, mul(v, t))
        bis = unit(add(u, v))
        ctr = add(B, mul(bis, R / math.sin(th / 2.0)))
        segs.append(("L", cur, T1))
        a0 = math.atan2(T1[1] - ctr[1], T1[0] - ctr[0])
        a1 = math.atan2(T2[1] - ctr[1], T2[0] - ctr[0])
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        segs.append(("A", ctr, R, a0, d))
        cur = T2
    segs.append(("L", cur, pts[-1]))

    P = []
    for s in segs:
        if s[0] == "L":
            A, B = s[1], s[2]
            L = norm(sub(B, A))
            n = max(int(L / DS), 2)
            for k in range(n):
                tt = k / n
                P.append((A[0] + (B[0] - A[0]) * tt, A[1] + (B[1] - A[1]) * tt))
        else:
            ctr, R, a0, d = s[1], s[2], s[3], s[4]
            n = max(int(abs(d) * R / DS), 3)
            for k in range(n):
                aa = a0 + d * k / n
                P.append((ctr[0] + R * math.cos(aa), ctr[1] + R * math.sin(aa)))
    P.append(pts[-1])
    s = [0.0]
    for i in range(1, len(P)):
        s.append(s[-1] + norm(sub(P[i], P[i - 1])))
    return P, s


def build(form, L_fire, n_step=0):
    h_step, h_drop = TYPES[form]
    c, sn = math.cos(SLOPE), math.sin(SLOPE)
    P0 = (0.0, 0.0)
    Pfb = (-L_COMB, 0.0)
    Pin = (-(L_COMB + APRON), 0.0)
    P1 = (L_fire * c, L_fire * sn)
    b = math.radians(FLUE_ANG)
    sf_pt = (P1[0] + 0.30 * c, P1[1] + 0.30 * sn)
    v = [Pin, P0, sf_pt,
         (sf_pt[0] + math.cos(b) * FLUE_RISE, sf_pt[1] + math.sin(b) * FLUE_RISE)]
    P, s = fillet_path(v, [2.60, 2.00])
    L = s[-1]

    def at(pt):
        j = min(range(len(P)), key=lambda i: norm(sub(P[i], pt)))
        return s[j]

    sfb, s0, s1, sf = at(Pfb), at(P0), at(P1), at(sf_pt)

    hc_stoke = -(h_step - h_drop) + H_STOKE
    hc_s = [0, sfb - EPS, sfb, sfb + 0.25, s0 - EPS, s0, s0 + 0.85,
            s1 - 0.60, s1, sf, L]
    hc_v = [hc_stoke, hc_stoke, hc_stoke, H_COMB, H_COMB, H_COMB, H_MAX,
            H_MAX, 0.92, 0.72, FLUE_H]
    w_s = [0, sfb - EPS, sfb + 0.25, s0, s0 + W_RAMP,
           s1 - W_TAPER, s1, sf, L]
    w_v = [W_STOKE, W_STOKE, W_COMB, 1.35, W_MAX, W_MAX, 1.05, 0.80, FLUE_W]

    ns = 260
    rings = []
    for i in range(ns):
        st = L * i / (ns - 1)
        j = min(range(len(s)), key=lambda k: abs(s[k] - st))
        j = max(1, min(j, len(P) - 2))
        px, pz = P[j]
        tv = unit(sub(P[j + 1], P[j - 1]))
        lift = (-(h_step - h_drop) if st < sfb - EPS
                else (-h_step if st < s0 - EPS else 0.0))
        if n_step and s0 <= st <= s1:
            Lch = s1 - s0
            dl = Lch / n_step
            kk = min(int((st - s0) / dl), n_step - 1)
            u_mid = (kk + 0.5) * dl
            dz = (u_mid - (st - s0)) * math.sin(SLOPE)
            lift += dz * math.cos(SLOPE)
        H = interp(st, hc_s, hc_v) - lift
        W = interp(st, w_s, w_v)
        up = (-tv[1], tv[0])
        ox, oz = px + up[0] * lift, pz + up[1] * lift
        ring = []
        for (u, vv) in section_ring(W, H):
            ring.append((ox + up[0] * vv, u, oz + up[1] * vv))
        rings.append(ring)
    return rings


def tube_tris(rings):
    tris = []
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(len(A)):
            k = (j + 1) % len(A)
            tris.append((A[j], B[j], B[k]))
            tris.append((A[j], B[k], A[k]))
    return tris


def cap_tris(ring, flip=False):
    c = tuple(sum(p[i] for p in ring) / len(ring) for i in range(3))
    tris = []
    for j in range(len(ring)):
        k = (j + 1) % len(ring)
        tris.append((c, ring[k], ring[j]) if flip else (c, ring[j], ring[k]))
    return tris


def signed_volume(tris):
    tot = 0.0
    for (a, b, c) in tris:
        n = (b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2],
             b[0] * c[1] - b[1] * c[0])
        tot += a[0] * n[0] + a[1] * n[1] + a[2] * n[2]
    return tot / 6.0


def write_stl(path, regions):
    with open(path, "w") as f:
        for name, tris in regions.items():
            f.write("solid %s\n" % name)
            for t in tris:
                ux = (t[1][0] - t[0][0], t[1][1] - t[0][1], t[1][2] - t[0][2])
                vx = (t[2][0] - t[0][0], t[2][1] - t[0][1], t[2][2] - t[0][2])
                n = (ux[1] * vx[2] - ux[2] * vx[1],
                     ux[2] * vx[0] - ux[0] * vx[2],
                     ux[0] * vx[1] - ux[1] * vx[0])
                ln = math.sqrt(sum(q * q for q in n)) or 1.0
                f.write("  facet normal %.6e %.6e %.6e\n"
                        % (n[0] / ln, n[1] / ln, n[2] / ln))
                f.write("    outer loop\n")
                for p in t:
                    f.write("      vertex %.6e %.6e %.6e\n" % p)
                f.write("    endloop\n  endfacet\n")
            f.write("endsolid %s\n" % name)


def make(form, L_fire, n_step=0, out=None):
    rings = build(form, L_fire, n_step)
    walls = tube_tris(rings)
    inlet = cap_tris(rings[0], flip=True)
    outlet = cap_tris(rings[-1], flip=False)
    if signed_volume(walls + inlet + outlet) < 0:
        walls = [(t[0], t[2], t[1]) for t in walls]
        inlet = [(t[0], t[2], t[1]) for t in inlet]
        outlet = [(t[0], t[2], t[1]) for t in outlet]
    if out:
        write_stl(out, dict(walls=walls, inlet=inlet, outlet=outlet))
    return walls, inlet, outlet


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "rom"))
    import geom

    if len(sys.argv) > 1:
        form, L, nst = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
        tag = "%s_L%03d%s" % (form, int(L * 10), "_S%d" % nst if nst else "")
        p = os.path.join(here, "kiln_%s.stl" % tag)
        make(form, L, nst, p)
        g = geom.extract(tag)
        print("%s  V=%.3f m3  습윤면적=%.2f m2  연돌고=%.3f m"
              % (tag, g["V"], g["A_wall"], g["H_stack"]))
        raise SystemExit

    print("배포 STL 과 대조 (계단 없음)\n")
    print("%-9s %9s %9s %9s %9s %9s %9s" %
          ("model", "V(기존)", "V(이식)", "A(기존)", "A(이식)", "H(기존)", "H(이식)"))
    for form in "ABC":
        for L in (2.5, 4.5, 6.5, 8.5):
            m = "%s_L%03d" % (form, int(L * 10))
            if not os.path.exists(os.path.join(here, "kiln_%s.stl" % m)):
                continue
            g1 = geom.extract(m)
            chk = "CHK_L%03d" % int(L * 10)
            make(form, L, 0, os.path.join(here, "kiln_%s.stl" % chk))
            g2 = geom.extract(chk)
            os.remove(os.path.join(here, "kiln_%s.stl" % chk))
            print("%-9s %9.3f %9.3f %9.2f %9.2f %9.3f %9.3f"
                  % (m, g1["V"], g2["V"], g1["A_wall"], g2["A_wall"],
                     g1["H_stack"], g2["H_stack"]))
