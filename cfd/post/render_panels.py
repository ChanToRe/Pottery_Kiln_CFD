#!/usr/bin/env python3
"""
pvbatch 전용 — 논문 Figure 용 **낱장** 패널의 온도장을 뽑는다.

원고 Fig 2. 한 장에 한 칸만 담는다. 최종 배치와 글자 삽입은
사용자가 하므로 여기서는 장식 없는 온도장만 그리고, 축은 `cfd/post/panel_axes.py`
가 Times 로 얹는다 (ParaView 의 AxesGrid 는 두께 0 인 단면에서 렌더되지 않는다).

전 패널이 **같은 카메라·같은 색범위**를 쓴다. 그래야 형식 간·시각 간 비교가
성립한다. 카메라를 평행투영으로 고정하므로 세계좌표 ↔ 픽셀 사상이 해석적으로
정해지고, 그 값을 `mapping.txt` 에 남겨 축 그리기가 받아 쓴다.

    DISPLAY=:0 pvbatch cfd/post/render_panels.py <출력디렉터리>
    (투고본 설정은 Rscripts/make_figures.sh 의 Fig 2 단계)

환경변수
    CFDDIR              케이스 상위 폴더   TIMES  시각 목록 [s]
    CASES               케이스:파일접두 목록 (기본 A_L065:A|B_L065:B|C_L065:C)
    TMIN/TMAX           색범위 [degC]      W/H    패널 픽셀크기
"""
import glob
import os
import sys

from paraview.simple import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pvfont

paraview.simple._DisableFirstRenderCameraReset()

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "cfd"))
import cases as _cases  # noqa: E402
CFD = os.environ.get("CFDDIR")   # 없으면 저장소의 비정상 케이스 (cases/<형식 이름>)
CASES = [tuple(p.split(":", 1))
         for p in os.environ.get("CASES", "A_L065:A|B_L065:B|C_L065:C").split("|")]
OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(_ROOT, "Results", "figures", "fig2_cfd_panels"))
W = int(os.environ.get("W", 880))
H = int(os.environ.get("H", 420))
TMIN = float(os.environ.get("TMIN", 0.0))
TMAX = float(os.environ.get("TMAX", 1200.0))
PRESET = os.environ.get("PRESET", "Jet")
# 등온선 [degC]. 색범위가 넓으면 중간 온도대의 차이가 색으로 읽히지 않는다.
# 선을 하나 그으면 "어디까지 열이 닿았는가" 가 한눈에 보인다.
ISO = [float(v) for v in os.environ.get("ISO", "").split(",") if v.strip()]
TFIELD = "T_degC"
RAW = os.path.join(OUT, "raw")   # 축 없는 원본 — panel_axes.py 가 읽는다
os.makedirs(RAW, exist_ok=True)

# ---------- 소스 ----------
slices, tlists = [], []
for m, _ in CASES:
    case = "%s/%s" % (CFD, m) if CFD else _cases.case_dir("transient", m)
    foam = glob.glob("%s/*.foam" % case)
    if not foam:
        foam = ["%s/%s.foam" % (case, m)]
        open(foam[0], "w").close()
    r = OpenFOAMReader(FileName=foam[0])
    r.MeshRegions = ["internalMesh"]
    r.CellArrays = ["T"]
    r.UpdatePipeline()
    tlists.append(sorted(r.TimestepValues or [0.0]))
    c2p = CellDatatoPointData(Input=r)
    cal = Calculator(Input=c2p)
    cal.AttributeType = "Point Data"
    cal.ResultArrayName = TFIELD
    cal.Function = "T - 273.15"
    sl = Slice(Input=cal)
    sl.SliceType = "Plane"
    sl.SliceType.Origin = [2.0, 0.0, 1.0]
    sl.SliceType.Normal = [0.0, 1.0, 0.0]
    sl.UpdatePipeline()
    slices.append(sl)

# ---------- 시각 ----------
# 세 형식이 모두 계산된 구간에서만 고른다 (C 가 먼저 끝난다).
t_end = min(t[-1] for t in tlists)
_env = os.environ.get("TIMES", "")
want = ([float(x) for x in _env.split(",")] if _env
        else [t_end * k / 5.0 for k in range(1, 6)])

