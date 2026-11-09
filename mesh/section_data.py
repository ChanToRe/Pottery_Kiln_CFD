#!/usr/bin/env python3
"""
종단면 개념도(2-3a, E-25·R-02)의 자료 — 가마 중심면(y = 0)의 바닥·천장선과 주요 치수.

형상은 STL 을 만든 생성기(mesh/kiln_geometry.py)의 링 배열에서 그대로 꺼낸다.
링마다 단면 꼭대기 가운데 점(아치 φ = 90°)이 천장, 바닥 가운데 점이 바닥이다.
벽은 바닥·천장선을 경로 법선 방향으로 벽 두께(0.35 m)만큼 밀어 낸 띠로 그린다(Fig 1 의
반투명 벽과 같은 정의 — mesh/render_geometry_panels.py 는 표면 법선 방향).

    python3 mesh/section_data.py
출력  Results/figures/section/profile_<형식>.csv   (x, z_floor, z_ceil, s — 원점: 화구 앞끝·가장 낮은 바닥)
      Results/figures/section/dims.csv            (치수 이름, 값, 근거)
"""
import csv
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "mesh"))
import kiln_geometry as K  # noqa: E402

OUT = os.path.join(ROOT, "Results", "figures", "section")
WALL_T = 0.35                      # Table 2 t_w
L_FIRE = 6.5
FUEL_BOX = (-1.55, -0.05)          # 연료층 x 범위 — cfd/*/system/topoSetDict (z 는 연소부 바닥 ~ 바닥 + 0.35)
TOP = K.N_ARCH // 2                # 아치 꼭대기 (φ = 90°, u = 0)
FL = (K.N_ARCH + 7, K.N_ARCH + 8)  # 바닥 점 i = 8·9 (u = ∓a/17) — 평균이 가운데


def profile(form):
    rings = K.build(form, L_FIRE)
    rows = []
    for r in rings:
        top = r[TOP]
        fx = 0.5 * (r[FL[0]][0] + r[FL[1]][0])
        fz = 0.5 * (r[FL[0]][2] + r[FL[1]][2])
        rows.append((fx, fz, top[0], top[2]))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    allp = {f: profile(f) for f in "ABC"}
    # 원점: 세 형식 공통으로 화구 앞끝(x 최소)·가장 낮은 바닥(z 최소) — Fig 2 축과 같은 기준
    x0 = min(min(p[0] for p in pr) for pr in allp.values())
    for f, pr in allp.items():
        z0 = min(p[1] for p in pr)
        with open(os.path.join(OUT, "profile_%s.csv" % f), "w", newline="") as fo:
            w = csv.writer(fo)
            # nx, nz: 경로 법선(위쪽) — 천장 − 바닥 방향. 벽 띠는 이 방향으로 민다(단차에서도 같은 법선).
            w.writerow(["x_floor", "z_floor", "x_ceil", "z_ceil", "nx", "nz"])
            for fx, fz, cx, cz in pr:
                d = math.hypot(cx - fx, cz - fz)
                w.writerow(["%.4f" % (fx - x0), "%.4f" % (fz - z0), "%.4f" % (cx - x0), "%.4f" % (cz - z0),
                            "%.5f" % ((cx - fx) / d), "%.5f" % ((cz - fz) / d)])
        with open(os.path.join(OUT, "origin_%s.txt" % f), "w") as fo:
            fo.write("x0 %.4f\nz0 %.4f\n" % (x0, z0))
    pr = allp["B"]
    xs = [p[0] for p in pr] + [p[2] for p in pr]
    zB0 = min(p[1] for p in pr)
    h_step, h_drop = K.TYPES["B"]
    dims = [
        ("overall_length", max(xs) - min(xs), "중심면 수평 길이 (화구 앞끝 ~ 연도 끝)"),
        ("ware_length", L_FIRE, "Table 2 L (경사 길이)"),
        ("slope_deg", math.degrees(K.SLOPE), "Table 2 θ"),
        ("firemouth_tunnel", K.APRON, "kiln_geometry.APRON"),
        ("firebox_length", K.L_COMB, "kiln_geometry.L_COMB"),
        ("firemouth_height", K.H_STOKE, "kiln_geometry.H_STOKE"),
        ("firebox_height", K.H_COMB, "kiln_geometry.H_COMB (소성실 바닥 기준 천장)"),
        ("ware_height", K.H_MAX, "kiln_geometry.H_MAX"),
        ("h_step_B", h_step, "Table 2 h_step"),
        ("h_drop_C", K.TYPES["C"][1], "Table 2 h_drop"),
        ("wall", WALL_T, "Table 2 t_w"),
        ("fuel_bed", 0.35, "Table 2 h_fuel, topoSetDict 연료층 높이"),
        ("fuel_x0", FUEL_BOX[0] - x0, "topoSetDict"),
        ("fuel_x1", FUEL_BOX[1] - x0, "topoSetDict"),
        ("step_x", 0.0 - x0, "연소부/소성부 경계 x = 0"),
        ("firebox_x", -K.L_COMB - x0, "화구/연소부 경계"),
        ("floor_B_z", -h_step - zB0, ""),
        ("flue_angle", K.FLUE_ANG, "kiln_geometry.FLUE_ANG"),
    ]
    with open(os.path.join(OUT, "dims.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["name", "value", "basis"])
        for n, v, b in dims:
            w.writerow([n, "%.4f" % v, b])
    for n, v, b in dims:
        print("%-18s %8.3f  %s" % (n, v, b))


if __name__ == "__main__":
    main()
