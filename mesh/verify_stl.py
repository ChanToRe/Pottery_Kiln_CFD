#!/usr/bin/env python3
"""
Results/geometry/ 에 다시 만든 STL 을 mesh/stl/ (계산에 쓴 STL) 과 대조한다.

    python3 mesh/verify_stl.py

stl_manifest.csv 의 각 행마다 Results/geometry/<생성기>/ 의 같은 이름 파일을 찾아
  ① md5 가 같으면 "동일"
  ② 다르면 꼭짓점 좌표를 수치로 비교한다. 꼭짓점이 1e-9 m 안에서 같고
     차이가 면 법선(facet normal)뿐이면 "꼭짓점 동일(법선 수치잡음)" 이다.
     법선은 snappyHexMesh·축소모델 어느 쪽도 읽지 않는다.
그 밖에는 "불일치" 로 보고하고 종료코드 1 을 돌려준다.
"""
import csv
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = {"generate_rev4.py": os.path.join(HERE, "..", "Results", "geometry", "rev4", "stl"),
         "kiln_geometry.py": os.path.join(HERE, "..", "Results", "geometry", "pure")}


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def vertices(p):
    out = []
    for line in open(p):
        t = line.split()
        if t and t[0] == "vertex":
            out.append(tuple(float(v) for v in t[1:4]))
    return out


def main():
    bad = 0
    with open(os.path.join(HERE, "stl_manifest.csv")) as f:
        for r in csv.DictReader(f):
            ref = os.path.join(HERE, "stl", r["stl_file"])
            new = os.path.join(BUILD[r["generator"]], r["source_name"])
            if md5(ref) != r["md5"]:
                print("%-22s 불일치 — stl/ 파일이 manifest md5 와 다르다" % r["stl_file"])
                bad += 1
                continue
            if not os.path.exists(new):
                print("%-22s 없음 — %s" % (r["stl_file"], new))
                bad += 1
                continue
            if md5(new) == r["md5"]:
                print("%-22s 동일 (md5)" % r["stl_file"])
                continue
            a, b = vertices(ref), vertices(new)
            dmax = max(abs(x - y) for p, q in zip(a, b) for x, y in zip(p, q)) if len(a) == len(b) else None
            if dmax is not None and dmax < 1e-9:
                print("%-22s 꼭짓점 동일 (최대차 %.1e m) — 법선 수치잡음만 다름" % (r["stl_file"], dmax))
            else:
                print("%-22s 불일치 (꼭짓점 수 %d/%d, 최대차 %s)"
                      % (r["stl_file"], len(a), len(b), dmax))
                bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
