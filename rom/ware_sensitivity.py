#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import efficiency
import rom
import run

BASE = rom.WARE_RHO * rom.WARE_CP

CASES = [
    ("기준            rho 1900 x cp 850", 1900.0, 850.0),
    ("범위 하한       rho 1490 x cp 701", 1490.0, 701.0),
    ("범위 상한       rho 2400 x cp 999", 2400.0, 999.0),
]


def fuel_of(model, fit, sched, ts, Ts):
    return efficiency.total(model, fit, sched, ts, Ts)


def main():
    sched = rom.load_schedule(run.SCHED)
    fit = run.load_fit()
    ts, Ts = run.load_curve()

    print("%-34s %9s %9s %9s %9s" % ("변형", "A[kg]", "B[kg]", "C[kg]", "형식차폭"))
    base_fuel = None
    for name, rho, cp in CASES:
        rom.WARE_RHO, rom.WARE_CP = rho, cp
        F = {}
        for t in "ABC":
            F[t] = fuel_of("%s_L065" % t, fit, sched, ts, Ts)
        lo, hi = min(F.values()), max(F.values())
        spread = (hi - lo) / lo * 100.0
        if base_fuel is None:
            base_fuel = F["B"]
            dev = 0.0
        else:
            dev = (F["B"] - base_fuel) / base_fuel * 100.0
        print("%-34s %9.0f %9.0f %9.0f %8.2f%%   (B 기준 대비 %+.2f%%)"
              % (name, F["A"], F["B"], F["C"], spread, dev))

    rom.WARE_RHO, rom.WARE_CP = 1900.0, 850.0


if __name__ == "__main__":
    main()
