#!/usr/bin/env python3
"""
토기가마 축소모델 (reduced-order model) — 소성 전 과정의 비정상 열수지

설계 원리: 시간척도로 물리를 자른다.
  초~분   부력 통풍·유동장           → 정상상태 CFD 가 담당 (cases/*_steady)
  시간~일 벽체·지반 축열, 승온·냉각  → 이 모델이 담당

CFD 가 이 모델에 넘겨주는 것은 두 가지 보정값이다 (calibrate.py 가
cases/<형식>_steady/log.solver 의 마지막 2,000 회 평균에서 읽는다).
  (1) 형식별 유효 유동면적 A_hot   ← CFD 화구 유입량
  (2) 대류 열전달계수 h_conv,ref   ← CFD 벽체 손실
통풍 구동높이 H 는 STL 형상에서 잰다 (geom.py).

구성
  기체 노드 1개 (열용량 무시, 매 스텝 대수적으로 품)
  구간별 1D 전도 스택 4개 (벽체 0.35 m + 지반 0.85 m, 후진오일러 + Thomas)

단위는 전부 SI, 온도는 K.
"""
import os
import math

# ── 물리상수 ─────────────────────────────────────────────
G = 9.81
R_AIR = 287.0
CP_AIR = 1050.0          # 고온 연소가스 평균 정압비열
SIGMA = 5.670374e-8
P_ATM = 101325.0

# ── 땔감의 이론 공기량 ───────────────────────────────────
# 땔감 조성: Ragland et al. 1991 표 3, 침엽수 9종 평균 (무수무회 기준 질량분율).
# 홍진근 2011 의 땔감은 소나무 90 %. 함수율은 LHV_EFF 와 같은 20 % (습량 기준).
# 회분·황은 뺐다. 이 조성의 이론 공기량은 무수무회 6.46, 습윤 땔감 1 kg 당 5.17 kg 이다.
# 투고본은 건조 기준 6.0 을 습윤 땔감 연료율에 곱했다 (오류목록 N-13·N-65).
WOOD_DAF = dict(C=0.527, H=0.063, O=0.408, N=0.002)
WOOD_MOIST = 0.20
Y_O2_AIR = 0.2314        # 건조 공기의 O₂ 질량분율
_MW = dict(C=12.011, H=1.008, O2=31.9988)
# 습윤 땔감 1 kg 이 완전연소할 때 쓰는 O₂ [kg]
O2_STOICH = (1.0 - WOOD_MOIST) * (WOOD_DAF["C"] * _MW["O2"] / _MW["C"]
                                  + WOOD_DAF["H"] * _MW["O2"] / (4 * _MW["H"]) - WOOD_DAF["O"])
AFR_WET = O2_STOICH / Y_O2_AIR          # 이론 공기량 [kg 공기 / kg 습윤 땔감]

# ── 재료 (원고 Table 4) ──────────────────────────────────
# dx0 은 표면쪽 첫 셀 두께. 등간격으로 두면 첫 셀 반두께의 전도저항이
# 표면 열전달저항(1,200 ℃ 에서 1/h ≈ 0.002 m2K/W)보다 6배 커져서
# 방사율·대류계수가 결과에 아예 닿지 못한다. 표면쪽을 조밀하게 준다.
WALL = dict(th=0.35, k=1.0, rho=1800.0, cp=900.0, n=22, dx0=0.0015)
# 지반 k 1.4 와 cp 는 같은 함수율이어야 한다. Farouki 1981 의 Cu = (γd/γw)(0.18 + w) 로
# 투고본 cp 880 은 함수율 약 4 %, k 1.4 는 약 15 % 에 해당해 서로 맞지 않았다 (오류목록 N-66).
# 함수율 15 % 로 맞추면 cp = (0.18 + 0.15)/(1 + 0.15) cal/g℃ = 1,200 J/kgK (ρ 1,900 은 습윤 밀도).
SOIL = dict(th=0.85, k=1.4, rho=1900.0, cp=1200.0, n=20, dx0=0.010)
T_FAR = 288.15           # 지중 항온 15 ℃
APRON_L, COMB_L = 1.30, 1.60      # 화구 터널·연소부 축길이 [m] (mesh/rev4_builder.py)
FLUE_L = 1.60 / math.sin(math.radians(68.0))