# ---------- 공통 카메라 ----------
bx0 = bz0 = 1e30
bx1 = bz1 = -1e30
for sl in slices:
    b = sl.GetDataInformation().GetBounds()
    bx0, bx1 = min(bx0, b[0]), max(bx1, b[1])
    bz0, bz1 = min(bz0, b[4]), max(bz1, b[5])
# 축 눈금의 0 은 가마 앞끝·바닥으로 잡는다. 해석 좌표계의 원점(소성실 시작)을
# 그대로 쓰면 Length 가 -3 m 부터 시작해 그림만 보는 사람에게 읽히지 않는다.
ox, oz = bx0, bz0
# ZOOM="x0,x1,z0,z1" 로 관심 영역만 잘라 볼 수 있다. 형상 차이가 연소부에만
# 있으므로 전체를 담으면 그 차이가 화면의 몇 픽셀로 눌린다.
_z = [float(v) for v in os.environ.get("ZOOM", "").split(",") if v.strip()]
if len(_z) == 4:
    bx0, bx1, bz0, bz1 = _z
PAD = 0.12 if not _z else 0.0
bx0 -= PAD
bx1 += PAD
bz0 -= PAD
bz1 += PAD
cx, cz = 0.5 * (bx0 + bx1), 0.5 * (bz0 + bz1)
# 가로·세로 중 더 빡빡한 쪽에 맞춘다 → 세 형식의 실제 크기 차이가 보인다.
scale = max(0.5 * (bz1 - bz0), 0.5 * (bx1 - bx0) * H / float(W))

view = CreateRenderView()
view.ViewSize = [W, H]
view.Background = [1, 1, 1]
view.UseColorPaletteForBackground = 0
view.OrientationAxesVisibility = 0
view.CameraParallelProjection = 1
view.CameraPosition = [cx, -30.0, cz]
view.CameraFocalPoint = [cx, 0.0, cz]
view.CameraViewUp = [0.0, 0.0, 1.0]
view.CameraParallelScale = scale

# 평행투영이므로 배율은 화면 세로 절반이 scale [m] 인 데서 정해진다.
ppm = H / (2.0 * scale)          # pixel per metre
with open("%s/mapping.txt" % RAW, "w") as fh:
    fh.write("# 세계좌표 -> 픽셀 (좌상단 원점)\n")
    fh.write("# x_px = W/2 + (X - cx)*ppm ;  y_px = H/2 - (Z - cz)*ppm\n")
    fh.write("W %d\nH %d\ncx %.9f\ncz %.9f\nppm %.9f\n" % (W, H, cx, cz, ppm))
    fh.write("tmin %.3f\ntmax %.3f\n" % (TMIN, TMAX))
    fh.write("xlim %.6f %.6f\nzlim %.6f %.6f\n" % (bx0, bx1, bz0, bz1))
    fh.write("origin %.6f %.6f\n" % (ox, oz))   # 눈금 0 으로 삼을 세계좌표
print("범위 x %.2f~%.2f  z %.2f~%.2f  %.2f px/m" % (bx0, bx1, bz0, bz1, ppm))

# ---------- 표시 ----------
disp, iso = [], []
for sl in slices:
    d = Show(sl, view)
    ColorBy(d, ("POINTS", TFIELD))
    d.Representation = "Surface"
    lut = GetColorTransferFunction(TFIELD)
    lut.ApplyPreset(PRESET, True)
    lut.AutomaticRescaleRangeMode = "Never"
    lut.RescaleTransferFunction(TMIN, TMAX)
    lut.UseAboveRangeColor = 0
    lut.UseBelowRangeColor = 0
    d.SetScalarBarVisibility(view, False)
    fe = FeatureEdges(Input=sl)
    fe.BoundaryEdges = 1
    fe.FeatureEdges = 0
    fe.NonManifoldEdges = 0
    fe.ManifoldEdges = 0
    ed = Show(fe, view)
    ColorBy(ed, None)
    ed.AmbientColor = [0.12, 0.12, 0.12]
    ed.DiffuseColor = [0.12, 0.12, 0.12]
    ed.LineWidth = 1.5
    if ISO:
        ct = Contour(Input=sl)
        ct.ContourBy = ["POINTS", TFIELD]
        ct.Isosurfaces = ISO
        ct.UpdatePipeline()
        cd = Show(ct, view)
        # ColorBy(cd, None) 은 Contour 출력에서 association 오류를 낸다.
        # 배열 이름을 직접 비워 단색으로 만든다.
        cd.ColorArrayName = ["POINTS", ""]
        cd.AmbientColor = [1.0, 1.0, 1.0]
        cd.DiffuseColor = [1.0, 1.0, 1.0]
        cd.LineWidth = 3.0
        iso.append(cd)
    disp.append((d, ed))

