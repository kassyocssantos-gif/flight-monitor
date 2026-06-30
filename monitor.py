#!/usr/bin/env python3
"""
flight-monitor — motor DINHEIRO via `fli` (Google Flights, sem chave/API key).
Para cada rota varre a janela de datas de IDA, pega a mais barata, compara com o
menor preco ja visto (state.json), grava history.csv e dispara alerta no Telegram
quando bate novo minimo ou o preco-alvo.

Depende so do pacote `flights` (CLI `fli`). Roda perfeito no GitHub Actions.
"""

import os
import sys
import csv
import json
import subprocess
import datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
# Multi-config: `python monitor.py [config.json]`. Cada config tem seu proprio
# state/history/report (sufixo derivado do nome: config_domestico -> *_domestico).
CONFIG_PATH = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "config.json")
_stem = os.path.splitext(os.path.basename(CONFIG_PATH))[0]
_suf = "" if _stem == "config" else "_" + _stem.replace("config_", "").replace("config", "")
HISTORY_PATH = os.path.join(ROOT, f"history{_suf}.csv")
STATE_PATH = os.path.join(ROOT, f"state{_suf}.json")
REPORT_PATH = os.path.join(ROOT, f"latest_report{_suf}.md")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def cheapest_for_route(origin, destination, start, end, cabin):
    """Chama `fli dates` e devolve {price, date} mais barato da janela, ou None."""
    cmd = ["fli", "dates", origin, destination,
           "--from", start, "--to", end, "--class", cabin, "--format", "json"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        print(f"  [diag {origin}-{destination}] timeout", flush=True)
        return None
    raw = out.stdout.strip()
    if not raw or "{" not in raw:
        diag = (out.stderr or out.stdout or "").strip().replace("\n", " ")[:300]
        print(f"  [diag {origin}-{destination}] rc={out.returncode} sem JSON: {diag}", flush=True)
        return None
    try:
        data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        print(f"  [diag {origin}-{destination}] JSON invalido: {raw[:200]}", flush=True)
        return None
    best = None
    for d in data.get("dates", []):
        price = d.get("price")
        if price is None:
            continue
        if best is None or price < best["price"]:
            best = {"price": float(price), "date": d.get("departure_date"),
                    "currency": d.get("currency", "USD")}
    return best


def send_whatsapp(text):
    """Envia via CallMeBot (HTTP, sem navegador) — roda no GitHub Actions.
    Setup unico: mandar 'I allow callmebot to send me messages' p/ +34 644 84 71 89
    no WhatsApp; o bot responde com a apikey. Sem WHATSAPP_PHONE+CALLMEBOT_APIKEY,
    so nao envia (igual ao comportamento antigo sem credenciais)."""
    phone = os.environ.get("WHATSAPP_PHONE")        # formato internacional, ex 5547988178754
    apikey = os.environ.get("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        return False
    import urllib.request
    import urllib.parse
    qs = urllib.parse.urlencode({"phone": phone, "text": text, "apikey": apikey})
    url = f"https://api.callmebot.com/whatsapp.php?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=30):
            return True
    except Exception:
        return False


def main():
    cfg = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {})
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    start, end = cfg["date_start"], cfg["date_end"]
    cabin = cfg.get("cabin", "ECONOMY")
    fx = cfg.get("usd_to_brl")  # opcional: mostra preco aproximado em BRL

    import concurrent.futures as cf
    target_default = cfg.get("target_usd")
    pax = cfg.get("pax", 1)

    report = [f"# flight-monitor — {now}",
              f"_Janela {start} a {end} · ida · {cabin} · {pax} pax · fonte Google Flights (fli)_", ""]
    history_rows, alerts = [], []

    # busca todas as rotas em paralelo (sao muitas) e ordena pelo preco
    def work(route):
        return route, cheapest_for_route(route["origin"], route["destination"], start, end, cabin)
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(work, cfg["routes"]))
    results.sort(key=lambda rb: rb[1]["price"] if rb[1] else 9e9)

    for route, best in results:
        o, d = route["origin"], route["destination"]
        target = route.get("target_usd", target_default)
        key = f"{o}-{d}"
        if not best:
            report.append(f"- **{key}**: sem resultado.")
            continue

        usd = best["price"]
        tot = usd * pax
        money = f" → R$ {usd * fx:.0f}/pax · R$ {tot * fx:.0f}/{pax}px" if fx else ""
        prev = state.get(key, {}).get("min_usd")
        is_low = prev is None or usd < prev
        on_target = target is None or usd <= target
        tag = (" 🟢 novo min" if is_low else "") + (" 🎯 ALVO" if on_target else "")

        report.append(f"- **{key}**: US$ {usd:.0f}{money} em {best['date']}"
                      f"{(' | min ant US$ ' + format(prev, '.0f')) if prev else ''}{tag}")
        history_rows.append([now, o, d, best["date"], f"{usd:.0f}", "USD"])

        # alerta = novo minimo DENTRO do alvo (sem ruido de minimos acima do alvo)
        if is_low:
            state[key] = {"min_usd": usd, "date": best["date"], "seen_at": now}
            if on_target:
                alerts.append(f"✈️ *{key}* R$ {tot * fx:.0f} ({pax}px) · "
                              f"US$ {usd:.0f}/pax em {best['date']} 🎯")

    # grava historico
    new_file = not os.path.exists(HISTORY_PATH)
    with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["checked_at", "origin", "destination", "date", "price", "currency"])
        w.writerows(history_rows)

    save_json(STATE_PATH, state)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print("\n".join(report))

    if alerts:
        titulo = cfg.get("nome", "passagens")
        ok = send_whatsapp(f"*Alerta {titulo}*\n\n" + "\n".join(alerts))
        print(f"\n{len(alerts)} alerta(s). WhatsApp: {'enviado' if ok else 'nao configurado'}.")
    else:
        print("\nSem alertas nesta rodada.")


if __name__ == "__main__":
    main()
