#!/usr/bin/env python3
"""
miles/smiles_scraper.py — MOTOR MILHAS (Smiles) via API real, dentro da sessao.

DESCOBERTA (2026-06-30, validado):
- A busca em milhas usa a API GET:
    https://api-air-flightsearch-blue.smiles.com.br/v1/airlines/search
    ?cabin=ECONOMIC&originAirportCode=BSB&destinationAirportCode=JFK
    &departureDate=2026-07-15&memberNumber=<seu>&adults=1&children=0&infants=0
    &forceCongener=false
  (departureDate em YYYY-MM-DD; memberNumber opcional — com ele vem o preco CLUB).
- Resposta JSON: requestedFlightSegmentList[].flightList[].fareList[] com
    {miles, baseMiles, g3.costTax (taxa BRL), money, type (SMILES|SMILES_CLUB),
     legListCost}, e flightList[].departure/arrival/stops/duration.
- Akamai + login: a chamada SO passa de DENTRO da sessao logada (cookies _abck/
  bm_sz + login). Por isso roda via fetch no Chrome real (credentials:include),
  nao por requests/curl externos (seriam bloqueados).

EXEC: conecta no Chrome real via CDP (Playwright connect_over_cdp) e roda o fetch
de dentro de uma aba em www.smiles.com.br. Requer Chrome com debug:
    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222
e estar LOGADO no Smiles. (No setup atual do Kassyo o Chrome nao expoe porta TCP;
ligue a flag acima para o modo standalone, ou rode a captura via flowa-control.)

Validado BSB->JFK 15/07: 263.500 milhas + R$ 311,73 (SMILES_CLUB) — ~R$ 5k vs
R$ 1.546 em dinheiro (US$ 281). Pra essa rota, dinheiro ganha de longe.
"""

import json
import os
import datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(ROOT, "miles_results.json")
CHROME_CDP = os.environ.get("CHROME_CDP", "http://localhost:9222")
MEMBER = os.environ.get("SMILES_MEMBER", "")  # opcional: traz preco Smiles Clube
CABIN = os.environ.get("SMILES_CABIN", "ECONOMIC")

# Rotas (origem, destino). Mesmas do motor-dinheiro p/ comparar milhas vs R$.
ROUTES = [
    ("BSB", "JFK"), ("BSB", "MIA"), ("BSB", "MCO"), ("BSB", "FLL"),
    ("FLN", "JFK"), ("CWB", "MIA"), ("NVT", "MIA"), ("VCP", "MIA"),
]
# Datas a checar (YYYY-MM-DD). A API e por dia; varremos alguns dias da janela.
DATES = ["2026-07-15", "2026-07-20", "2026-07-25", "2026-08-01"]

API = "https://api-air-flightsearch-blue.smiles.com.br/v1/airlines/search"


def api_url(origin, destination, date):
    qs = (f"?cabin={CABIN}&originAirportCode={origin}&destinationAirportCode={destination}"
          f"&departureDate={date}&memberNumber={MEMBER}"
          f"&adults=1&children=0&infants=0&forceCongener=false")
    return API + qs


def extract_offers(api_json, date):
    """Extrai ofertas em milhas (validado contra a resposta real do Smiles)."""
    offers = []
    for seg in api_json.get("requestedFlightSegmentList", []) or []:
        for fl in seg.get("flightList", []) or []:
            stops = fl.get("stops")
            dur = fl.get("duration", {}) or {}
            for fare in fl.get("fareList", []) or []:
                miles = fare.get("miles")
                if not miles:
                    continue
                tax = fare.get("g3", {}).get("costTax") if fare.get("g3") else None
                tax = tax if tax is not None else fare.get("money", 0)
                try:
                    tax = float(str(tax).replace(",", "."))
                except (TypeError, ValueError):
                    tax = 0.0
                offers.append({
                    "miles": int(miles),
                    "taxes_brl": tax,
                    "type": fare.get("type"),        # SMILES | SMILES_CLUB
                    "date": date,
                    "stops": stops,
                    "route": fare.get("legListCost"),
                    "duration_h": dur.get("hours"),
                })
    return offers


def fetch_via_chrome(page, url):
    """Roda o fetch DENTRO da sessao (herda cookies Akamai + login)."""
    res = page.evaluate(
        """async (u) => {
            const r = await fetch(u, {credentials:'include'});
            const t = await r.text();
            return {status: r.status, body: t};
        }""", url)
    if res.get("status") != 200:
        return None
    try:
        return json.loads(res["body"])
    except (ValueError, KeyError):
        return None


def scrape():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright nao instalado. Rode: pip install -r miles/requirements.txt")
        return []

    results = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CHROME_CDP)
        except Exception as e:
            print(f"Sem CDP em {CHROME_CDP}: {e}\n"
                  "Suba o Chrome com --remote-debugging-port=9222 (e logado no Smiles).")
            return []

        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        # precisa estar num contexto do dominio p/ os cookies irem no fetch
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            if "smiles.com.br" not in (page.url or ""):
                page.goto("https://www.smiles.com.br/home", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        for origin, destination in ROUTES:
            best = None
            for date in DATES:
                try:
                    data = fetch_via_chrome(page, api_url(origin, destination, date))
                except Exception as e:
                    print(f"  [diag {origin}-{destination} {date}] {e}")
                    continue
                if not data:
                    continue
                for off in extract_offers(data, date):
                    if best is None or off["miles"] < best["miles"]:
                        best = off
            results.append({"route": f"{origin}-{destination}", "cheapest": best})
    return results


def main():
    data = {
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cabin": CABIN,
        "dates": DATES,
        "results": scrape(),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
