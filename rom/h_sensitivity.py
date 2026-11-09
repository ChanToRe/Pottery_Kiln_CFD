#!/usr/bin/env python3
"""
대류계수를 억지로 키우면 연료가 움직이는가 — 원고 Discussion 의 "대류계수를
4배로 올려도 연료 변화 0.05 %" 시험을 현재 설정으로 다시 한다.

투고본의 0.05 % 는 2026-08-09 에 B_L065_S2(2단 시험 형상), h_ref 5.88, 그때의
보정·φ 로 계산한 값이다 (reference/rom/h_sensitivity_2026-08-09_old.txt). 그 스크립트는
남아 있지 않아, 같은 시험을 투고본 최종 설정(B_L065 와 계단 3종, rom_phi.csv)으로
새로 짰다. 따라서 수치는 원고의 0.05 % 와 같지 않을 수 있다.

    python3 h_sensitivity.py        → Results/rom/h_sensitivity.txt
"""
import os

import calibrate
import efficiency
import rom
import run

MODELS = ["B_L065", "B_L065_S6", "B_L065_S12", "B_L065_S20"]
FACTORS = [1.0, 2.0, 4.0]


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()
    h0 = calibrate.h_conv_ref("B")
    L = ["대류계수 배율 시험 — h_conv_ref(B) = %.4f W/m2K, 자연대류 하한 %.1f W/m2K"
         % (h0, rom.H_NAT),
         "적재 %.2f / 차폐 %.2f, 소성실 1 m 분할, φ = Results/rom/rom_phi.csv\n"
         % (rom.LOAD_FRAC, rom.BLOCK_FRAC),
         "%-12s %6s %10s %10s %10s %10s" % ("model", "h 배율", "연료[kg]", "×1 대비[%]",
                                          "최후단[℃]", "앞뒤차[℃]")]
    for m in MODELS:
        base = None
        for f in FACTORS:
            k, rows, _ = efficiency.demand(m, fit, sched, ts, Ts, seg_m=1.0,
                                           h_conv_ref=f * h0)
            fuel = sum(r["fuel"] for r in rows)
            ware = [k.T[i] - 273.15 for i in range(1, len(k.T) - 1)]
            base = fuel if base is None else base
            row = "%-12s %6.1f %10.1f %10.3f %10.1f %10.1f" % (
                m, f, fuel, 100.0 * (fuel / base - 1.0), ware[-1], max(ware) - min(ware))
            print(row, flush=True)
            L.append(row)
    txt = "\n".join(L)
    with open(os.path.join(run.RESULTS, "h_sensitivity.txt"), "w") as fh:
        fh.write(txt + "\n")
    print("\n→ Results/rom/h_sensitivity.txt")


if __name__ == "__main__":
    main()
