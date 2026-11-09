#!/usr/bin/env python3
"""다시 계산한 결과를 논문(수정본)에 적은 값과 대조한다.

    python3 verify.py            (run_all.sh 의 마지막 단계)

1부  논문의 수치 — 본문·표·보충자료에 적은 값을 산출물에서 다시 읽어 허용오차 안인지 본다.
     축소모델 값은 반올림 자릿수까지, CFD 에서 온 값은 계산 기계·병렬 분할에 따른 차이를 보아
     넉넉히 (아래 각 항목의 tol). 형식 C 의 1,000 ℃ 면 침투는 분할 4·6·8·10 판의 범위로 본다.
2부  저장소에 올린 산출물 — Results/ 의 표·요약(csv·txt)을 git 에 올린 판과 숫자 단위로 비교해
     가장 큰 상대 차이를 보인다 (참고 — 판정은 1부).
판정이 하나라도 실패면 종료 코드 1.
"""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
R = lambda *p: os.path.join(ROOT, "Results", *p)  # noqa: E731
FAILS = []


def rows(path):
    return list(csv.DictReader(open(path)))


def check(label, got, want, tol):
    ok = got is not None and abs(got - want) <= tol
    print("  %-52s 논문 %-9s 다시 계산 %-11s %s" % (label, want, "—" if got is None else ("%.4g" % got),
                                                   "OK" if ok else "★ 다름"))
    if not ok:
        FAILS.append(label)


def section(t):
    print("\n" + t)


def part1():
    print("=" * 96 + "\n1부 논문(수정본)의 수치\n" + "=" * 96)
    form = {r["model"][0]: r for r in rows(R("rom", "study_form.csv"))}
    length = {r["model"]: r for r in rows(R("rom", "study_length.csv"))}
    steps = {r["model"]: r for r in rows(R("rom", "study_steps.csv"))}

    section("연소부 형식 (Results/rom/study_form.csv)")
    for t, v in zip("ABC", (3463, 3600, 3506)):
        check("형식 %s 연료 [kg]" % t, float(form[t]["fuel_kg"]), v, 0.6)
    f = [float(form[t]["fuel_kg"]) for t in "ABC"]
    check("형식 간 연료 차 (최대−최소)/최소 [%]", 100 * (max(f) - min(f)) / min(f), 4.0, 0.05)
    for t, v in zip("ABC", (55.3, 54.7, 55.3)):
        check("형식 %s 소성실 앞뒤 온도차 78 h [℃]" % t, float(form[t]["dT_C"]), v, 0.05)

    section("소성실 길이 (Results/rom/study_length.csv)")
    for m, fuel, dT, spec in (("B_L025", 2806, 10.2, 7.89), ("B_L045", 3222, 31.7, 4.18),
                              ("B_L065", 3600, 54.7, 3.00), ("B_L085", 3973, 79.3, 2.43)):
        r = length[m]
        check("%s 연료 [kg]" % m, float(r["fuel_kg"]), fuel, 0.6)
        check("%s 앞뒤 온도차 [℃]" % m, float(r["dT_C"]), dT, 0.05)
        check("%s 기물 1 kg 당 연료 [kg/kg]" % m, float(r["fuel_kg"]) / float(r["ware_kg"]), spec, 0.005)

    section("소성실 계단 (Results/rom/study_steps.csv)")
    for m, fuel in (("B_L065", 3600), ("B_L065_S6", 3648), ("B_L065_S12", 3647), ("B_L065_S20", 3641)):
        check("%s 연료 [kg]" % m, float(steps[m]["fuel_kg"]), fuel, 0.6)

    section("구간별 화구 개구율 φ (Results/rom/rom_phi.csv, S2 Table)")
    for r, v in zip(rows(R("rom", "rom_phi.csv")), (0.314, 0.216, 0.231, 0.337, 0.229, 0.070)):
        check("φ %s–%s h" % (r["t0_h"], r["t1_h"]), float(r["phi"]), v, 0.002)

    section("정상상태 CFD 보정값 (Results/rom/calibration.txt) — CFD 에서 온 값")
    cal = open(R("rom", "calibration.txt")).read()
    href = dict(re.findall(r"^\s+([ABC])\s+h_conv,ref = ([\d.]+)", cal, re.M))
    ahot = dict(re.findall(r"^([ABC])_L065\s+[\d.]+\s+[\d.]+\s+([\d.]+)", cal, re.M))
    for t, h, a in zip("ABC", (4.29, 6.09, 3.92), (0.194, 0.184, 0.230)):
        check("형식 %s h_ref [W m-2 K-1]" % t, float(href[t]) if t in href else None, h, 0.03 * h)
        check("형식 %s A_hot [m2]" % t, float(ahot[t]) if t in ahot else None, a, 0.02 * a)

    section("1,000 ℃ 면 45 s 까지 최대 침투 (Results/cfd/flame_penetration_max.csv) — CFD")
    pen = {r["form"]: r for r in rows(R("cfd", "flame_penetration_max.csv"))}
    for t, lo, hi in (("A", 3.46, 3.46), ("B", 2.89, 2.91), ("C", 1.87, 2.62)):
        check("형식 %s 분할 4·6·8·10 최소 [m]" % t, float(pen[t]["max_x_min_m"]), lo, 0.05)
        check("형식 %s 분할 4·6·8·10 최대 [m]" % t, float(pen[t]["max_x_max_m"]), hi, 0.05)

    section("수치 점검 (Results/checks/summary_2-2abd.txt, oppoint.csv) — CFD")
    s = open(R("checks", "summary_2-2abd.txt")).read()
    fine = dict(re.findall(r"^\s+([ABC])\s+기본 np6 [\d.]+ \(범위 [^)]*\)\s+조밀 np6 ([\d.]+)", s, re.M))
    co2 = dict(re.findall(r"^\s+([ABC])\s+maxCo 10: .*maxCo 2: ([\d.]+)", s, re.M))
    for t, v in zip("ABC", (3.24, 2.76, 2.73)):
        check("조밀 격자 침투 %s [m]" % t, float(fine[t]) if t in fine else None, v, 0.05)
    for t, v in zip("ABC", (3.46, 2.87, 1.96)):
        check("최대 Courant 2 침투 %s [m]" % t, float(co2[t]) if t in co2 else None, v, 0.05 if t != "C" else 0.10)
    ratio = [float(r["mdot_rom"]) / float(r["mdot_cfd"]) for r in rows(R("checks", "oppoint.csv"))]
    check("조업점 유입량 비 (식 1 / CFD) 최소", min(ratio), 0.84, 0.01)
    check("조업점 유입량 비 (식 1 / CFD) 최대", max(ratio), 0.94, 0.01)

    section("78 h 에너지 수지 (Results/rom/energy_audit.txt, S8 Table)")
    e = open(R("rom", "energy_audit.txt")).read()
    num = lambda pat: float(re.search(pat, e).group(1))  # noqa: E731
    check("투입 발열 [GJ]", num(r"투입 발열\s+([\d.]+)"), 52.92, 0.005)
    check("배기 [%]", num(r"배기 엔탈피[^\n]*\(\s*([\d.]+) %\)"), 54.0, 0.05)
    check("벽·바닥 [%]", num(r"기체 → 벽·바닥 표면[^\n]*\(\s*([\d.]+) %\)"), 43.9, 0.05)
    check("적재물 [%]", num(r"기체 → 적재물 \(= 적재물 축열\)[^\n]*\(\s*([\d.]+) %\)"), 2.1, 0.05)
    check("벽 쪽 열 중 복사 [%]", num(r"기체 → 벽 표면 열 중 복사 ([\d.]+) %"), 95.3, 0.5)
    check("적재물 쪽 열 중 복사 [%]", num(r"기체 → 적재물 열 중 복사 ([\d.]+) %"), 93.1, 0.5)


