#!/usr/bin/env python3
import os
import sys

import calibrate
import efficiency
import geom
import rom
import run

LENS = [("B_L025", 2.5), ("B_L045", 4.5), ("B_L065", 6.5), ("B_L085", 8.5)]


def lsq(xs, ys, deg=1):
    n = deg + 1
    A = [[sum(x ** (i + j) for x in xs) for j in range(n)] for i in range(n)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p] = A[p], A[i]
        b[i], b[p] = b[p], b[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    c = [0.0] * n
    for i in range(n - 1, -1, -1):
        c[i] = (b[i] - sum(A[i][j] * c[j] for j in range(i + 1, n))) / A[i][i]
    return c


def r2(xs, ys, c):
    pred = [sum(ci * x ** i for i, ci in enumerate(c)) for x in xs]
    m = sum(ys) / len(ys)
    ss_t = sum((y - m) ** 2 for y in ys)
    ss_r = sum((y - p) ** 2 for y, p in zip(ys, pred))
    return 1 - ss_r / ss_t if ss_t else 1.0


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()

    print("비교 2 — 소성실 길이별 연료 소요량 (② 수평연소 유단식)\n")
    print("고정: 소성 절차(6구간 78 h) · 실측 승온곡선 · 화구 개구율 φ(t)")
    print("미지: 구간별 발열률 → 연료 소요량\n")

    res = []
    for model, L in LENS:
        g = geom.extract(model)
        print("  %s  소성부 %.1f m  내용적 %.2f m³  연돌고 %.2f m" %
              (model, L, g["V"], g["H_stack"]))
        k, rows, info = efficiency.demand(model, fit, sched, ts, Ts)
        tot = sum(r["fuel"] for r in rows)
        lam = min(r["lam_min"] for r in rows)
        peak = max(r["Q"] for r in rows)
        res.append(dict(model=model, L=L, V=g["V"], H=g["H_stack"],
                        A=g["A_wall"], fuel=tot, lam=lam, Q=peak,
                        mdot=rows[-1]["mdot"]))
        print("     -> 연료 %.0f kg   최고 발열률 %.0f kW   λ최소 %.2f\n"
              % (tot, peak / 1e3, lam))

    xs = [r["L"] for r in res]
    ys = [r["fuel"] for r in res]
    c1 = lsq(xs, ys, 1)
    c2 = lsq(xs, ys, 2)

    L = []
    L.append("비교 2 — 소성실 길이별 연료 소요량\n")
    L.append("② 수평연소 유단식 고정. 동일한 소성 절차에서 실측 승온곡선을")
    L.append("재현하는 데 필요한 연료를 길이별로 역산했다.\n")
    L.append("%-9s %7s %8s %8s %9s %10s %11s %8s" %
             ("model", "L[m]", "V[m³]", "연돌고", "습윤면적", "연료[kg]", "연료/V[kg/m³]", "λ최소"))
    for r in res:
        L.append("%-9s %7.1f %8.2f %8.2f %9.2f %10.0f %11.1f %8.2f" %
                 (r["model"], r["L"], r["V"], r["H"], r["A"], r["fuel"],
                  r["fuel"] / r["V"], r["lam"]))

    L.append("\n── 회귀 ──")
    L.append("1차   연료[kg] = %.1f + %.1f x L[m]      R² = %.5f"
             % (c1[0], c1[1], r2(xs, ys, c1)))
    L.append("2차   연료[kg] = %.1f + %.1f L + %.2f L²   R² = %.5f"
             % (c2[0], c2[1], c2[2], r2(xs, ys, c2)))
    L.append("")
    L.append("잔차 (1차):")
    for r in res:
        p = c1[0] + c1[1] * r["L"]
        L.append("  L=%.1f m   실측 %5.0f   회귀 %5.0f   차 %+5.0f kg (%+.1f %%)"
                 % (r["L"], r["fuel"], p, r["fuel"] - p, 100 * (r["fuel"] - p) / r["fuel"]))

    L.append("\n── 읽는 법 ──")
    L.append("절편 %.0f kg  = 소성부 길이가 0 이어도 드는 연료." % c1[0])
    L.append("               화구·연소부·연도를 데우고 그 벽체를 축열시키는 몫이다.")
    L.append("기울기 %.0f kg/m = 소성부를 1 m 늘릴 때 추가로 드는 연료." % c1[1])
    base = c1[0]
    for r in res:
        L.append("  L=%.1f m 에서 고정비 비중 %.0f %%  (연료 %.0f kg 중 %.0f kg)"
                 % (r["L"], 100 * base / r["fuel"], r["fuel"], base))

    txt = "\n".join(L)
    print(txt)
    with open(os.path.join(run.RESULTS, "rom_length.txt"), "w") as f:
        f.write(txt + "\n")
    with open(os.path.join(run.RESULTS, "rom_length.csv"), "w") as f:
        f.write("model,L_m,V_m3,H_stack_m,A_wall_m2,fuel_kg,fuel_per_V,lam_min,Q_peak_kW\n")
        for r in res:
            f.write("%s,%.1f,%.3f,%.3f,%.2f,%.1f,%.2f,%.3f,%.1f\n" %
                    (r["model"], r["L"], r["V"], r["H"], r["A"], r["fuel"],
                     r["fuel"] / r["V"], r["lam"], r["Q"] / 1e3))
    print("\n→ Results/rom_length.txt, rom_length.csv")
    return res, c1, c2


if __name__ == "__main__":
    main()
