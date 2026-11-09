#!/usr/bin/env python3
"""
비교 연구의 수치를 한 번에 계산해 CSV 로 남긴다.

그림 스크립트가 제각기 축소모델을 다시 돌리면 보정이 바뀔 때마다 어긋난다.
계산은 여기서 한 번만 하고, 그림은 이 CSV 만 읽는다.

    python3 study_data.py            (rom_phi.csv 가 먼저 있어야 한다 — run.py)

출력
    Results/rom/study_length.csv   소성실 길이 4수준
    Results/rom/study_steps.csv    소성실 단 4수준
    Results/rom/study_form.csv     연소부 형식 3종
    Results/rom/study_fuel_exact.csv  위 세 표의 연료량 정밀값 (그래프 자료의 kg 정수 반올림용.
                                      표는 0.1 kg 까지만 적으므로 다시 반올림하면 두 번 반올림이 된다)
"""
import os

import efficiency
import rom
import run

R = run.RESULTS
SEG = 1.0


def one(model, fit, sched, ts, Ts):
    k, rows, _ = efficiency.demand(model, fit, sched, ts, Ts, seg_m=SEG)
    fuel = sum(r["fuel"] for r in rows)
    # λ 는 두 가지로 잰다. 이름을 뭉뚱그리면 경로마다 다른 값이 나오고
    # 실제로 그랬다 — efficiency.py 는 순간 최솟값, 여기는 구간평균의
    # 최솟값을 "λ최소" 라 부르고 있었다 (1.11 대 1.34).
    lam = min(r["lam"] for r in rows)               # 구간평균 중 최솟값
    lam_i = min(r["lam_min"] for r in rows)         # 순간 최솟값
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
    exact = []
    for fn, key, items in sets:
        out = []
        for m, v in items:
            print("  %s ..." % m, flush=True)
            d = one(m, fit, sched, ts, Ts)
            d[key] = v
            d["model"] = m
            out.append(d)
            exact.append((fn[len("study_"):-len(".csv")], m, d["fuel"]))
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
    p = os.path.join(R, "study_fuel_exact.csv")
    with open(p, "w") as f:
        f.write("study,model,fuel_kg\n")
        for s, m, v in exact:
            f.write("%s,%s,%.6f\n" % (s, m, v))
    print("→ %s" % p)


if __name__ == "__main__":
    main()
