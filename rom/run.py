#!/usr/bin/env python3
import os
import sys
import math

import calibrate
import rom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RESULTS = os.path.join(ROOT, "Results")
SCHED = os.path.join(ROOT, "cfd", "fuel_schedule.csv")
CURVE = os.path.join(ROOT, "References", "홍진근2011_표3_승온곡선_digitized.csv")

DT = 60.0
T_SEAL = 78 * 3600.0
T_END = 342 * 3600.0
T_AMB = 292.45
FIT_FORM = "B"


def load_curve():
    ts, Ts = [], []
    with open(CURVE) as f:
        for line in f:
            if line.startswith("#") or line.startswith("t_h"):
                continue
            p = line.split(",")
            if len(p) >= 2:
                ts.append(float(p[0]) * 3600.0)
                Ts.append(float(p[1]) + 273.15)
    return ts, Ts


def curve_at(ts, Ts, t):
    if t <= ts[0]:
        return Ts[0]
    for i in range(1, len(ts)):
        if t <= ts[i]:
            f = (t - ts[i - 1]) / (ts[i] - ts[i - 1])
            return Ts[i - 1] + f * (Ts[i] - Ts[i - 1])
    return Ts[-1]


FIT_NODE = os.environ.get("FIT_NODE", "ware1")
SEG_M = float(os.environ.get("SEG_M", "1.0"))


def fit_T(k):
    n = len(k.T)
    if FIT_NODE == "comb" or n < 2:
        return k.T[0]
    if FIT_NODE == "ware1" or n == 2:
        return k.T[1]
    return sum(k.T[1:n - 1]) / (n - 2)


def advance(k, sched, t0, t1, phi, rows=None, every=600.0, qmul=1.0):
    n = int(round((t1 - t0) / DT))
    nxt = t0
    for i in range(n):
        r = k.step(DT, qmul * rom.Q_at(sched, t0 + i * DT), phi)
        if rows is not None and r["t"] >= nxt:
            r["stored"] = k.stored()
            rows.append(r)
            nxt += every
    return fit_T(k)


def fit_phi(sched, ts, Ts):
    k, _ = calibrate.build("%s_L065" % FIT_FORM, seg_m=SEG_M, T_amb=T_AMB)
    bounds = [p[0] for p in sched if p[1] > 0] + [T_SEAL]
    out = []
    for j in range(len(bounds) - 1):
        t0, t1 = bounds[j], bounds[j + 1]
        target = curve_at(ts, Ts, t1)
        state = k.save()
        lo, hi = 1e-4, 1.0

        def endT(phi):
            k.restore(state)
            return advance(k, sched, t0, t1, phi)

        Thi, Tlo = endT(hi), endT(lo)
        if Thi >= target:
            phi, note = hi, "개방한계"
        elif Tlo <= target:
            phi, note = lo, "폐쇄한계"
        else:
            for _ in range(18):
                mid = math.sqrt(lo * hi)
                if endT(mid) > target:
                    lo = mid
                else:
                    hi = mid
            phi, note = math.sqrt(lo * hi), ""
        k.restore(state)
        got = advance(k, sched, t0, t1, phi)
        out.append(dict(t0=t0, t1=t1, phi=phi, target=target, got=got,
                        note=note, Q=rom.Q_at(sched, t0)))
    return out


def phi_at(fit, t):
    if t >= T_SEAL:
        return 0.0
    for f in fit:
        if t < f["t1"]:
            return f["phi"]
    return fit[-1]["phi"]


def run_full(model, sched, fit):
    k, info = calibrate.build(model, seg_m=SEG_M, T_amb=T_AMB)
    rows = []
    marks = sorted(set([f["t1"] for f in fit] + [T_SEAL, T_END]))
    t = 0.0
    for m in marks:
        advance(k, sched, t, m, phi_at(fit, t), rows)
        t = m
    return k, rows, info


def energy_budget(rows):
    E = [0.0, 0.0, 0.0]
    for i in range(1, len(rows)):
        dt = rows[i]["t"] - rows[i - 1]["t"]
        for j, k in enumerate(("Q", "q_exh", "q_wall")):
            E[j] += 0.5 * (rows[i][k] + rows[i - 1][k]) * dt
    return E


PHI_CSV = os.path.join(RESULTS, "rom_phi.csv")


def save_fit(fit):
    with open(PHI_CSV, "w") as f:
        f.write("t0_h,t1_h,phi,Q_kW,target_C,got_C,note\n")
        for x in fit:
            f.write("%.1f,%.1f,%.6f,%.1f,%.1f,%.1f,%s\n" %
                    (x["t0"] / 3600, x["t1"] / 3600, x["phi"], x["Q"] / 1e3,
                     x["target"] - 273.15, x["got"] - 273.15, x["note"]))


def load_fit():
    fit = []
    with open(PHI_CSV) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split(",")
            fit.append(dict(t0=float(p[0]) * 3600, t1=float(p[1]) * 3600,
                            phi=float(p[2]), Q=float(p[3]) * 1e3,
                            target=float(p[4]) + 273.15,
                            got=float(p[5]) + 273.15, note=p[6]))
    return fit


