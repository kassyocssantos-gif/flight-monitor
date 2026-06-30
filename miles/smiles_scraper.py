#!/usr/bin/env python3
"""
miles/smiles_scraper.py — MOTOR MILHAS (best-effort).

⚠️ IMPORTANTE / LEIA:
- Isto e um ESQUELETO. O site do Smiles muda com frequencia e quebra scrapers,
  e raspar pode violar os Termos de Uso. Use por sua conta, com baixa frequencia.
- Precisa de navegador (Playwright). Por isso roda no GitHub Actions, NAO no Vercel.
- A funcao parse_results() precisa ser ajustada aos seletores atuais do site.
  O fluxo, a navegacao e a saida ja estao prontos — falta plugar os seletores.

Instalacao (no Actions ou local):
    pip install playwright
    python -m playwright install chromium

Uso:
    python miles/smiles_scraper.py
"""

import json
import os
import datetime as dt

# Rotas a checar em milhas (origem, destino). Edite a vontade.
ROUTES = [
    ("BSB", "JFK"),
    ("BSB", "MIA"),
    ("GRU", "MIA"),
    ("VCP", "MCO"),
]
DATE_START = "2026-07-15"
DATE_END = "2026-08-05"
OUT_PATH = os.path.join(os.path.dirname(__file__), "miles_results.json")


def build_url(origin, destination, date):
    """Monta a URL de busca do Smiles. Ajuste se o padrao mudar."""
    return (
        "https://www.smiles.com.br/mfe/emissao-passagem/"
        f"?adults=1&children=0&infants=0&cabin=ECONOMIC"
        f"&originAirport={origin}&destinationAirport={destination}"
        f"&departureDate={date}&tripType=2&searchType=g"
    )


def parse_results(page):
    """
    TODO: ajustar aos seletores atuais do Smiles.
    Deve devolver uma lista de dicts: [{"miles": int, "taxes_brl": float, ...}]
    Exemplo de abordagem (pseudo):
        cards = page.query_selector_all("[data-testid='flight-card']")
        for c in cards:
            miles = c.query_selector(".miles-amount").inner_text()
            ...
    """
    return []


def scrape():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright nao instalado. Rode: pip install playwright && "
              "python -m playwright install chromium")
        return []

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="pt-BR")
        page = ctx.new_page()
        for origin, destination in ROUTES:
            url = build_url(origin, destination, DATE_START)
            try:
                page.goto(url, timeout=60000, wait_until="networkidle")
                page.wait_for_timeout(4000)  # deixa o JS carregar os voos
                offers = parse_results(page)
                cheapest = min(offers, key=lambda x: x["miles"]) if offers else None
                results.append({
                    "route": f"{origin}-{destination}",
                    "cheapest": cheapest,
                    "found": len(offers),
                })
            except Exception as e:
                results.append({"route": f"{origin}-{destination}", "error": str(e)})
        browser.close()
    return results


def main():
    data = {
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"start": DATE_START, "end": DATE_END},
        "results": scrape(),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
