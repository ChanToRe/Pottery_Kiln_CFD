#!/usr/bin/env python3
"""
2-2c (E-06) CFD 수렴 이력·격자 품질·보존 검사 — 원고에 쓰인 CFD 6 건(정상 3, 비정상 3)의 로그에서.

    python3 cfd/checks/convergence_summary.py

  있으면 함께: 조밀 격자(Results/checks/grid, 2-2a), C Courant 2(Results/checks/courant/C_co2, 2-2b),
  조업점(Results/checks/oppoint, 2-2d). 조업점의 에너지%는 막은 화구로 나간 열을 빼고 센 값이다
  (막은 화구까지 넣은 수지는 summarize_checks.py).

  격자 품질   mesh/<M>/log.checkMesh (셀 수, 최대 종횡비, 비직교도 최대·평균, 최대 skewness, 판정)
  정상 해     마지막 2,000 회: 변수별 초기 잔차 평균·최대, 질량(화구 유입 − 출구 유출)/유입,
              에너지 (ṁ cp (T출구 − 외기) + 벽 손실)/발열, 누적 연속방정식 오차, 온도 상한 발동
  비정상 해   시간 단계별 변수의 첫 풀이 초기 잔차 (45 s 전체의 중앙값·최대),
              시간 단계 연속방정식 오차(global) 최대, 누적 오차, 최대 Courant 수, 온도 상한 발동
  잔차 이력   Results/checks/convergence/residuals_<steady|transient>_<M>.csv (보충자료 그림용)
출력: Results/checks/convergence/summary.txt, convergence.csv
"""
import csv
import os
import re
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cases  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "Results", "checks", "convergence")
MODELS = ["A_L065", "B_L065", "C_L065"]
T_AMB, CP, NAVG = 292.45, 1100.0, 2000
FIELDS = ["Ux", "Uy", "Uz", "h", "p_rgh", "k", "omega"]          # 정상: k-ω SST
FIELDS_T = ["Ux", "Uy", "Uz", "h", "p_rgh", "k", "epsilon"]      # 비정상: k-ε
RES = re.compile(r"Solving for (\w+), Initial residual = ([-\d.e+]+)")
LINES = []


def say(s=""):
    print(s)
    LINES.append(s)


def heat_kw(case):
    txt = open(os.path.join(case, "system", "fvOptions")).read()
    return float(re.search(r"h\s+\(([\d.eE+-]+)\s+0\)", txt).group(1)) / 1e3


def mesh_quality(M, log):
    t = open(log, errors="ignore").read()
    g = lambda p: (re.search(p, t, re.I | re.M).group(1) if re.search(p, t, re.I | re.M) else "")
    return dict(model=M, cells=g(r"^\s*cells:\s*(\d+)"), aspect_max=g(r"Max aspect ratio = ([\d.e+-]+)"),
                nonorth_max=g(r"non-orthogonality Max: ([\d.e+-]+)"), nonorth_avg=g(r"average: ([\d.e+-]+)"),
                skew_max=g(r"Max skewness = ([\d.e+-]+)"),
                verdict="OK" if "Mesh OK" in t else "Failed %s" % g(r"Failed (\d+) mesh checks"))


