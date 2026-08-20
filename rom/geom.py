#!/usr/bin/env python3
import math
import os

MESH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh")

SLOPE_DEG = 15.0
L_COMB = 1.60
APRON = 1.30
ZONES = ("stoke", "comb", "ware", "flue")


def stl_resolve(base):
    return base + ".gz" if os.path.exists(base + ".gz") else base


def stl_open(path, mode="rt"):
    if path.endswith(".gz"):
        import gzip
        return gzip.open(path, mode)
    return open(path, mode.replace("t", ""))


def read_stl(path):
    solids, name, tri, buf = {}, None, None, []
    with stl_open(path) as f:
        for line in f:
            t = line.split()
            if not t:
                continue
            if t[0] == "solid":
                name = t[1] if len(t) > 1 else "solid"
                solids[name] = []
            elif t[0] == "outer":
                buf = []
            elif t[0] == "vertex":
                buf.append((float(t[1]), float(t[2]), float(t[3])))
            elif t[0] == "endloop":
                solids[name].append(tuple(buf))
    return solids


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def tri_area_normal(t):
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = t
    n = _cross((x1 - x0, y1 - y0, z1 - z0), (x2 - x0, y2 - y0, z2 - z0))
    a = 0.5 * math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    return a, n


def centroid(t):
    return tuple(sum(v[i] for v in t) / 3.0 for i in range(3))


def signed_volume(tris):
    s = 0.0
    for (a, b, c) in tris:
        n = _cross(b, c)
        s += a[0] * n[0] + a[1] * n[1] + a[2] * n[2]
    return s / 6.0


def cross_section_area(walls, x0, tol=1e-4):
    segs = []
    for t in walls:
        d = [v[0] - x0 for v in t]
        if min(d) > 0 or max(d) < 0:
            continue
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if (d[i] > 0) != (d[j] > 0) and d[i] != d[j]:
                f = d[i] / (d[i] - d[j])
                pts.append((t[i][1] + f * (t[j][1] - t[i][1]),
                            t[i][2] + f * (t[j][2] - t[i][2])))
        if len(pts) == 2:
            segs.append(pts)
    if not segs:
        return 0.0

    def near(a, b):
        return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol

    loop = list(segs.pop(0))
    changed = True
    while changed and segs:
        changed = False
        for i, s in enumerate(segs):
            for a, b in ((0, 1), (1, 0)):
                if near(s[a], loop[-1]):
                    loop.append(s[b])
                    segs.pop(i)
                    changed = True
                    break
                if near(s[a], loop[0]):
                    loop.insert(0, s[b])
                    segs.pop(i)
                    changed = True
                    break
            if changed:
                break
    a = 0.0
    for i in range(len(loop)):
        y1, z1 = loop[i]
        y2, z2 = loop[(i + 1) % len(loop)]
        a += y1 * z2 - y2 * z1
    return abs(a) / 2.0


def extract(model, mesh_dir=MESH_DIR, seg_m=None):
    L_fire = int(model.split("_L")[1][:3]) / 10.0
    path = stl_resolve(os.path.join(mesh_dir, "kiln_%s.stl" % model))
    s = read_stl(path)
    walls, inlet, outlet = s["walls"], s["inlet"], s["outlet"]

    V = abs(signed_volume(walls + inlet + outlet))

    def area(tris):
        return sum(tri_area_normal(t)[0] for t in tris)

    def area_centroid(tris):
        tot, cz = 0.0, 0.0
        for t in tris:
            a = tri_area_normal(t)[0]
            tot += a
            cz += a * centroid(t)[2]
        return tot, cz / tot

    A_in, z_in = area_centroid(inlet)
    A_out, z_out = area_centroid(outlet)

    x_P1 = (L_fire + 0.30) * math.cos(math.radians(SLOPE_DEG))
    x_fb, x_0 = -L_COMB, 0.0

    n_ware = 1
    if seg_m:
        n_ware = max(1, int(round(L_fire / seg_m)))
    ware_keys = ["ware"] if n_ware == 1 else ["ware%d" % (i + 1) for i in range(n_ware)]

    zone_area = dict((z, 0.0) for z in ("stoke", "comb", "flue"))
    for z in ware_keys:
        zone_area[z] = 0.0
    for t in walls:
        a = tri_area_normal(t)[0]
        x = centroid(t)[0]
        if x < x_fb:
            zone_area["stoke"] += a
        elif x < x_0:
            zone_area["comb"] += a
        elif x < x_P1:
            j = min(int((x - x_0) / (x_P1 - x_0) * n_ware), n_ware - 1)
            zone_area[ware_keys[j]] += a
        else:
            zone_area["flue"] += a

    zone_vol = dict((z, 0.0) for z in zone_area)
    FLUE_V = 0.55 * 0.48 * 0.8 * (1.60 / math.sin(math.radians(68.0)))
    nsl = 12
    for j, (za, xa, xb) in enumerate(
            [("stoke", min(v[0] for t in walls for v in t), x_fb),
             ("comb", x_fb, x_0)]
            + [(ware_keys[i], x_0 + (x_P1 - x_0) * i / n_ware,
                x_0 + (x_P1 - x_0) * (i + 1) / n_ware) for i in range(n_ware)]):
        acc = 0.0
        for i in range(nsl):
            x = xa + (xb - xa) * (i + 0.5) / nsl
            acc += cross_section_area(walls, x)
        zone_vol[za] = acc / nsl * (xb - xa)
    zone_vol["flue"] = FLUE_V
    s = sum(zone_vol.values())
    if s > 0:
        for z in zone_vol:
            zone_vol[z] *= V / s

    return dict(
        model=model, type=model[0], L_fire=L_fire,
        V=V, A_in=A_in, A_out=A_out,
        H_stack=z_out - z_in,
        A_wall=sum(zone_area.values()),
        zone_area=zone_area,
        zone_vol=zone_vol,
        ware_keys=ware_keys,
        seg_len=(x_P1 - x_0) / n_ware / math.cos(math.radians(SLOPE_DEG)),
        A_cross=cross_section_area(walls, x_0 + 0.15),
    )


if __name__ == "__main__":
    print("%-9s %8s %8s %8s %8s | %s" %
          ("model", "V[m3]", "A_in", "A_out", "H[m]",
           "  ".join("%7s" % z for z in ZONES)))
    for t in "ABC":
        g = extract("%s_L065" % t)
        print("%-9s %8.3f %8.4f %8.4f %8.3f | %s" %
              (g["model"], g["V"], g["A_in"], g["A_out"], g["H_stack"],
               "  ".join("%7.2f" % g["zone_area"][z] for z in ZONES)))
