import ollama
import json
from config import (
    AGENTE_0, AGENTE_1, AGENTE_2,
    SCORE_MINIMO, PRIORIDAD_CVS, CVS_POR_AREA, CVS
)

def _llamar_ollama(modelo: str, prompt: str) -> str:
    try:
        respuesta = ollama.chat(
            model=modelo,
            messages=[{"role": "user", "content": prompt}]
        )
        return respuesta["message"]["content"].strip()
    except Exception as e:
        print(f"Error llamando a {modelo}: {e}")
        return ""

def _extraer_json(texto: str) -> dict:
    inicio = texto.find("{")
    fin    = texto.rfind("}") + 1
    if inicio == -1 or fin == 0:
        return {}
    try:
        return json.loads(texto[inicio:fin])
    except json.JSONDecodeError:
        return {}

def agente_0_clasificar_area(oferta: dict) -> str:
    prompt = (
        "Clasifica esta oferta laboral en una sola palabra. "
        "Responde SOLO con una de estas palabras exactas sin tildes: "
        "desarrollo, datos, automatizacion, callcenter, administrativo, soporte_ti, bodega, otro\n\n"
        f"Titulo: {oferta.get('titulo', '')}\n"
        f"Descripcion: {oferta.get('descripcion', '')[:300]}\n\n"
        "Responde SOLO la palabra. Sin explicacion. Sin puntuacion."
    )
    area = _llamar_ollama(AGENTE_0, prompt).lower().strip()
    area = area.replace("á","a").replace("é","e").replace("ó","o").replace("ú","u").replace("í","i")
    area = area.split()[0] if area else "otro"
    areas_validas = list(CVS_POR_AREA.keys())
    if area not in areas_validas:
        print(f"  Agente 0 area desconocida '{area}', usando 'otro'")
        area = "otro"
    print(f"  Area detectada: {area}")
    return area

def agente_1_evaluar_cv(oferta: dict, nombre_cv: str, texto_cv: str) -> dict:
    prompt = (
        "Eres un evaluador ESTRICTO de idoneidad laboral en Chile. "
        "Compara el CV con la oferta y asigna un puntaje DIFERENCIADO de 1.0 a 10.0.\n\n"
        f"OFERTA:\n"
        f"Titulo: {oferta.get('titulo', '')}\n"
        f"Empresa: {oferta.get('empresa', '')}\n"
        f"Descripcion: {oferta.get('descripcion', '')[:500]}\n\n"
        f"CV ({nombre_cv}):\n{texto_cv}\n\n"
        "CRITERIOS — se muy especifico:\n"
        "- 9-10: cumple TODOS los requisitos tecnicos mencionados\n"
        "- 7-8:  cumple MAS DEL 60%, experiencia relevante clara\n"
        "- 5-6:  cumple entre 30-60%, perfil relacionado\n"
        "- 3-4:  cumple MENOS DEL 30%, perfil distinto\n"
        "- 1-2:  area completamente diferente\n\n"
        "DESCARTE AUTOMATICO — score 2 o menos si:\n"
        "- Exige ingles avanzado y CV no lo menciona\n"
        "- Area del CV es completamente distinta a la oferta\n"
        "- CV de bodega evaluando oferta tech o viceversa\n\n"
        "Se ESTRICTO. No des 8+ si hay dudas. Diferencia claramente entre CVs.\n\n"
        'Responde SOLO con este JSON sin texto adicional:\n'
        '{"score": 7.2, "razon": "explicacion especifica en maximo 15 palabras"}'
    )
    texto_respuesta = _llamar_ollama(AGENTE_1, prompt)
    resultado = _extraer_json(texto_respuesta)
    score = resultado.get("score", 0)
    if not isinstance(score, (int, float)) or not (1 <= score <= 10):
        score = 0.0
    return {
        "score": round(float(score), 1),
        "razon": resultado.get("razon", "Sin evaluacion disponible")
    }

