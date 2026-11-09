#!/usr/bin/env python3
"""limiter_swap.sh 산출물 요약: CFD 에너지 수지·리미터·국소 최고온도, 보정값, 형식별 연료.

    python3 cfd/checks/limiter_summary.py Results/checks/limiter_swap
"""
import os
import re
import sys

OUT = sys.argv[1]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "cfd"))
import cases as _cases  # noqa: E402
T_AMB, CP, Q_SRC, N = 292.45, 1100.0, 150.0, 40    # 외기 K, cp J/kgK(thermophysicalProperties), 발열 kW, 마지막 40 표본


def series(txt, pat):
    return [float(x) for x in re.findall(pat, txt)]


def mean(v):
    return sum(v) / len(v)


def t_max(case):
    """마지막 시간 디렉터리의 T 내부장 최댓값과 2,600 K 이상 셀 수."""
    last = sorted((d for d in os.listdir(case) if re.fullmatch(r"\d+", d)), key=int)[-1]
    t = open(os.path.join(case, last, "T")).read()
    i = t.index("internalField")
    m = re.search(r"List<scalar>\s*(\d+)\s*\(", t[i:])
    vals = [float(x) for x in t[i + m.end():].split(")")[0].split()]
    return max(vals), sum(v >= 2599.9 for v in vals)


def cfd(case):
    txt = open(os.path.join(case, "log.solver"), errors="ignore").read()
    md = [abs(x) for x in series(txt, r"sum\(outlet\) of phi = ([-\d.e+]+)")][-N:]
    to = series(txt, r"areaAverage\(outlet\) of T = ([\d.e+-]+)")[-N:]
    tv = series(txt, r"volAverage\(region0\) of T = ([\d.e+-]+)")[-N:]
    wl = [abs(x) for x in series(txt, r"min/max/integ\(walls\) = [-\d.e+]+, [-\d.e+]+, ([-\d.e+]+)")][-N:]
    lim = re.findall(r"Upper limited (\d+)", txt)
    q = mean([m * CP * (t - T_AMB) for m, t in zip(md, to)]) / 1e3 + mean(wl) / 1e3
    tm, nhot = t_max(case)
    return dict(mdot=mean(md), Tv=mean(tv) - 273.15, wall=mean(wl) / 1e3, bal=q,
                lim=("없음" if not lim else lim[-1]), Tmax=tm, nhot=nhot)


cases = [("A_L065 (기준, 리미터 있음)", _cases.case_dir("steady", "A_L065")),
         ("A_nolim (리미터 뺌)", os.path.join(OUT, "A_nolim")),
         ("B_L065 (기준, 리미터 없음)", _cases.case_dir("steady", "B_L065")),
         ("B_lim (리미터 더함)", os.path.join(OUT, "B_lim")),
         ("C_L065 (기준, 리미터 있음)", _cases.case_dir("steady", "C_L065"))]
print("1. 정상상태 CFD (마지막 2,000 회 평균). 수지 = ṁ·cp·(출구 면적평균 T − 외기) + 벽 손실, 발열 150 kW 대비")
print("   %-28s %8s %9s %8s %16s %12s %10s %10s" % ("케이스", "ṁ[kg/s]", "체적T[℃]", "벽[kW]",
                                                    "수지[kW]", "리미터 셀", "최고T[K]", "≥2600K셀"))
for name, c in cases:
    r = cfd(c)
    print("   %-28s %8.4f %9.2f %8.2f %8.1f (%5.1f%%) %12s %10.0f %10d" % (
        name, r["mdot"], r["Tv"], r["wall"], r["bal"], r["bal"] / Q_SRC * 100, r["lim"], r["Tmax"], r["nhot"]))

print("\n2. 축소모델 (보정 평균 = 마지막 2,000 회)")
print("   %-9s %9s %9s %9s %8s %8s %8s %7s %7s %7s %9s" % (
    "경우", "A_hot A", "A_hot B", "A_hot C", "h A", "h B", "h C", "연료 A", "연료 B", "연료 C", "φ(52-78h)"))
for v in ("base", "A_nolim", "B_lim"):
    d = os.path.join(OUT, "rom_" + v, "Results", "rom")
    cal = open(os.path.join(d, "calibration.txt")).read()
    ah = dict(re.findall(r"^([ABC])_L065\s+[\d.]+\s+[\d.]+\s+([\d.]+)", cal, re.M))
    h = dict(re.findall(r"^\s+([ABC])\s+h_conv,ref = ([\d.]+)", cal, re.M))
    eff = open(os.path.join(d, "rom_efficiency.txt")).read()
    fuel = re.findall(r"^[①②③].*?\s(\d{4})\s", eff, re.M)
    phi = open(os.path.join(d, "rom_phi.csv")).read().strip().splitlines()[-1].split(",")[2]
    print("   %-9s %9s %9s %9s %8.3f %8.3f %8.3f %7s %7s %7s %9.4f" % (
        v, ah["A"], ah["B"], ah["C"], float(h["A"]), float(h["B"]), float(h["C"]),
        fuel[0], fuel[1], fuel[2], float(phi)))
