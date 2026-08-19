#!/usr/bin/env python3
import glob
import os

from paraview.simple import *

paraview.simple._DisableFirstRenderCameraReset()

ROOT = "/home/chanhyeok/Kiln"
OUT = os.path.join(ROOT, "Results", "flame_penetration.csv")
LEVEL = 1000.0

rows = []
for model in ("A", "B", "C"):
    case = os.path.join(ROOT, "cfd", "%s_L065.cold" % model)
    foam = glob.glob("%s/*.foam" % case)
    if not foam:
        foam = [os.path.join(case, "%s.foam" % model)]
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