def agente_2_analizar_postulacion(oferta: dict, nombre_cv: str, texto_cv: str) -> dict:
    prompt = (
        "Eres un asistente de busqueda de empleo en Chile. "
        "Analiza la oferta y el CV. Responde en JSON con esta estructura exacta.\n\n"
        f"OFERTA:\n"
        f"Titulo: {oferta.get('titulo', '')}\n"
        f"Empresa: {oferta.get('empresa', '')}\n"
        f"Descripcion: {oferta.get('descripcion', '')[:600]}\n\n"
        f"CV ({nombre_cv}):\n{texto_cv}\n\n"
        "Extrae de la oferta los 4 requisitos mas importantes.\n"
        "Luego indica cuales cumple el CV con [+] y cuales no con [-].\n"
        "Da un consejo practico de 1 linea para mejorar la postulacion.\n"
        "Para accion usa: postular_directo, requiere_login, o tiene_preguntas\n\n"
        'Responde SOLO con este JSON:\n'
        '{"fortalezas": ["req cumplido 1", "req cumplido 2", "req cumplido 3"], '
        '"brechas": ["req no cumplido 1", "req no cumplido 2"], '
        '"consejo": "consejo practico en 1 linea", '
        '"accion": "postular_directo", '
        '"respuestas_extra": {}}'
    )
    texto_respuesta = _llamar_ollama(AGENTE_2, prompt)
    resultado = _extraer_json(texto_respuesta)
    return {
        "fortalezas":       resultado.get("fortalezas", []),
        "brechas":          resultado.get("brechas", []),
        "consejo":          resultado.get("consejo", ""),
        "accion":           resultado.get("accion", "postular_directo"),
        "respuestas_extra": resultado.get("respuestas_extra", {}),
        "resumen":          "",
    }

def analizar_oferta(oferta: dict, forzar_cv: str = None) -> dict:
    print(f"\nAnalizando: {oferta.get('titulo')} — {oferta.get('empresa')}")
    print("-" * 50)

    # Si viene forzar_cv (ej: bodega presencial), saltar Agente 0
    if forzar_cv and forzar_cv in CVS:
        area = forzar_cv
        cvs_a_evaluar = [forzar_cv]
        print(f"  CV forzado: {forzar_cv} (sin clasificacion)")
    else:
        area = agente_0_clasificar_area(oferta)
        cvs_a_evaluar = CVS_POR_AREA.get(area, CVS_POR_AREA["otro"])
    print(f"  CVs a evaluar: {cvs_a_evaluar}")

    scores  = {}
    razones = {}

    for nombre_cv in cvs_a_evaluar:
        print(f"  Evaluando CV '{nombre_cv}'...")
        evaluacion = agente_1_evaluar_cv(oferta, nombre_cv, CVS[nombre_cv])
        scores[nombre_cv]  = evaluacion["score"]
        razones[nombre_cv] = evaluacion["razon"]
        print(f"    Score: {evaluacion['score']} — {evaluacion['razon'][:60]}...")

    todos_los_scores = {cv: scores.get(cv) for cv in CVS.keys()}

    cvs_que_pasan = {
        nombre: score
        for nombre, score in scores.items()
        if score is not None and score >= SCORE_MINIMO
    }

    if not cvs_que_pasan:
        print(f"  Ningun CV supero el umbral {SCORE_MINIMO}. Descartada.")
        return {
            "scores":      todos_los_scores,
            "mejor_cv":    None,
            "mejor_score": max(scores.values()) if scores else 0,
            "descartada":  True,
            "analisis":    None,
        }

    mejor_cv = max(
        cvs_que_pasan,
        key=lambda nombre: (
            cvs_que_pasan[nombre],
            -PRIORIDAD_CVS.index(nombre) if nombre in PRIORIDAD_CVS else -99
        )
    )
    mejor_score = cvs_que_pasan[mejor_cv]
    print(f"\n  CV ganador: '{mejor_cv}' con score {mejor_score}")

    print(f"  Agente 2 analizando con CV '{mejor_cv}'...")
    analisis = agente_2_analizar_postulacion(oferta, mejor_cv, CVS[mejor_cv])
    print(f"  Accion sugerida: {analisis['accion']}")
    print(f"  Analisis completo.")

    return {
        "scores":      todos_los_scores,
        "razones":     razones,
        "mejor_cv":    mejor_cv,
        "mejor_score": mejor_score,
        "descartada":  False,
        "analisis":    analisis,
    }

if __name__ == "__main__":
    oferta_test = {
        "url":         "https://cl.computrabajo.com/test",
        "portal":      "computrabajo",
        "titulo":      "Analista de Datos",
        "empresa":     "TechCorp Chile",
        "ubicacion":   "Remoto",
        "salario":     "$1.500.000",
        "descripcion": (
            "Buscamos Analista de Datos con Python, SQL y Excel. "
            "Automatizacion de reportes. Experiencia minima 2 anos. "
            "Trabajo remoto. Ingles intermedio deseable."
        ),
    }
    resultado = analizar_oferta(oferta_test)
    print("\n" + "="*50)
    for cv, score in resultado["scores"].items():
        if score is not None:
            print(f"  {cv:20} -> {score}")
    print(f"\nMejor CV:    {resultado['mejor_cv']}")
    print(f"Mejor score: {resultado['mejor_score']}")
    if resultado["analisis"]:
        print(f"\nFortalezas: {resultado['analisis']['fortalezas']}")
        print(f"Brechas:    {resultado['analisis']['brechas']}")
        print(f"Consejo:    {resultado['analisis']['consejo']}")
