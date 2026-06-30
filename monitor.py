#!/usr/bin/env python3
"""
flight-monitor — motor DINHEIRO via `fli` (Google Flights, sem chave/API key).
Para cada rota varre a janela de datas de IDA, pega a mais barata, compara com o
menor preco ja visto (state.json), grava history.csv e dispara alerta no Telegram
quando bate novo minimo ou o preco-alvo.

Depende so do pacote `flights` (CLI `fli`). Roda perfeito no GitHub Actions.
"""

import os
import csv
import json
import subprocess
import datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
HISTORY_PATH = os.path.join(ROOT, "history.csv")
STATE_PATH = os.path.join(ROOT, "state.json")
REPORT_PATH = os.path.join(ROOT, "latest_report.md")


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
        return None
    raw = out.stdout.strip()
    if not raw or "{" not in raw:
        return None
    try:
        data = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
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

    report = [f"# flight-monitor — {now}",
              f"_Janela {start} a {end} · ida · {cabin} · fonte Google Flights (fli)_", ""]
    history_rows, alerts = [], []

    for route in cfg["routes"]:
        o, d = route["origin"], route["destination"]
        target = route.get("target_usd")
        key = f"{o}-{d}"
        best = cheapest_for_route(o, d, start, end, cabin)
        if not best:
            report.append(f"- **{key}**: sem resultado.")
            continue

        usd = best["price"]
        brl = f" (~R$ {usd * fx:.0f})" if fx else ""
        prev = state.get(key, {}).get("min_usd")
        is_low = prev is None or usd < prev
        hit = target is not None and usd <= target
        tag = (" 🟢 novo minimo" if is_low else "") + (" 🎯 meta" if hit else "")

        report.append(
            f"- **{key}**: US$ {usd:.0f}{brl} em {best['date']}"
            f"{(' | min anterior US$ ' + format(prev, '.0f')) if prev else ''}{tag}")
        history_rows.append([now, o, d, best["date"], f"{usd:.0f}", "USD"])

        if is_low or hit:
            alerts.append(f"✈️ *{key}* US$ {usd:.0f}{brl} em {best['date']}{tag}")
            state[key] = {"min_usd": usd, "date": best["date"], "seen_at": now}

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
        ok = send_whatsapp("*Alerta de passagens*\n\n" + "\n".join(alerts))
        print(f"\n{len(alerts)} alerta(s). WhatsApp: {'enviado' if ok else 'nao configurado'}.")
    else:
        print("\nSem alertas nesta rodada.")


if __name__ == "__main__":
    main()
