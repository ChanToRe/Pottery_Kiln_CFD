#!/usr/bin/env python3
"""
R 그래프(Fig 7·8·9)가 읽는 작은 CSV 를 계산 결과에서 만든다.

예전에는 Data/Kiln_*.csv 를 손으로 옮겨 적었다. 계산을 다시 돌리면 그림이
따라오도록 여기서 자동으로 만든다.

    python3 Rscripts/make_graph_data.py
입력  Results/rom/study_form.csv, study_length.csv, study_steps.csv
      Results/rom/study_fuel_exact.csv   (연료량 정밀값 — kg 정수는 여기서 반올림)
      Results/cfd/flame_penetration_max.csv  (45 s 까지 최대 거리, 결정 K22 — 막대는 본계산 6 분할 값,
        분할 4·6·8·10 범위는 pen_min_m·pen_max_m 열)
      투고본 재현(시계열 csv 를 KILN_PENETRATION 으로 줄 때)은 t = 43 s 에 가장 가까운 시각
      — 비정상 CFD 없이 돌릴 때는 KILN_PENETRATION=<csv 경로> 로 다른 파일(예: 투고본
        reference/cfd/flame_penetration.csv)을 명시한다. 둘 다 없으면 Kiln_Form.csv 만
        만들지 않고 실패로 끝난다(Kiln_Length·Kiln_Steps 는 만든다).
출력  Data/Kiln_Form.csv, Kiln_Length.csv, Kiln_Steps.csv
"""
import csv
import os
import sys
from decimal import ROUND_HALF_UP, Decimal

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROM = os.path.join(ROOT, "Results", "rom")
CFD = os.path.join(ROOT, "Results", "cfd")
OUT = os.path.join(ROOT, "Data")   # R 그래프가 읽는 표 (저장소 첫 판과 같은 자리)
T_PEN = 43.0                    # 투고본이 쓴 침투 깊이 시각 [s] — 시계열 csv 를 줄 때만
DESC = {"A": "Horizontal, unstepped", "B": "Horizontal, stepped", "C": "Vertical, stepped"}
STEP_X0 = 30                    # 계단 없음(0단)을 그래프 오른쪽 밖에 둘 자리 — 그림에서는 뺀다


def kg(study, model, _exact={}):
    """연료량을 kg 정수로 — 정밀값(study_fuel_exact.csv)에서 사사오입한다.

    study_*.csv 는 0.1 kg 까지만 적는다. 그 값을 다시 반올림하면 두 번 반올림이 된다:
    계단 6단은 정밀값 3666.50099 kg → 표 3666.5 → "%.0f"(짝수 쪽) 3666 으로,
    원고 3,667 과 어긋났다.
    """
    if not _exact:
        for r in rows(os.path.join(ROM, "study_fuel_exact.csv")):
            _exact[(r["study"], r["model"])] = r["fuel_kg"]
    return str(Decimal(_exact[(study, model)]).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def penetration_csv():
    """침투 거리 CSV 경로. 이 폴더의 CFD 결과가 우선이고, 없으면 KILN_PENETRATION 이 가리키는 파일."""
    own = os.path.join(CFD, "flame_penetration_max.csv")
    if os.path.exists(own):
        return own
    alt = os.environ.get("KILN_PENETRATION")
    if alt and os.path.exists(alt):
        print("   침투 거리: KILN_PENETRATION = %s 을 쓴다" % alt)
        return alt
    return None


def penetration(path):
    """{형식: (t 또는 None, 막대 값, 최소, 최대)}"""
    data = rows(path)
    if data and "max_x_np6_m" in data[0]:                     # penetration_max.py 출력
        return {r["form"]: (None, float(r["max_x_np6_m"]), float(r["max_x_min_m"]), float(r["max_x_max_m"]))
                for r in data}
    best = {}
    for r in data:
        if not r["x_penetration_m"]:
            continue
        t, m = float(r["t_s"]), r["model"]
        if m not in best or abs(t - T_PEN) < abs(best[m][0] - T_PEN):
            x = float(r["x_penetration_m"])
            best[m] = (t, x, x, x)
    return best


def write(name, header, data):
    p = os.path.join(OUT, name)
    with open(p, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(data)
    print("→ %s" % os.path.relpath(p, ROOT))


def main():
    os.makedirs(OUT, exist_ok=True)
    length = rows(os.path.join(ROM, "study_length.csv"))
    write("Kiln_Length.csv", ["length_m", "fuel_kg", "spread_C"],
          [[r["L_m"], kg("length", r["model"]), r["dT_C"]] for r in length])
    steps = rows(os.path.join(ROM, "study_steps.csv"))
    steps = [r for r in steps if r["n_step"] != "0"] + [r for r in steps if r["n_step"] == "0"]
    write("Kiln_Steps.csv", ["steps", "x_pos", "fuel_kg", "finite"],
          [[r["n_step"], r["n_step"] if r["n_step"] != "0" else STEP_X0,
            kg("steps", r["model"]), "TRUE" if r["n_step"] != "0" else "FALSE"]
           for r in steps])
    # Fig 7b 의 침투 거리는 비정상 CFD 결과가 있어야 한다 — 그래서 맨 뒤에 만든다
    path = penetration_csv()
    if path is None:
        print("  ★ Results/cfd/flame_penetration_max.csv 가 없다 (비정상 CFD·transient-np·cfd-post 를 먼저 돌리거나 "
              "KILN_PENETRATION 을 지정) — Kiln_Form.csv 를 만들지 않았다")
        sys.exit(1)
    pen = penetration(path)
    form = rows(os.path.join(ROM, "study_form.csv"))
    write("Kiln_Form.csv", ["form", "desc", "fuel_kg", "penetration_m", "pen_min_m", "pen_max_m"],
          [[r["model"][0], DESC[r["model"][0]], kg("form", r["model"])]
           + ["%.3f" % v for v in pen[r["model"][0]][1:]] for r in form])
    for m in sorted(pen):
        t, x, lo, hi = pen[m]
        print("   침투 %s: %s %.4f m (범위 %.4f–%.4f)" % (m, "45 s 까지 최대" if t is None else "t = %.4f s," % t, x, lo, hi))


if __name__ == "__main__":
    main()
