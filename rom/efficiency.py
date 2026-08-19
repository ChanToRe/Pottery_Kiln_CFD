#!/usr/bin/env python3
import os
import sys

import calibrate
import rom
import run

AIR_PER_WOOD = 6.0
LAM_MIN = 1.0


def demand(model, fit, sched, ts, Ts, verbose=False, seg_m=None, **over):
    if seg_m is None:
        seg_m = run.SEG_M
    kw = dict(T_amb=run.T_AMB)
    kw.update(over)
    k, info = calibrate.build(model, seg_m=seg_m, **kw)
    rows = []
    for f in fit:
        t0, t1, phi = f["t0"], f["t1"], f["phi"]
        target = run.curve_at(ts, Ts, t1)
        state = k.save()

        def endT(m):
            k.restore(state)
            return run.advance(k, sched, t0, t1, phi, qmul=m)

        lo, hi = 0.15, 6.0
        if endT(hi) < target:
            m, note = hi, "상한"
        elif endT(lo) > target:
            m, note = lo, "하한"
        else:
            for _ in range(20):
                mid = 0.5 * (lo + hi)
                if endT(mid) < target:
                    lo = mid
                else:
                    hi = mid
            m, note = 0.5 * (lo + hi), ""

        k.restore(state)
        n = int(round((t1 - t0) / run.DT))
        md_sum, lam_min, lam_sum = 0.0, 1e9, 0.0
        Q0 = rom.Q_at(sched, t0)
        for i in range(n):
            r = k.step(run.DT, m * Q0, phi)
            fuel_rate = m * Q0 / rom.LHV_EFF
            lam = r["mdot"] / (AIR_PER_WOOD * fuel_rate) if fuel_rate > 0 else 1e9
            lam_min = min(lam_min, lam)
            lam_sum += lam
            md_sum += r["mdot"]
        dur = t1 - t0
        rows.append(dict(t0=t0, t1=t1, m=m, note=note, target=target,
                         Q=m * Q0, fuel=m * Q0 / rom.LHV_EFF * dur,
                         lam=lam_sum / n, lam_min=lam_min,
                         mdot=md_sum / n, dur=dur))
        if verbose:
            print("    %3.0f-%3.0f h  m=%.3f  Q=%6.1f kW  연료 %6.1f kg  "
                  "λ=%.2f %s" % (t0 / 3600, t1 / 3600, m, m * Q0 / 1e3,
                                 rows[-1]["fuel"], rows[-1]["lam"], note))
    return k, rows, info


def total(model, fit, sched, ts, Ts, seg_m=None, **over):
    _, rows, _ = demand(model, fit, sched, ts, Ts, seg_m=seg_m, **over)
    return sum(r["fuel"] for r in rows)


