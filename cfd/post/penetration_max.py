#!/usr/bin/env python3
"""
1,000 ℃ 면 침투의 원고 지표: 45 s 까지 도달한 최대 거리 (결정 K22).

C 형식은 선단이 나아갔다 물러났다 사라지기를 되풀이해 한 시각의 값이 병렬 분할에 따라
크게 갈린다(README §6-3). 그래서 시각을 정하지 않고 계산 끝까지의 최댓값을
쓰고, 분할만 다른 판(본계산 6 분할 + cfd/run_transient_np.sh)의 범위를 함께 낸다.

    python3 cfd/post/penetration_max.py

입력: Results/cfd/flame_penetration.csv (본계산), Results/cfd/np/flame_penetration_np.csv (재현판)
출력: Results/cfd/flame_penetration_max.csv
"""
import csv
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CFD = os.path.join(ROOT, "Results", "cfd")
T_END = 45.0
SOURCES = [(os.path.join(CFD, "flame_penetration.csv"), "np6"),
           (os.path.join(CFD, "np", "flame_penetration_np.csv"), None)]


def runs():
    """{(형식, 판): 최대 x} — 판 이름은 'np6' 처럼 분할 수."""
    out = {}
    for path, tag in SOURCES:
        if not os.path.exists(path):
            raise FileNotFoundError("%s 가 없다 — run_all.sh cfd-post / cfd/run_transient_np.sh 먼저" % path)
        for r in csv.DictReader(open(path)):
            if not r["x_penetration_m"] or float(r["t_s"]) > T_END + 0.5:
                continue
            m = re.match(r"([ABC])(?:_(np\d+))?$", r["model"])
            key = (m.group(1), tag or m.group(2))
            x = float(r["x_penetration_m"])
            out[key] = max(out.get(key, x), x)
    return out


def main():
    r = runs()
    rows = []
    print("1,000 ℃ 면 — %g s 까지 도달한 최대 거리 [m] (소성실 입구 x = 0)" % T_END)
    for f in "ABC":
        v = sorted(((k[1], x) for k, x in r.items() if k[0] == f), key=lambda p: int(p[0][2:]))
        xs = [x for _, x in v]
        print("  %s  %s   범위 %.2f–%.2f  평균 %.2f  (%d 판)" % (
            f, "  ".join("%s %.2f" % p for p in v), min(xs), max(xs), sum(xs) / len(xs), len(xs)))
        rows.append((f, len(xs), min(xs), max(xs), sum(xs) / len(xs),
                     dict(v).get("np6"), ";".join("%s=%.4f" % p for p in v)))
    out = os.path.join(CFD, "flame_penetration_max.csv")
    with open(out, "w") as fo:
        fo.write("form,n_runs,max_x_min_m,max_x_max_m,max_x_mean_m,max_x_np6_m,runs\n")
        for f, n, lo, hi, mean, base, s in rows:
            fo.write("%s,%d,%.4f,%.4f,%.4f,%.4f,%s\n" % (f, n, lo, hi, mean, base, s))
    print("→ %s" % out)


if __name__ == "__main__":
    main()
