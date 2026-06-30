# Motor Milhas (Smiles) — local, via Chrome real

Diferente do motor-dinheiro (que usa a `fli` e roda na nuvem/Actions), milhas **não
dá pra rodar no GitHub Actions**. Investigação confirmou o porquê:

- **Akamai Bot Manager** (sensor data, `_abck`/`bm_sz`) + site é **SPA React**.
- Headless + IP de datacenter do Actions = **bloqueado**.
- Preço/disponibilidade em milhas vem de **API XHR** (`/v1/search`), não do HTML.

## Como funciona (a saída certa)
O scraper conecta no **seu Chrome real** via **CDP** — assim herda a sessão logada,
os cookies Akamai válidos e o IP residencial — e **intercepta a resposta da API**
`/v1/search` em vez de raspar o DOM (frágil). A `x-api-key` e os cookies vão no
request automaticamente; **nada hardcoded**.

## Pré-requisitos (seus — uma vez)
1. **Chrome com debug ligado:**
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   ```
   (ou ative em `chrome://inspect`). Confirme: `curl localhost:9222/json/version`.
2. **Logado no Smiles** nesse Chrome (só você tem a credencial).

## Rodar
```bash
pip install -r miles/requirements.txt
python -m playwright install chromium
python miles/smiles_scraper.py
```
Gera `miles/miles_results.json` com o mais barato em milhas por rota.

## Status: aguardando 1ª validação
O fluxo (CDP + captura da API) está pronto. Falta **uma rodada com sua sessão
logada** pra confirmar o formato real da resposta: o scraper salva a 1ª resposta
crua em `_raw_sample` dentro do JSON; com ela ajusto `extract_offers()` aos nomes
de campo reais (miles, taxas, data). Só depois disso agendamos (launchd) — não
agendo o que ainda não validei rodando.

## Verdades importantes
- **Frágil por natureza:** quando o Smiles muda a API, o parser pode precisar de ajuste.
- **ToS:** raspar pode violar os Termos do Smiles. Use por sua conta, baixa frequência.
- **Depende da máquina ligada** + Chrome aberto/logado (é o custo de furar o Akamai).

## Milhas vs dinheiro
Compare `milhas × custo_do_milheiro + taxas` com o preço em dinheiro do monitor.
Piso de referência: **US$ 281 (BSB→NY) ≈ R$ 1.560**.
