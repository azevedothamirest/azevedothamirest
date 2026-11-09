# 🤖 Job Bot — vagas de QA no Telegram

Bot pessoal que busca vagas de QA (Sênior/Pleno), avalia a compatibilidade com o seu perfil usando o Claude, pesquisa quanto a empresa paga e prepara o currículo ajustado + mensagem de apresentação.

**Fontes:** Gupy · InHire · LinkedIn (vagas públicas) · Remotive
**Filtro de local:** remoto em todo o Brasil; híbrido/presencial só em Recife.

## Como funciona
1. A cada 3h o bot busca vagas novas.
2. O Claude dá uma nota de 0–100, resume a vaga e a empresa, aponta pontos fortes/lacunas e pesquisa na web o salário da empresa para sugerir sua pretensão (CLT e PJ).
3. 🟢 ≥ 80% → mensagem na hora · 🟡 60–79% → resumo diário às 19h · 🔴 < 60% → descartada.
4. Botões em cada vaga:
   - **✏️ Ajustar CV** → currículo `.docx` reescrito para a vaga (só com fatos reais do seu perfil) + lista do que mudou
   - **✅ Candidatar** → CV ajustado + mensagem de apresentação + pretensão + link para enviar
   - **❌ Ignorar** · **🔗 Ver vaga**

O envio final é feito por você (1 clique no link): candidatura automática no LinkedIn/Gupy viola os termos de uso e pode bloquear sua conta.

## Comandos
| Comando | O que faz |
|---|---|
| `/buscar` | busca agora |
| `/vagas` | vagas boas ainda abertas |
| `/candidaturas` | candidaturas feitas |
| `/status 12 entrevista` | atualiza candidatura (entrevista, recusada, proposta) |
| `/addempresa nubank` | passa a acompanhar `nubank.inhire.app` |
| `/empresas` | empresas InHire acompanhadas |

## Configuração (uma vez)
1. **Bot do Telegram:** no Telegram, fale com `@BotFather` → `/newbot` → copie o token.
2. **Seu chat id:** fale com `@userinfobot` e copie o número.
3. **Chave do Claude:** crie em https://platform.claude.com → API Keys.
4. Defina as variáveis de ambiente (nunca coloque no código):
   ```
   TELEGRAM_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ANTHROPIC_API_KEY=...
   ```

### Rodar no seu computador
```bash
pip install -r requirements.txt
python bot.py
```

### Rodar 24h na nuvem (Railway — mais fácil)
1. railway.com → New Project → Deploy from GitHub repo → escolha este repositório (pasta `job-bot`).
2. Em *Variables*, adicione as 3 variáveis acima.
3. Em *Volumes*, monte um volume em `/data` (para guardar o histórico).
O `Dockerfile` já está pronto. Fly.io ou Render também funcionam.

## Personalizar
- `perfil.md` → seu currículo base (fonte da verdade para o CV ajustado).
- `config.yaml` → palavras-chave, faixas salariais, notas de corte, intervalo, empresas InHire.
- Custo: cada vaga avaliada é uma chamada ao Claude com pesquisa na web. Para gastar menos, troque `modelo_claude` para `claude-sonnet-5-5` ou `claude-haiku-5-5` no `config.yaml`.

## Observações
- InHire não tem portal único: o bot só vê as empresas listadas em `inhire_empresas` / `/addempresa`.
- As fontes usam endpoints públicos que podem mudar; se uma falhar, as outras continuam e o erro aparece no log.
