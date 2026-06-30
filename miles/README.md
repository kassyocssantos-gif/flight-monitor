# Motor Milhas (Smiles) — local, via API real na sessão

Diferente do motor-dinheiro (`fli`, roda na nuvem/Actions), milhas exige a **sessão
logada do Smiles** (Akamai Bot Manager bloqueia chamada externa). Roda local, no
Chrome real do Kassyo.

## O que foi descoberto (2026-06-30, validado)
Investigando o **tripmilhas.com** (curadoria de promoções, site Wix) achei o
deep-link correto do Smiles e, com ele, a **API real de disponibilidade em milhas**:

```
GET https://api-air-flightsearch-blue.smiles.com.br/v1/airlines/search
    ?cabin=ECONOMIC&originAirportCode=BSB&destinationAirportCode=JFK
    &departureDate=2026-07-15&memberNumber=<seu>&adults=1&children=0&infants=0
    &forceCongener=false
```

- `departureDate` = `YYYY-MM-DD`. `memberNumber` opcional (com ele vem o preço **Clube**).
- Resposta: `requestedFlightSegmentList[].flightList[].fareList[]` →
  `{miles, baseMiles, g3.costTax (taxa R$), money, type (SMILES|SMILES_CLUB), legListCost}`.
- **Só passa de DENTRO da sessão logada** (cookies Akamai `_abck`/`bm_sz` + login) —
  por isso o fetch roda no Chrome real (`credentials:include`), não via curl externo.

**Validado BSB→JFK 15/07:** 263.500 milhas + R$ 311,73 (Clube) ≈ **R$ 5.000** vs
**R$ 1.546 em dinheiro** (US$ 281). Pra essa rota, dinheiro ganha de longe.

## Por que não roda no GitHub Actions
Headless + IP de datacenter = Akamai bloqueia. Precisa de Chrome real logado +
IP residencial. É o custo de furar o Akamai.

## Execução (a decidir)
O `smiles_scraper.py` conecta no Chrome via **CDP** (`connect_over_cdp`) e roda o
fetch da API de dentro da aba logada. Requer Chrome com debug:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

E estar logado no Smiles. No setup atual o Chrome do Kassyo não expõe porta TCP
(flowa-control conecta por canal próprio), então as opções são:

- **Sob demanda** (mais simples): peça "checa milhas das minhas rotas" — rodo a
  captura na hora via flowa-control e comparo com o motor-dinheiro.
- **Standalone agendado**: subir o Chrome com `--remote-debugging-port=9222` e
  agendar `smiles_scraper.py` no launchd.
- **Tripmilhas como fonte de promoções**: raspar a lista de oportunidades do
  tripmilhas (Wix, sem Akamai, roda até na nuvem) — pega o que ELES curam, não
  suas rotas sob demanda.

## Rodar (modo standalone)
```bash
pip install -r miles/requirements.txt
python -m playwright install chromium
SMILES_MEMBER=<seu_numero> python miles/smiles_scraper.py
```
Gera `miles/miles_results.json` (mais barato em milhas por rota).

## Verdades importantes
- **ToS:** consultar a API/raspar pode violar os Termos do Smiles. Baixa frequência.
- **Depende da máquina ligada + Chrome logado.**
- **Milhas vs dinheiro:** compare `milhas × custo_do_milheiro + taxas` com o preço
  em R$ do motor-dinheiro. Piso: US$ 281 (BSB→NY) ≈ R$ 1.560.
