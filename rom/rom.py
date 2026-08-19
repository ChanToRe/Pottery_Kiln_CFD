#!/usr/bin/env python3
import os
import math

G = 9.81
R_AIR = 287.0
CP_AIR = 1050.0
SIGMA = 5.670374e-8
P_ATM = 101325.0

WALL = dict(th=0.35, k=1.0, rho=1800.0, cp=900.0, n=22, dx0=0.0015)
SOIL = dict(th=0.85, k=1.4, rho=1900.0, cp=880.0, n=20, dx0=0.010)
T_FAR = 288.15
APRON_L, COMB_L = 1.30, 1.60
FLUE_L = 1.60 / math.sin(math.radians(68.0))


def graded(th, n, dx0):
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

CFD = dict(
    T_amb=278.15,
    T_bulk=444.15,
    Q=150.0e3,
    mdot={"A": 0.884, "B": 0.886},
    wall_loss={"A": 15.3e3, "B": 17.7e3},
    A_wall={"A": 48.67, "B": 50.36},
    R_ext=0.3,
)
C_IN = 0.80
EPS_RAD = 0.80
H_NAT = 3.0
F_RAD_AX = 0.70

LOAD_FRAC = float(os.environ.get("LOAD_FRAC", "0.5"))
BLOCK_FRAC = float(os.environ.get("BLOCK_FRAC", "0.10"))
WARE_EPS = 0.60
WARE_DP = 0.20
WARE_RHO = 1900.0
WARE_CP = 850.0
WARE_HOLLOW = 0.30
RAD_RANGE = 1.0


class Stack:

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
        self.Uf = [1.0 / (dx[i] / (2 * k[i]) + dx[i + 1] / (2 * k[i + 1]))
                   for i in range(self.n - 1)]
        self.U_out = 1.0 / (dx[-1] / (2 * k[-1]))
        self._half_in = dx[0] / (2 * k[0])

    def U_in(self, h):
        return 1.0 / (1.0 / h + self._half_in)

    def surface_T(self, Tg, h):
        q = self.U_in(h) * (Tg - self.T[0])
        return Tg - q / h

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
        for i in range(1, n):
            w = a[i] / b[i - 1]
            b[i] -= w * c[i - 1]
            d[i] -= w * d[i - 1]
        x = [0.0] * n
        x[n - 1] = d[n - 1] / b[n - 1]
        for i in range(n - 2, -1, -1):
            x[i] = (d[i] - c[i] * x[i + 1]) / b[i]
        self.T = x
        return Uin * (Tg - x[0]) * self.A

    def stored(self, Tref):
        return sum(self.rc[i] * self.dx[i] * (self.T[i] - Tref)
                   for i in range(self.n)) * self.A


def calibrate_A_hot(H_stack, A_in, mdot, T_amb, T_bulk):
    rho_a = P_ATM / (R_AIR * T_amb)
    rho_g = P_ATM / (R_AIR * T_bulk)
    dp = G * H_stack * (rho_a - rho_g)
    tot = 2.0 * dp / mdot ** 2
    inlet = 1.0 / (C_IN ** 2 * rho_a * A_in ** 2)
    hot = tot - inlet
    if hot <= 0:
        raise ValueError("보정 실패: 화구 저항만으로 CFD 유량을 넘어선다")
    return 1.0 / math.sqrt(hot * rho_g)


def draft(Tg, phi, H_stack, A_in, A_hot, T_amb):
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


def build_nodes(geo):
    wk = geo.get("ware_keys", ["ware"])
    if len(wk) == 1:
        return [("comb", ("stoke", "comb")), ("ware", ("ware", "flue"))]
    return ([("comb", ("stoke", "comb"))]
            + [(k, (k,)) for k in wk]
            + [("flue", ("flue",))])


class Ware:

    def __init__(self, V_gas, T0):
        V_load = LOAD_FRAC * V_gas
        solid = (1.0 - WARE_EPS) * WARE_HOLLOW * V_load
        self.m_cp = WARE_RHO * WARE_CP * solid
        self.A = 6.0 * (1.0 - WARE_EPS) / WARE_DP * V_load
        self.T = T0

    def step(self, dt, Tg, h):
        if self.m_cp <= 0.0:
            return 0.0
        c = self.m_cp / dt
        self.T = (c * self.T + h * self.A * Tg) / (c + h * self.A)
        return h * self.A * (Tg - self.T)

    def stored(self, Tref):
        return self.m_cp * (self.T - Tref)