def graded(th, n, dx0):
    """dx0 에서 시작하는 등비 셀 배열. 합이 th 가 되는 공비를 찾는다."""
    if n * dx0 >= th:
        return [th / n] * n
    lo, hi = 1.0 + 1e-9, 3.0
    for _ in range(80):
        r = 0.5 * (lo + hi)
        s = dx0 * (r ** n - 1.0) / (r - 1.0)
        if s < th:
            lo = r
        else:
            hi = r
    r = 0.5 * (lo + hi)
    dx = [dx0 * r ** i for i in range(n)]
    f = th / sum(dx)
    return [d * f for d in dx]

# ── 정상상태 CFD 보정 조건 (cases/*_steady) ──────────────────
# 유입량·벽체손실·체적평균온도는 여기 적지 않는다. calibrate.py 가 매번
# cases/<형식>_steady/log.solver 에서 읽는다 (예전 판의 하드코딩 기록값
# 0.884 kg/s 등은 벽 0.20 m 시절 값이라 지웠다).
# 벽 경계조건(externalWallHeatFluxTemperature)의 층 두께·열전도율·바깥 열전달계수.
# cases/*_steady/0/T 의 walls 와 같아야 한다 — calibrate.py 가 사전이 있으면 대조한다.
CFD_WALL = dict(th=0.35, k=1.0, h_out=10.0)
CFD_STEADY = dict(
    # 정상상태 CFD 의 외기. 투고본은 정상 5 ℃ · 비정상 15 ℃ · 축소모델 19.3 ℃ 로 셋이 달랐다
    # (에디터 E-34). 이제 셋 다 19.3 ℃ (홍진근 2011 각주 2 의 건조기간 평균, N-61).
    T_amb=292.45,
    # 벽 경계조건의 외부 저항으로 calibrate.h_conv_ref 가 총저항에서 벗겨낸다.
    # 직렬 저항 th/k + 1/h_out = 0.35/1.0 + 1/10 = 0.45 m2K/W.
    # 투고본은 벽 0.20 m 시절 값 0.30 (0.20/1.0 + 1/10)으로 계산되었다 (수정제의 E-11).
    R_ext=CFD_WALL["th"] / CFD_WALL["k"] + 1.0 / CFD_WALL["h_out"],
)
C_IN = 0.80              # 화구 터널 유량계수 (날카로운 오리피스 0.6~ 터널 0.9)
EPS_RAD = 0.80           # 내부 유효 방사율 (원래 폴더 rom/sensitivity.py 의 민감도 대상 — 원고에 안 쓰여 옮기지 않음)
H_NAT = 3.0              # 자연대류 하한 [W/m2K]
F_RAD_AX = 0.70          # 연소실↔소성실 축방향 복사 교환계수 (형상계수 포함)
H_EXP = 0.8              # 대류계수의 질량유속 지수 h ∝ G^H_EXP (Dittus–Boelter 꼴). 민감도 대상(E-09, rom/sensitivity.py)

