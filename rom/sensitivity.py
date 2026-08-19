#!/usr/bin/env python3
import os

import calibrate
import rom
import run


def peak_to_seal(model, fit, sched, **over):
    kw = dict(T_amb=run.T_AMB)
    kw.update(over)
    k, _ = calibrate.build(model, **kw)
    rows = []
    t = 0.0
    for f in fit:
        run.advance(k, sched, t, f["t1"], f["phi"], rows, every=3600.0)
        t = f["t1"]
    return max(r["T_comb"] for r in rows) - 273.15


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    h0 = calibrate.h_conv_ref("A")

    cases = [("기준", {}, None),
             ("내부 방사율 ε 0.80 → 0.60", {"eps_rad": 0.60}, None),
             ("내부 방사율 ε 0.80 → 0.95", {"eps_rad": 0.95}, None),
             ("축방향 복사 F 0.70 → 0.50", {}, ("F_RAD_AX", 0.50)),
             ("축방향 복사 F 0.70 → 0.90", {}, ("F_RAD_AX", 0.90)),
             ("대류계수 h x0.7", {"h_conv_ref": 0.7 * h0}, None),
             ("대류계수 h x1.4", {"h_conv_ref": 1.4 * h0}, None),
             ("벽체 k 1.0 → 0.8", {}, ("WALL_K", 0.8)),
             ("벽체 k 1.0 → 1.4", {}, ("WALL_K", 1.4)),
             ("외기 19.3 → 5.0 ℃", {"T_amb": 278.15}, None)]

    print("%-26s %7s %7s %7s %9s" % ("변형", "A[℃]", "B[℃]", "C[℃]", "형식차폭"))
    base_spread = None
    lines = []
    for name, over, glob in cases:
        saved = None
        if glob:
            key, val = glob
            if key == "WALL_K":
                saved = rom.WALL["k"]
                rom.WALL["k"] = val
            else:
                saved = getattr(rom, key)
                setattr(rom, key, val)
        T = dict((t, peak_to_seal("%s_L065" % t, fit, sched, **over)) for t in "ABC")
        if glob:
            key, _ = glob
            if key == "WALL_K":
                rom.WALL["k"] = saved
            else:
                setattr(rom, key, saved)
        spread = max(T.values()) - min(T.values())
        if base_spread is None:
            base_spread = spread
            base_T = dict(T)
        row = "%-26s %7.0f %7.0f %7.0f %9.0f" % (name, T["A"], T["B"], T["C"], spread)
        print(row)
        lines.append(row)

    txt = ("민감도 — 최고 연소실 온도 [℃]\n\n"
           "%-26s %7s %7s %7s %9s\n" % ("변형", "A", "B", "C", "형식차폭")
           + "\n".join(lines) + "\n\n"
           "기준 조건에서 형식 간 차이는 %.0f ℃ 이고,\n"
           "파라미터 하나를 불확실 범위 끝으로 옮기면 온도가 그보다 크게 움직인다.\n"
           % base_spread)
    with open(os.path.join(run.RESULTS, "rom_sensitivity.txt"), "w") as f:
        f.write(txt)
    print("\n→ Results/rom_sensitivity.txt")


if __name__ == "__main__":
    main()
