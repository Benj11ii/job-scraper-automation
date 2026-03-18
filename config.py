import os
from dotenv import load_dotenv

load_dotenv()

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("CHAT_ID")

# ─── MODELOS OLLAMA ──────────────────────────────────────────────────────────
AGENTE_0 = "qwen3:4b-instruct"        # clasifica área de la oferta (ultra rápido)
AGENTE_1 = "qwen3:4b-instruct"    # evalúa cada CV vs oferta → score
AGENTE_2 = "qwen3:4b-instruct"  # analiza postulación con el mejor CV

# ─── PARÁMETROS DEL SISTEMA ──────────────────────────────────────────────────
SCORE_MINIMO          = float(os.getenv("SCORE_MINIMO", "7.0"))
CONFIRMAR_POSTULACION = True   # SIEMPRE pedir confirmación antes de postular
GUARDAR_DESCARTADAS   = True   # guardar ofertas bajo el umbral para historial

# ─── HORARIO ─────────────────────────────────────────────────────────────────
HORA_INICIO   = 5
HORA_FIN      = 23
DIAS_SEMANA   = "mon-fri"
INTERVALO_MIN = 30

# ─── PORTALES ────────────────────────────────────────────────────────────────
PORTALES = [
    "https://www.computrabajo.cl",
    "https://cl.indeed.com",
    "https://www.laborum.cl",
    "https://www.trabajando.com/cl",
]

# ─── PALABRAS CLAVE ──────────────────────────────────────────────────────────
PALABRAS_CLAVE = [
    "analista de datos", "automatización procesos", "python developer",
    "analista procesos", "analista calidad", "desarrollador python",
    "business intelligence", "analista KPI", "analista reportería",
    "full stack python", "soporte TI", "analista sistemas",
    "supervisor calidad", "analista operaciones", "coordinador datos",
]

# ─── UBICACIONES ACEPTADAS ───────────────────────────────────────────────────
UBICACIONES = [
    "remoto", "teletrabajo", "trabajo remoto", "home office",
    "Santiago", "Villarrica", "Temuco", "Araucanía",
]

# ─── PRIORIDAD DE CVs (desempate) ────────────────────────────────────────────
# Si dos CVs tienen el mismo score exacto, gana el de menor índice aquí.
# Define qué perfil quieres proyectar con más frecuencia.
PRIORIDAD_CVS = [
    "automatizacion",   # 1° — perfil más diferenciador
    "analista",         # 2°
    "desarrollador",    # 3°
    "callcenter",       # 4°
    "bodega",           # 5° — solo si no hay nada mejor
]

# ─── CVs POR ÁREA DETECTADA ──────────────────────────────────────────────────
# Agente 0 detecta el área → solo se evalúan los CVs relevantes.
# Evita evaluar los 5 siempre. Ahorra tiempo y RAM.
CVS_POR_AREA = {
    "desarrollo":      ["desarrollador", "automatizacion"],
    "datos":           ["analista", "automatizacion"],
    "automatizacion":  ["automatizacion", "analista", "desarrollador"],
    "callcenter":      ["callcenter", "analista"],
    "administrativo":  ["analista", "callcenter"],
    "soporte_ti":      ["desarrollador", "automatizacion"],
    "bodega":          ["bodega"],
    "otro":            ["analista", "callcenter"],  # fallback
}

# ─── REGLA DE POSTULACIÓN ÚNICA ──────────────────────────────────────────────
# Una URL = una sola postulación posible, sin importar cuántos CVs la evalúen.
# El sistema selecciona SOLO el CV con mayor score para el Agente 2.
# En empate exacto de score usa el orden de PRIORIDAD_CVS.
# El Agente 2 nunca recibe más de un CV por oferta.

# ─── ESTADOS DE UNA OFERTA ───────────────────────────────────────────────────
ESTADOS = {
    "nueva":          "encontrada, sin evaluar aún",
    "pendiente":      "evaluada, esperando tu confirmación en Telegram",
    "postulada":      "postulación enviada con éxito",
    "manual":         "requiere acción manual (login, formulario complejo)",
    "descartada":     "todos los CVs bajo el umbral",
    "ignorada":       "marcada por ti como no relevante",
    "sin_respuesta":  "postulaste, sin respuesta aún",
    "en_proceso":     "en entrevistas o proceso activo",
    "rechazada":      "empresa descartó la candidatura",
    "cerrada":        "la oferta ya no está disponible en el portal",
}

