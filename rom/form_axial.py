#!/usr/bin/env python3
"""
비교 1 (개정) — 연소부 형식별 소성실 축방향 온도와 조업 난이도

예전 판은 축방향 불균일도를 정상상태 CFD(cases/*_steady)에서 읽었다. 그 계산은
화구 완전 개방 · 150 kW · λ≈14 로 **소성이 일어나지 않는 조건**이며 온도가
40–408 ℃ 에 머문다. 소성 창(1,000–1,100 ℃)을 논할 수 있는 해가 아니다.

여기서는 비교 2 와 같은 방식으로, 실제 조업점에서 78 시간을 돌린 축소모델의
구간별 온도를 쓴다. 연료는 앞과 같이 역문제로 구한다.

산출
  구간별 온도 (t = 78 h)
  앞뒤 온도차          — 조업자가 감당해야 할 축방향 편차
  유효 소성구간        — 1,000 ℃ 이상인 길이 (도질토기 소결 하한)
  소성 창 안 구간      — 1,000–1,100 ℃ 사이. 변형 상한을 넘지 않으면서 익는 구간

실행:  python3 rom/form_axial.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import geom
import length_axial as LA
import rom
import run

FORMS = [("A_L065", "1 horizontal, unstepped"),
         ("B_L065", "2 horizontal, stepped"),
         ("C_L065", "3 vertical, stepped")]
T_LO = 1000.0                   # 도질토기 소결 하한 [℃]
# 상한 1,100 ℃ 는 '변형이 시작된 온도'가 아니다. 홍진근 2011: 최고 약 1,200 ℃ 에서 2열 고배가
# 앞으로 휘기 시작해 그 뒤 1,000–1,100 ℃ 를 유지했다 (N-49). 사용자 결정(2026-10-20): 값은 두고
# '실험이 유지한 조업 온도대'로 뜻을 바꾼다. 다른 범위는 민감도로 함께 낸다 (E-16).
T_HI = 1100.0                   # 조업 온도대 상한 [℃]
SEG_M = LA.SEG_M


def in_window(T, seg_len, n_ware):
    """1,000–1,100 ℃ 안에 든 소성부 길이 [m]. 구간 단위로 센다."""
    ware = T[1:1 + n_ware]
    return seg_len * sum(1 for t in ware if T_LO <= t <= T_HI)


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()

    print("비교 1 (개정) — 형식별 소성실 축방향 온도, 구간 %.1f m" % SEG_M)
    print("적재 부피점유율 %.2f · 복사차폐율 %.2f · 78 h\n"
          % (rom.LOAD_FRAC, rom.BLOCK_FRAC))

    out = []
    for model, label in FORMS:
        g = geom.extract(model, seg_m=SEG_M)
        nw = len(g["ware_keys"])
        k, fuel, rows, hist = LA.run_one(model, fit, sched, ts, Ts)
        T = [x - 273.15 for x in k.T]
        ware = T[1:1 + nw]
        out.append(dict(model=model, label=label, fuel=fuel, T=T, nw=nw,
                        seg=g["seg_len"], H=g["H_stack"],
                        front=ware[0], back=ware[-1],
                        spread=ware[0] - ware[-1],
                        eff=LA.eff_length(T, g["seg_len"], nw),
                        win=in_window(T, g["seg_len"], nw),
                        total=nw * g["seg_len"]))
        print("  %-9s 연료 %.0f kg  축방향 %s"
              % (model, fuel, " ".join("%.0f" % x for x in T)))

    L = ["비교 1 (개정) — 형식별 소성실 축방향 온도와 조업 난이도\n",
         "실제 조업점(역산 발열 · 화구 개구율 φ(t))에서 78 h 를 돌린 축소모델이다.",
         "정상상태 CFD (화구 완전개방 150 kW, 40-408 ℃) 를 쓰던 예전 판을 대체한다.\n",
         "%-9s %9s %8s %9s %9s %10s %12s %12s" %
         ("model", "연료[kg]", "연돌고", "앞[℃]", "뒤[℃]", "앞뒤차[℃]",
          "≥1000℃[m]", "창안[m]")]
    for r in out:
        L.append("%-9s %9.0f %7.2fm %9.0f %9.0f %10.1f %11.2f %12.2f"
                 % (r["model"], r["fuel"], r["H"], r["front"], r["back"],
                    r["spread"], r["eff"], r["win"]))

    L.append("\n구간별 온도 [℃]  (연소실 → 최후단, t = 78 h)")
    for r in out:
        L.append("  %-9s %s" % (r["model"], "  ".join("%5.0f" % x for x in r["T"])))

    L.append("\n── 읽는 법 ──")
    L.append("앞뒤차가 크면 앞쪽은 과소성, 뒤쪽은 미소성이 된다. 조업자가 승온을")
    L.append("멈추는 시점이 그 편차에 걸린다 — 앞쪽 기물이 휘기 시작하면 뒤쪽이")
    L.append("아직 덜 익었어도 더 올릴 수 없다(조성원·홍진근 2011).")
    L.append("창안[m] 은 1,000-1,100 ℃ 에 함께 든 길이다. 이것이 한 번의 조업에서")
    L.append("실제로 쓸 수 있는 소성부의 길이다.")

    txt = "\n".join(L)
    print("\n" + txt)
    with open(os.path.join(run.RESULTS, "rom_form_axial.txt"), "w") as f:
        f.write(txt + "\n")
    with open(os.path.join(run.RESULTS, "rom_form_axial.csv"), "w") as f:
        f.write("model,fuel_kg,H_stack_m,T_front_C,T_back_C,spread_C,"
                "eff_len_m,window_len_m,ware_len_m,"
                + ",".join("T%d" % i for i in range(12)) + "\n")
        for r in out:
            f.write("%s,%.1f,%.3f,%.1f,%.1f,%.1f,%.3f,%.3f,%.3f,%s\n" %
                    (r["model"], r["fuel"], r["H"], r["front"], r["back"],
                     r["spread"], r["eff"], r["win"], r["total"],
                     ",".join("%.1f" % x for x in (r["T"] + [0] * 12)[:12])))
    print("\n→ Results/rom/rom_form_axial.{txt,csv}")


if __name__ == "__main__":
    main()
