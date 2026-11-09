#!/usr/bin/env python3
"""
Fig 4·6 낱장의 온도 색표 (원래 section.py 에 있던 두 함수만 옮겼다).

    rainbow(f)   0..1 → RGB  (투고본 Fig 4·6 기본)
    inferno(f)   0..1 → RGB  (PALETTE=inferno)
    jet(f)       0..1 → RGB  (PALETTE=jet) — Fig 2 의 ParaView 'Jet' 과 같은 색 (수정본, E-26)
"""

# ParaView 5.10 'Jet' 프리셋의 RGBPoints (이 환경의 pvbatch 에서 lut.ApplyPreset("Jet") 로 읽은 값,
# 0..1 정규화, 색 공간 RGB 선형 보간). Fig 2 의 CFD 단면과 Fig 4·6 의 색이 같아야 범례 하나로 읽힌다.
_JET = [(0.0, (0.0, 0.0, 0.5625)), (0.111111, (0.0, 0.0, 1.0)), (0.36508, (0.0, 1.0, 1.0)),
        (0.492063, (0.5, 1.0, 0.5)), (0.619047, (1.0, 1.0, 0.0)), (0.873016, (1.0, 0.0, 0.0)),
        (1.0, (0.5, 0.0, 0.0))]


def jet(f):
    """0..1 → RGB (ParaView Jet)."""
    f = max(0.0, min(1.0, f))
    for i in range(1, len(_JET)):
        x1, c1 = _JET[i - 1]
        x2, c2 = _JET[i]
        if f <= x2:
            t = (f - x1) / (x2 - x1)
            return tuple(int(round(255 * (c1[k] + t * (c2[k] - c1[k])))) for k in range(3))
    return tuple(int(round(255 * c)) for c in _JET[-1][1])


def rainbow(f):
    """0..1 → RGB. 파랑→청록→초록→노랑→빨강. 온도 구간이 좁을 때
    inferno 보다 색 변화가 커서 등온선이 눈에 띈다."""
    stops = [(0.00, (0, 0, 140)), (0.12, (0, 0, 255)), (0.30, (0, 200, 255)),
             (0.50, (0, 220, 60)), (0.68, (255, 240, 0)), (0.85, (255, 120, 0)),
             (1.00, (170, 0, 0))]
    f = max(0.0, min(1.0, f))
    for i in range(1, len(stops)):
        x1, c1 = stops[i - 1]
        x2, c2 = stops[i]
        if f <= x2:
            t = (f - x1) / (x2 - x1)
            return tuple(int(c1[k] + t * (c2[k] - c1[k])) for k in range(3))
    return stops[-1][1]


def inferno(f):
    """0..1 → RGB. 흰 배경에서 최고온부가 사라지지 않는 램프 (검정→노랑)."""
    stops = [(0.00, (12, 8, 38)), (0.15, (60, 15, 85)), (0.30, (114, 31, 96)),
             (0.50, (168, 46, 80)), (0.68, (213, 80, 46)), (0.84, (243, 137, 22)),
             (0.94, (250, 195, 44)), (1.00, (252, 254, 164))]
    f = max(0.0, min(1.0, f))
    for i in range(1, len(stops)):
        x1, c1 = stops[i - 1]
        x2, c2 = stops[i]
        if f <= x2:
            t = (f - x1) / (x2 - x1)
            return tuple(int(c1[k] + t * (c2[k] - c1[k])) for k in range(3))
    return stops[-1][1]