# ─── NOTIFICACIONES ──────────────────────────────────────────────────────────
RESUMEN_HORA    = "23:00"   # resumen automático diario
NOTIFICAR_NUEVA = True      # notificar cada oferta nueva en tiempo real
UMBRAL_URGENTE  = 8.5       # score para marcar URGENTE en Telegram

# ─── CVs ─────────────────────────────────────────────────────────────────────

CV_AUTOMATIZACION = """
PERFIL: Especialista en Automatización Inteligente · IA Aplicada · Full Stack Python
Nombre: Benjamín Carmona Vega | Villarrica, Chile | Disponible remoto

PROPUESTA DE VALOR:
Perfil híbrido entre eficiencia operacional y desarrollo de software inteligente.
7 años gestionando KPIs críticos en sectores de alta exigencia, evolucionando hacia
automatización con Python, SQL e IA Generativa. Creador de iasesoria.cl.

STACK: Python · SQL · GAS · HTML · Claude/Gemini/GPT APIs · Ollama · LMStudio
Prompt Engineering (RCTF, CoT, SFT) · Git/GitHub · Excel Avanzado · Power Query
Salesforce · Genesys Cloud · Siebel

LOGROS: +30% productividad con sistema GAS automatizado · +3pts FCR liderando equipos
Integración IA local y cloud para pymes · iasesoria.cl operativo 2025

EXPERIENCIA: Freelance asesor tecnológico (2025) · Banco Estado (2024-2025)
Supervisor Calidad Ventas Técnicas (2023-2024) · Supervisor/Analista Holdtech (2018-2023)

FORMACIÓN: Bootcamp Full Stack Python SENCE (cursando)
Técnico Programación IP San Sebastián (cursando) · Certificación Google TI (2024)
"""

CV_ANALISTA = """
PERFIL: Analista de Calidad y Procesos · Supervisor · Gestión de Datos
Nombre: Benjamín Carmona Vega | Villarrica, Chile | Disponible remoto

PERFIL PROFESIONAL:
Analista con 7 años en Cobranza Resolutiva y Atención al Cliente de alta exigencia.
Especializado en optimizar eficiencia operativa mediante automatización (GAS, SQL)
y gestión basada en datos (KPIs). Experto en QA y cumplimiento normativo.

STACK: GAS · SQL · Power Query · Excel Avanzado · Salesforce · Siebel · BSCS
Genesys Cloud · ZSmart · IA Aplicada (Claude, Gemini, GPT, Ollama)
KPIs: FCR · TMO · EPA · NPS · Auditoría de Calidad (QA)

LOGROS: +30% productividad reportería automatizada · +3pts FCR en plataforma
Análisis datos masivos para monitoreo de calidad en Call Center

EXPERIENCIA: Freelance (2025) · Banco Estado reclamos complejos (2024-2025)
Supervisor Analista Calidad Ventas Técnicas (2023-2024) · Holdtech (2017-2023)

FORMACIÓN: Bootcamp Full Stack Python SENCE (cursando)
Técnico Programación (cursando) · Certificación Google TI · Prevención de Fraude (2024)
"""

