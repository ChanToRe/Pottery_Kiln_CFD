#!/usr/bin/env python3
"""
Fig 4·6 낱장 렌더링 라이브러리 — **실제 가마 형상**(STL 중앙면 실루엣) 위에
**적재 포함 축소모델**의 구간 온도를 칠한다. panels_length.py 가 쓴다.
(원래 section_real.py. 그 안의 GIF 생성 main 은 원고에 쓰이지 않아 뺐다.)

panels_length.py 가 틀(X0·X1·Z0·Z1·PW·PH)과 색범위(TLO·THI)를 덮어쓴다.
"""
import math
import os

import calibrate
import geom
import rom
import run
import colormaps as S

# 색표 — 기본은 레인보우(투고본). PALETTE=inferno·jet 로 바꿀 수 있다(수정본은 jet — Fig 2 와 같은 색).
CMAP = {"inferno": S.inferno, "jet": S.jet}.get(os.environ.get("PALETTE", ""), S.rainbow)
# 색범위 [℃] (panels_length.py 가 TLO·THI 로 덮어쓴다)
TLO = float(os.environ.get("TLO", "900"))
THI = float(os.environ.get("THI", "1200"))

SEG_M = 1.0                       # 소성실 축방향 분할 [m]
PW, PH = 748, 262                 # 패널 크기 [px] (panels_length.py 가 덮어쓴다)
# 벽체·지반 표시 깊이 [m]. 0 이면 가마 내부만 그린다(Fig 2 의 CFD 단면과
# 같은 모양). panels_length.py 는 0 을 쓴다.
SOIL_D = float(os.environ.get("SOIL_D", "0"))
X0, X1 = -3.4, 12.0               # 실좌표 범위 [m] (panels_length.py 가 덮어쓴다)
Z0, Z1 = (-1.45, 4.95) if SOIL_D > 0 else (-0.75, 4.35)


def silhouette(model, nb=260, win=0.10):
    """STL 중앙면에서 바닥·천정 실루엣과 구간 경계를 뽑는다."""
    tris = geom.read_stl(os.path.join(geom.STL_DIR, "kiln_%s.stl" % model))["walls"]
    g = geom.extract(model, seg_m=SEG_M)
    xs = [v[0] for t in tris for v in t]
    xa, xb = min(xs), max(xs)
    # 칸을 서로 겹치게 잡는다. 칸을 좁혀 나누면 바닥 정점만 들어가는 칸이
    # 생겨 단면이 납작하게 붕괴한다(그 자리에 세로 줄무늬가 남는다).
    prof = []
    for i in range(nb):
        c = xa + (xb - xa) * (i + 0.5) / nb
        zz = [v[2] for t in tris for v in t
              if abs(v[0] - c) < win and abs(v[1]) < 0.30]
        if len(zz) >= 2:
            prof.append((c, min(zz), max(zz)))
    x_P1 = (g["L_fire"] + 0.30) * math.cos(math.radians(geom.SLOPE_DEG))
    wk = g["ware_keys"]

    def zone_at(x):
        if x < -geom.L_COMB:
            return "stoke"
        if x < 0.0:
            return "comb"
        if x < x_P1:
            j = min(int(x / x_P1 * len(wk)), len(wk) - 1)
            return wk[j]
        return "flue"
    return prof, zone_at, g


