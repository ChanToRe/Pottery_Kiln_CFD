"""
삼국시대 토기가마(등요) 내부공간 파라메트릭 3D 모델러
(원 파일명 mesh/kiln_gen.py — rev4 생성기의 공용 함수)
- OpenFOAM(snappyHexMesh)용 STL 생성기
- 모델링 대상은 '가마 구조체'가 아니라 '내부 유동영역(fluid domain)'의 경계면이다.

좌표계: x = 가마 주축(화구→연도, 오름 방향), y = 좌우, z = 연직 상방. 단위 m.
"""
import numpy as np

# ----------------------------------------------------------------------------
# 단면 형상: 평바닥 + 초타원(superellipse) 아치 천장
# ----------------------------------------------------------------------------
N_ARCH = 64      # 아치부 분할수
N_FLOOR = 16     # 바닥부 분할수
N_RING = N_ARCH + N_FLOOR


def section_ring(width, height, n_exp=2.4):
    """국소좌표 (u=좌우, v=상방)에서 닫힌 단면 폴리곤 반환. shape (N_RING, 2)"""
    a, b = width / 2.0, height
    phi = np.linspace(0.0, np.pi, N_ARCH, endpoint=False)   # 우측 바닥 -> 좌측 바닥
    u = a * np.sign(np.cos(phi)) * np.abs(np.cos(phi)) ** (2.0 / n_exp)
    v = b * np.abs(np.sin(phi)) ** (2.0 / n_exp)
    arch = np.column_stack([u, v])
    # 바닥: 좌측(-a) -> 우측(+a), 양 끝점은 아치와 중복되지 않게
    t = np.linspace(0.0, 1.0, N_FLOOR + 2)[1:-1]
    floor = np.column_stack([-a + 2 * a * t, np.zeros_like(t)])
    return np.vstack([arch, floor])


# ----------------------------------------------------------------------------
# 삼각형 생성
# ----------------------------------------------------------------------------
def tube_tris(rings):
    """링 사이 측면 삼각형. 반환: (K,3,3)"""
    ns, nr, _ = rings.shape
    tris = []
    for i in range(ns - 1):
        A, B = rings[i], rings[i + 1]
        for j in range(nr):
            k = (j + 1) % nr
            tris.append([A[j], B[j], B[k]])
            tris.append([A[j], B[k], A[k]])
    return np.array(tris)


def cap_tris(ring, flip=False):
    """단면 폴리곤을 중심점 팬 삼각분할로 막음"""
    c = ring.mean(axis=0)
    nr = len(ring)
    tris = []
    for j in range(nr):
        k = (j + 1) % nr
        tris.append([c, ring[k], ring[j]] if flip else [c, ring[j], ring[k]])
    return np.array(tris)


def signed_volume(tris):
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    return np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0


def check_watertight(*tri_sets):
    """모든 에지가 정확히 2번 등장하는지(닫힌 2-manifold) 확인"""
    allt = np.vstack(tri_sets)
    V = np.round(allt.reshape(-1, 3), 6)
    uniq, inv = np.unique(V, axis=0, return_inverse=True)
    F = inv.reshape(-1, 3)
    e = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.sort(e, axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    return dict(n_tri=len(F), n_vert=len(uniq), open_edges=int((cnt != 2).sum()),
                euler=len(uniq) - len(np.unique(e, axis=0)) + len(F))


# ----------------------------------------------------------------------------
# STL 출력
# ----------------------------------------------------------------------------
def _stl_solid(name, tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n = n / ln
    out = [f"solid {name}"]
    for t, nv in zip(tris, n):
        out.append(f"  facet normal {nv[0]:.6e} {nv[1]:.6e} {nv[2]:.6e}")
        out.append("    outer loop")
        for p in t:
            out.append(f"      vertex {p[0]:.6e} {p[1]:.6e} {p[2]:.6e}")
        out.append("    endloop")
        out.append("  endfacet")
    out.append(f"endsolid {name}")
    return "\n".join(out)


def write_stl(path, regions):
    """regions: dict[name] = (K,3,3). snappyHexMesh용 multi-solid ASCII STL"""
    with open(path, "w") as f:
        for name, tris in regions.items():
            f.write(_stl_solid(name, tris) + "\n")
