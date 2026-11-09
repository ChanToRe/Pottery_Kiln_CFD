#!/usr/bin/env python3
"""
축소모델 78 h 에너지 수지와 복사 몫 (2-2f E-10, 2-2g E-12). 모델 식은 바꾸지 않는다 —
rom.Kiln.step 과 같은 계산을 하면서 열 흐름을 갈래별로 적는다.

    python3 energy_audit.py            (rom/ 에서)

대상: 형식 B (보정 형식), 소성실 1 m 분할, 역산 φ(t) (Results/rom/rom_phi.csv), 발열 일정 각주 4.
  수지    투입(발열 적분) = 배기 엔탈피 + 벽·바닥·지반 축열 증가 + 지중 경계(15 ℃) 유출
          + 적재물 축열 증가 + 기체 노드 축열(준정상이라 0) — 닫힘 %.
  복사 몫  기체 → 벽 표면 열류를 대류(h_c)·복사(h_r = εσ(T²+Ts²)(T+Ts)) 계수 비로 나눔.
          기체 → 적재물도 같게. 구간 사이 축방향 복사 교환(C_ax 항)은 따로 적분.
  직렬 저항 (E-12) 시각별로 표면 열저항 1/(h_c+h_r)·1/h_c 와 벽 전도 저항 th/k(0.35 m),
          축열 침투 깊이 √(αt) 를 비교.
출력: Results/rom/energy_audit.txt, energy_audit_series.csv
"""
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import calibrate  # noqa: E402
import rom  # noqa: E402
import run  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "Results", "rom")
MODEL = "B_L065"


