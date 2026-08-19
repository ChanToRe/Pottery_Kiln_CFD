#!/usr/bin/env python3
import os
import sys

import calibrate
import efficiency
import geom
import rom
import run

SEG_M = 1.0
TAG = os.environ.get("TAG", "")
rom_rr = float(os.environ.get("RAD_RANGE", "1.0"))
LOAD = float(os.environ.get("LOAD_FRAC", rom.LOAD_FRAC))
BLOCK = os.environ.get("BLOCK_FRAC", rom.BLOCK_FRAC)
T_FIRE = 1000.0
LENS = [("B_L025", 2.5), ("B_L045", 4.5), ("B_L065", 6.5), ("B_L085", 8.5)]
FRAME_H = 1.0


def run_one(model, fit, sched, ts, Ts, frames=None):
    k, rows, info = efficiency.demand(model, fit, sched, ts, Ts, seg_m=SEG_M)
    fuel = sum(r["fuel"] for r in rows)

    k2, _ = calibrate.build(model, seg_m=SEG_M, T_amb=run.T_AMB)
    hist = []
    nxt = 0.0
    for r in rows:
        n = int(round((r["t1"] - r["t0"]) / run.DT))
        for i in range(n):
            k2.step(run.DT, r["Q"], next(f["phi"] for f in fit if f["t1"] == r["t1"]))
            if k2.t >= nxt:
                hist.append((k2.t / 3600.0, [x - 273.15 for x in k2.T]))
                nxt += FRAME_H * 3600.0
    return k2, fuel, rows, hist


def eff_length(T, seg_len, n_ware):
    ware = T[1:1 + n_ware]
    tot = 0.0
    for i, t in enumerate(ware):
        if t >= T_FIRE:
            tot += seg_len
        elif i > 0 and ware[i - 1] >= T_FIRE:
            f = (ware[i - 1] - T_FIRE) / (ware[i - 1] - t)
            tot += seg_len * max(0.0, min(1.0, f))
    return tot


def main():
    rom.RAD_RANGE = rom_rr
    rom.LOAD_FRAC = LOAD
    rom.BLOCK_FRAC = float(BLOCK) if BLOCK is not None else None
    print("적재 부피점유율 %.2f, 복사차폐율 %s, 도달거리 %.2f\n"
          % (LOAD, BLOCK if BLOCK is not None else "=점유율", rom_rr))
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()

    print("비교 2 (개정) — 소성실 축방향 온도, 구간 %.1f m\n" % SEG_M)
    out = []
    for model, L in LENS:
        g = geom.extract(model, seg_m=SEG_M)
        nw = len(g["ware_keys"])
        print("  %s  소성부 %.1f m -> %d 구간 x %.2f m" % (model, L, nw, g["seg_len"]))
        k, fuel, rows, hist = run_one(model, fit, sched, ts, Ts)
        T = [x - 273.15 for x in k.T]
        ef = eff_length(T, g["seg_len"], nw)
        out.append(dict(model=model, L=L, V=g["V"], nw=nw, seg=g["seg_len"],
                        fuel=fuel, T=T, eff=ef, hist=hist,
                        Tmin=min(T[1:1 + nw]), Tmax=T[0]))
        print("     연료 %.0f kg   축방향 %s" % (fuel, " ".join("%.0f" % x for x in T)))
        print("     유효 소성구간 %.2f / %.2f m  (%.0f %%)\n"
              % (ef, nw * g["seg_len"], 100 * ef / (nw * g["seg_len"])))

    L = []
    L.append("비교 2 (개정) — 소성실 축방향 온도와 유효 소성용적\n")
    L.append("② 수평연소 유단식. 소성부를 %.1f m 구간으로 쪼개 각 구간 온도를 계산했다." % SEG_M)
    L.append("소성 하한 %.0f ℃ (도질토기). 연료는 앞과 같이 역문제로 구했다.\n" % T_FIRE)
    L.append("%-9s %6s %9s %9s %9s %11s %10s %12s" %
             ("model", "L[m]", "연료[kg]", "연소실[℃]", "최후단[℃]",
              "유효구간[m]", "유효비율", "연료/유효m"))
    for r in out:
        L.append("%-9s %6.1f %9.0f %9.0f %9.0f %11.2f %9.0f %% %12.0f" %
                 (r["model"], r["L"], r["fuel"], r["Tmax"], r["Tmin"],
                  r["eff"], 100 * r["eff"] / (r["nw"] * r["seg"]),
                  r["fuel"] / r["eff"] if r["eff"] > 0 else 0))

    L.append("\n구간별 온도 [℃]  (연소실 → 최후단, t = 78 h)")
    for r in out:
        L.append("  L=%.1f m  %s" % (r["L"], "  ".join("%5.0f" % x for x in r["T"])))

    L.append("\n── 읽는 법 ──")
    r0, r1 = out[0], out[-1]
    L.append("소성부를 %.1f → %.1f m 로 늘리면" % (r0["L"], r1["L"]))
    L.append("  연료        %.0f → %.0f kg   (+%.0f %%)"
             % (r0["fuel"], r1["fuel"], 100 * (r1["fuel"] / r0["fuel"] - 1)))
    L.append("  유효구간    %.2f → %.2f m   (+%.0f %%)"
             % (r0["eff"], r1["eff"], 100 * (r1["eff"] / r0["eff"] - 1)))
    L.append("  연료/유효m  %.0f → %.0f kg/m  (%+.0f %%)"
             % (r0["fuel"] / r0["eff"], r1["fuel"] / r1["eff"],
                100 * ((r1["fuel"] / r1["eff"]) / (r0["fuel"] / r0["eff"]) - 1)))

    txt = "\n".join(L)
    print(txt)
    with open(os.path.join(run.RESULTS, "rom_length_axial%s.txt" % TAG), "w") as f:
        f.write(txt + "\n")
    with open(os.path.join(run.RESULTS, "rom_length_axial%s.csv" % TAG), "w") as f:
        f.write("model,L_m,fuel_kg,eff_len_m,eff_frac,fuel_per_eff_m," +
                ",".join("T%d" % i for i in range(12)) + "\n")
        for r in out:
            f.write("%s,%.1f,%.1f,%.3f,%.4f,%.1f,%s\n" %
                    (r["model"], r["L"], r["fuel"], r["eff"], r["eff"] / r["L"],
                     r["fuel"] / r["eff"],
                     ",".join("%.1f" % x for x in (r["T"] + [0] * 12)[:12])))
    with open(os.path.join(run.RESULTS, "rom_length_axial_hist%s.csv" % TAG), "w") as f:
        f.write("model,t_h,node,T_C\n")
        for r in out:
            for th, Ts_ in r["hist"]:
                for i, x in enumerate(Ts_):
                    f.write("%s,%.2f,%d,%.1f\n" % (r["model"], th, i, x))
    print("\n→ Results/rom_length_axial.{txt,csv}, rom_length_axial_hist.csv")
    return out


if __name__ == "__main__":
    main()