class Kiln:
    def __init__(self, geo, T_amb=292.45, eps_rad=EPS_RAD, A_hot=None,
                 h_conv_ref=None, mdot_ref=0.884):
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
        vol = geo.get("zone_vol", {})
        self.ware = []
        for nm, zs in build_nodes(geo):
            V = sum(vol.get(z, 0.0) for z in zs if z.startswith("ware"))
            self.ware.append(Ware(V, T_amb))
        blk = LOAD_FRAC if BLOCK_FRAC is None else BLOCK_FRAC
        self.C_ax = F_RAD_AX * SIGMA * geo["A_cross"] * (1.0 - blk)
        n = len(self.nodes)
        D = math.sqrt(4.0 * geo["A_cross"] / math.pi)
        dx = geo.get("seg_len") or 1.0
        D = D * RAD_RANGE
        phi1 = 1.0 / (1.0 + (dx / D) ** 2)
        self.rad_w = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    self.rad_w[i][j] = (1.0 / (1.0 + (abs(i - j) * dx / D) ** 2)) / phi1
        vol = geo.get("zone_vol", {})
        seg = geo.get("seg_len") or 1.0
        axlen = {"stoke": APRON_L, "comb": COMB_L,
                 "flue": FLUE_L}
        A_sec = {}
        for z in self.stacks:
            A_sec[z] = vol.get(z, 0.0) / (seg if z.startswith("ware") else
                                          axlen.get(z, 1.0))
        raw = dict((z, (A_sec[z] ** -0.8 if A_sec[z] > 0 else 1.0))
                   for z in self.stacks)
        wsum = sum(self.stacks[z].A for z in self.stacks)
        avg = sum(raw[z] * self.stacks[z].A for z in self.stacks) / wsum
        self.gfac = dict((z, raw[z] / avg) for z in self.stacks)
        for z, st in self.stacks.items():
            st.gf = self.gfac[z]
        self.T = [T_amb for _ in self.nodes]
        self.mdot = 0.0
        self.t = 0.0

    def h_conv(self, mdot):
        if mdot <= 1e-6:
            return H_NAT
        return max(H_NAT, self.h_ref * (mdot / self.mdot_ref) ** 0.8)

    def h_zone(self, z, mdot):
        h0 = self.h_conv(mdot)
        f = self.gfac.get(z, 1.0)
        return max(H_NAT, h0 * f)

    def _h_of(self, st, Tg, hc):
        Ts = st.T[0]
        h = hc
        for _ in range(3):
            hr = self.eps * SIGMA * (Tg * Tg + Ts * Ts) * (Tg + Ts)
            h = hc + hr
            Ts = st.surface_T(Tg, h)
        return h

    def _node_resid(self, T, stacks, Q, Tin, mdot, hc, Tnb, ware=None):
        loss = sum(st.U_in(self._h_of(st, T, hc * st.gf)) * (T - st.T[0]) * st.A
                   for st in stacks)
        wsum, wT4 = Tnb
        qx = self.C_ax * (wsum * T ** 4 - wT4)
        qw = 0.0
        if ware is not None and ware.A > 0.0:
            hw = hc + self.eps * SIGMA * (T * T + ware.T * ware.T) * (T + ware.T)
            qw = hw * ware.A * (T - ware.T)
        return Q + mdot * CP_AIR * (Tin - T) - loss - qx - qw

    def _solve_node(self, stacks, Q, Tin, mdot, hc, Tnb, ware=None):
        args = (stacks, Q, Tin, mdot, hc, Tnb, ware)
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

    def _solve_field(self, Q, phi):
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
                                        self.ware[i])
                Tin = T[i]
            Tmean = sum(T) / len(T)
            mdot = draft(Tmean, phi, self.H, self.A_in, self.A_hot, self.T_amb)
            hc = self.h_conv(mdot)
        return T, mdot, hc

    def step(self, dt, Q, phi):
        T, mdot, hc = self._solve_field(Q, phi)
        q_wall = 0.0
        q_ware = 0.0
        for i, (_, stacks) in enumerate(self.nodes):
            for st in stacks:
                q_wall += st.step(dt, T[i], self._h_of(st, T[i], hc * st.gf))
            w = self.ware[i]
            if w.A > 0.0:
                hw = hc + self.eps * SIGMA * (T[i] ** 2 + w.T ** 2) * (T[i] + w.T)
                q_ware += w.step(dt, T[i], hw)
        self.T, self.mdot = T, mdot
        self.t += dt
        q_exh = mdot * CP_AIR * (T[-1] - self.T_amb)
        return dict(t=self.t, T_comb=T[0], T_flue=T[-1], dT=T[0] - T[-1],
                    mdot=mdot, Q=Q, phi=phi, q_wall=q_wall, q_exh=q_exh,
                    q_ware=q_ware, h_conv=hc,
                    T_ware=[w.T for w in self.ware])

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

    def wall_profile(self, zone="comb"):
        st = self.stacks[zone]
        depth, acc = [], 0.0
        for i in range(st.n):
            acc += st.dx[i] / 2 if i == 0 else (st.dx[i - 1] + st.dx[i]) / 2
            depth.append(acc)
        return depth, list(st.T)


LHV_EFF = 14.7e6
FUEL_TOTAL = 3600.0


def load_schedule(path, total_kg=FUEL_TOTAL):
    pts = []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("t_s"):
                continue
            p = line.split(",")
            if len(p) >= 4:
                pts.append([float(p[0]), float(p[3])])
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
