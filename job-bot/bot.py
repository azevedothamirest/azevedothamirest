"""Bot do Telegram: busca vagas, avalia com o Claude e prepara a candidatura."""
import asyncio
import datetime as dt
import html
import json
import logging
import os
import tempfile
from pathlib import Path

import yaml
from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

import analise
import cv
import db
from fontes import Vaga, coletar, local_aceito

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jobbot")

AQUI = Path(__file__).parent
CFG = yaml.safe_load((AQUI / "config.yaml").read_text())
PERFIL = (AQUI / "perfil.md").read_text()
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])  # só você usa o bot
e = html.escape


def rowid(vid):
    with db.con() as c:
        return c.execute("SELECT rowid FROM vagas WHERE id=?", (vid,)).fetchone()[0]


def por_rowid(rid):
    with db.con() as c:
        return c.execute("SELECT rowid,* FROM vagas WHERE rowid=?", (rid,)).fetchone()


def emoji(nota):
    return "🟢" if nota >= CFG["notas"]["imediato"] else "🟡" if nota >= CFG["notas"]["resumo_diario"] else "🔴"


def mensagem(v: dict, a: dict) -> str:
    sal = a.get("salario_sugerido") or {}
    linhas = [
        f"{emoji(a['nota'])} <b>{a['nota']}% compatível</b>", "",
        f"💼 <b>{e(v['titulo'])}</b>",
        f"🏢 {e(v['empresa'])} · via {v['fonte']}",
        f"📍 {e(v['modelo'].capitalize())} · {e(v['local'])} · {e(a.get('contrato', ''))}",
    ]
    if a.get("faixa_anunciada"):
        linhas.append(f"💰 Anunciado: {e(str(a['faixa_anunciada']))}")
    linhas += ["", "📝 <b>Resumo</b>", e(a.get("resumo_vaga", ""))]
    if a.get("stack"):
        linhas.append("Stack: " + e(", ".join(a["stack"])))
    if a.get("empresa_resumo"):
        linhas += ["", "🏢 <b>Sobre a empresa</b>", e(a["empresa_resumo"])]
    linhas += ["", "✅ <b>Onde você se encaixa</b>"] + [f"• {e(x)}" for x in a.get("pontos_fortes", [])]
    if a.get("lacunas"):
        linhas += ["", "⚠️ <b>O que falta</b>"] + [f"• {e(x)}" for x in a["lacunas"]]
    if sal:
        linhas += ["", "💵 <b>Pretensão sugerida</b>",
                   f"CLT: {e(str(sal.get('clt', '?')))} · PJ: {e(str(sal.get('pj', '?')))}",
                   f"<i>{e(str(sal.get('base', '')))}</i>"]
    if a.get("dica"):
        linhas += ["", f"💡 {e(a['dica'])}"]
    return "\n".join(linhas)[:4000]


def botoes(rid, url):
    return InlineKeyboardMarkup([
        [Btn("✅ Candidatar", callback_data=f"cand:{rid}"), Btn("✏️ Ajustar CV", callback_data=f"cv:{rid}")],
        [Btn("❌ Ignorar", callback_data=f"ign:{rid}"), Btn("🔗 Ver vaga", url=url)],
    ])


async def enviar_vaga(bot, rid):
    r = por_rowid(rid)
    v, a = json.loads(r["dados"]), json.loads(r["analise"])
    await bot.send_message(CHAT_ID, mensagem(v, a), parse_mode=ParseMode.HTML,
                           reply_markup=botoes(rid, v["url"]), disable_web_page_preview=True)


# ---------------------------------------------------------------- busca
async def buscar(ctx: ContextTypes.DEFAULT_TYPE):
    empresas = db.empresas_inhire(CFG.get("inhire_empresas", []))
    vagas = await asyncio.to_thread(coletar, CFG, empresas)
    cidade = CFG["localizacao"]["hibrido_presencial"]
    novas = [v for v in vagas if not db.existe(v.id) and local_aceito(v, cidade)]
    log.info("%d vagas coletadas, %d novas", len(vagas), len(novas))
    enviadas = 0
    for v in novas:
        try:
            a = await asyncio.to_thread(analise.avaliar, v, PERFIL, CFG)
        except Exception as ex:
            log.warning("Falha ao avaliar %s: %s", v.id, ex)
            continue
        nota = int(a.get("nota", 0))
        if nota >= CFG["notas"]["imediato"]:
            db.salvar(v, a, nota, "enviada")
            await enviar_vaga(ctx.bot, rowid(v.id))
            enviadas += 1
        elif nota >= CFG["notas"]["resumo_diario"]:
            db.salvar(v, a, nota, "resumo")
        else:
            db.salvar(v, a, nota, "descartada")
    return len(novas), enviadas