class AuditKiln(rom.Kiln):
    """step 을 rom.Kiln.step 과 같은 순서·식으로 하되 갈래별 열류를 돌려준다."""

    def step(self, dt, Q, phi):
        T, mdot, hc = self._solve_field(Q, phi, dt)
        a = dict(wall_conv=0.0, wall_rad=0.0, ware_conv=0.0, ware_rad=0.0, axial=0.0,
                 far=0.0, hc_mean=0.0, hr_mean=0.0, A=0.0)
        n = len(self.nodes)
        for i, (_, stacks) in enumerate(self.nodes):
            for st in stacks:
                hcs = self.h_surf(hc, st.gf)
                h = self._h_of(st, T[i], hcs)
                q = st.step(dt, T[i], h)
                a["wall_conv"] += q * hcs / h
                a["wall_rad"] += q * (h - hcs) / h
                a["far"] += st.U_out * (st.T[-1] - rom.T_FAR) * st.A
                a["hc_mean"] += hcs * st.A
                a["hr_mean"] += (h - hcs) * st.A
                a["A"] += st.A
            w = self.ware[i]
            if w.A > 0.0:
                hcw = self.h_surf(hc, self.ware_gf[i])
                hrw = self.eps * rom.SIGMA * (T[i] ** 2 + w.T ** 2) * (T[i] + w.T)
                q = w.step(dt, T[i], hcw + hrw)
                a["ware_conv"] += q * hcw / (hcw + hrw)
                a["ware_rad"] += q * hrw / (hcw + hrw)
            wr = self.rad_w[i]
            net = self.C_ax * (sum(wr) * T[i] ** 4 - sum(wr[j] * T[j] ** 4 for j in range(n)))
            a["axial"] += max(net, 0.0)          # 내보내는 쪽만 더한다 = 구간 사이 복사 교환량
        self.T, self.mdot = T, mdot
        self.t += dt
        a["exh"] = mdot * rom.CP_AIR * (T[-1] - self.T_amb)
        a["hc_mean"] /= a["A"]
        a["hr_mean"] /= a["A"]
        a.update(t=self.t, Q=Q, mdot=mdot, T_front=T[1], T_comb=T[0])
        return a


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    k0, _ = calibrate.build(MODEL, seg_m=run.SEG_M, T_amb=run.T_AMB)
    k = AuditKiln(k0.geo, k0.A_hot, k0.h_ref, k0.mdot_ref, T_amb=run.T_AMB)
    E0_wall = sum(st.stored(k.T_amb) for st in k.stacks.values())
    E0_ware = sum(w.stored(k.T_amb) for w in k.ware)
    tot = dict((x, 0.0) for x in ("Q", "exh", "wall_conv", "wall_rad", "ware_conv", "ware_rad", "axial", "far"))
    series = []
    alpha = rom.WALL["k"] / (rom.WALL["rho"] * rom.WALL["cp"])
    for f in fit:
        nstep = int(round((f["t1"] - f["t0"]) / run.DT))
        for i in range(nstep):
            t = f["t0"] + i * run.DT
            a = k.step(run.DT, rom.Q_at(sched, t), f["phi"])
            for x in tot:
                tot[x] += a[x] * run.DT
            if int(round(k.t)) % 3600 == 0:
                series.append(dict(t_h=k.t / 3600, Q_kW=a["Q"] / 1e3, T_front_C=a["T_front"] - 273.15,
                                   mdot=a["mdot"], hc=a["hc_mean"], hr=a["hr_mean"],
                                   rad_share_wall=a["wall_rad"] / (a["wall_rad"] + a["wall_conv"]) if a["wall_rad"] + a["wall_conv"] else 0,
                                   q_exh_kW=a["exh"] / 1e3, q_wall_kW=(a["wall_conv"] + a["wall_rad"]) / 1e3,
                                   q_ware_kW=(a["ware_conv"] + a["ware_rad"]) / 1e3, q_axial_kW=a["axial"] / 1e3,
                                   R_surf=1 / (a["hc_mean"] + a["hr_mean"]), R_conv_only=1 / a["hc_mean"] if a["hc_mean"] else float("inf"),
                                   R_wall=rom.WALL["th"] / rom.WALL["k"], depth_m=math.sqrt(alpha * k.t)))
    dE_wall = sum(st.stored(k.T_amb) for st in k.stacks.values()) - E0_wall
    dE_ware = sum(w.stored(k.T_amb) for w in k.ware) - E0_ware
    # 지중 경계 유출은 T_FAR(15 ℃) 기준이고 축열은 외기(19.3 ℃) 기준이라, 처음부터 경계로 드는 열이 있다.
    to_wall = tot["wall_conv"] + tot["wall_rad"]
    to_ware = tot["ware_conv"] + tot["ware_rad"]
    G = 1e9
    L = []
    say = L.append
    say("축소모델 78 h 에너지 수지·복사 몫 (형식 %s, 소성실 1 m 분할, 역산 φ, 외기 %.1f ℃)" % (MODEL, run.T_AMB - 273.15))
    say("")
    say("[2-2g] 에너지 수지 [GJ] (0–78 h)")
    say("  투입 발열                      %7.2f" % (tot["Q"] / G))
    say("  배기 엔탈피 (연도 출구)         %7.2f  (%4.1f %%)" % (tot["exh"] / G, 100 * tot["exh"] / tot["Q"]))
    say("  기체 → 벽·바닥 표면            %7.2f  (%4.1f %%)" % (to_wall / G, 100 * to_wall / tot["Q"]))
    say("     그중 벽·지반 축열 증가       %7.2f" % (dE_wall / G))
    say("     그중 지중 경계(15 ℃) 유출   %7.2f" % (tot["far"] / G))
    say("  기체 → 적재물 (= 적재물 축열)  %7.2f  (%4.1f %%)   축열 증가 %.2f" % (to_ware / G, 100 * to_ware / tot["Q"], dE_ware / G))
    close = (tot["exh"] + to_wall + to_ware) / tot["Q"]
    say("  닫힘 (배기 + 벽 + 적재물)/투입  %6.2f %%" % (100 * close))
    say("  벽 쪽 내부 검사 (축열 + 경계 유출)/표면 유입  %6.2f %%" % (100 * (dE_wall + tot["far"]) / to_wall))
    say("")
    say("[2-2f] 복사 몫")
    say("  기체 → 벽 표면 열 중 복사 %.1f %%, 대류 %.1f %%" % (100 * tot["wall_rad"] / to_wall, 100 * tot["wall_conv"] / to_wall))
    say("  기체 → 적재물 열 중 복사 %.1f %%, 대류 %.1f %%" % (100 * tot["ware_rad"] / to_ware, 100 * tot["ware_conv"] / to_ware))
    say("  구간 사이 축방향 복사 교환 %.2f GJ (투입의 %.1f %%)" % (tot["axial"] / G, 100 * tot["axial"] / tot["Q"]))
    say("")
    say("시각별 (면적 가중 평균 계수, 벽 표면)")
    say("  %5s %7s %8s %7s %7s %7s | %8s %8s %8s %8s | %7s %7s %7s %7s" % (
        "t h", "Q kW", "앞 ℃", "h_c", "h_r", "복사%", "R_표면", "R_대류만", "R_벽", "침투 m", "배기kW", "벽kW", "기물kW", "축복사kW"))
    for s in series:
        if s["t_h"] in (12, 26, 40, 45, 50, 52, 54, 60, 66, 72, 78):
            say("  %5.0f %7.1f %8.0f %7.2f %7.1f %7.1f | %8.4f %8.3f %8.3f %8.3f | %7.1f %7.1f %7.1f %7.1f" % (
                s["t_h"], s["Q_kW"], s["T_front_C"], s["hc"], s["hr"], 100 * s["rad_share_wall"],
                s["R_surf"], s["R_conv_only"], s["R_wall"], s["depth_m"], s["q_exh_kW"], s["q_wall_kW"], s["q_ware_kW"], s["q_axial_kW"]))
    say("  R 단위 m2K/W. R_벽 = 벽 두께/열전도율 = 0.35/1.0 (정상 상태일 때의 전도 저항). 침투 = √(α t), α = k/(ρ c) 벽.")
    say("  축열은 저항이 아니다 — 벽이 데워지는 동안 표면으로 든 열은 대부분 벽 안에 쌓이고(위 '축열 증가'),")
    say("  78 h 동안 열이 스며든 깊이는 √(αt) 로 벽 두께와 견줄 수 있다.")
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "energy_audit.txt"), "w").write("\n".join(L) + "\n")
    with open(os.path.join(OUT, "energy_audit_series.csv"), "w", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=list(series[0]))
        w.writeheader()
        w.writerows(series)
    print("\n".join(L))


if __name__ == "__main__":
    main()