# ── 적재물 (원고 Table 5) ────────────────────────────────
# 소성실에 재임한 토기. 세 가지로 작용한다.
#   (1) 열용량   — 가마와 함께 데워야 하므로 승온이 느려진다
#   (2) 표면적   — 기체와 열을 주고받는 면이 늘어난다
#   (3) 복사 차폐 — 연소부에서 소성실 안쪽까지의 시선을 막는다
# LOAD_FRAC 는 단면에서 토기가 차지하는 비율. 0 이면 빈 가마다.
# 실제 조업은 화염이 지나갈 길을 위에 남기므로 1 이 될 수 없다.
# 적재 단면 점유율 — 질량·표면적을 정한다 (0 = 빈 가마).
#
# **기본값은 여기서만 정한다.** 예전에는 호출하는 쪽마다 rom.LOAD_FRAC 을 직접
# 대입했고, 대입하지 않는 경로(efficiency.py)가 빈 가마로 돌아 결과가 갈렸다.
# 기본값을 0 으로 두면 "설정을 잊은 경로" 가 조용히 다른 물리를 푼다 —
# 조업 중인 가마는 차 있는 것이 정상이므로 그쪽을 기본으로 삼는다.
LOAD_FRAC = float(os.environ.get("LOAD_FRAC", "0.5"))
# 복사 차폐율은 **부피 점유율과 다르다.** 토기는 바닥에 열을 지어 쌓이고
# 위쪽에 화염 통로가 남으므로, 부피의 절반을 차지해도 축방향 시선의 절반을
# 막지는 않는다. 둘을 묶으면(차폐 = 0.5) 모델의 연소실–연도 온도차가 181 ℃ 로 벌어진다.
#   부피 점유율 0.5 — **가정값**이다. 보고서에는 토기 점수(성형 191점, 소성 결과 '100여점')만
#     있고 질량 기록이 없다. 예전 주석의 '191점 ≈ 1,300 kg' 은 보고서에 없는 값이다 (N-62, N-15).
#   복사 차폐율 0.10 — 보고서 본문 '연소실과 연도부의 온도 차이는 … 폐쇄 직전에 120℃ 내외'에
#     모델의 연소실 노드 − 연도 노드를 맞춘 값이다. 보고서의 측온점은 소성실 4곳(A–D)과
#     연도부 1곳이고, 같은 보고서 <표 4> 의 측점 A − D 가 77 h 에 125 ℃ 다. 그러면 120 ℃ 는
#     소성실 앞뒤 차에 가깝고, 모델의 소성실 앞뒤 차(투고본 58 ℃)는 그 절반 이하다 (N-59).
#     사용자 결정(2026-10-20): 0.10 을 그대로 두고 이 차이를 한계로 밝힌다.
# 복사 차폐율. LOAD_FRAC 과 같은 이유로 기본값을 여기서만 정한다 —
# 이것을 None 으로 두었을 때 efficiency.py 와 study_data.py 가 3.0 % 갈렸다.
BLOCK_FRAC = float(os.environ.get("BLOCK_FRAC", "0.10"))
WARE_EPS = 0.60          # 적재층 공극률
WARE_DP = 0.20           # 기종 평균 특성치수 [m]
WARE_RHO = 1900.0        # 토기 밀도 [kg/m3]
WARE_CP = 850.0          # 토기 비열 [J/kgK]
# 그릇은 속이 비어 있다. 공극률 0.60 은 **그릇 사이** 빈틈이고, 그릇 외피
# 안쪽도 대부분 비어 있다. 두께 ~1 cm, 크기 ~20 cm 의 얇은 용기면
# 도자 부피 / 외피 부피 ≈ 3t/R ≈ 0.3. 이 항을 빼면 질량이 3 배 과대해진다.
WARE_HOLLOW = 0.30       # 그릇 외피 대비 실제 도자 부피 비
# 축방향 복사의 도달거리 배율. 1.0 = 빈 가마(시선이 끝까지 뚫린다).
# 소성실에 토기가 차면 시선이 막혀 도달거리가 짧아진다 — 적재 효과의 대용값.
RAD_RANGE = 1.0