CV_DESARROLLADOR = """
PERFIL: Desarrollador Full Stack Python Trainee · Técnico en Programación
Nombre: Benjamín Carmona Vega | Villarrica, Chile | Disponible remoto

PERFIL PROFESIONAL:
Desarrollador orientado a automatización y back-end. Cursando Bootcamp Full Stack
Python y Técnico en Programación. 7 años experiencia en operaciones y QA con
visión analítica para identificar cuellos de botella y convertirlos en código.

LENGUAJES: Python · SQL · Google Apps Script · HTML (aprendizaje activo: Kotlin)
IA & LLMs: Claude · Gemini · GPT · Ollama · LMStudio · Prompt Engineering
DATOS: SQL Server/MySQL · Power Query · Excel Avanzado · Google Sheets
DEVTOOLS: Git/GitHub · Google AI Studio · Jupyter Notebook
CRM: Salesforce · Siebel · BSCS · Genesys Cloud

PROYECTOS: iasesoria.cl (plataforma digitalización pymes, 2025)
Sistema Reportes GAS automatizado (+30% productividad)

EXPERIENCIA: Freelance dev/asesor tecnológico (2025)
Supervisor Analista Calidad (2023-2024) · Holdtech datos/cobranzas (2018-2023)

FORMACIÓN: Bootcamp Full Stack Python SENCE (cursando)
Técnico Programación (cursando) · Certificación Google TI (2024)
"""

CV_CALLCENTER = """
PERFIL: Ejecutivo Atención al Cliente · Call Center · Cobranza Resolutiva
Nombre: Benjamín Carmona Vega | Villarrica, Chile | Disponible remoto/presencial

PERFIL PROFESIONAL:
Profesional con 7 años en atención bancaria, cobranza y plataformas de alta exigencia.
Especialista en resolución al primer contacto (FCR) y reclamos complejos bajo
normativa regulatoria bancaria.

PLATAFORMAS: Salesforce · Siebel · BSCS · Genesys Cloud · ZSmart
KPIs: FCR · NPS · EPA · TMO
HERRAMIENTAS: Google Sheets · Excel · Módulos internos auditoría

LOGROS: FCR sostenido sobre promedio de plataforma · Extensión contratos por resultados
+30% productividad con herramientas seguimiento KPIs
Reclamos bancarios complejos bajo normativa BancoEstado

EXPERIENCIA: Banco Estado ejecutivo reclamos (2024-2025)
Supervisor Cobranzas EPA Holdtech (2020-2023) · Analista Indicadores (2018-2020)
Ejecutivo Multiskill/Encargado Nocturno Holdtech (2017-2018)

FORMACIÓN: Técnico Programación (cursando) · Certificaciones call center y fraude (2024)
Excel SENCE (2021) · Liderazgo equipos SENCE (2021)
"""

CV_BODEGA = """
PERFIL: Reponedor · Auxiliar de Bodega · Carga y Descarga
Nombre: Benjamín Carmona Vega | Villarrica, Chile

PERFIL:
Persona responsable con capacidad física para carga, descarga y reposición.
Experiencia práctica en mantenimiento de orden y limpieza en entornos agrícolas,
instalaciones y servicios. Habilidades de organización y seguimiento de procedimientos.

HABILIDADES: Carga y descarga · Orden y limpieza · Trabajo en equipo
Seguimiento de procedimientos · Responsabilidad y puntualidad

EXPERIENCIA: Reponedor bebestibles CCU/Andina supermercado Molco (2025-2026)
Callcenter e informático múltiples empresas (2017-2025)
Aseo limpieza terrenos (2016) · Auxiliar aseo SIGES CHILE cárcel (2014)
Auxiliar casino Eulen Chile (2012) · Trabajador temporal Floragro (2011)

FORMACIÓN: Educación Media Científico-Humanista (2012)
Certificaciones habilidades blandas y técnicas (2021-2024)
"""

# Diccionario unificado — acceso por clave en el resto del código
CVS = {
    "automatizacion": CV_AUTOMATIZACION,
    "analista":       CV_ANALISTA,
    "desarrollador":  CV_DESARROLLADOR,
    "callcenter":     CV_CALLCENTER,
    "bodega":         CV_BODEGA,
}

# ─── BÚSQUEDA PRESENCIAL PARA CV BODEGA ──────────────────────────────────────
# Estas palabras clave NO usan filtro remoto
# Buscan presencial en Villarrica y Temuco únicamente
PALABRAS_CLAVE_BODEGA = [
    "reponedor",
    "auxiliar de aseo",
    "auxiliar de bodega",
    "operario de bodega",
    "auxiliar aseo",
    "bodega",
    "carga y descarga",
    "limpieza",
]

CIUDADES_BODEGA = [
    "villarrica",
]