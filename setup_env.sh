#!/bin/bash
# Python·R 환경을 env/ 아래에 만든다 (micromamba, conda-forge). OpenFOAM·ParaView 는 따로 설치한다 (README).
#   env/kiln  python 3.11 + numpy                     → mesh/generate_rev4.py
#             R 4.3.3 + ggplot2 patchwork here png jpeg → Rscripts/*.R          (약 1.5 GB)
#   env/doc   python 3.11 + openpyxl 3.1.5            → Rscripts/make_supporting.py (S1–S8 Table)
#
#   bash setup_env.sh            env/kiln 은 잠금 파일(kiln-explicit.txt)대로 — 하위 의존성까지 같은 판
#   bash setup_env.sh --solve    주요 패키지 판만 고정하고 나머지는 conda 가 고른다
#
# R 그래프가 바이트 단위로 같으려면 cairo·freetype·fontconfig·libtiff·pango 까지 같은 판이어야 하므로
# 잠금 파일을 기본으로 쓴다 (linux-64). 축소모델·CFD 후처리는 시스템 python3 (표준 라이브러리만)으로 돈다.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
MM="${MICROMAMBA:-$(command -v micromamba || echo "$HOME/.local/bin/micromamba")}"
mkdir -p "$HERE/env"
if [ "$1" != "--solve" ] && [ -f "$HERE/kiln-explicit.txt" ]; then
  "$MM" create -y -p "$HERE/env/kiln" -f "$HERE/kiln-explicit.txt"
else
  "$MM" create -y -p "$HERE/env/kiln" -c conda-forge \
      python=3.11 numpy=2.4.6 \
      r-base=4.3.3 r-ggplot2=3.5.2 r-here=1.0.1 r-patchwork=1.3.2 r-png=0.1_8 r-jpeg=0.1_11
fi
"$MM" create -y -p "$HERE/env/doc" -c conda-forge python=3.11 openpyxl=3.1.5
"$HERE/env/kiln/bin/python" -c "import numpy; print('numpy', numpy.__version__)"
"$HERE/env/kiln/bin/Rscript" -e 'cat("ggplot2", as.character(packageVersion("ggplot2")), "\n")'
"$HERE/env/doc/bin/python" -c "import openpyxl; print('openpyxl', openpyxl.__version__)"