def build_codes(model):
    """픽셀마다 (구간, 기체/고체, 깊이 인덱스) 를 미리 굳힌다.

    형상은 프레임마다 안 바뀌므로 한 번만 계산한다. 고체 깊이는 경계를
    촘촘히 표본해 원반을 찍는 방식(거리 변환)으로 구한다 — 픽셀마다
    전 경계를 훑으면 너무 느리다.
    """
    prof, zone_at, g = silhouette(model)
    zones = ["stoke", "comb"] + g["ware_keys"] + ["flue"]
    k, _ = calibrate.build(model, seg_m=SEG_M, T_amb=run.T_AMB)
    depth_of = {}
    for z in zones:
        st = k.stacks[z]
        d, acc = [], 0.0
        for i in range(st.n):
            acc += st.dx[i] / 2 if i == 0 else (st.dx[i - 1] + st.dx[i]) / 2
            d.append(acc)
        depth_of[z] = d

    sx = PW / (X1 - X0)
    sz = PH / (Z1 - Z0)
    OUT = len(zones) * 64
    codes = [OUT] * (PW * PH)

    # 1) 기체공간
    inside = [[False] * PH for _ in range(PW)]
    px = [p[0] for p in prof]
    for i in range(PW):
        x = X0 + (i + 0.5) / sx
        # 최근접 구간을 쓰면 표본 간격이 픽셀보다 굵은 곳에서 세로 줄이 생긴다.
        # 바닥·천정을 선형보간해 메운다.
        if x < px[0] or x > px[-1]:
            continue
        j2 = 0
        while j2 < len(px) - 1 and px[j2 + 1] < x:
            j2 += 1
        a, b = prof[j2], prof[min(j2 + 1, len(prof) - 1)]
        f = 0.0 if b[0] == a[0] else (x - a[0]) / (b[0] - a[0])
        zf = a[1] + f * (b[1] - a[1])
        zc = a[2] + f * (b[2] - a[2])
        zi = zones.index(zone_at(x))
        for j in range(PH):
            z = Z1 - (j + 0.5) / sz
            if zf <= z <= zc:
                codes[j * PW + i] = zi * 64
                inside[i][j] = True

    # 2) 고체 — 경계에서 원반 찍기 (거리 변환). SOIL_D=0 이면 생략.
    if SOIL_D <= 0:
        return codes, zones, g, prof, zone_at, depth_of
    dist = [1e9] * (PW * PH)
    zidx = [0] * (PW * PH)
    rad_px = int(SOIL_D * sx) + 2
    for (x, zf, zc) in prof:
        zi = zones.index(zone_at(x))
        for zb in (zf, zc):
            ci = int((x - X0) * sx)
            cj = int((Z1 - zb) * sz)
            for dj in range(-rad_px, rad_px + 1):
                jj = cj + dj
                if not (0 <= jj < PH):
                    continue
                for di in range(-rad_px, rad_px + 1):
                    ii = ci + di
                    if not (0 <= ii < PW) or inside[ii][jj]:
                        continue
                    d = math.hypot(di / sx, dj / sz)
                    o = jj * PW + ii
                    if d < dist[o]:
                        dist[o] = d
                        zidx[o] = zi
    for o in range(PW * PH):
        if codes[o] != OUT or dist[o] > SOIL_D:
            continue
        z = zones[zidx[o]]
        dd = depth_of[z]
        if dist[o] > dd[-1]:
            continue
        di = 0
        while di < len(dd) - 1 and dd[di] < dist[o]:
            di += 1
        codes[o] = zidx[o] * 64 + 1 + min(di, 61)
    return codes, zones, g, prof, zone_at, depth_of


BG = (252, 252, 253)


def palette(k, zones, depth_of=None):
    """구간별 색표. 고체는 **깊이에 따라 배경색으로 흐려진다.**

    지반 1 m 를 그대로 칠하면 바깥이 지중온도(15 ℃)라 색표의 검정 쪽으로 가
    가마 둘레가 검은 덩어리가 된다. 벽면 근처의 열파만 보이면 되므로
    깊이 비율만큼 배경과 섞는다.
    """
    pal = [bytes(BG)] * (len(zones) * 64 + 1)
    names = [nm for nm, _ in rom.build_nodes(k.geo)]
    node_of = {}
    for z in zones:
        node_of[z] = (0 if z in ("stoke", "comb")
                      else len(k.T) - 1 if z == "flue" else names.index(z))
    for zi, z in enumerate(zones):
        Tg = k.T[node_of[z]] - 273.15
        pal[zi * 64] = bytes(CMAP((Tg - TLO) / (THI - TLO)))
        st = k.stacks[z]
        dd = depth_of[z] if depth_of else None
        for di in range(min(st.n, 62)):
            c = CMAP((st.T[di] - 273.15 - TLO) / (THI - TLO))
            if dd is not None and SOIL_D > 0:
                w = min(1.0, max(0.0, dd[di] / SOIL_D)) ** 0.7   # 배경 혼합비
                c = tuple(int(c[q] + (BG[q] - c[q]) * w) for q in range(3))
            pal[zi * 64 + 1 + di] = bytes(c)
    return pal, node_of
