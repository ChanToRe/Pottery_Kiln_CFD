#!/bin/bash
# 이 저장소만으로 논문(수정본)의 계산 전체를 처음부터 다시 한다.
#
#   bash run_all.sh               전부 (20 코어 기준 약 13 시간 — 수치 점검이 절반 이상)
#   bash run_all.sh <단계> …      골라서
#
# 단계 (이 순서로 의존한다)
#   geometry      STL 풀기·생성기로 다시 만들어 대조   mesh/make_stl.sh             ~10초
#   mesh          CFD 격자 (3 형식)                    mesh/make_mesh.sh            ~30초
#   steady        정상상태 보정 CFD                    cfd/run_steady.sh            ~30분 (3개 동시)
#   transient     비정상 냉시동 CFD                    cfd/run_transient.sh         ~30분 (3개 동시)
#   transient-np  같은 계산의 병렬 분할 4·8·10 판       cfd/run_transient_np.sh      ~100분
#   cfd-post      1,000 ℃ 면 침투·45 s 까지 최대 거리   cfd/post/*.py                ~1분
#   rom           축소모델 전 분석·민감도·에너지 수지   rom/run_rom.sh               ~90분
#   checks        수치 점검 (격자, 시간 간격, 조업점,    cfd/checks/*                 ~8시간
#                 온도 리미터 바꿔 풀기, 수렴·보존 정리)
#   figures       그림 낱장·그래프                     Rscripts/make_figures.sh     ~30분
#   supporting    S1–S8 Table, S1 Fig                  Rscripts/make_supporting.py, S1_Fig.R
#   logs          계산 로그를 Results/logs 에 보관      cfd/archive_logs.sh
#   verify        원고(수정본) 수치와 대조              verify.py
#   clean         만들어진 산출물을 지운다 (기본 단계에는 없다)
#
# CFD 를 다시 풀지 않고 축소모델 이후만 확인하려면: bash run_all.sh geometry rom figures verify
# (보정은 Results/logs 에 보관한 정상상태 로그를 읽는다.)
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/paths.sh"
cd "$HERE"
set -o pipefail
STEPS=${*:-"geometry mesh steady transient transient-np cfd-post rom checks figures supporting logs verify"}

step() {
  local name=$1; shift
  echo "################ $name  ($(date '+%H:%M:%S'))"
  mkdir -p Results/run
  if "$@" 2>&1 | tee "Results/run/$name.log"; then
    echo "  → $name 끝"
  else
    echo "  ★ $name 실패 — Results/run/$name.log"; exit 1
  fi
}

checks() {
  bash cfd/checks/run_checks.sh "${KILN_BUDGET:-16}" || return 1
  bash cfd/checks/limiter_swap.sh || return 1
  python3 cfd/checks/summarize_checks.py || return 1
  python3 cfd/checks/convergence_summary.py || return 1
}

supporting() {
  "$KILN_DOC_PY" Rscripts/make_supporting.py || return 1
  FONTCONFIG_FILE=$KILN_ROOT/Results/figures/graphs/fonts.conf "$KILN_RSCRIPT" Rscripts/S1_Fig.R
}

for s in $STEPS; do
  case $s in
    geometry)  step geometry  bash mesh/make_stl.sh ;;
    mesh)      step mesh      bash mesh/make_mesh.sh ;;
    steady)    step steady    bash cfd/run_steady.sh ;;
    transient) step transient bash cfd/run_transient.sh ;;
    transient-np) step transient-np bash cfd/run_transient_np.sh ;;
    cfd-post)  step cfd-post  bash -c '"$KILN_PVBATCH" cfd/post/flame_penetration.py && python3 cfd/post/penetration_max.py' ;;
    rom)       step rom       bash rom/run_rom.sh ;;
    checks)    step checks    checks ;;
    figures)   step figures   bash Rscripts/make_figures.sh ;;
    supporting) step supporting supporting ;;
    logs)      step logs      bash cfd/archive_logs.sh ;;
    verify)    step verify    python3 verify.py ;;
    clean)
      echo "################ clean"
      # 저장소에 올리는 산출물(Results/ 의 그림·표·요약, Results/logs)은 git 으로 되돌릴 수 있다.
      rm -rf Results/cfd/np Results/checks/{grid,courant,oppoint,limiter_swap} Results/geometry Results/run mesh/stl
      find . -path ./env -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +
      for C in mesh/?_L065 ; do rm -rf "$C"/constant "$C"/log.*; done
      for C in cases/* ; do
        ( cd "$C" && for d in $(ls | grep -E '^[0-9]+(\.[0-9]+)?(e[-+]?[0-9]+)?$'); do [ "$d" = 0 ] || rm -rf "$d"; done
          rm -rf constant/polyMesh constant/triSurface processor* postProcessing log.* *.foam )
      done
      echo "  → 계산 산출물 삭제 끝" ;;
    *) echo "모르는 단계: $s"; exit 1 ;;
  esac
done
