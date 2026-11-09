"""
백제 한성기 중부지역 토기가마 요인설계 모델러 (축방향 연장 방식)
(원 파일명 mesh/kiln_gen2.py 에서 rev4 생성기가 쓰는 fillet_path 만 옮겼다)

핵심 설계원칙:
  단면 제원(폭·고)과 화구부·연도부 형상을 '절대 호장(arclength)' 기준으로 정의한다.
  따라서 소성부 길이만 늘어나고 유입부/유출부 형상은 모든 모델에서 동일하다.
  -> 길이 효과가 다른 형상 요인과 교락되지 않는다.

중심선은 직선 + 원호 필렛으로 구성하여 곡률(1/R)을 명시적으로 통제한다.
  자기교차 방지조건: 천장고 H < 곡률반경 R  (실제로는 H/R < 0.7 유지)
"""
import numpy as np

DS = 0.02   # 중심선 샘플 간격 (m)


# ---------------------------------------------------------------- 필렛 경로 --
def fillet_path(pts, radii):
    """직선 폴리라인 + 꼭짓점 원호 필렛 -> (P, kappa) 등간격 샘플"""
    pts = [np.asarray(p, float) for p in pts]
    segs = []          # ('L', A, B) 또는 ('A', center, R, a0, a1, sign)
    cur = pts[0]
    for i in range(1, len(pts) - 1):
        A, B, C = pts[i - 1], pts[i], pts[i + 1]
        R = radii[i - 1]
        u = (A - B) / np.linalg.norm(A - B)
        v = (C - B) / np.linalg.norm(C - B)
        cosang = np.clip(u @ v, -1, 1)
        th = np.arccos(cosang)                 # 두 변 사이 끼인각
        if th > np.pi - 1e-6 or R <= 0:        # 거의 일직선
            continue
        t = R / np.tan(th / 2)
        T1, T2 = B + u * t, B + v * t
        bis = (u + v); bis /= np.linalg.norm(bis)
        ctr = B + bis * (R / np.sin(th / 2))
        segs.append(('L', cur.copy(), T1.copy()))
        a0 = np.arctan2(*(T1 - ctr)[::-1])
        a1 = np.arctan2(*(T2 - ctr)[::-1])
        d = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        segs.append(('A', ctr.copy(), R, a0, d))
        cur = T2.copy()
    segs.append(('L', cur.copy(), pts[-1].copy()))

    P, K = [], []
    for s in segs:
        if s[0] == 'L':
            A, B = s[1], s[2]
            L = np.linalg.norm(B - A)
            n = max(int(L / DS), 2)
            tt = np.linspace(0, 1, n, endpoint=False)
            P.append(A + (B - A) * tt[:, None]); K.append(np.zeros(n))
        else:
            ctr, R, a0, d = s[1], s[2], s[3], s[4]
            n = max(int(abs(d) * R / DS), 3)
            aa = a0 + d * np.linspace(0, 1, n, endpoint=False)
            P.append(ctr + R * np.column_stack([np.cos(aa), np.sin(aa)]))
            K.append(np.full(n, 1.0 / R))
    P.append(pts[-1][None, :]); K.append(np.zeros(1))
    P = np.vstack(P); K = np.concatenate(K)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    return P, K, s
