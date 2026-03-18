import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from apscheduler.schedulers.background import BackgroundScheduler

from config import HORA_INICIO, HORA_FIN, DIAS_SEMANA, INTERVALO_MIN
from database import (
    obtener_ofertas_hoy, obtener_pendientes, obtener_postuladas,
    cambiar_estado, marcar_postulada, resumen_del_dia, crear_tablas
)
from notifier import enviar_texto, enviar_resumen
from scheduler import ciclo_busqueda, ciclo_resumen, crear_scheduler

load_dotenv()
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
log = logging.getLogger(__name__)

# ─── COMANDOS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 *Buscador de trabajo activo*\n\n"
        "Comandos disponibles:\n"
        "/hoy — ofertas encontradas hoy\n"
        "/pendientes — ofertas esperando revisión\n"
        "/postuladas — historial de postulaciones\n"
        "/buscar — forzar búsqueda ahora\n"
        "/estado — estado del sistema\n"
        "/pausar — detener búsquedas\n"
        "/reanudar — reanudar búsquedas",
        parse_mode="Markdown"
    )

async def cmd_hoy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ofertas = obtener_ofertas_hoy()
    if not ofertas:
        await update.message.reply_text("Sin ofertas encontradas hoy todavía.")
        return

    nombres_cv = {
        "automatizacion": "Automatización",
        "analista":       "Analista/QA",
        "desarrollador":  "Desarrollador",
        "callcenter":     "Call Center",
        "bodega":         "Bodega",
    }
    iconos_estado = {
        "pendiente":  "⏳",
        "postulada":  "✅",
        "ignorada":   "✗",
        "descartada": "—",
        "manual":     "👆",
    }

    texto = f"📋 *Ofertas de hoy — {len(ofertas)} encontradas*\n{'─'*28}\n\n"

    for i, o in enumerate(ofertas[:15], 1):
        estado  = iconos_estado.get(o.get("estado", ""), "·")
        cv      = nombres_cv.get(o.get("mejor_cv", ""), "—")
        score   = o.get("mejor_score", 0)
        titulo  = o.get("titulo", "")[:35]
        empresa = o.get("empresa", "")[:20]
        texto  += f"{estado} *{titulo}*\n"
        texto  += f"   {empresa} · {cv} · {score}/10\n\n"

    if len(ofertas) > 15:
        texto += f"_... y {len(ofertas)-15} más_"

    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_pendientes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ofertas = obtener_pendientes()
    if not ofertas:
        await update.message.reply_text("Sin ofertas pendientes. Todo revisado.")
        return

    texto = f"⏳ *{len(ofertas)} ofertas pendientes de revisión*\n{'─'*28}\n\n"
    botones = []

    for o in ofertas[:8]:
        titulo  = o.get("titulo", "")[:30]
        empresa = o.get("empresa", "")[:15]
        score   = o.get("mejor_score", 0)
        oid     = o.get("id")
        texto  += f"• *{titulo}*\n  {empresa} · {score}/10\n\n"
        botones.append([
            InlineKeyboardButton(f"✅ Postulé — {titulo[:20]}", callback_data=f"postulada:{oid}"),
            InlineKeyboardButton("✗ Ignorar", callback_data=f"ignorada:{oid}"),
        ])

    markup = InlineKeyboardMarkup(botones)
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)

