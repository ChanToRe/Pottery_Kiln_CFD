"""ParaView 글꼴 — 그림 안 모든 글자를 Times New Roman 으로.

VTK 내장 'Times' 는 Times 계열 대체 자형(Nimbus Roman)이다. 논문에 쓰려면
실제 자형이어야 하므로 FontFamily='File' 로 `fonts/times.ttf` 를 직접 물린다.
그 파일이 없으면 내장 'Times' 로 물러선다.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
TIMES = os.environ.get("TTF_PATH", os.path.join(_HERE, "..", "..", "fonts", "times.ttf"))
_HAVE = os.path.exists(TIMES)


def serif(disp, prefixes=("",)):
    """Text/AnnotateTime display 또는 ScalarBar 에 Times 를 건다.

    ScalarBar 는 Title/Label 두 벌을 따로 가지므로 prefixes 로 넘긴다.
    """
    for p in prefixes:
        try:
            if _HAVE:
                setattr(disp, p + "FontFamily", "File")
                setattr(disp, p + "FontFile", os.path.abspath(TIMES))
            else:
                setattr(disp, p + "FontFamily", "Times")
        except Exception as e:      # 속성이 없는 프록시는 조용히 넘어간다
            print(f"[pvfont] {p}FontFamily 설정 실패: {e}", flush=True)


def scalarbar(sb):
    serif(sb, ("Title", "Label"))