# ── 1D 전도 스택 ─────────────────────────────────────────
class Stack:
    """표면에서 지중까지 수직 1D 전도. 후진오일러(무조건 안정) + Thomas."""

    def __init__(self, area, T0):
        self.A = area
        dx, k, rc = [], [], []
        for m in (WALL, SOIL):
            for d in graded(m["th"], m["n"], m["dx0"]):
                dx.append(d)
                k.append(m["k"])
                rc.append(m["rho"] * m["cp"])
        self.dx, self.k, self.rc = dx, k, rc
        self.n = len(dx)
        self.T = [T0] * self.n
        # 내부 면 전도 컨덕턴스 [W/m2K]
        self.Uf = [1.0 / (dx[i] / (2 * k[i]) + dx[i + 1] / (2 * k[i + 1]))
                   for i in range(self.n - 1)]
        self.U_out = 1.0 / (dx[-1] / (2 * k[-1]))
        self._half_in = dx[0] / (2 * k[0])

    def U_in(self, h):
        """기체 → 첫 셀 중심까지의 총 컨덕턴스 (대류·복사 + 반셀 전도)"""
        return 1.0 / (1.0 / h + self._half_in)

    def prepare(self, dt):
        """이번 스텝의 벽을 표면 첫 셀에서 본 등가 x0 = A0 + B0·q0 를 구한다.

        q0 [W/m2] 는 기체에서 첫 셀로 드는 열류다. 기체 노드는 이 등가로 벽 손실을
        셈해야 벽의 후진오일러 갱신(step)과 같은 열류를 쓴다. 투고본은 이전 스텝의
        첫 셀 온도로 손실을 셈했는데, 첫 셀(1.5 mm)이 한 스텝(60 s) 안에 거의 기체
        온도까지 데워지므로 기체가 잃은 열이 벽이 받은 열보다 컸다 — 2 h 시험에서
        발열의 5.5 % 가 어디에도 가지 않고 사라졌다 (오류목록 N-74).
        """
        n, dx, rc = self.n, self.dx, self.rc
        b = [0.0] * n
        d = [0.0] * n
        for i in range(n):
            cap = rc[i] * dx[i] / dt
            b[i] = cap
            d[i] = cap * self.T[i]
            if i > 0:
                b[i] += self.Uf[i - 1]
            if i == n - 1:
                b[i] += self.U_out
                d[i] += self.U_out * T_FAR
            else:
                b[i] += self.Uf[i]
        e = [0.0] * n
        e[0] = 1.0
        for i in range(1, n):            # 하삼각 소거 (a_i = c_{i-1} = −Uf_{i-1})
            w = -self.Uf[i - 1] / b[i - 1]
            b[i] += w * self.Uf[i - 1]
            d[i] -= w * d[i - 1]
            e[i] -= w * e[i - 1]
        xd, xe = d[n - 1] / b[n - 1], e[n - 1] / b[n - 1]
        for i in range(n - 2, -1, -1):
            xd = (d[i] + self.Uf[i] * xd) / b[i]
            xe = (e[i] + self.Uf[i] * xe) / b[i]
        self._A0, self._B0 = xd, xe

    def q_in(self, Tg, h):
        """기체 Tg, 표면 계수 h 일 때 이번 스텝에 실제로 벽에 드는 열류 [W/m2] (prepare 뒤)"""
        U = self.U_in(h)
        return U * (Tg - self._A0) / (1.0 + self._B0 * U)

    def surface_T(self, Tg, h):
        """표면온도 — 복사 계산에 필요 (이번 스텝 갱신 뒤의 값)"""
        return Tg - self.q_in(Tg, h) / h

    def step(self, dt, Tg, h):
        n, dx, rc = self.n, self.dx, self.rc
        a = [0.0] * n
        b = [0.0] * n
        c = [0.0] * n
        d = [0.0] * n
        Uin = self.U_in(h)
        for i in range(n):
            cap = rc[i] * dx[i] / dt
            b[i] = cap
            d[i] = cap * self.T[i]
            if i == 0:
                b[i] += Uin
                d[i] += Uin * Tg
            else:
                a[i] = -self.Uf[i - 1]
                b[i] += self.Uf[i - 1]
            if i == n - 1:
                b[i] += self.U_out
                d[i] += self.U_out * T_FAR
            else:
                c[i] = -self.Uf[i]
                b[i] += self.Uf[i]
        # Thomas
        for i in range(1, n):
            w = a[i] / b[i - 1]
            b[i] -= w * c[i - 1]
            d[i] -= w * d[i - 1]
        x = [0.0] * n
        x[n - 1] = d[n - 1] / b[n - 1]
        for i in range(n - 2, -1, -1):
            x[i] = (d[i] - c[i] * x[i + 1]) / b[i]
        self.T = x
        return Uin * (Tg - x[0]) * self.A      # 이번 스텝 벽으로 간 열류 [W]

    def stored(self, Tref):
        return sum(self.rc[i] * self.dx[i] * (self.T[i] - Tref)
                   for i in range(self.n)) * self.A


