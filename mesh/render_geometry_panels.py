# 비교 1(연소부 형식)·2(소성부 길이)·3(소성실 단)의 형상 낱장 패널.
#   DISPLAY=:0 pvbatch mesh/render_geometry_panels.py      (run_all.sh figures)
#   원고 Fig 1(형식)·Fig 3(길이)·Fig 5(계단) 의 낱장.
#
# 두 겹 표현이다. 안쪽은 유체 영역(= 가마 내부 형상) 불투명, 바깥은 그 면을
# 법선 방향으로 벽체 두께 0.35 m 만큼 밀어낸 것 반투명.
#
# **한 도면 안의 패널은 같은 카메라·같은 축척이다.** 초점과 평행축척을 그 도면의
# 기준 형상(ANCHOR)에 한 번 고정하고 그 도면의 모든 패널에 그대로 쓴다. 따라서
# 짧은 가마는 짧게 보인다. 투고본은 도면마다 ANCHOR·SCALE·VIEW 가 다르다
# (Fig 1 kiln_A_L065·0.37·1600x1120, Fig 3 kiln_B_L085·0.40·1250x1120,
#  Fig 5 kiln_B_L065·0.37·1600x1120 — Rscripts/make_figures.sh).
#
# 글자·범례·축척막대는 넣지 않는다.
from paraview.simple import *
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WALL_T = 0.35                      # 벽체·천장 두께 [m]
GAS = [0.792, 0.800, 0.310]        # 안쪽 유체 영역
SHELL = [0.855, 0.882, 0.878]      # 바깥 벽체
SHELL_OPACITY = 0.30

# 카메라 — 화구 쪽 사선. 방향은 세 도면 공통.
# 기본값은 가장 긴 형상(소성부 8.5 m)에 축척을 맞춘 것이다. 투고본 설정은
# make_figures.sh 가 도면마다 ANCHOR·SCALE·VIEW 환경변수로 준다.
ANCHOR = os.environ.get("ANCHOR", "kiln_B_L085")
CAM = (-0.85, -0.60, 0.42)
SCALE = float(os.environ.get("SCALE", "0.40"))
VIEW = [int(v) for v in os.environ.get("VIEW", "2000,1120").split(",")]

# 계단은 소성부 바닥에 있어 오목한 모서리가 많다. 법선을 나눠 밀어내면 면이
# 서로 파고들어 잔털이 생기므로, 계단 형상만 법선을 평균낸다.
FEAT_SMOOTH = ["kiln_B_L065_S6", "kiln_B_L065_S12", "kiln_B_L065_S20"]

SETS = [
    ("forms", "Results/figures/fig1_forms_3d",
     [("A", "kiln_A_L065"), ("B", "kiln_B_L065"), ("C", "kiln_C_L065")]),
    ("length", "Results/figures/fig3_length_3d",
     [("L025", "kiln_B_L025"), ("L045", "kiln_B_L045"),
      ("L065", "kiln_B_L065"), ("L085", "kiln_B_L085")]),
    ("steps", "Results/figures/fig5_steps_3d",
     [("S00", "kiln_B_L065"), ("S06", "kiln_B_L065_S6"),
      ("S12", "kiln_B_L065_S12"), ("S20", "kiln_B_L065_S20")]),
]


def walls_only(stem, tmp):
    """ASCII STL 에서 walls solid 만 떼어 낸다.
    화구·연도 마구리까지 밀어내면 관 끝이 막힌다."""
    src = os.path.join(ROOT, "mesh", "stl", stem + ".stl")
    dst = os.path.join(tmp, "walls_%s.stl" % stem)
    keep, out = False, []
    with open(src) as fh:
        for line in fh:
            s = line.lstrip()
            if s.startswith("solid"):
                keep = s.split()[1:2] == ["walls"]
            if keep:
                out.append(line)
            if s.startswith("endsolid") and keep:
                keep = False
    with open(dst, "w") as fh:
        fh.writelines(out)
    return dst


probe = STLReader(FileNames=[os.path.join(ROOT, "mesh", "stl", ANCHOR + ".stl")])
probe.UpdatePipeline()
b = probe.GetDataInformation().GetBounds()
CX, CY, CZ = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2
SPAN = max(b[1] - b[0], b[3] - b[2], b[5] - b[4])
print("anchor %s  bounds %s  span %.2f" % (ANCHOR, b, SPAN))
Delete(probe)

view = CreateRenderView()
view.ViewSize = VIEW
view.Background = [1.0, 1.0, 1.0]
view.UseColorPaletteForBackground = 0
view.OrientationAxesVisibility = 0
view.CameraParallelProjection = 1


def set_camera():
    """첫 Render 가 ResetCamera 를 소진한다. 그 뒤라야 축척이 남는다."""
    fx, fy, fz = CAM
    view.CameraFocalPoint = [CX, CY, CZ]
    view.CameraPosition = [CX + fx * SPAN, CY + fy * SPAN, CZ + fz * SPAN]
    view.CameraViewUp = [0.0, 0.0, 1.0]
    view.CameraParallelScale = SPAN * SCALE


def panel(stem, path, tmp):
    inner = STLReader(FileNames=[os.path.join(ROOT, "mesh", "stl", stem + ".stl")])
    di = Show(inner, view)
    di.Representation = "Surface"
    ColorBy(di, None)              # STL 이 실어온 배열로 칠하지 않는다
    di.DiffuseColor = GAS
    di.AmbientColor = GAS
    di.Ambient = 0.20
    di.Diffuse = 0.85
    di.Specular = 0.30
    di.SpecularPower = 30

    src2 = STLReader(FileNames=[walls_only(stem, tmp)])
    norm = GenerateSurfaceNormals(Input=src2)
    norm.FeatureAngle = 179.0 if stem in FEAT_SMOOTH else 45.0
    shell = WarpByVector(Input=norm)
    shell.Vectors = ["POINTS", "Normals"]
    shell.ScaleFactor = WALL_T
    ds = Show(shell, view)
    ds.Representation = "Surface"
    ColorBy(ds, None)
    ds.DiffuseColor = SHELL
    ds.AmbientColor = SHELL
    ds.Opacity = SHELL_OPACITY
    ds.Ambient = 0.35
    ds.Diffuse = 0.70
    ds.Specular = 0.05

    Render()
    set_camera()
    Render()
    # Quality 는 JPEG 전용이다. PNG 로 저장하면 그 인자를 받지 않는다.
    if path.lower().endswith(".jpg"):
        SaveScreenshot(path, view, ImageResolution=VIEW, Quality=95)
    else:
        SaveScreenshot(path, view, ImageResolution=VIEW)
    print("  wrote", path)

    for p in (shell, norm, src2, inner):
        Hide(p, view)
        Delete(p)


# ONLY=forms 처럼 주면 그 집합만 다시 뽑는다.
_only = [x for x in os.environ.get("ONLY", "").split(",") if x]
for name, outdir, cases in SETS:
    if _only and name not in _only:
        continue
    out = os.path.join(ROOT, outdir)
    tmp = os.path.join(out, "_walls")
    os.makedirs(tmp, exist_ok=True)
    print("[%s]" % name)
    for tag, stem in cases:
        fn = "form_%s_3d.png" % tag if name == "forms" else "%s_%s.png" % (name, tag)
        panel(stem, os.path.join(out, fn), tmp)
    shutil.rmtree(tmp)          # 벽체만 뽑은 중간 STL — 렌더가 끝나면 필요 없다

# view 는 지우지 않는다. 지우면 종료 시 X 연결이 끊겨 SIGABRT 가 난다.