def steps_of(txt):
    """[(시각 문자열, 블록 본문)]"""
    parts = re.split(r"^Time = ([\d.e+-]+)$", txt, flags=re.M)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def steady(case, M, tag):
    txt = open(os.path.join(case, "log.solver"), errors="ignore").read()
    steps = steps_of(txt)
    rows = []
    for t, body in steps:
        r = {"iter": int(t)}
        for f, v in RES.findall(body):
            if f in FIELDS and f not in r:              # 같은 반복에서 첫 풀이(p_rgh 는 두 번)
                r[f] = float(v)
        rows.append(r)
    write_csv("residuals_steady%s_%s.csv" % (tag, M.rstrip("*")), ["iter"] + FIELDS, rows)
    last = rows[-1]["iter"]
    tail_rows = [r for r in rows if r["iter"] > last - NAVG]
    tail = "".join(b for t, b in steps if int(t) > last - NAVG)
    num = lambda p: [abs(float(x)) for x in re.findall(p, tail)]
    m_in = num(r"sum\(inlet\) of phi = ([-\d.e+]+)")
    m_out = num(r"sum\(outlet\) of phi = ([-\d.e+]+)")
    T_out = num(r"areaAverage\(outlet\) of T = ([\d.e+-]+)")
    wall = num(r"min/max/integ\(walls\) = [-\d.e+]+, [-\d.e+]+, ([-\d.e+]+)")
    cum = re.findall(r"cumulative = ([-\d.e+]+)", tail)
    lim = [int(x) for x in re.findall(r"Upper limited (\d+)", tail)]
    mi, mo = st.mean(m_in), st.mean(m_out)
    bal = (mi * CP * (st.mean(T_out) - T_AMB) + st.mean(wall)) / (heat_kw(case) * 1e3)
    d = dict(kind="steady" + tag, model=M, iters=last,
             mass_imbalance_pct=100 * (mi - mo) / mi, energy_balance_pct=100 * bal,
             cum_continuity=float(cum[-1]) if cum else float("nan"),
             limiter_cells_max=max(lim) if lim else 0)
    for f in FIELDS:
        v = [r[f] for r in tail_rows if f in r]
        d[f + "_mean"], d[f + "_max"] = st.mean(v), max(v)
    return d


def transient(case, M):
    txt = open(os.path.join(case, "log.solver"), errors="ignore").read()
    steps = steps_of(txt)
    rows = []
    gl, co, lim = [], [], []
    for t, body in steps:
        r = {"t_s": float(t)}
        # 변수별 그 시간 단계의 첫 풀이 (k·omega 는 마지막 PIMPLE 반복에서만 푼다)
        for f, v in RES.findall(body):
            if f in FIELDS_T and f not in r:
                r[f] = float(v)
        rows.append(r)
        gl += [abs(float(x)) for x in re.findall(r"global = ([-\d.e+]+)", body)]
        co += [float(x) for x in re.findall(r"Courant Number mean: [\d.e+-]+ max: ([\d.e+-]+)", body)]
        lim += [int(x) for x in re.findall(r"Upper limited (\d+)", body)]
    write_csv("residuals_transient_%s.csv" % (M.rstrip("*") + "_fine" if M.endswith("*") else M), ["t_s"] + FIELDS_T, rows)
    cum = re.findall(r"cumulative = ([-\d.e+]+)", txt)
    d = dict(kind="transient", model=M, iters=len(rows), t_end=rows[-1]["t_s"],
             continuity_global_max=max(gl), cum_continuity=float(cum[-1]),
             courant_max=max(co), limiter_cells_max=max(lim) if lim else 0,
             limiter_steps=sum(1 for x in lim if x > 0))
    for f in FIELDS_T:
        v = [r[f] for r in rows if f in r and r["t_s"] > 0.5]
        d[f + "_median"], d[f + "_max"] = st.median(v), max(v)
    return d