# ── 통풍 (부력 구동, 준정상) ─────────────────────────────
def calibrate_A_hot(H_stack, A_in, mdot, T_amb, T_bulk):
    """CFD 유입량 한 점에서 형식별 유효 고온부 유동면적을 역산한다."""
    rho_a = P_ATM / (R_AIR * T_amb)
    rho_g = P_ATM / (R_AIR * T_bulk)
    dp = G * H_stack * (rho_a - rho_g)
    tot = 2.0 * dp / mdot ** 2                       # = Σ K/(ρA²)
    inlet = 1.0 / (C_IN ** 2 * rho_a * A_in ** 2)
    hot = tot - inlet
    if hot <= 0:
        raise ValueError("보정 실패: 화구 저항만으로 CFD 유량을 넘어선다")
    return 1.0 / math.sqrt(hot * rho_g)


def draft(Tg, phi, H_stack, A_in, A_hot, T_amb):
    """화구 개구율 phi 에서의 유입 질량유량 [kg/s]"""
    if phi <= 0.0:
        return 0.0
    rho_a = P_ATM / (R_AIR * T_amb)
    rho_g = P_ATM / (R_AIR * Tg)
    dp = G * H_stack * (rho_a - rho_g)
    if dp <= 0.0:
        return 0.0
    res = (1.0 / (C_IN ** 2 * rho_a * (phi * A_in) ** 2)
           + 1.0 / (rho_g * A_hot ** 2))
    return math.sqrt(2.0 * dp / res)


# ── 모델 본체 ────────────────────────────────────────────
# 기체 노드는 유로 순서대로 이어진다. 최소 2개여야 실측 검증 기준인
# "연소실–연도부 온도차 300 → 120 ℃" 를 계산할 수 있고,
# 소성실을 축방향으로 쪼개면(geom.extract 의 seg_m) 어느 구간이 소성 온도에
# 닿는지 — 즉 유효 소성용적 — 를 볼 수 있다.
def build_nodes(geo):
    """유로 순서 [(이름, [구간명...]), ...]. 소성부 분할 여부를 자동 반영한다."""
    wk = geo.get("ware_keys", ["ware"])
    if len(wk) == 1:
        return [("comb", ("stoke", "comb")), ("ware", ("ware", "flue"))]
    return ([("comb", ("stoke", "comb"))]
            + [(k, (k,)) for k in wk]
            + [("flue", ("flue",))])


class Ware:
    """소성실 한 구간에 재임한 토기 — 집중 열용량 하나.

    질량   m  = ρ (1−ε) V_load,   V_load = LOAD_FRAC × 구간 기체용적
    표면적 A  = 6(1−ε)/dp × V_load        (충전층 비표면적)
    기체와 대류·복사로 주고받고, 스스로 데워지며 승온을 늦춘다.
    토기 벽이 얇아(~1 cm) Biot 수가 작으므로 집중정수로 둔다.
    """

    def __init__(self, V_gas, T0):
        V_load = LOAD_FRAC * V_gas
        solid = (1.0 - WARE_EPS) * WARE_HOLLOW * V_load
        self.m_cp = WARE_RHO * WARE_CP * solid
        self.A = 6.0 * (1.0 - WARE_EPS) / WARE_DP * V_load
        self.T = T0

    def step(self, dt, Tg, h):
        """후진오일러 한 스텝. 반환값은 기체에서 토기로 간 열류 [W]."""
        if self.m_cp <= 0.0:
            return 0.0
        c = self.m_cp / dt
        self.T = (c * self.T + h * self.A * Tg) / (c + h * self.A)
        return h * self.A * (Tg - self.T)

    def stored(self, Tref):
        return self.m_cp * (self.T - Tref)


