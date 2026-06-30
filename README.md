# ✈️ flight-monitor

Monitor de passagens que roda sozinho no **GitHub Actions** e te avisa no **Telegram**
quando uma rota bate um novo mínimo ou o preço-alvo. Já vem com suas rotas campeãs
(BSB, FLN, CWB, NVT, VCP → NY / Miami / Orlando / FLL).

**Dois motores:**
- 💵 **Dinheiro** (`monitor.py`) → usa a lib **`fli`** (Google Flights). **Sem API key, sem navegador, sem KV.** Estável.
- 🎟️ **Milhas** (`miles/`) → scraper Smiles **best-effort** (Playwright). Frágil, opcional.

> Validado: `fli` retornou BSB→JFK **US$ 281 (~R$ 1.560)** em 16/07 — sem nenhuma chave.

---

## Motor dinheiro (o principal)

### Rodar local
```bash
pip install -r requirements.txt
python monitor.py
```
Gera `latest_report.md`, `history.csv` e `state.json`, e manda alerta no Telegram
(se as variáveis estiverem setadas).

### Rodar automático no GitHub Actions (recomendado)
1. Suba o repo:
   ```bash
   git init && git add . && git commit -m "flight-monitor"
   git branch -M main
   git remote add origin git@github.com:kassyocssantos-gif/flight-monitor.git
   git push -u origin main
   ```
2. (Opcional) Telegram em **Settings → Secrets and variables → Actions**:
   `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` (bot via @BotFather; chat_id via
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).
3. Pronto. O workflow roda todo dia às **06:00 (Brasília)**. Pra testar agora:
   **Actions → flight-monitor → Run workflow**. O histórico é commitado de volta no repo.

### Personalizar (`config.json`)
- `routes`: trechos + `target_usd` (preço que dispara o 🎯).
- `date_start` / `date_end`: sua janela de ida.
- `usd_to_brl`: só pra mostrar o valor aproximado em reais no relatório.

---

## Motor milhas (opcional, best-effort)
Veja `miles/README.md`. É um esqueleto: navegação pronta, falta plugar os seletores
atuais do Smiles. Precisa de navegador (Playwright) → roda no Actions, não no Vercel.
Milhas não têm API/MCP oficial; raspar é frágil e sujeito ao ToS do Smiles.

---

## Bônus: a `fli` também é um MCP
A própria lib expõe um **servidor MCP** (`fli-mcp`). Dá pra plugar no Claude Desktop/Code
e buscar voos por conversa, sem chave. Útil pra checagens manuais rápidas além do monitor.

---

## Por que não Amadeus / Vercel?
- **Amadeus** exige cadastro + cota; a `fli` não precisa de nada disso.
- **Vercel** é serverless (disco efêmero, timeout curto, e o motor-milhas precisa de
  navegador). O **GitHub Actions** roda os dois motores e guarda o histórico no repo,
  sem storage externo. Por isso ele é a casa do projeto.
