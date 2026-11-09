#!/usr/bin/env python3
"""
STL 에서 축소모델 입력 형상량을 추출한다 (순수 Python, numpy 없음).

축소모델이 필요로 하는 것은 격자가 아니라 몇 개의 적분량뿐이다.
  - 내용적 V
  - 화구·연도 개구면적
  - 연돌고 H (부력 통풍의 구동 높이)
  - 구간별 습윤면적 A_zone  ← A/B/C 형식차가 들어오는 자리

구간 분할은 형상 생성기(mesh/rev4_builder.py, kiln_geometry.py)의 축방향 정거장을 그대로 쓴다.
    x < -1.60           화구(stoke)
    -1.60 <= x < 0      연소부(comb)     ← h_step/h_drop 이 작용하는 구간
    0 <= x < x(P1)      소성부(ware)
    x >= x(P1)          연도(flue)
"""
import math
import os

STL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh", "stl")

SLOPE_DEG = 15.0
L_COMB = 1.60          # 연소부 길이
APRON = 1.30           # 화구 터널 길이
ZONES = ("stoke", "comb", "ware", "flue")


def read_stl(path):
    """ASCII STL → {solid_name: [(v0, v1, v2), ...]}"""
    solids, name, tri, buf = {}, None, None, []
    with open(path) as f:
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
    """삼각형 면적과 (정규화 안 된) 법선"""
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = t
    n = _cross((x1 - x0, y1 - y0, z1 - z0), (x2 - x0, y2 - y0, z2 - z0))
    a = 0.5 * math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    return a, n


def centroid(t):
    return tuple(sum(v[i] for v in t) / 3.0 for i in range(3))


def signed_volume(tris):
    """발산정리: V = (1/6) Σ v0 · (v1 × v2)"""
    s = 0.0
    for (a, b, c) in tris:
        n = _cross(b, c)
        s += a[0] * n[0] + a[1] * n[1] + a[2] * n[2]
    return s / 6.0


def cross_section_area(walls, x0, tol=1e-4):
    """평면 x=x0 로 자른 단면적. 노드 간 축방향 복사 교환면이다.

    잘린 선분을 끝점으로 이어 폐곡선을 만든 뒤 신발끈 공식으로 면적을 낸다.
    (법선 x 성분의 부호로 방향을 통일하는 방법은 측벽에서 nx≈0 이라 실패한다.)
    """
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

    # 최대 폐곡선 하나를 잇는다
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


def extract(model, stl_dir=STL_DIR, seg_m=None):
    """model 예: 'A_L065' → 축소모델 입력 dict

    seg_m 을 주면 소성부를 그 길이(m)에 가깝게 축방향으로 쪼개
    zone_area 에 'ware1'..'wareN' 으로 넣는다. 소성실 안에서 어느 구간이
    소성 온도에 닿는지 보려면 축방향 해상도가 필요하다.
    seg_m=None 이면 'ware' 하나로 둔다 (기존 동작).
    """
    # 'B_L065' -> 6.5 m. 'B_L065_S2'(계단 2단) 처럼 접미사가 붙을 수 있다.
    L_fire = int(model.split("_L")[1][:3]) / 10.0
    path = os.path.join(stl_dir, "kiln_%s.stl" % model)
    s = read_stl(path)
    walls, inlet, outlet = s["walls"], s["inlet"], s["outlet"]

    V = abs(signed_volume(walls + inlet + outlet))

    def area(tris):
        return sum(tri_area_normal(t)[0] for t in tris)

    # 개구부 도심 (연돌고 산정용)
    def area_centroid(tris):
        tot, cz = 0.0, 0.0
        for t in tris:
            a = tri_area_normal(t)[0]
            tot += a
            cz += a * centroid(t)[2]
        return tot, cz / tot

    A_in, z_in = area_centroid(inlet)
    A_out, z_out = area_centroid(outlet)

    # 축방향 정거장
    # 연도는 P1 에서 0.30 m 더 간 지점부터 68° 로 솟는다 (mesh/rev4_builder.build)
    x_P1 = (L_fire + 0.30) * math.cos(math.radians(SLOPE_DEG))
    x_fb, x_0 = -L_COMB, 0.0

    # 소성부 축방향 분할 (x 투영 기준). 경사 15° 이므로 실제 축길이는 x/cos15.
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

    # 구간별 기체 용적 — 적재량·적재 표면적이 여기서 나온다.
    # 단면적을 축방향으로 적분한다 (경사 15° 이므로 길이는 x/cos15).
    zone_vol = dict((z, 0.0) for z in zone_area)
    # 연도부는 68° 로 솟아 x 절단이 무의미하다. 형상 제원으로 잡는다.
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
        # x=const 절단면은 경사구간에서 비스듬해 면적이 이미 1/cos15 배다.
        # 따라서 ∫A(x)dx 가 그대로 부피이고, cos 보정을 또 넣으면 안 된다.
        zone_vol[za] = acc / nsl * (xb - xa)
    zone_vol["flue"] = FLUE_V
    # 단면 적분은 굽은 구간에서 총량을 10 % 남짓 넘긴다(x=const 절단이 축에
    # 수직이 아니다). 상대 분포는 쓸 만하므로 **총량을 STL 의 정확한 부피에
    # 맞춰 정규화**한다. 적재량은 상대 분포로 정해지므로 이걸로 충분하다.
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
        A_cross=cross_section_area(walls, x_0 + 0.15),  # 연소실↔소성실 경계 단면
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
