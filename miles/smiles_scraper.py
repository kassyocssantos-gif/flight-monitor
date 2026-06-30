#!/usr/bin/env python3
"""
miles/smiles_scraper.py — MOTOR MILHAS (Smiles) via CDP no Chrome REAL.

POR QUE ASSIM (e nao Playwright headless no Actions):
- O Smiles roda atras de Akamai Bot Manager (sensor data, _abck/bm_sz) + e um SPA
  React. Headless + IP de datacenter (GitHub Actions) = bloqueado. Confirmado.
- A saida: conectar no SEU Chrome real (sessao logada, IP residencial, cookies
  Akamai validos) via CDP e INTERCEPTAR a resposta da API de disponibilidade
  (`/v1/search`) — em vez de raspar o DOM (fragil). A x-api-key e os cookies vao
  no request automaticamente; nada hardcoded.

PRE-REQUISITOS (seus — uma vez):
  1. Subir o Chrome com debug:
       /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
         --remote-debugging-port=9222
     (ou ativar em chrome://inspect). Confirme: curl localhost:9222/json/version
  2. Estar LOGADO no Smiles nesse Chrome (so voce tem a credencial).

USO:
    pip install -r miles/requirements.txt   # playwright
    python -m playwright install chromium    # so p/ as libs; usamos o SEU Chrome
    python miles/smiles_scraper.py

Saida: miles/miles_results.json (mais barato em milhas por rota + amostra crua
da 1a resposta da API em _raw_sample, p/ ajustar o parser na 1a validacao).
"""

import json
import os
import datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(ROOT, "miles_results.json")
CHROME_CDP = os.environ.get("CHROME_CDP", "http://localhost:9222")

# Rotas a checar em milhas (origem, destino). Edite a vontade.
ROUTES = [
    ("BSB", "JFK"),
    ("BSB", "MIA"),
    ("GRU", "MIA"),
    ("VCP", "MCO"),
]
DATE_START = "2026-07-15"
DATE_END = "2026-08-05"

# A API de disponibilidade do Smiles. Casamos por substring na URL (robusto a
# troca de host de producao): toda resposta cuja URL contenha um destes.
API_MATCH = ("/v1/search", "airfares/search", "flightavailability")


def build_search_url(origin, destination, date):
    """Deep-link da busca de emissao (dispara a chamada de availability)."""
    return (
        "https://www.smiles.com.br/mfe/emissao-passagem/"
        f"?adults=1&children=0&infants=0&cabin=ECONOMIC"
        f"&originAirport={origin}&destinationAirport={destination}"
        f"&departureDate={date}&tripType=2&searchType=g"
    )


def extract_offers(api_json):
    """
    Extrai ofertas em milhas da resposta da API de disponibilidade.
    Defensivo: o Smiles muda os nomes; tentamos os caminhos conhecidos e, se
    nada casar, devolvemos [] (o _raw_sample salvo permite ajustar na validacao).
    Alvo: lista de {miles:int, taxes_brl:float, date:str, flight:str}.
    """
    offers = []
    segs = (api_json.get("requestedFlightSegmentList")
            or api_json.get("segments") or [])
    for seg in segs:
        flights = seg.get("flightList") or seg.get("flights") or []
        for fl in flights:
            date = (fl.get("departure", {}) or {}).get("date") or fl.get("departureDate")
            fares = fl.get("fareList") or fl.get("fares") or []
            for fare in fares:
                miles = fare.get("miles") or fare.get("milesAmount")
                if not miles:
                    continue
                taxes = (fare.get("money") or fare.get("airlineTax")
                         or fare.get("taxAmount") or 0)
                offers.append({
                    "miles": int(miles),
                    "taxes_brl": float(taxes or 0),
                    "date": date,
                    "flight": fl.get("flightNumber") or fl.get("number"),
                })
    return offers


def scrape():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright nao instalado. Rode: pip install -r miles/requirements.txt")
        return [], None

    results, raw_sample = [], None
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CHROME_CDP)
        except Exception as e:
            print(f"Nao conectei no Chrome via CDP em {CHROME_CDP}: {e}\n"
                  "Suba o Chrome com --remote-debugging-port=9222 e tente de novo.")
            return [], None

        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        captured = {"json": None}

        def on_response(resp):
            try:
                if any(m in resp.url for m in API_MATCH) and resp.request.method in ("GET", "POST"):
                    captured["json"] = resp.json()
            except Exception:
                pass

        page.on("response", on_response)

        for origin, destination in ROUTES:
            captured["json"] = None
            try:
                page.goto(build_search_url(origin, destination, DATE_START),
                          timeout=60000, wait_until="domcontentloaded")
                # espera a chamada de availability chegar (ate ~25s)
                for _ in range(50):
                    if captured["json"] is not None:
                        break
                    page.wait_for_timeout(500)
                api_json = captured["json"]
                if api_json is None:
                    results.append({"route": f"{origin}-{destination}",
                                    "error": "API /v1/search nao capturada (login? Akamai? deep-link?)"})
                    continue
                if raw_sample is None:
                    raw_sample = api_json  # 1a resposta crua p/ ajuste do parser
                offers = extract_offers(api_json)
                cheapest = min(offers, key=lambda x: x["miles"]) if offers else None
                results.append({"route": f"{origin}-{destination}",
                                "cheapest": cheapest, "found": len(offers)})
            except Exception as e:
                results.append({"route": f"{origin}-{destination}", "error": str(e)})

        page.close()
    return results, raw_sample


def main():
    results, raw_sample = scrape()
    data = {
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": DATE_START, "end": DATE_END},
        "results": results,
        # amostra crua da 1a resposta — usada SO na 1a validacao p/ ajustar
        # extract_offers() aos nomes reais; pode remover depois.
        "_raw_sample": raw_sample,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in data.items() if k != "_raw_sample"},
                     indent=2, ensure_ascii=False))
    if raw_sample is not None:
        print(f"\n[ok] amostra crua da API salva em {OUT_PATH} (_raw_sample) "
              "p/ ajustar extract_offers() se necessario.")


if __name__ == "__main__":
    main()
