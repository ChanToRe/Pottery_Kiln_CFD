"""
백제 한성기 중부지역 토기가마 — 연소부 2요인 모델러 (개정 3판, rev4 STL 생성용)
(원 파일명 mesh/kiln_gen5.py)

개정 내용 (실측 도면 검토 반영)
  - 연소부는 앞뒤 벽이 수직이고 바닥이 평평한 구덩이다 (경사 바닥 아님).
  - 화구·연소부 바닥 모두 수평. 소성부만 15° 경사.
  - 두 개의 독립 형상요인:
      h_step : 연소부 바닥 -> 소성부 바닥 단차
      h_drop : 화구 바닥 -> 연소부 바닥 낙차 (수직 연료투입 여부)

  형식 대응
      A ① 수평연소 무단식   h_step=0     h_drop=0
      B ② 수평연소 유단식   h_step=0.35  h_drop=0
      C ③ 수직연소 유단식   h_step=0.35  h_drop=0.55
  (3판에서 유단식 단높이를 0.55 → 0.35 m 로 통일하고 반사실 형식 ④ 를 뺐다.
   실제 값은 아래 STEP_B·STEP_C·DROP_C·TYPES 가 정한다.)
"""
import numpy as np
from rev4_common import section_ring, tube_tris, cap_tris, signed_volume, write_stl, N_RING
from rev4_fillet import fillet_path

SLOPE = np.deg2rad(15.0)
W_MAX, H_MAX = 2.20, 1.10       # 소성부 최대폭 / 천장고
W_RAMP, W_TAPER = 1.00, 0.80
L_COMB = 1.60                   # 연소부 길이 (고정)
APRON = 1.30                    # 화구 터널 길이
W_STOKE, H_STOKE = 0.95, 0.70   # 화구 단면
W_COMB, H_COMB = 1.25, 0.95     # 연소부 폭 / 기본 천장고
FLUE_W, FLUE_H, FLUE_ANG = 0.55, 0.48, 68.0
D_BURIAL = 1.60
FLUE_RISE = D_BURIAL / np.sin(np.deg2rad(FLUE_ANG))
EPS = 1e-3

STEP_B = 0.35    # ② 수평연소 유단식 단높이
STEP_C = 0.35    # ③ 수직연소 유단식 단높이
DROP_C = 0.55    # ③ 화구->연소부 낙차

TYPES = {
    'A': (0.0,    0.0,    "① 수평연소 무단식  (1기)"),
    'B': (STEP_B, 0.0,    "② 수평연소 유단식  (2기)"),
    'C': (STEP_C, DROP_C, "③ 수직연소 유단식  (3기)"),
}


def build(h_step, h_drop, L_fire, ns=260):
    d = np.array([np.cos(SLOPE), np.sin(SLOPE)])
    P0 = np.array([0.0, 0.0])                  # 연소부/소성부 경계 (단 위치)
    Pfb = np.array([-L_COMB, 0.0])             # 화구/연소부 경계 (낙차 위치)
    Pin = np.array([-(L_COMB + APRON), 0.0])
    P1 = P0 + d * L_fire
    b = np.deg2rad(FLUE_ANG)
    v = [Pin, P0, P1 + d * 0.30,
         P1 + d * 0.30 + np.array([np.cos(b), np.sin(b)]) * FLUE_RISE]
    # x=0 의 필렛 R=2.6 -> 접선길이 0.34 m, 연소부 최대 단면고 1.50 기준 h/R=0.58
    P, K, s = fillet_path(v, [2.60, 2.00])
    L = s[-1]
    at = lambda pt: s[np.argmin(np.linalg.norm(P - pt, axis=1))]
    sfb, s0, s1 = at(Pfb), at(P0), at(P1)
    sf = at(P1 + d * 0.30)

    # 바닥 표고: 화구 -(h_step-h_drop) / 연소부 -h_step / 소성부 0
    lift = np.where(s < sfb - EPS, -(h_step - h_drop),
                    np.where(s < s0 - EPS, -h_step, 0.0))

    # 천장 오프셋(중심선 기준 절대값). 바닥과 독립적으로 정의해야
    # 낙차 지점에서 천장이 함께 내려가는 오목 노치가 생기지 않는다.
    hc_stoke = -(h_step - h_drop) + H_STOKE       # 화구 천장 절대표고
    hc = np.interp(s,
                   [0, sfb - EPS, sfb, sfb + 0.25, s0 - EPS, s0, s0 + 0.85,
                    s1 - 0.60, s1, sf, L],
                   [hc_stoke, hc_stoke, hc_stoke, H_COMB,
                    H_COMB, H_COMB, H_MAX, H_MAX, 0.92, 0.72, FLUE_H])
    H = hc - lift

    W = np.interp(s,
                  [0, sfb - EPS, sfb + 0.25, s0, s0 + W_RAMP,
                   s1 - W_TAPER, s1, sf, L],
                  [W_STOKE, W_STOKE, W_COMB, 1.35, W_MAX,
                   W_MAX, 1.05, 0.80, FLUE_W])

    st = np.linspace(0, L, ns)
    Pi = np.column_stack([np.interp(st, s, P[:, 0]), np.interp(st, s, P[:, 1])])
    Ki = np.interp(st, s, K)
    Wi, Hi, Li = (np.interp(st, s, X) for X in (W, H, lift))
    T = np.gradient(Pi, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)

    rings = np.empty((ns, N_RING, 3))
    right = np.array([0.0, 1.0, 0.0])
    for i in range(ns):
        Tv = np.array([T[i, 0], 0.0, T[i, 1]])
        up = np.cross(Tv, right); up /= np.linalg.norm(up)
        org = np.array([Pi[i, 0], 0.0, Pi[i, 1]]) + up * Li[i]
        sec = section_ring(Wi[i], Hi[i])
        rings[i] = org + sec[:, 0:1] * right + sec[:, 1:2] * up

    return dict(rings=rings, s=st, P=Pi, W=Wi, H=Hi, lift=Li,
                hR=float((Hi * Ki).max()), sfb=sfb, s0=s0, s1=s1, L_path=L)


def finalize(r):
    walls = tube_tris(r['rings'])
    inlet = cap_tris(r['rings'][0], flip=True)
    outlet = cap_tris(r['rings'][-1], flip=False)
    if signed_volume(np.vstack([walls, inlet, outlet])) < 0:
        walls, inlet, outlet = (x[:, ::-1] for x in (walls, inlet, outlet))
    return walls, inlet, outlet
