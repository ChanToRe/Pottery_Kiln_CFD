#!/usr/bin/env python3
"""
케이스 여러 개를 cfd/run_case.sh 로 푸는 간단한 대기열. 동시에 쓰는 MPI 프로세스 합이 budget 을
넘지 않게 앞에서부터 띄운다 (물리 코어 10 · 스레드 20 · 메모리 7 GB 기계 기준 기본 16).

    python3 cfd/checks/case_queue.py <budget> <케이스>...      분할 수는 각 케이스 decomposeParDict 에서
진행 기록: Results/checks/queue.log
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LOG = os.path.join(ROOT, "Results", "checks", "queue.log")


def nproc(case):
    txt = open(os.path.join(case, "system", "decomposeParDict")).read()
    return int(re.search(r"numberOfSubdomains\s+(\d+)", txt).group(1))


def log(msg):
    line = "%s  %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main():
    budget = int(sys.argv[1])
    todo = [(os.path.abspath(c), nproc(c)) for c in sys.argv[2:]]
    running = {}
    fails = 0
    log("대기열 시작: %d 건, 예산 %d" % (len(todo), budget))
    while todo or running:
        used = sum(n for _, n in running.values())
        for item in list(todo):
            case, n = item
            if used + n <= budget:
                p = subprocess.Popen(["bash", os.path.join(ROOT, "cfd", "run_case.sh"), case],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                running[p] = (case, n)
                todo.remove(item)
                used += n
                log("시작 ×%d %s" % (n, os.path.relpath(case, ROOT)))
        time.sleep(20)
        for p in list(running):
            if p.poll() is not None:
                case, n = running.pop(p)
                out = p.stdout.read().strip().splitlines()
                fails += p.returncode != 0
                log("%s rc=%d %s" % ("끝" if p.returncode == 0 else "★실패", p.returncode,
                                     out[-1] if out else os.path.relpath(case, ROOT)))
    log("대기열 끝 (실패 %d)" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
