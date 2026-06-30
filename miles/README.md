# Motor Milhas (Smiles) — best-effort

Este módulo é um **esqueleto** para checar preços em **milhas** no Smiles. Diferente
do motor-dinheiro (que usa a `fli` e é estável), milhas **não têm API/MCP oficial** —
só dá pra raspar, e isso é frágil.

## Verdades importantes
- **Quebra fácil:** quando o Smiles muda o site, o scraper para. Espere manutenção.
- **Precisa de navegador** (Playwright) → roda no **GitHub Actions**, não no Vercel.
- **Termos de Uso:** raspar pode violar o ToS do Smiles. Use por sua conta, baixa frequência.
- **Licença:** se você copiar lógica de algum repo da comunidade, respeite a licença dele.

## O que já está pronto
Navegação, montagem de URL, loop de rotas, headless e a escrita do resultado em
`miles_results.json`. **Falta só** ajustar `parse_results()` aos seletores atuais do site.

## Como completar (em ~30 min no Claude Code)
1. `pip install playwright && python -m playwright install chromium`
2. Rode `python miles/smiles_scraper.py` com `headless=False` pra ver a tela.
3. Inspecione os cards de voo e preencha os seletores em `parse_results()`.
4. Opcional: pegue um repo open-source ativo de Smiles como referência dos seletores
   (busque no GitHub na hora — eles mudam de nome/somem).

## Como decidir milhas vs dinheiro
Compare `milhas × custo_do_milheiro + taxas` com o preço em dinheiro do monitor.
Piso de referência: **US$ 281 (BSB→NY) ≈ R$ 1.560**.