class Kiln:
    def __init__(self, geo, A_hot, h_conv_ref, mdot_ref, T_amb=292.45, eps_rad=EPS_RAD):
        """geo: rom.geom.extract() 결과. T_amb 기본 19.3 ℃ — 홍진근 2011 각주 2 의 가마 건조기간
        (2009-05-12–22) 평균기온. 소성 기간의 외기는 보고서에 없어 대용값으로 쓴다 (N-61)

        A_hot·h_conv_ref·mdot_ref 는 정상상태 CFD 보정값이다 — calibrate.build 가 넘긴다.
        """
        self.geo = geo
        self.T_amb = T_amb
        self.eps = eps_rad
        self.H = geo["H_stack"]
        self.A_in = geo["A_in"]
        self.A_hot = A_hot
        self.h_ref = h_conv_ref
        self.mdot_ref = mdot_ref
        self.stacks = dict((z, Stack(a, T_amb))
                           for z, a in geo["zone_area"].items() if a > 0)
        for st in self.stacks.values():
            st.gf = 1.0
        self.nodes = [(nm, [self.stacks[z] for z in zs if z in self.stacks])
                      for nm, zs in build_nodes(geo)]
        # 노드별 적재물 (소성실 구간에만 둔다 — 연소부·연도에는 토기를 재지 않는다)
        vol = geo.get("zone_vol", {})
        self.ware = []
        for nm, zs in build_nodes(geo):
            V = sum(vol.get(z, 0.0) for z in zs if z.startswith("ware"))
            self.ware.append(Ware(V, T_amb))
        # 적재는 시선을 막는다. 자유 단면(1−LOAD_FRAC)만 축방향 복사를 통과시킨다.
        blk = LOAD_FRAC if BLOCK_FRAC is None else BLOCK_FRAC
        self.C_ax = F_RAD_AX * SIGMA * geo["A_cross"] * (1.0 - blk)
        # 축방향 복사는 **이웃끼리만** 주고받게 두면 안 된다. 노드를 잘게
        # 쪼갤수록 끝에서 끝까지의 전달이 1/N 로 약해져, 같은 가마인데
        # 분할 수만 바꿔도 온도차가 두 배가 된다(6분할에서 263 ℃ vs 실측 120).
        # 터널 안에서 복사는 먼 구간까지 직접 도달하므로, 1/(1+(d/D)²) 로 감쇠하는
        # 전 구간 교환으로 둔다. 이 꼴은 점에서 원판을 보는 형상계수이고, 동축 원판끼리의
        # 형상계수보다 꼬리가 1.3–1.5 배 무거워 앞뒤차를 줄이는 쪽이다 (점검표 수식 E-06).
        # 최근접 이웃 가중치를 1 로 정규화한다. 그래야 분할하지 않은(2노드)
        # 경우가 기존과 정확히 같아 F_RAD_AX 보정과 실측 대조가 유지되고,
        # 분할했을 때 장거리 항만 더해진다.
        n = len(self.nodes)
        D = math.sqrt(4.0 * geo["A_cross"] / math.pi)      # 수력직경
        dx = geo.get("seg_len") or 1.0
        D = D * RAD_RANGE
        phi1 = 1.0 / (1.0 + (dx / D) ** 2)
        self.rad_w = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.rad_w[i][j] = (1.0 / (1.0 + (abs(i - j) * dx / D) ** 2)) / phi1
        # 구간별 대표 단면적 = 구간 용적 / 구간 축길이
        vol = geo.get("zone_vol", {})
        seg = geo.get("seg_len") or 1.0
        axlen = {"stoke": APRON_L, "comb": COMB_L,
                 "flue": FLUE_L}
        A_sec = {}
        for z in self.stacks:
            A_sec[z] = vol.get(z, 0.0) / (seg if z.startswith("ware") else
                                          axlen.get(z, 1.0))
        # G ∝ 1/A → h ∝ G^0.8 ∝ A^-0.8. 습윤면적 가중 평균을 1 로 맞춘다.
        raw = dict((z, (A_sec[z] ** -H_EXP if A_sec[z] > 0 else 1.0))
                   for z in self.stacks)
        wsum = sum(self.stacks[z].A for z in self.stacks)
        avg = sum(raw[z] * self.stacks[z].A for z in self.stacks) / wsum
        self.gfac = dict((z, raw[z] / avg) for z in self.stacks)
        for z, st in self.stacks.items():
            st.gf = self.gfac[z]
        # 적재물은 자기 구간의 국소 유속을 받는다 (소성실 구간 배수, 없으면 1).
        self.ware_gf = []
        for nm, zs in build_nodes(geo):
            wz = [z for z in zs if z.startswith("ware") and z in self.gfac]
            self.ware_gf.append(self.gfac[wz[0]] if wz else 1.0)
        self.T = [T_amb for _ in self.nodes]
        self.mdot = 0.0
        self.t = 0.0

    # -- 대류계수: CFD 기준점에서 Re^0.8 로 외삽 -------------
    def h_conv(self, mdot):
        """강제대류 계수의 가마 평균값 h_ref (ṁ/ṁ_ref)^0.8 — 하한을 걸지 않은 값.

        면마다 쓰는 값은 h_surf 다. 하한은 구간 배수를 곱한 **뒤에** 건다.
        투고본은 하한을 먼저 걸고 배수를 곱해, 소성실 구간(배수 0.67–0.76)의
        계수가 하한보다 낮은 2.0–2.3 W/m2K 가 되었다 (오류목록 N-67).
        """
        if mdot <= 1e-6:
            return 0.0
        return self.h_ref * (mdot / self.mdot_ref) ** H_EXP

    @staticmethod
    def h_surf(hc, gf):
        """구간 면의 대류계수 — **국소 질량유속** G = ṁ/A_단면 으로 스케일한 뒤 자연대류 하한.

        유량 ṁ 만 쓰면 단면이 좁아져 유속이 빨라지는 효과를 못 본다.
        구간 배수 gf 는 기준 조건에서 습윤면적 가중 평균이 1 이 되도록
        정규화되어 있으므로 CFD 보정(h_ref)은 그대로 유지된다.
        """
        return max(H_NAT, hc * gf)

    def _h_of(self, st, Tg, hc):
        """대류 + 복사. 표면온도가 복사에 되먹임되므로 짧게 반복한다."""
        Ts = st.T[0]
        h = hc
        for _ in range(3):
            hr = self.eps * SIGMA * (Tg * Tg + Ts * Ts) * (Tg + Ts)
            h = hc + hr
            Ts = st.surface_T(Tg, h)
        return h

    def _node_resid(self, T, stacks, Q, Tin, mdot, hc, Tnb, ware=None, wgf=1.0):
        """노드 잔차: 유입 엔탈피 + 발열 − 유출 엔탈피 − 벽 흡수 ∓ 축방향 복사

        축방향 복사항이 없으면 1,200 ℃ 에서 연소실–연도 온도차가 실측
        (최대 300 ℃)의 1.4 배로 벌어진다. 그 온도대에서는 두 공간 사이의
        복사 교환이 대류·이류보다 크다.
        """
        loss = sum(st.q_in(T, self._h_of(st, T, self.h_surf(hc, st.gf))) * st.A
                   for st in stacks)
        # 축방향 복사 순손실. Tnb = (Σ_j w_ij, Σ_j w_ij T_j⁴) 로 미리 접어
        # 두므로 이분법 안에서는 O(1) 이다. 더 뜨거운 이웃이 많으면 음수(=흡수).
        wsum, wT4 = Tnb
        qx = self.C_ax * (wsum * T ** 4 - wT4)
        qw = 0.0
        if ware is not None and ware.A > 0.0:
            hw = self.h_surf(hc, wgf) + self.eps * SIGMA * (T * T + ware.T * ware.T) * (T + ware.T)
            # Ware.step 의 후진오일러와 같은 열류 (적재물 온도가 이번 스텝에 오른 뒤의 값)
            c = ware.m_cp / self._dt
            qw = hw * ware.A * c / (c + hw * ware.A) * (T - ware.T)
        return Q + mdot * CP_AIR * (Tin - T) - loss - qx - qw

    def _solve_node(self, stacks, Q, Tin, mdot, hc, Tnb, ware=None, wgf=1.0):
        args = (stacks, Q, Tin, mdot, hc, Tnb, ware, wgf)
        lo, hi = self.T_amb, 2600.0
        if self._node_resid(lo, *args) <= 0:
            return lo
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            if self._node_resid(mid, *args) > 0:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _solve_field(self, Q, phi, dt):
        """유량·노드온도·축복사를 함께 푼다 (외부 반복 5회면 수렴)."""
        self._dt = dt
        for st in self.stacks.values():
            st.prepare(dt)
        T = list(self.T)
        mdot = self.mdot
        hc = self.h_conv(mdot)
        n = len(self.nodes)
        for _ in range(5):
            Tin = self.T_amb
            for i, (_, stacks) in enumerate(self.nodes):
                q = Q if i == 0 else 0.0
                w = self.rad_w[i]
                nb = (sum(w), sum(w[j] * T[j] ** 4 for j in range(n)))
                T[i] = self._solve_node(stacks, q, Tin, mdot, hc, nb,
                                        self.ware[i], self.ware_gf[i])
                Tin = T[i]
            Tmean = sum(T) / len(T)
            mdot = draft(Tmean, phi, self.H, self.A_in, self.A_hot, self.T_amb)
            hc = self.h_conv(mdot)
        return T, mdot, hc

    def step(self, dt, Q, phi):
        T, mdot, hc = self._solve_field(Q, phi, dt)
        q_wall = 0.0
        q_ware = 0.0
        for i, (_, stacks) in enumerate(self.nodes):
            for st in stacks:
                q_wall += st.step(dt, T[i], self._h_of(st, T[i], self.h_surf(hc, st.gf)))
            w = self.ware[i]
            if w.A > 0.0:
                hw = (self.h_surf(hc, self.ware_gf[i])
                      + self.eps * SIGMA * (T[i] ** 2 + w.T ** 2) * (T[i] + w.T))
                q_ware += w.step(dt, T[i], hw)
        self.T, self.mdot = T, mdot
        self.t += dt
        q_exh = mdot * CP_AIR * (T[-1] - self.T_amb)
        return dict(t=self.t, T_comb=T[0], T_flue=T[-1], dT=T[0] - T[-1],
                    mdot=mdot, Q=Q, phi=phi, q_wall=q_wall, q_exh=q_exh,
                    q_ware=q_ware, h_conv=hc,
                    T_ware=[w.T for w in self.ware])

    # -- 상태 저장/복원 (역문제에서 구간별로 되감기) ---------
    def save(self):
        return ([list(st.T) for st in self.stacks.values()],
                list(self.T), self.mdot, self.t, [w.T for w in self.ware])

    def restore(self, s):
        for st, T in zip(self.stacks.values(), s[0]):
            st.T = list(T)
        self.T, self.mdot, self.t = list(s[1]), s[2], s[3]
        if len(s) > 4:
            for w, Tw in zip(self.ware, s[4]):
                w.T = Tw

    def stored(self):
        return (sum(st.stored(self.T_amb) for st in self.stacks.values())
                + sum(w.stored(self.T_amb) for w in self.ware))


