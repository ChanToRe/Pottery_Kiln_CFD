#!/usr/bin/env python3
"""
2-2o (E-02) 값의 구분표 — 지정(문헌·실측에서 그대로), 가정, 보정(맞춰 정함), 계산(모델 출력).
값은 코드·결과 파일에서 읽는다 (손으로 옮겨 적지 않는다). 근거는 코드 주석과 원고 표의 출처.

    python3 value_classes.py          (rom/ 에서, Results/rom/sensitivity/base.json 이 있어야 한다)
출력: Results/rom/value_classes.csv, value_classes.txt
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import calibrate  # noqa: E402
import geom  # noqa: E402
import rom  # noqa: E402
import run  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))
RES = os.path.join(ROOT, "Results", "rom")


def main():
    base = json.load(open(os.path.join(RES, "sensitivity", "base.json")))
    phi = list(csv.DictReader(open(os.path.join(RES, "rom_phi.csv"))))
    cal = dict((t, calibrate.read_cfd("%s_L065" % t)) for t in "ABC")
    hr = dict((t, calibrate.h_conv_ref(t)) for t in "ABC")
    ah = dict((t, calibrate.A_hot_of(t)) for t in "ABC")
    g = dict((t, geom.extract("%s_L065" % t)) for t in "ABC")
    F = base["models"]
    rows = []

    def add(cls, name, value, basis):
        rows.append(dict(class_=cls, quantity=name, value=value, basis=basis))

    # 지정
    add("지정", "총 땔감", "%.0f kg" % rom.FUEL_TOTAL, "홍진근 2011 본문 (발열 일정의 총량으로 쓴다)")
    add("지정", "발열 일정 (6 구간)", " / ".join("%s" % r["Q_kW"] for r in phi) + " kW",
        "홍진근 2011 각주 4 투입률 × 발열량. 마지막 구간은 총량 3,600 kg 에 맞춤")
    add("지정", "소성 시간", "78 h", "홍진근 2011")
    add("지정", "유효 저위발열량", "%.1f MJ/kg" % (rom.LHV_EFF / 1e6), "Ragland et al. 1991 (함수율 20 %)")
    add("지정", "이론 공기량", "%.2f kg/kg (습윤 땔감)" % (rom.O2_STOICH / rom.Y_O2_AIR), "Ragland et al. 1991 침엽수 조성")
    add("지정", "외기", "%.1f ℃" % (run.T_AMB - 273.15), "홍진근 2011 각주 2 (건조기간 평균, 소성기 대용)")
    add("지정", "벽 k·ρ·c", "%.1f / %.0f / %.0f" % (rom.WALL["k"], rom.WALL["rho"], rom.WALL["cp"]), "원고 Table (hein2008, petcu2023)")
    add("지정", "지반 k·ρ·c", "%.1f / %.0f / %.0f" % (rom.SOIL["k"], rom.SOIL["rho"], rom.SOIL["cp"]), "Farouki 1981 (함수율 15 %)")
    add("지정", "형상 H (A/B/C)", " / ".join("%.2f m" % g[t]["H_stack"] for t in "ABC"), "형상(STL)")
    add("지정", "화구 면적 A_in (A/B/C)", " / ".join("%.3f m2" % g[t]["A_in"] for t in "ABC"), "형상(STL)")
    # 가정
    add("가정", "적재 부피 점유율", "%.2f" % rom.LOAD_FRAC, "가정값 — 보고서에 질량 기록 없음 (rom.py 주석)")
    add("가정", "내부 방사율 ε", "%.2f" % rom.EPS_RAD, "가정값")
    add("가정", "화구 유량계수 C_in", "%.2f" % rom.C_IN, "가정값 — 자료가 정하는 것은 C_in·φ (2-2k)")
    add("가정", "대류 지수", "%.1f" % rom.H_EXP, "Dittus–Boelter 꼴 (2-2e 민감도)")
    add("가정", "축방향 복사 교환계수", "%.2f" % rom.F_RAD_AX, "가정값")
    add("가정", "축방향 복사 핵", "1/(1+(d/D)^2)", "이 연구의 기하 근사")
    # 보정
    add("보정", "유효 고온부 면적 A_hot (A/B/C)", " / ".join("%.4f m2" % ah[t] for t in "ABC"),
        "정상 CFD 화구 유입량 (150 kW, 화구 완전개방)")
    add("보정", "대류계수 h_ref (A/B/C)", " / ".join("%.3f W/m2K" % hr[t] for t in "ABC"),
        "정상 CFD 벽 손실에서 외부저항 0.45 를 벗김")
    add("보정", "기준 유량 ṁ_ref (A/B/C)", " / ".join("%.3f kg/s" % cal[t]["mdot"] for t in "ABC"), "정상 CFD")
    add("보정", "화구 개구율 φ (6 구간, 형식 B)", " / ".join("%.3f" % float(r["phi"]) for r in phi),
        "판독 승온곡선(−2 h)에 소성실 첫 구간 기체온도를 맞춤")
    add("보정", "복사 차폐율", "%.2f" % rom.BLOCK_FRAC, "보고서 '폐쇄 직전 연소실–연도부 120 ℃' 에 맞춘 값 (rom.py 주석, K4)")
    add("보정(결과)", "앞 구간 78 h 온도", "1,140 ℃", "보정 목표 — 모든 경우에 같다 (N-02)")
    add("보정(결과)", "형식 B 땔감", "%.0f kg" % F["B_L065"]["fuel"], "φ 를 B 에서 역산하므로 구성상 3,600 kg — 독립 검증이 아니다")
    # 계산
    add("계산", "형식 A·C 땔감", "%.0f / %.0f kg" % (F["A_L065"]["fuel"], F["C_L065"]["fuel"]), "같은 φ(t)·승온곡선을 A·C 에 적용")
    add("계산", "길이별 땔감 2.5/4.5/8.5 m", " / ".join("%.0f" % F[m]["fuel"] for m in ("B_L025", "B_L045", "B_L085")) + " kg", "")
    add("계산", "소성실 앞뒤 온도차 2.5/4.5/6.5/8.5 m",
        " / ".join("%.1f" % (F[m]["gas"][1] - min(F[m]["gas"][1:-1])) for m in ("B_L025", "B_L045", "B_L065", "B_L085")) + " ℃", "78 h")
    add("계산", "최소 공기비 (A/B/C)", " / ".join("%.2f" % F[m]["lam_min"] for m in ("A_L065", "B_L065", "C_L065")), "")
    add("계산", "1,000 ℃ 면 45 s 최대 침투", "Results/cfd/flame_penetration_max.csv", "비정상 CFD (K22)")
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, "value_classes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["class_", "quantity", "value", "basis"])
        w.writeheader()
        w.writerows(rows)
    L = ["2-2o 값의 구분 (E-02) — 지정 / 가정 / 보정 / 계산", ""]
    for r in rows:
        L.append("%-8s %-30s %-40s %s" % (r["class_"], r["quantity"], r["value"], r["basis"]))
    open(os.path.join(RES, "value_classes.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
