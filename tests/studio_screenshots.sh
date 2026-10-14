#!/usr/bin/env bash
# Sobe o QoE Studio numa porta própria e tira screenshots das áreas, em claro e escuro,
# com o Chrome headless. Falha se o console do navegador mostrar um erro não tratado.
#
#   tests/studio_screenshots.sh [pasta-de-saida]     (padrão: /tmp/qoe-studio-telas)
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
cd "$raiz"   # core/carga.DATA_DIR é relativo: o servidor precisa rodar da raiz
saida="${1:-/tmp/qoe-studio-telas}"
porta=8199
mkdir -p "$saida"

"$raiz/venv/bin/python" "$raiz/src/ml/studio.py" --port "$porta" >"$saida/servidor.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do
  curl -sf -o /dev/null "http://127.0.0.1:$porta/api/payload" && break
  sleep 1
done

erros=0
# nome|hash|espera em ms (o Modelo avalia o rascunho no servidor, que leva até ~40 s)
for tela in "dados|dados|8000" "conjunto|datasets|8000" "modelo|modelo|60000" "laboratorio|laboratorio|20000"; do
  IFS='|' read -r nome hash espera <<<"$tela"
  for tema in light dark; do
    arquivo="$saida/$nome-$tema.png"
    google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=1366,1500 \
      --enable-logging=stderr --v=0 --virtual-time-budget="$espera" \
      --screenshot="$arquivo" "http://127.0.0.1:$porta/?theme=$tema#$hash" 2>"$saida/$nome-$tema.log" || true
    if grep -E "Uncaught|RangeError|TypeError" "$saida/$nome-$tema.log"; then
      echo "ERRO no console: $nome ($tema)"
      erros=1
    fi
    echo "$arquivo"
  done
done
exit "$erros"