# ---------- 패널 ----------
tlog = open("%s/times.txt" % OUT, "w")
for i, (m, tag) in enumerate(CASES):
    for k, tw in enumerate(want):
        tv = min(tlists[i], key=lambda v: abs(v - tw))
        for j, (d, ed) in enumerate(disp):
            d.Visibility = (j == i)
            ed.Visibility = (j == i)
            if iso:
                iso[j].Visibility = (j == i)
        # ViewTime 을 반드시 함께 옮겨야 한다. UpdatePipeline 만 부르면
        # 화면은 ViewTime(기본 0) 의 장을 그려 전부 냉시동 상태로 나온다.
        view.ViewTime = tv
        slices[i].UpdatePipeline(time=tv)
        p = "%s/%s_t%d.png" % (RAW, tag, k + 1)
        SaveScreenshot(p, view, ImageResolution=[W, H], TransparentBackground=0)
        tlog.write("%s t%d %s %.4f\n" % (tag, k + 1, m, tv))
        print("  %s  t=%.2f s (요청 %.2f)" % (os.path.basename(p), tv, tw), flush=True)
tlog.close()

# ---------- 컬러바 (배치는 사용자가 하므로 따로 뽑는다) ----------
# 수정본은 Fig 2·4·6 공통 색표 하나를 rom/panels_length.py 가 만든다(NO_CBAR=1, E-26).
if os.environ.get("NO_CBAR") == "1":
    print("완료: %s (%d 장, 컬러바 없음)" % (OUT, len(CASES) * len(want)))
else:
    for j, (d, ed) in enumerate(disp):
        d.Visibility = (j == 0)
        ed.Visibility = False
        if iso:
            iso[j].Visibility = False
    d0 = disp[0][0]
    d0.Opacity = 0.0
    lut = GetColorTransferFunction(TFIELD)
    d0.SetScalarBarVisibility(view, True)
    sb = GetScalarBar(lut, view)
    # 조판에서 가로 제목을 따로 얹을 때는 CBAR_TITLE="" 로 비운다.
    sb.Title = os.environ.get("CBAR_TITLE", "Temperature (\u00b0C)")
    sb.ComponentTitle = ""
    sb.TitleColor = [0, 0, 0]
    sb.LabelColor = [0, 0, 0]
    sb.WindowLocation = "Any Location"
    sb.Position = [0.16, 0.05]
    sb.ScalarBarLength = 0.90
    sb.ScalarBarThickness = int(os.environ.get("CBAR_TH", "26"))
    sb.TitleFontSize = int(os.environ.get("CBAR_FS", "17"))
    sb.LabelFontSize = int(os.environ.get("CBAR_FS", "17")) - 2
    sb.Orientation = "Vertical"
    sb.AutomaticLabelFormat = 0
    sb.LabelFormat = "%.0f"
    sb.RangeLabelFormat = "%.0f"
    # 100 단위로만 눈금을 단다. 자동 눈금은 1.2e+03 같은 표기가 섞인다.
    _step = float(os.environ.get("CBAR_STEP", "100"))
    _lab = []
    _v = _step * round(TMIN / _step)
    while _v <= TMAX + 1e-9:
        if _v >= TMIN - 1e-9:
            _lab.append(_v)
        _v += _step
    sb.UseCustomLabels = 1
    sb.CustomLabels = _lab
    sb.AddRangeLabels = 0
    pvfont.scalarbar(sb)
    _cw = int(os.environ.get("CBAR_W", "230"))
    _ch = int(os.environ.get("CBAR_H", "430"))
    view.ViewSize = [_cw, _ch]
    SaveScreenshot("%s/colorbar.png" % OUT, view, ImageResolution=[_cw, _ch])
    print("→ colorbar.png")
    print("완료: %s (%d 장 + 컬러바)" % (OUT, len(CASES) * len(want)))