def main(refit=True):
    os.makedirs(RESULTS, exist_ok=True)
    sched = rom.load_schedule(SCHED)
    ts, Ts = load_curve()

    print("── 1. 화구 개구율 역산 (형식 %s, 실측 승온곡선 대조) ──\n" % FIT_FORM)
    if refit or not os.path.exists(PHI_CSV):
        fit = fit_phi(sched, ts, Ts)
        save_fit(fit)
    else:
        fit = load_fit()
    print("%9s %8s %8s %9s %9s %7s" %
          ("구간[h]", "Q[kW]", "φ", "실측[℃]", "계산[℃]", "개구[m2]"))
    for f in fit:
        print("%3.0f - %3.0f %8.0f %8.4f %9.0f %9.0f %7.3f  %s" %
              (f["t0"] / 3600, f["t1"] / 3600, f["Q"] / 1e3, f["phi"],
               f["target"] - 273.15, f["got"] - 273.15,
               f["phi"] * 0.5538, f["note"]))

    print("\n── 2. 전 공정 342 h (φ 동일 적용) ──\n")
    out = {}
    for t in "ABC":
        m = "%s_L065" % t
        k, rows, info = run_full(m, sched, fit)
        out[t] = (k, rows, info)
        with open(os.path.join(RESULTS, "rom_%s.csv" % m), "w") as f:
            f.write("t_h,T_comb_C,T_flue_C,dT_C,mdot,phi,Q_kW,q_wall_kW,"
                    "q_exh_kW,stored_GJ\n")
            for r in rows:
                f.write("%.4f,%.1f,%.1f,%.1f,%.4f,%.4f,%.1f,%.2f,%.2f,%.4f\n" %
                        (r["t"] / 3600, r["T_comb"] - 273.15, r["T_flue"] - 273.15,
                         r["dT"], r["mdot"], r["phi"], r["Q"] / 1e3,
                         r["q_wall"] / 1e3, r["q_exh"] / 1e3, r["stored"] / 1e9))
        print("  %s 저장 (%d행)" % (m, len(rows)))

    L = []
    L.append("축소모델 결과 — L065, φ(t) 는 %s 형식에서 역산해 세 형식에 공통 적용" % FIT_FORM)
    L.append("(조업자 행동을 고정하고 가마 형식만 바꾼 대조)\n")
    L.append("%-4s %7s %7s %8s %8s %9s %9s %8s %8s" %
             ("형식", "연돌고", "유입", "최고T", "봉인T", "91h", "342h", "축열", "배기"))
    L.append("%-4s %7s %7s %8s %8s %9s %9s %8s %8s" %
             ("", "[m]", "[kg/s]", "[℃]", "[℃]", "[℃]", "[℃]", "[GJ]", "[%]"))
    for t in "ABC":
        k, rows, info = out[t]
        def at(h):
            return min(rows, key=lambda r: abs(r["t"] - h * 3600))
        peak = max(rows, key=lambda r: r["T_comb"])
        E_in, E_exh, E_wall = energy_budget(rows)
        L.append("%-4s %7.2f %7.3f %8.0f %8.0f %9.0f %9.0f %8.2f %8.1f" %
                 (t, k.H, at(70)["mdot"], peak["T_comb"] - 273.15,
                  at(77.9)["T_comb"] - 273.15, at(91)["T_comb"] - 273.15,
                  at(342)["T_comb"] - 273.15,
                  max(r["stored"] for r in rows) / 1e9, 100 * E_exh / E_in))

    L.append("\n── 실측 대조 (피팅에 쓰지 않은 독립 검증) ──")
    L.append("%-22s %14s %14s" % ("항목", "실측", "계산 (A/B/C)"))
    fired = dict((t, [r for r in out[t][1] if r["t"] <= T_SEAL]) for t in "ABC")
    L.append("%-22s %14s %14s" %
             ("폐쇄 직전 연소실-연도 ΔT", "120 ℃ 내외",
              " / ".join("%.0f" % min(fired[t], key=lambda r: abs(r["t"] - 77.9 * 3600))["dT"]
                         for t in "ABC")))
    L.append("%-22s %14s %14s" %
             ("최대 연소실-연도 ΔT", "300 ℃",
              " / ".join("%.0f" % max(r["dT"] for r in fired[t]) for t in "ABC")))
    L.append("%-22s %14s %14s" %
             ("최고온도", "1,205 ℃",
              " / ".join("%.0f" % max(r["T_comb"] - 273.15 for r in fired[t]) for t in "ABC")))
    L.append("%-22s %14s %14s" %
             ("화구 개구면적", "기록 없음",
              "%.3f m2 (%.0fx%.0f cm)" % (fit[-1]["phi"] * 0.5538,
                                          100 * (fit[-1]["phi"] * 0.5538) ** 0.5,
                                          100 * (fit[-1]["phi"] * 0.5538) ** 0.5)))
    L.append("  → docs/03 이 정상상태 CFD 의 λ 역산으로 독립 추정한 값: 0.06 m2 (25x25 cm)")

    E_in, E_exh, E_wall = energy_budget(out["B"][1])
    L.append("\n에너지 수지 (B, 342 h): 투입 %.2f GJ = 배기 %.2f + 벽체 %.2f GJ  (닫힘 %.2f %%)"
             % (E_in / 1e9, E_exh / 1e9, E_wall / 1e9,
                100 * (E_exh + E_wall) / E_in))
    L.append("실측 총 연료 3,600 kg x 14.7 MJ/kg = 52.92 GJ")
    txt = "\n".join(L)
    print("\n" + txt)
    with open(os.path.join(RESULTS, "rom_summary.txt"), "w") as f:
        f.write(txt + "\n")
    return out, fit, sched, (ts, Ts)


if __name__ == "__main__":
    main()