async def resumo_diario(ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.por_status("resumo")
    if not rows:
        return
    await ctx.bot.send_message(CHAT_ID, f"🟡 <b>Resumo do dia:</b> {len(rows)} vagas entre "
                               f"{CFG['notas']['resumo_diario']}% e {CFG['notas']['imediato'] - 1}%",
                               parse_mode=ParseMode.HTML)
    for r in rows:
        db.status(r["id"], "enviada")
        await enviar_vaga(ctx.bot, rowid(r["id"]))


# ---------------------------------------------------------------- botões
async def clique(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    acao, rid = q.data.split(":")
    r = por_rowid(int(rid))
    v, a = json.loads(r["dados"]), json.loads(r["analise"])

    if acao == "ign":
        db.status(r["id"], "ignorada")
        await q.edit_message_reply_markup(None)
        await q.message.reply_text("❌ Vaga ignorada.")
        return

    await q.message.reply_text("⏳ Ajustando seu currículo para essa vaga…")
    novo = await asyncio.to_thread(analise.ajustar_cv, Vaga(**v), PERFIL, a, CFG)
    arq = Path(tempfile.gettempdir()) / f"Thamires_Azevedo_CV_{v['empresa'][:30].replace(' ', '_')}.docx"
    cv.gerar(novo, str(arq))
    mudancas = "\n".join(f"• {e(m)}" for m in novo.get("mudancas", []))
    with open(arq, "rb") as f:
        await q.message.reply_document(f, caption=f"✏️ <b>O que mudou:</b>\n{mudancas}"[:1000],
                                       parse_mode=ParseMode.HTML)

    if acao == "cand":
        db.status(r["id"], "candidatada")
        sal = a.get("salario_sugerido") or {}
        await q.message.reply_text(
            "✅ <b>Candidatura pronta</b>\n\n"
            f"📨 <b>Mensagem de apresentação:</b>\n{e(novo.get('carta', ''))}\n\n"
            f"💵 Pretensão: CLT {e(str(sal.get('clt', '?')))} · PJ {e(str(sal.get('pj', '?')))}\n\n"
            f"🔗 Envie aqui: {e(v['url'])}\n\n"
            "Depois atualize com /status.",
            parse_mode=ParseMode.HTML, disable_web_page_preview=True)


# ---------------------------------------------------------------- comandos
def so_dona(f):
    async def w(update: Update, ctx):
        if update.effective_chat.id != CHAT_ID:
            return
        return await f(update, ctx)
    return w


@so_dona
async def start(update: Update, ctx):
    await update.message.reply_text(
        "👋 Oi, Thamires! Eu procuro vagas de QA pra você.\n\n"
        "/buscar – buscar agora\n/vagas – vagas boas ainda abertas\n"
        "/candidaturas – onde você já se candidatou\n"
        "/status <id> <entrevista|recusada|proposta> – atualizar candidatura\n"
        "/addempresa <nome> – acompanhar empresa na InHire (nome.inhire.app)\n"
        "/empresas – empresas InHire acompanhadas")


@so_dona
async def cmd_buscar(update: Update, ctx):
    await update.message.reply_text("🔎 Buscando vagas… pode levar alguns minutos.")
    novas, enviadas = await buscar(ctx)
    await update.message.reply_text(f"Pronto: {novas} vagas novas analisadas, {enviadas} acima de "
                                    f"{CFG['notas']['imediato']}%.")


@so_dona
async def cmd_vagas(update: Update, ctx):
    rows = db.por_status("enviada", "resumo")[:15]
    if not rows:
        return await update.message.reply_text("Nenhuma vaga aberta no momento.")
    txt = "\n".join(f"{emoji(r['nota'])} {r['nota']}% · {e(json.loads(r['dados'])['titulo'])} – "
                    f"{e(json.loads(r['dados'])['empresa'])}" for r in rows)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)


@so_dona
async def cmd_candidaturas(update: Update, ctx):
    rows = db.por_status("candidatada", "entrevista", "proposta", "recusada")
    if not rows:
        return await update.message.reply_text("Nenhuma candidatura ainda.")
    txt = "\n".join(f"#{rowid(r['id'])} · {r['status']} · {e(json.loads(r['dados'])['titulo'])} – "
                    f"{e(json.loads(r['dados'])['empresa'])}" for r in rows)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)


@so_dona
async def cmd_status(update: Update, ctx):
    try:
        rid, st = ctx.args[0].lstrip("#"), ctx.args[1].lower()
        db.status(por_rowid(int(rid))["id"], st)
        await update.message.reply_text(f"Atualizado: #{rid} → {st}")
    except Exception:
        await update.message.reply_text("Uso: /status <id> <entrevista|recusada|proposta>")


@so_dona
async def cmd_addempresa(update: Update, ctx):
    if not ctx.args:
        return await update.message.reply_text("Uso: /addempresa nome (o que vem antes de .inhire.app)")
    nome = ctx.args[0].lower().replace(".inhire.app", "").replace("https://", "")
    db.add_inhire(nome)
    await update.message.reply_text(f"✅ {nome}.inhire.app adicionada.")


@so_dona
async def cmd_empresas(update: Update, ctx):
    await update.message.reply_text("\n".join(db.empresas_inhire(CFG.get("inhire_empresas", []))))


def main():
    app = Application.builder().token(TOKEN).build()
    for nome, f in [("start", start), ("buscar", cmd_buscar), ("vagas", cmd_vagas),
                    ("candidaturas", cmd_candidaturas), ("status", cmd_status),
                    ("addempresa", cmd_addempresa), ("empresas", cmd_empresas)]:
        app.add_handler(CommandHandler(nome, f))
    app.add_handler(CallbackQueryHandler(clique))

    jq = app.job_queue
    jq.run_repeating(buscar, interval=CFG["intervalo_busca_horas"] * 3600, first=10)
    h, m = map(int, CFG["horario_resumo_diario"].split(":"))
    tz = dt.timezone(dt.timedelta(hours=-3))  # Recife
    jq.run_daily(resumo_diario, time=dt.time(h, m, tzinfo=tz))
    app.run_polling()


if __name__ == "__main__":
    main()