def write_csv(name, fields, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    say("2-2c CFD 수렴·격자 품질·보존 검사 (E-06)\n")
    say("격자 품질 (checkMesh)")
    say("%-8s %8s %9s %10s %10s %9s %s" % ("model", "cells", "종횡비max", "비직교max", "비직교avg", "skew max", "판정"))
    mq = []
    for M in MODELS:
        q = mesh_quality(M, os.path.join(ROOT, "mesh", M, "log.checkMesh"))
        mq.append(q)
        say("%-8s %8s %9s %10s %10s %9s %s" % (M, q["cells"], q["aspect_max"], q["nonorth_max"],
                                                q["nonorth_avg"], q["skew_max"], q["verdict"]))
    fine = os.path.join(ROOT, "Results", "checks", "grid", "mesh")
    for M in MODELS:
        log = os.path.join(fine, M, "log.checkMesh")
        if os.path.exists(log):
            q = mesh_quality(M + "*", log)
            mq.append(q)
            say("%-8s %8s %9s %10s %10s %9s %s" % (q["model"], q["cells"], q["aspect_max"], q["nonorth_max"],
                                                    q["nonorth_avg"], q["skew_max"], q["verdict"]))
    say("  (* 조밀 격자, 2-2a)")
    write_csv("mesh_quality.csv", list(mq[0]), mq)

    rows = []
    say("\n정상 해 (buoyantSimpleFoam, 150 kW, 화구 완전개방) — 마지막 %d 회" % NAVG)
    say("%-8s %6s | %s | %8s %8s %10s %6s" % ("model", "반복", " ".join("%8s" % f for f in FIELDS),
                                             "질량%", "에너지%", "누적연속", "상한셀"))
    for M in MODELS:
        d = steady(cases.case_dir("steady", M), M, "")
        rows.append(d)
        say("%-8s %6d | %s | %8.3f %8.1f %10.2e %6d" % (M, d["iters"], " ".join("%8.1e" % d[f + "_mean"] for f in FIELDS),
                                                       d["mass_imbalance_pct"], d["energy_balance_pct"],
                                                       d["cum_continuity"], d["limiter_cells_max"]))
    chk = os.path.join(ROOT, "Results", "checks")
    extra = [("grid/steady/" + M, M + "*", "_fine") for M in MODELS]
    op = os.path.join(chk, "oppoint")
    if os.path.isdir(op):
        extra += [("oppoint/" + d, d, "_oppoint") for d in sorted(os.listdir(op))]
    for sub, name, tag in extra:
        case = os.path.join(chk, sub)
        if not os.path.exists(os.path.join(case, "log.solver")):
            continue
        d = steady(case, name, tag)
        rows.append(d)
        say("%-8s %6d | %s | %8.3f %8.1f %10.2e %6d" % (name, d["iters"], " ".join("%8.1e" % d[f + "_mean"] for f in FIELDS),
                                                       d["mass_imbalance_pct"], d["energy_balance_pct"],
                                                       d["cum_continuity"], d["limiter_cells_max"]))
    say("  (잔차는 변수별 초기 잔차의 평균. 최대는 convergence.csv. * 조밀 격자. 조업점 에너지%는 막은 화구 손실 제외)")
    say("\n비정상 해 (buoyantPimpleFoam, 0–45 s, maxCo 10, 6 분할) — 시간 단계별 변수의 첫 풀이")
    say("%-8s %6s | %s | %10s %10s %6s %6s" % ("model", "단계", " ".join("%8s" % f for f in FIELDS_T),
                                             "연속max", "누적연속", "Co max", "상한셀"))
    for M in MODELS:
        d = transient(cases.case_dir("transient", M), M)
        rows.append(d)
        say("%-8s %6d | %s | %10.2e %10.2e %6.1f %6d" % (M, d["iters"], " ".join("%8.1e" % d[f + "_median"] for f in FIELDS_T),
                                                         d["continuity_global_max"], d["cum_continuity"],
                                                         d["courant_max"], d["limiter_cells_max"]))
    for sub, name in [("grid/transient/" + M, M + "*") for M in MODELS] + [("courant/C_co2", "C_co2")]:
        case = os.path.join(chk, sub)
        if not os.path.exists(os.path.join(case, "log.solver")):
            continue
        d = transient(case, name)
        d["kind"] = "transient_fine" if name.endswith("*") else "transient_co2"
        rows.append(d)
        say("%-8s %6d | %s | %10.2e %10.2e %6.1f %6d" % (name, d["iters"], " ".join("%8.1e" % d[f + "_median"] for f in FIELDS_T),
                                                         d["continuity_global_max"], d["cum_continuity"],
                                                         d["courant_max"], d["limiter_cells_max"]))
    say("  (잔차는 0.5 s 이후 중앙값. 상한셀: 온도 상한 270–2,600 K 에 걸린 셀 수 최대 — 결정 K21)")
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    write_csv("convergence.csv", keys, rows)
    open(os.path.join(OUT, "summary.txt"), "w").write("\n".join(LINES) + "\n")
    print("→ Results/checks/convergence/summary.txt")


if __name__ == "__main__":
    main()