NUM = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def part2():
    print("\n" + "=" * 96 + "\n2부 저장소에 올린 산출물과 비교 (참고)\n" + "=" * 96)
    try:
        listed = subprocess.check_output(["git", "-C", ROOT, "ls-files", "Results"], text=True).split()
    except Exception as e:  # git 이 없거나 zip 으로 받은 경우
        print("  git 판을 읽지 못해 건너뛴다: %s" % e)
        return
    for f in listed:
        if not f.endswith((".csv", ".txt")) or f.startswith("Results/logs/") or f.startswith("Results/run/"):
            continue
        try:
            old = subprocess.check_output(["git", "-C", ROOT, "show", "HEAD:" + f], text=True)
            new = open(os.path.join(ROOT, f)).read()
        except Exception:
            print("  %-60s 없음" % f)
            continue
        a, b = NUM.findall(old), NUM.findall(new)
        if len(a) != len(b):
            print("  %-60s 숫자 개수가 다름 (%d → %d)" % (f, len(a), len(b)))
            continue
        d = max([abs(float(x) - float(y)) / max(abs(float(x)), 1e-12) for x, y in zip(a, b)] or [0.0])
        print("  %-60s 최대 상대 차 %.2e" % (f, d))


if __name__ == "__main__":
    part1()
    part2()
    print("\n판정: %s" % ("모두 같다" if not FAILS else "★ %d 항목 다름 — %s" % (len(FAILS), ", ".join(FAILS))))
    sys.exit(1 if FAILS else 0)
