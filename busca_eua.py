#!/usr/bin/env python3
"""
busca_eua.py — busca pontual: melhor voo Brasil -> EUA (dinheiro, via fli).
Janela e passageiros parametrizaveis. Preco do fli e por pessoa; multiplicamos.
Roda as rotas em paralelo e ordena pelo total.

Uso: python busca_eua.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--pax N]
"""
import subprocess, json, sys, concurrent.futures as cf

FROM = "2026-06-30"
TO = "2026-08-05"
PAX = 2
USD_BRL = 5.5

# argumentos simples
a = sys.argv
if "--from" in a: FROM = a[a.index("--from")+1]
if "--to" in a: TO = a[a.index("--to")+1]
if "--pax" in a: PAX = int(a[a.index("--pax")+1])

# origens e destinos (gateways US por regiao). Sobrescreva com --origins/--dests.
ORIGINS = ["GRU", "VCP", "FLN", "CWB", "NVT", "JOI", "POA"]   # default: SP + Sul
DESTS = ["MIA", "MCO", "FLL", "JFK", "EWR", "LAX"]
if "--origins" in a: ORIGINS = a[a.index("--origins")+1].upper().split(",")
if "--dests" in a: DESTS = a[a.index("--dests")+1].upper().split(",")
ROUTES = [(o, d) for o in ORIGINS for d in DESTS]

def cheapest(o, d):
    try:
        out = subprocess.run(
            ["fli", "dates", o, d, "--from", FROM, "--to", TO,
             "--class", "ECONOMY", "--format", "json"],
            capture_output=True, text=True, timeout=300)
        raw = out.stdout
        j = json.loads(raw[raw.index("{"):raw.rindex("}")+1])
        xs = [x for x in j.get("dates", []) if x.get("price")]
        if not xs:
            return None
        m = min(xs, key=lambda x: x["price"])
        return {"route": f"{o}-{d}", "usd": m["price"], "date": m.get("departure_date")}
    except Exception:
        return None

def main():
    res = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(lambda rt: cheapest(*rt), ROUTES):
            if r:
                res.append(r)
    res.sort(key=lambda x: x["usd"])
    print(f"\nMELHOR VOO BR->EUA (ida) | janela {FROM} a {TO} | {PAX} pax | economia\n")
    print(f"{'Rota':10} {'1 pax USD':>10} {f'{PAX}pax USD':>10} {f'{PAX}pax R$':>11}  Data")
    print("-"*60)
    for r in res:
        tot = r["usd"] * PAX
        print(f"{r['route']:10} {r['usd']:>10.0f} {tot:>10.0f} {tot*USD_BRL:>11.0f}  {r['date']}")
    if res:
        b = res[0]
        print(f"\n>>> MAIS BARATO: {b['route']} em {b['date']} — "
              f"US$ {b['usd']*PAX:.0f} (R$ {b['usd']*PAX*USD_BRL:.0f}) p/ {PAX} pessoas")

if __name__ == "__main__":
    main()
