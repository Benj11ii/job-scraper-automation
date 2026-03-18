import asyncio
import os
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def _bot() -> Bot:
    return Bot(token=TOKEN)

NOMBRES_CV = {
    "automatizacion": "Automatizacion",
    "analista":       "Analista/QA",
    "desarrollador":  "Desarrollador",
    "callcenter":     "Call Center",
    "bodega":         "Bodega",
}

async def _enviar_oferta_async(oferta: dict, scores: dict, analisis: dict):
    bot = _bot()

    mejor_cv    = oferta.get("mejor_cv", "")
    mejor_score = oferta.get("mejor_score", 0)

    llenos = int(mejor_score)
    barra  = "█" * llenos + "░" * (10 - llenos)

    fecha_pub = oferta.get("fecha_publicacion", "")
    fecha_ext = oferta.get("fecha_encontrada", "")[:10] if oferta.get("fecha_encontrada") else datetime.now().strftime("%Y-%m-%d")
    fecha_val = fecha_pub if fecha_pub else fecha_ext
    fecha_key = "Publicada" if fecha_pub else "Registrada"

    salario     = oferta.get("salario", "").strip()
    salario_val = salario if salario else "No indica sueldo"

    scores_lineas = ""
    for cv, score in scores.items():
        if score is not None:
            marca = ">" if cv == mejor_cv else " "
            scores_lineas += f"  {marca} {NOMBRES_CV.get(cv, cv)}: {score}/10\n"

    fortalezas = analisis.get("fortalezas", [])[:4]
    brechas    = analisis.get("brechas", [])[:3]

    requisitos_lineas = ""
    for f in fortalezas:
        requisitos_lineas += f"  [+] {f}\n"
    for b in brechas:
        requisitos_lineas += f"  [-] {b}\n"

    consejo      = analisis.get("consejo", "")
    consejo_linea = f"\nConsejo: {consejo}" if consejo else ""

    texto = (
        f"*Nueva oferta · {oferta.get('portal','').upper()}*\n"
        f"{'─'*32}\n"
        f"*{oferta.get('titulo', '')}*\n"
        f"`{'Empresa':<10}: {oferta.get('empresa', '')}`\n"
        f"`{'Modalidad':<10}: {oferta.get('ubicacion', 'Remoto')}`\n"
        f"`{'Sueldo':<10}: {salario_val}`\n"
        f"`{fecha_key:<10}: {fecha_val}`\n"
        f"{'─'*32}\n"
        f"`{'Afinidad':<10}: {mejor_score}/10`\n"
        f"`{barra}`\n"
        f"`{'CV usado':<10}: {NOMBRES_CV.get(mejor_cv, mejor_cv)}`\n\n"
        f"*Scores por CV:*\n{scores_lineas}\n"
        f"*Requisitos vs tu perfil:*\n{requisitos_lineas}"
        f"{consejo_linea}"
    )

    url_oferta   = oferta.get("url", "")
    url_postular = oferta.get("url_postular", "")
    oferta_id    = oferta.get("id", 0)
    accion       = analisis.get("accion", "postular_directo")

    botones = [
        [InlineKeyboardButton("Ver oferta", url=url_oferta)],
        [
            InlineKeyboardButton("Ya postule", callback_data=f"postulada:{oferta_id}"),
            InlineKeyboardButton("No me interesa", callback_data=f"ignorada:{oferta_id}"),
        ],
    ]

    markup = InlineKeyboardMarkup(botones)

    await bot.send_message(
        chat_id=CHAT_ID,
        text=texto,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
        disable_web_page_preview=True,
    )

def enviar_oferta(oferta: dict, scores: dict, analisis: dict):
    asyncio.run(_enviar_oferta_async(oferta, scores, analisis))

async def _enviar_resumen_async(resumen: dict):
    bot = _bot()
    hoy = datetime.now().strftime("%d/%m/%Y")
    texto = (
        f"*Resumen del dia — {hoy}*\n"
        f"{'─'*32}\n"
        f"`{'Busquedas':<12}: {resumen.get('busquedas', 0)}`\n"
        f"`{'Encontradas':<12}: {resumen.get('encontradas', 0)}`\n"
        f"`{'Relevantes':<12}: {resumen.get('relevantes', 0)}`\n"
        f"`{'Postuladas':<12}: {resumen.get('postuladas', 0)}`\n"
        f"`{'Pendientes':<12}: {resumen.get('pendientes', 0)}`\n"
        f"`{'Historico':<12}: {resumen.get('historico', 0)}`\n"
    )
    if resumen.get("pendientes", 0) > 0:
        texto += f"\n{resumen['pendientes']} ofertas esperando revision."
    await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode=ParseMode.MARKDOWN)

def enviar_resumen(resumen: dict):
    asyncio.run(_enviar_resumen_async(resumen))

async def _enviar_texto_async(texto: str):
    bot = _bot()
    await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode=ParseMode.MARKDOWN)

def enviar_texto(texto: str):
    asyncio.run(_enviar_texto_async(texto))

def enviar_inicio():
    enviar_texto(
        "*Buscador de trabajo iniciado*\n"
        "Ofertas remotas(Chile) y presenciales en Villarrica L-V 05:00-23:00 cada 30 min\n\n"
        "/hoy — ofertas de hoy\n"
        "/pendientes — por revisar\n"
        "/postuladas — historial\n"
        "/buscar — forzar busqueda\n"
        "/estado — estado del sistema\n"
        "/pausar — detener\n"
        "/reanudar — reanudar"
    )

def enviar_error(mensaje: str):
    enviar_texto(f"*Error del sistema*\n`{mensaje}`")

if __name__ == "__main__":
    print("Probando nuevo formato...")

    oferta_test = {
        "id":                1,
        "titulo":            "Analista QA y Lider QA",
        "empresa":           "Evalua Consultores SpA",
        "portal":            "computrabajo",
        "ubicacion":         "Remoto",
        "salario":           "",
        "url":               "https://cl.computrabajo.com/ejemplo",
        "url_postular":      "https://candidato.cl.computrabajo.com/apply/?oi=ejemplo",
        "mejor_cv":          "desarrollador",
        "mejor_score":       7.5,
        "fecha_publicacion": "Hace 2 dias",
        "fecha_encontrada":  "2026-03-17T10:00:00",
    }

    scores_test = {
        "automatizacion": 7.0,
        "analista":       None,
        "desarrollador":  7.5,
        "callcenter":     None,
        "bodega":         None,
    }

    analisis_test = {
        "fortalezas": [
            "Experiencia en QA operacional y auditorias de calidad",
            "Python y SQL para automatizacion de pruebas",
            "Formacion full stack con logica de negocio aplicada",
            "Uso de Salesforce y Genesys en entornos regulados",
        ],
        "brechas": [
            "Sin experiencia directa liderando equipos QA formales",
            "Formacion tecnica aun en curso",
        ],
        "consejo": "Destacar experiencia en auditoria y KPIs en carta de presentacion",
        "accion":  "postular_directo",
        "resumen": "",
    }

    enviar_oferta(oferta_test, scores_test, analisis_test)
    print("Enviado. Revisa Telegram.")