def sens():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()
    cases = [("기준", {}, None),
             ("벽체 k 1.0 → 0.8", {}, ("WALL_K", 0.8)),
             ("벽체 k 1.0 → 1.4", {}, ("WALL_K", 1.4)),
             ("축방향 복사 F 0.7 → 0.5", {}, ("F_RAD_AX", 0.5)),
             ("외기 19.3 → 5.0 ℃", {"T_amb": 278.15}, None)]
    L = ["연료 소요량 민감도 — 형식 간 차폭이 유지되는가\n",
         "%-24s %8s %8s %8s %9s %9s" %
         ("변형", "①[kg]", "②[kg]", "③[kg]", "차폭[kg]", "차폭[%]")]
    for name, over, glob in cases:
        saved = None
        if glob:
            key, val = glob
            if key == "WALL_K":
                saved, rom.WALL["k"] = rom.WALL["k"], val
            else:
                saved = getattr(rom, key)
                setattr(rom, key, val)
        T = dict((t, total("%s_L065" % t, fit, sched, ts, Ts, **over)) for t in "ABC")
        if glob:
            key, _ = glob
            if key == "WALL_K":
                rom.WALL["k"] = saved
            else:
                setattr(rom, key, saved)
        sp = max(T.values()) - min(T.values())
        row = "%-24s %8.0f %8.0f %8.0f %9.0f %9.1f" % (
            name, T["A"], T["B"], T["C"], sp, 100 * sp / min(T.values()))
        print(row, flush=True)
        L.append(row)
    L.append("")
    L.append("절대 연료량은 파라미터에 따라 크게 움직이지만, 형식 간 차폭이")
    L.append("어느 조건에서도 4 % 안에 머무는지가 결론의 관건이다.")
    txt = "\n".join(L)
    with open(os.path.join(run.RESULTS, "rom_efficiency_sens.txt"), "w") as f:
        f.write(txt + "\n")
    print("\n→ Results/rom_efficiency_sens.txt")


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()
    base = sum(p[1] * (sched[i + 1][0] - p[0])
               for i, p in enumerate(sched[:-1])) / rom.LHV_EFF

    print("비교 1 — 연소부 형식별 연료 효율\n")
    print("고정: 소성 절차(6구간 78 h) + 실측 승온곡선 + 화구 개구율 φ(t)")
    print("미지: 구간별 발열률 → 연료 소요량\n")
    print("실측 기준(양산 호계동): 총 %.0f kg / %.2f GJ\n" % (base, base * rom.LHV_EFF / 1e9))

    NAME = {"A": "① 수평연소 무단식", "B": "② 수평연소 유단식",
            "C": "③ 수직연소 유단식"}
    res = {}
    for t in "ABC":
        print("  %s %s" % (t, NAME[t]))
        k, rows, info = demand("%s_L065" % t, fit, sched, ts, Ts, verbose=True)
        res[t] = (k, rows, info)
        print()

    L = []
    L.append("비교 1 — 연소부 형식별 연료 효율 (L065)\n")
    L.append("동일한 소성 절차(구간 시각·목표 온도·화구 개구율)에서")
    L.append("실측 승온곡선을 재현하는 데 필요한 연료를 형식별로 역산했다.\n")
    L.append("%-20s %10s %10s %9s %9s %8s" %
             ("형식", "총연료[kg]", "열량[GJ]", "실측대비", "연돌고[m]", "λ최소"))
    ref = sum(r["fuel"] for r in res["B"][1])
    for t in "ABC":
        k, rows, info = res[t]
        tot = sum(r["fuel"] for r in rows)
        lam = min(r["lam_min"] for r in rows)
        L.append("%-20s %10.0f %10.2f %+8.1f %% %9.2f %8.2f" %
                 (NAME[t], tot, tot * rom.LHV_EFF / 1e9,
                  100 * (tot / ref - 1), k.H, lam))
    L.append("")
    L.append("실측 총 연료 %.0f kg (홍진근 2011). 실측대비 는 ② 를 기준으로 한 증감." % base)

    lam_bad = [(t, r) for t in "ABC" for r in res[t][1] if r["lam_min"] < LAM_MIN]
    if lam_bad:
        L.append("")
        L.append("⚠ 공기비 λ < 1 구간 (연소 불가 — 해가 물리적으로 성립하지 않음):")
        for t, r in lam_bad:
            L.append("   %s  %3.0f-%3.0f h  λ_min=%.2f" %
                     (t, r["t0"] / 3600, r["t1"] / 3600, r["lam_min"]))
    else:
        L.append("")
        L.append("공기비 λ 는 모든 형식·구간에서 1 이상이다 — 세 해 모두 연소가 성립한다.")

    L.append("")
    L.append("구간별 상세 (연료 [kg] / 공기비 λ)")
    L.append("%-12s %s" % ("구간[h]", "  ".join("%14s" % NAME[t][:1] for t in "ABC")))
    for j in range(len(fit)):
        cells = []
        for t in "ABC":
            r = res[t][1][j]
            cells.append("%7.1f (%.2f)" % (r["fuel"], r["lam"]))
        r0 = res["A"][1][j]
        L.append("%3.0f - %3.0f    %s" %
                 (r0["t0"] / 3600, r0["t1"] / 3600, "  ".join("%14s" % c for c in cells)))

    txt = "\n".join(L)
    print(txt)
    with open(os.path.join(run.RESULTS, "rom_efficiency.txt"), "w") as f:
        f.write(txt + "\n")
    print("\n→ Results/rom_efficiency.txt")
    return res


if __name__ == "__main__":
    if "--sens" in sys.argv:
        sens()
    else:
        main()