async def cmd_postuladas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ofertas = obtener_postuladas()
    if not ofertas:
        await update.message.reply_text("Aún no hay postulaciones registradas.")
        return

    nombres_cv = {
        "automatizacion": "Automatización",
        "analista":       "Analista/QA",
        "desarrollador":  "Desarrollador",
        "callcenter":     "Call Center",
        "bodega":         "Bodega",
    }

    texto = f"✅ *{len(ofertas)} postulaciones realizadas*\n{'─'*28}\n\n"
    for o in ofertas[:10]:
        titulo  = o.get("titulo", "")[:35]
        empresa = o.get("empresa", "")[:20]
        cv      = nombres_cv.get(o.get("cv_usado", ""), "—")
        fecha   = o.get("fecha_postulada", "")[:10]
        estado  = o.get("estado", "postulada")
        texto  += f"✅ *{titulo}*\n"
        texto  += f"   {empresa} · CV: {cv} · {fecha}\n"
        texto  += f"   Estado: {estado}\n\n"

    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r    = resumen_del_dia()
    hora = datetime.now().strftime("%H:%M")
    scheduler_activo = ctx.bot_data.get("scheduler_activo", True)
    estado_scheduler = "🟢 Activo" if scheduler_activo else "🔴 Pausado"

    texto = (
        f"📊 *Estado del sistema — {hora}*\n"
        f"{'─'*28}\n"
        f"Scheduler: {estado_scheduler}\n"
        f"Horario: L-V {HORA_INICIO}:00 — {HORA_FIN}:00\n"
        f"Intervalo: cada {INTERVALO_MIN} minutos\n\n"
        f"*Hoy:*\n"
        f"  Encontradas:  {r['encontradas']}\n"
        f"  Relevantes:   {r['relevantes']}\n"
        f"  Postuladas:   {r['postuladas']}\n"
        f"  Pendientes:   {r['pendientes']}\n\n"
        f"*Histórico total:*\n"
        f"  Postuladas:   {r['historico']}\n"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_buscar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Iniciando búsqueda manual... (puede tardar varios minutos)")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, ciclo_busqueda)

async def cmd_pausar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    scheduler = ctx.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.pause()
        ctx.bot_data["scheduler_activo"] = False
        await update.message.reply_text("⏸ Búsquedas pausadas. Usa /reanudar para continuar.")
    else:
        await update.message.reply_text("El scheduler no está activo.")

async def cmd_reanudar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    scheduler = ctx.bot_data.get("scheduler")
    if scheduler:
        scheduler.resume()
        ctx.bot_data["scheduler_activo"] = True
        await update.message.reply_text("▶️ Búsquedas reanudadas.")
    else:
        await update.message.reply_text("El scheduler no está disponible.")

# ─── BOTONES INLINE ───────────────────────────────────────────────────────────

async def manejar_botones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Maneja los botones 'Ya postulé' y 'No me interesa'
    que aparecen en cada notificación de oferta.
    """
    query = update.callback_query
    await query.answer()

    data = query.data  # formato: "postulada:123" o "ignorada:123"
    accion, oferta_id_str = data.split(":")
    oferta_id = int(oferta_id_str)

    nombres_cv = {
        "automatizacion": "Automatización",
        "analista":       "Analista/QA",
        "desarrollador":  "Desarrollador",
        "callcenter":     "Call Center",
        "bodega":         "Bodega",
    }

    if accion == "postulada":
        # Obtener el mejor CV de la oferta para registrarlo
        from database import conectar
        conn, cursor = conectar()
        cursor.execute("SELECT mejor_cv, titulo FROM ofertas WHERE id=?", (oferta_id,))
        fila = cursor.fetchone()
        conn.close()

        if fila:
            cv_usado  = fila["mejor_cv"] or "analista"
            titulo    = fila["titulo"]
            marcar_postulada(oferta_id, cv_usado)
            cv_nombre = nombres_cv.get(cv_usado, cv_usado)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                f"*Postulacion registrada*\n"
                f"_{titulo[:40]}_\n"
                f"CV: {cv_nombre}",
                parse_mode="Markdown"
            )
        else:
            await query.answer("Oferta no encontrada en BD", show_alert=True)

    elif accion == "ignorada":
        cambiar_estado(oferta_id, "ignorada")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✗ Oferta ignorada y archivada.")

# ─── MENSAJES DE TEXTO (voz transcrita) ──────────────────────────────────────

async def manejar_texto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Recibe mensajes de texto libres — incluyendo transcripciones de voz.
    Interpreta comandos naturales como 'qué encontraste hoy' o 'muéstrame las pendientes'.
    """
    texto = update.message.text.lower()

    if any(p in texto for p in ["hoy", "encontraste", "encontró", "del día"]):
        await cmd_hoy(update, ctx)
    elif any(p in texto for p in ["pendiente", "revisar", "sin revisar"]):
        await cmd_pendientes(update, ctx)
    elif any(p in texto for p in ["postul", "apliqué", "aplique"]):
        await cmd_postuladas(update, ctx)
    elif any(p in texto for p in ["busca", "buscar", "busca ahora", "busca ya"]):
        await cmd_buscar(update, ctx)
    elif any(p in texto for p in ["estado", "cómo vas", "como vas", "resumen"]):
        await cmd_estado(update, ctx)
    elif any(p in texto for p in ["pausa", "detén", "detener", "para"]):
        await cmd_pausar(update, ctx)
    else:
        await update.message.reply_text(
            "No entendí ese comando. Prueba:\n"
            "/hoy /pendientes /postuladas /buscar /estado"
        )

# ─── INICIO ───────────────────────────────────────────────────────────────────

def main():
    crear_tablas()

    app = Application.builder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("hoy",       cmd_hoy))
    app.add_handler(CommandHandler("pendientes",cmd_pendientes))
    app.add_handler(CommandHandler("postuladas",cmd_postuladas))
    app.add_handler(CommandHandler("estado",    cmd_estado))
    app.add_handler(CommandHandler("buscar",    cmd_buscar))
    app.add_handler(CommandHandler("pausar",    cmd_pausar))
    app.add_handler(CommandHandler("reanudar",  cmd_reanudar))

    # Botones inline
    app.add_handler(CallbackQueryHandler(manejar_botones))

    # Mensajes de texto libre y voz transcrita
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_texto))

    # Scheduler en background
    scheduler = crear_scheduler()
    scheduler.start()
    app.bot_data["scheduler"]        = scheduler
    app.bot_data["scheduler_activo"] = True

    log.info("Sistema iniciado. Esperando comandos en Telegram...")
    enviar_texto("🟢 *Sistema iniciado*\nBuscando ofertas remotas L-V 08:00–23:00 cada 30 min.")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