# ── 연료 스케줄 (홍진근 2011 실측) ───────────────────────
LHV_EFF = 14.7e6          # 함수율 20 % 소나무 유효 저위발열량 [J/kg]
FUEL_TOTAL = 3600.0       # 실측 총 땔감 [kg]


def load_schedule(path, total_kg=FUEL_TOTAL):
    """계단형 스케줄. 각 행의 발열률은 그 시각부터 다음 시각까지 유지된다.

    fuel_schedule.csv 를 선형보간 테이블로 읽으면 52 h 이후 발열률이
    0 으로 흘러내린다. 실측은 53–78 h 를 100–150 kg/h 로 유지했으므로
    계단형이 맞다. 마지막 구간의 투입률은 총량이 실측 3,600 kg 이 되도록
    맞춘다 (보고서 각주 4 가 이 구간을 100–150 kg/h 범위로만 준다). 같은 보고서
    <표 4> 에는 54–77 h 의 구간별 땔감량도 있으나(N-60), 이 일정은 각주 4 를 쓴다
    (사용자 결정 2026-10-20 — <표 4> 는 검증 자료로 둔다).
    """
    pts = []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("t_s"):
                continue
            p = line.split(",")
            if len(p) >= 4:
                pts.append([float(p[0]), float(p[3])])
    # 마지막 활성 구간(발열률 0 직전)을 총량에 맞춰 재조정
    last = max(i for i in range(len(pts)) if pts[i][1] > 0)
    fixed = sum(pts[i][1] * (pts[i + 1][0] - pts[i][0]) for i in range(last))
    span = pts[last + 1][0] - pts[last][0]
    pts[last][1] = (total_kg * LHV_EFF - fixed) / span
    return [tuple(p) for p in pts]


def Q_at(pts, t):
    q = pts[0][1]
    for tk, qk in pts:
        if t >= tk:
            q = qk
        else:
            break
    return q
