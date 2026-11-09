#!/usr/bin/env python3
"""
OpenFOAM ascii polyMesh 에서 패치 면의 중심·면적을 읽는 작은 도구 (표준 라이브러리만).

    python3 cfd/checks/meshtools.py <케이스> <패치>     패치 면 수·면적·범위를 출력
"""
import os
import re
import sys


def _list(path):
    """'n ( ... )' 꼴 ascii 목록을 읽어 문자열 항목 목록으로 돌려준다."""
    txt = open(path).read()
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    txt = txt[txt.index("}", txt.index("FoamFile")) + 1:]
    m = re.search(r"^\s*(\d+)\s*\(", txt, re.M)
    body = txt[m.end():txt.rindex(")")]
    return int(m.group(1)), body


def points(case):
    n, body = _list(os.path.join(case, "constant/polyMesh/points"))
    p = [tuple(map(float, t.split())) for t in re.findall(r"\(([^()]*)\)", body)]
    assert len(p) == n
    return p


def faces(case):
    n, body = _list(os.path.join(case, "constant/polyMesh/faces"))
    f = [tuple(map(int, t.split())) for t in re.findall(r"\d+\(([^()]*)\)", body)]
    assert len(f) == n
    return f


def boundary(case):
    txt = open(os.path.join(case, "constant/polyMesh/boundary")).read()
    out = {}
    for name, blk in re.findall(r"^\s*(\w+)\s*\{([^}]*)\}", txt, re.M):
        if name == "FoamFile":
            continue
        nf = re.search(r"nFaces\s+(\d+)", blk)
        sf = re.search(r"startFace\s+(\d+)", blk)
        if nf and sf:
            out[name] = (int(sf.group(1)), int(nf.group(1)))
    return out


def _face_geom(pts, f):
    """다각형 면의 중심과 면적 (삼각형 부채꼴)."""
    c0 = [sum(pts[i][k] for i in f) / len(f) for k in range(3)]
    ax = ay = az = 0.0
    cx = cy = cz = 0.0
    tot = 0.0
    for a, b in zip(f, f[1:] + f[:1]):
        p, q = pts[a], pts[b]
        u = [p[k] - c0[k] for k in range(3)]
        v = [q[k] - c0[k] for k in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ar = 0.5 * (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
        tc = [(c0[k] + p[k] + q[k]) / 3 for k in range(3)]
        cx += ar * tc[0]; cy += ar * tc[1]; cz += ar * tc[2]
        tot += ar
    return (cx / tot, cy / tot, cz / tot), tot


def patch_faces(case, patch):
    """[(중심 (x,y,z), 면적), ...]"""
    pts, fcs = points(case), faces(case)
    s, n = boundary(case)[patch]
    return [_face_geom(pts, fcs[i]) for i in range(s, s + n)]


if __name__ == "__main__":
    pf = patch_faces(sys.argv[1], sys.argv[2])
    xs = [c[0] for c, _ in pf]; ys = [c[1] for c, _ in pf]; zs = [c[2] for c, _ in pf]
    print("%s: 면 %d, 면적 %.5f m2, x %.3f–%.3f, y %.3f–%.3f, z %.3f–%.3f" % (
        sys.argv[2], len(pf), sum(a for _, a in pf), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
