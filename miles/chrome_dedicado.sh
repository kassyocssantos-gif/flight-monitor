#!/usr/bin/env bash
# Sobe um Chrome DEDICADO (perfil isolado) com debug, só pro radar de milhas.
# Nao mexe no seu Chrome principal. Suba 1x, logue no Smiles nesse Chrome, e
# deixe rodando. O busca_milhas.py / radar conecta nele via CDP (porta 9222).
#
# Uso:  bash miles/chrome_dedicado.sh
# Depois: logue no Smiles na janela que abrir. Confirme: curl localhost:9222/json/version

set -e
PORT=9222
# porta livre intercalada (nunca mata a ocupada)
while lsof -ti:$PORT >/dev/null 2>&1; do PORT=$((PORT+1)); done

PROFILE="$HOME/.chrome-smiles-radar"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

echo "Subindo Chrome dedicado na porta $PORT (perfil $PROFILE)..."
"$CHROME" \
  --remote-debugging-port=$PORT \
  --remote-allow-origins=* \
  --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check \
  "https://www.smiles.com.br/home" >/dev/null 2>&1 &

echo "Chrome dedicado subindo. PORTA CDP = $PORT"
echo "1) Logue no Smiles na janela que abriu (fica salvo nesse perfil)."
echo "2) Rode o radar apontando pra esta porta:"
echo "     CHROME_CDP=http://localhost:$PORT SMILES_MEMBER=<seu> python busca_milhas.py CWB MIA 2026-07-15"
