#!/usr/bin/env python3
"""
1,000 ℃ 면이 소성실로 들어간 거리를 매 시각 계산한다.

  DISPLAY=:0 pvbatch cfd/post/flame_penetration.py      (run_all.sh cfd-post)

대상은 비정상 냉시동 케이스 cases/{A_horizontal_unstepped,B_horizontal_stepped,C_vertical_stepped} 의 저장 시각 전부
(0–45 s, 1 s 간격). 출력: Results/cfd/flame_penetration.csv
원고 지표는 45 s 까지의 최댓값이다 (cfd/post/penetration_max.py, 결정 K22). 투고본은 43 s 값을 썼다.

다른 케이스 묶음(병렬 분할 재현판 등)을 읽을 때:
  KILN_PEN_CASES="A=<케이스>,C=<케이스>" KILN_PEN_OUT=<csv> pvbatch cfd/post/flame_penetration.py

정의: 1,000 ℃ 등온면의 **최대 x**. 소성실 입구가 x = 0 이므로 음수면 아직
연소부 안에 있다는 뜻이다. 등온면이 아직 없으면 빈 값으로 둔다.
"""
import glob
import os
import sys

from paraview.simple import *

paraview.simple._DisableFirstRenderCameraReset()

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.environ.get("KILN_PEN_OUT", os.path.join(ROOT, "Results", "cfd", "flame_penetration.csv"))
sys.path.insert(0, os.path.join(ROOT, "cfd"))
import cases as _cases  # noqa: E402
CASES = [(m, _cases.case_dir("transient", m)) for m in ("A", "B", "C")]
if os.environ.get("KILN_PEN_CASES"):
    CASES = [tuple(s.split("=", 1)) for s in os.environ["KILN_PEN_CASES"].split(",")]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
LEVEL = 1000.0          # ℃ — 도질토기 소성 하한

rows = []
for model, case in CASES:
    foam = glob.glob("%s/*.foam" % case)
    if not foam:
        foam = [os.path.join(case, "%s.foam" % os.path.basename(case))]      # run_case.sh 와 같은 이름
        open(foam[0], "w").close()
    r = OpenFOAMReader(FileName=foam[0])
    r.MeshRegions = ["internalMesh"]
    r.CellArrays = ["T"]
    r.UpdatePipeline()
    times = sorted(r.TimestepValues or [0.0])

    c2p = CellDatatoPointData(Input=r)
    cal = Calculator(Input=c2p)
    cal.AttributeType = "Point Data"
    cal.ResultArrayName = "T_degC"
    cal.Function = "T - 273.15"

    ct = Contour(Input=cal)
    ct.ContourBy = ["POINTS", "T_degC"]
    ct.Isosurfaces = [LEVEL]

    for t in times:
        ct.UpdatePipeline(t)
        di = ct.GetDataInformation()
        n = di.GetNumberOfPoints()
        x = di.GetBounds()[1] if n > 0 else None
        rows.append((model, t, n, x))
        print("%s  t=%6.2f  pts=%7d  x_max=%s"
              % (model, t, n, "%.3f" % x if x is not None else "-"))

    for p in (ct, cal, c2p, r):
        Delete(p)

with open(OUT, "w") as f:
    f.write("model,t_s,n_points,x_penetration_m\n")
    for m, t, n, x in rows:
        f.write("%s,%.4f,%d,%s\n" % (m, t, n, "" if x is None else "%.4f" % x))
print("\n→ %s" % OUT)
