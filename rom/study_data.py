#!/usr/bin/env python3
import os
import sys

import efficiency
import rom
import run

R = run.RESULTS
SEG = 1.0


def one(model, fit, sched, ts, Ts):
    k, rows, _ = efficiency.demand(model, fit, sched, ts, Ts, seg_m=SEG)
    fuel = sum(r["fuel"] for r in rows)
    lam = min(r["lam"] for r in rows)
    lam_i = min(r["lam_min"] for r in rows)
    mw = sum(w.m_cp for w in k.ware) / rom.WARE_CP
    w = [k.T[i] - 273.15 for i in range(1, len(k.T) - 1)]
    mu = sum(w) / len(w)
    sd = (sum((x - mu) ** 2 for x in w) / len(w)) ** 0.5
    return dict(fuel=fuel, lam=lam, lam_i=lam_i, ware=mw, T=w, front=w[0], back=w[-1],
                dT=max(w) - min(w), sd=sd, mean=mu,
                comb=k.T[0] - 273.15, flue=k.T[-1] - 273.15,
                L=k.geo["L_fire"], H=k.H)


def main():
    sched = rom.load_schedule(run.SCHED)
    ts, Ts = run.load_curve()
    fit = run.load_fit()
    print("기준점 %s · 적재 %.2f/%.2f" % (run.FIT_NODE, rom.LOAD_FRAC, rom.BLOCK_FRAC))

    sets = [
        ("study_length.csv", "L_m",
         [("B_L025", 2.5), ("B_L045", 4.5), ("B_L065", 6.5), ("B_L085", 8.5)]),
        ("study_steps.csv", "n_step",
         [("B_L065", 0), ("B_L065_S6", 6), ("B_L065_S12", 12), ("B_L065_S20", 20)]),
        ("study_form.csv", "form",
         [("A_L065", 1), ("B_L065", 2), ("C_L065", 3)]),
    ]
    for fn, key, items in sets:
        out = []
        for m, v in items:
            print("  %s ..." % m, flush=True)
            d = one(m, fit, sched, ts, Ts)
            d[key] = v
            d["model"] = m
            out.append(d)
        p = os.path.join(R, fn)
        with open(p, "w") as f:
            f.write("model,%s,fuel_kg,lambda_segmean_min,lambda_inst_min,ware_kg,T_front_C,T_back_C,"
                    "dT_C,sd_C,T_mean_C,T_comb_C,T_flue_C,stack_m,segments\n" % key)
            for d in out:
                f.write("%s,%s,%.1f,%.3f,%.3f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.2f,%s\n"
                        % (d["model"], d[key], d["fuel"], d["lam"], d["lam_i"], d["ware"],
                           d["front"], d["back"], d["dT"], d["sd"], d["mean"],
                           d["comb"], d["flue"], d["H"],
                           " ".join("%.0f" % x for x in d["T"])))
        print("→ %s" % p)
        publish(p, fn)


PUBLISH = {
    "study_form.csv":   ["result_1"],
    "study_length.csv": ["result_2"],
    "study_steps.csv":  ["result_3"],
}


def publish(src, fn):
    import shutil
    for r in PUBLISH.get(fn, []):
        d = os.path.join(R, r, "data")
        if os.path.isdir(d):
            shutil.copy2(src, os.path.join(d, fn))
            print("   ↳ %s/data/%s" % (r, fn))


if __name__ == "__main__":
    main()
