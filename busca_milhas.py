#!/usr/bin/env python3
"""
busca_milhas.py — "clone" do buscador tripmilhas, porém MELHOR: busca as milhas
reais na API do Smiles E o preco em dinheiro (fli), converte milhas->R$ e diz o
que vale mais. O tripmilhas so redireciona pro Smiles; aqui a gente resolve.

MILHAS: API Smiles /v1/airlines/search (precisa sessao logada — Akamai). Roda no
Chrome real via CDP; ou cole o JSON de uma captura em --json.
DINHEIRO: fli (Google Flights), sem chave.

Custo do milheiro: R$ 15/mil (config CUSTO_MILHEIRO). Milhas->R$ = milhas*15/1000 + taxa.

Uso:
  SMILES_MEMBER=435442571 python busca_milhas.py CWB MIA 2026-07-15 [--pax 2] [--milheiro 15]
"""
import subprocess, json, sys, os

a = sys.argv
if len(a) < 4:
    print("uso: python busca_milhas.py ORIGEM DESTINO YYYY-MM-DD [--pax N] [--milheiro 15]")
    sys.exit(1)
ORIGIN, DEST, DATE = a[1].upper(), a[2].upper(), a[3]
PAX = int(a[a.index("--pax")+1]) if "--pax" in a else 1
CUSTO_MILHEIRO = float(a[a.index("--milheiro")+1]) if "--milheiro" in a else 15.0
USD_BRL = 5.5
MEMBER = os.environ.get("SMILES_MEMBER", "")
CHROME_CDP = os.environ.get("CHROME_CDP", "http://localhost:9222")

API = ("https://api-air-flightsearch-blue.smiles.com.br/v1/airlines/search"
       f"?cabin=ALL&originAirportCode={ORIGIN}&destinationAirportCode={DEST}"
       f"&departureDate={DATE}&memberNumber={MEMBER}&adults={PAX}"
       "&children=0&infants=0&forceCongener=false")


def parse_milhas(api_json):
    """Menor tarifa 100% milhas (sem MONEY) e menor hibrida. Milhas por 'adults'."""
    pure = hib = None
    for seg in api_json.get("requestedFlightSegmentList", []) or []:
        for fl in seg.get("flightList", []) or []:
            for f in fl.get("fareList", []) or []:
                if not f.get("miles"):
                    continue
                tax = f.get("g3", {}).get("costTax") if f.get("g3") else f.get("money", 0)
                try:
                    tax = float(str(tax).replace(",", "."))
                except (TypeError, ValueError):
                    tax = 0.0
                rec = {"miles": f["miles"], "tax": tax, "type": f.get("type"),
                       "rota": f.get("legListCost"), "stops": fl.get("stops")}
                if "MONEY" in (f.get("type") or ""):
                    if hib is None or f["miles"] < hib["miles"]:
                        hib = rec
                else:
                    if pure is None or f["miles"] < pure["miles"]:
                        pure = rec
    return pure, hib


def get_milhas():
    """Via Chrome real (CDP). Alternativa: passar --json arquivo com a resposta."""
    if "--json" in a:
        with open(a[a.index("--json")+1], encoding="utf-8") as f:
            return parse_milhas(json.load(f))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[milhas] Playwright ausente e sem --json; pulando milhas.")
        return None, None
    try:
        with sync_playwright() as p:
            br = p.chromium.connect_over_cdp(CHROME_CDP)
            ctx = br.contexts[0] if br.contexts else br.new_context()
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            if "smiles.com.br" not in (pg.url or ""):
                pg.goto("https://www.smiles.com.br/home", wait_until="domcontentloaded", timeout=60000)
            res = pg.evaluate("""async(u)=>{const r=await fetch(u,{credentials:'include'});return await r.text();}""", API)
            return parse_milhas(json.loads(res))
    except Exception as e:
        print(f"[milhas] sem CDP/sessao ({e}); rode com Chrome --remote-debugging-port + logado, ou --json.")
        return None, None


def get_dinheiro():
    try:
        out = subprocess.run(["fli", "search", ORIGIN, DEST, "--date", DATE,
                              "--class", "ECONOMY", "--format", "json"],
                             capture_output=True, text=True, timeout=180)
        raw = out.stdout
        j = json.loads(raw[raw.index("{"):raw.rindex("}")+1])
        flights = j.get("flights") or j.get("results") or []
        prices = [x.get("price") for x in flights if x.get("price")]
        return min(prices) if prices else None
    except Exception:
        return None


def main():
    print(f"\n🔎 {ORIGIN}→{DEST} · {DATE} · {PAX} pax · milheiro R$ {CUSTO_MILHEIRO:.0f}\n")
    pure, hib = get_milhas()
    usd = get_dinheiro()

    if pure:
        rs = pure["miles"] * CUSTO_MILHEIRO / 1000 + pure["tax"]
        print(f"🎟️ Milhas (100%): {pure['miles']:,} milhas + R$ {pure['tax']:.0f} "
              f"= ~R$ {rs:.0f}  [{pure['type']}, {pure.get('stops')} paradas, {pure.get('rota')}]")
    if hib:
        print(f"   Híbrido (milhas+R$): {hib['miles']:,} milhas + taxa R$ {hib['tax']:.0f} [{hib['type']}]")
    if usd:
        rd = usd * USD_BRL
        print(f"💵 Dinheiro: US$ {usd:.0f} = ~R$ {rd:.0f}")

    if pure and usd:
        rs = pure["miles"] * CUSTO_MILHEIRO / 1000 + pure["tax"]
        rd = usd * USD_BRL
        win = "DINHEIRO" if rd < rs else "MILHAS"
        print(f"\n>>> Melhor: {win} (R$ {min(rs,rd):.0f} vs R$ {max(rs,rd):.0f}, "
              f"dif {abs(rs-rd)/min(rs,rd)*100:.0f}%)  · por pax")


if __name__ == "__main__":
    main()
