from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from config import HORA_INICIO, HORA_FIN, DIAS_SEMANA, INTERVALO_MIN, PALABRAS_CLAVE
from scraper import buscar_todas, obtener_descripcion
from analyzer import analizar_oferta
from database import guardar_oferta, guardar_scores, marcar_postulada, cambiar_estado, existe_url, existe_por_titulo_empresa, resumen_del_dia
from notifier import enviar_oferta, enviar_resumen, enviar_texto, enviar_error

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── TRABAJO PRINCIPAL ────────────────────────────────────────────────────────

def ciclo_busqueda():
    """
    Se ejecuta cada 30 minutos L-V entre 08:00 y 23:00.
    1. Scraping de todos los portales
    2. Por cada oferta nueva → analizar con los 3 agentes
    3. Si pasa el umbral → notificar a Telegram
    4. Guardar todo en SQLite
    """
    ahora = datetime.now().strftime("%H:%M")
    log.info(f"Iniciando ciclo de búsqueda — {ahora}")

    try:
        # Paso 1: scraping
        ofertas = buscar_todas()
        nuevas  = 0

        for oferta in ofertas:
            # Saltar si ya está en la base de datos
            if existe_url(oferta["url"]):
                continue
            if existe_por_titulo_empresa(oferta.get("titulo",""), oferta.get("empresa","")):
                continue

            # Saltar si ya fue postulada previamente (detectado por scraper)
            if oferta.get("postulada_previamente"):
                oferta_id = guardar_oferta(oferta)
                if oferta_id:
                    cambiar_estado(oferta_id, "postulada", "Postulada antes del sistema")
                continue

            # Paso 2: obtener descripcion completa
            try:
                oferta["descripcion"] = obtener_descripcion(oferta["url"], oferta["portal"])
            except Exception as e:
                log.warning(f"Sin descripcion: {e}")
                oferta["descripcion"] = ""

            # Paso 3: guardar oferta nueva
            oferta_id = guardar_oferta(oferta)
            if not oferta_id:
                continue
            nuevas += 1

            # Paso 4: analizar con agentes
            try:
                resultado = analizar_oferta(oferta, forzar_cv=oferta.get("forzar_cv"))
            except Exception as e:
                log.error(f"Error analizando {oferta['titulo']}: {e}")
                enviar_error(f"Error analizando: {oferta['titulo'][:40]}")
                continue

            scores      = resultado["scores"]
            mejor_cv    = resultado["mejor_cv"]
            mejor_score = resultado["mejor_score"]

            # Guardar scores en la BD
            guardar_scores(oferta_id, scores, mejor_cv or "", mejor_score)

            # Paso 4: si fue descartada, cambiar estado y seguir
            if resultado["descartada"]:
                cambiar_estado(oferta_id, "descartada",
                               f"Score máximo: {mejor_score}")
                log.info(f"Descartada: {oferta['titulo']} (score {mejor_score})")
                continue

            # Paso 5: notificar a Telegram
            oferta["id"]          = oferta_id
            oferta["mejor_cv"]    = mejor_cv
            oferta["mejor_score"] = mejor_score

            try:
                enviar_oferta(oferta, scores, resultado["analisis"])
                cambiar_estado(oferta_id, "pendiente", "Notificada a Telegram")
                log.info(f"Notificada: {oferta['titulo']} — {mejor_cv} {mejor_score}")
            except Exception as e:
                log.error(f"Error notificando: {e}")
                enviar_error(f"Error notificando: {oferta['titulo'][:40]}")

        log.info(f"Ciclo completado — {nuevas} ofertas nuevas procesadas")

    except Exception as e:
        log.error(f"Error en ciclo de búsqueda: {e}")
        enviar_error(f"Error en ciclo: {str(e)[:100]}")


def ciclo_resumen():
    """Se ejecuta a las 23:00 todos los días L-V."""
    log.info("Enviando resumen diario...")
    try:
        resumen = resumen_del_dia()
        enviar_resumen(resumen)
    except Exception as e:
        log.error(f"Error en resumen: {e}")


# ─── CONFIGURACIÓN DEL SCHEDULER ─────────────────────────────────────────────

def crear_scheduler() -> BackgroundScheduler:
    """
    Crea y configura el scheduler con dos jobs:
    1. ciclo_busqueda — cada 30 min, L-V, 08:00-23:00
    2. ciclo_resumen  — cada día L-V a las 23:00
    """
    scheduler = BackgroundScheduler(timezone="America/Santiago")

    # Job 1: búsqueda cada 30 minutos en horario laboral
    scheduler.add_job(
    ciclo_busqueda,
    trigger=CronTrigger(
        day_of_week=DIAS_SEMANA,
        hour=f"{HORA_INICIO}-{HORA_FIN}",
        minute=f"0/{INTERVALO_MIN}",
        timezone="America/Santiago",
    ),
    id="busqueda",
    name="Búsqueda de ofertas",
    max_instances=1,
    misfire_grace_time=300,
    coalesce=True,        # si se perdieron ciclos, ejecutar solo uno
    replace_existing=True,
)

    # Job 2: resumen diario a las 23:00
    scheduler.add_job(
        ciclo_resumen,
        trigger=CronTrigger(
            day_of_week=DIAS_SEMANA,
            hour=23,
            minute=0,
            timezone="America/Santiago",
        ),
        id="resumen",
        name="Resumen diario",
        max_instances=1,
    )

    # Job 3: limpieza semanal cada lunes 07:00
    scheduler.add_job(
        limpiar_bd_antigua,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=7,
            minute=0,
            timezone="America/Santiago",
        ),
        id="limpieza",
        name="Limpieza BD semanal",
        max_instances=1,
    )
    log.info("Scheduler configurado. Próxima búsqueda al siguiente intervalo programado.")
    return scheduler



def limpiar_bd_antigua():
    """Elimina ofertas descartadas/ignoradas con mas de 7 dias. Corre cada lunes."""
    from datetime import datetime, timedelta
    from database import conectar
    conn, cursor = conectar()
    fecha_limite = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute("""
        DELETE FROM ofertas
        WHERE fecha_encontrada < ?
        AND estado IN ('descartada', 'ignorada', 'cerrada')
    """, (fecha_limite,))
    eliminadas = cursor.rowcount
    conn.commit()
    conn.close()
    log.info(f"BD limpiada: {eliminadas} ofertas antiguas eliminadas")

def forzar_busqueda():
    """
    Ejecuta una búsqueda inmediata fuera del horario programado.
    La llama el comando /buscar de Telegram.
    """
    log.info("Búsqueda forzada por comando /buscar")
    enviar_texto("🔍 Iniciando búsqueda manual...")
    ciclo_busqueda()


# ─── TEST ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Probando scheduler — ejecutando UN ciclo de búsqueda ahora...\n")
    print("(esto tarda varios minutos porque scraping + Ollama corren completos)\n")
    ciclo_busqueda()
    print("\nCiclo completado. Revisa Telegram y jobs.db")
