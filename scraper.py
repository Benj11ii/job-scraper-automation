import time
import json
import ollama
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from config import PALABRAS_CLAVE, AGENTE_1

TIMEOUT = 20000
PAGINAS_POR_BUSQUEDA = 3

def _crear_navegador(playwright):
    nav = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    ctx = nav.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="es-CL",
    )
    return nav, ctx

def _palabra_a_slug(palabra: str) -> str:
    return palabra.lower().strip().replace(" ", "-")

def _ya_postulada(tarjeta) -> bool:
    tag = tarjeta.query_selector("span.tag.postulated")
    if tag is None:
        return False
    clases = tag.get_attribute("class") or ""
    return "hide" not in clases

def _es_reciente(texto_fecha: str) -> bool:
    """
    Verifica si una oferta es reciente usando dateparser.
    Acepta hasta 3 dias atras. Rechaza fechas absolutas antiguas.
    """
    import dateparser
    import re
    from datetime import datetime, timedelta

    if not texto_fecha or texto_fecha.strip() == "":
        return True

    # Limpiar texto extra como "(actualizada)" o "(editada)"
    texto_limpio = re.sub(r"\(.*?\)", "", texto_fecha).strip()

    fecha = dateparser.parse(
        texto_limpio,
        languages=["es"],
        settings={
            "PREFER_DATES_FROM": "past",
            "RELATIVE_BASE": datetime.now(),
        }
    )

    if not fecha:
        return False  # no reconocido — rechazar

    limite = datetime.now() - timedelta(days=4)
    return fecha >= limite

def _fallback_ollama(html_crudo: str, portal: str) -> list:
    print(f"    Fallback Ollama para {portal}...")
    prompt = f"""Extrae ofertas laborales de este HTML de {portal}.
Responde SOLO con lista JSON sin texto adicional:
[{{"titulo":"","empresa":"","ubicacion":"","salario":"","url":"","descripcion":""}}]
Si no hay ofertas: []
HTML: {html_crudo[:4000]}"""
    try:
        r = ollama.chat(model=AGENTE_1, messages=[{"role":"user","content":prompt}])
        texto = r["message"]["content"].strip()
        i, f = texto.find("["), texto.rfind("]") + 1
        if i == -1: return []
        result = json.loads(texto[i:f])
        print(f"    Fallback extrajo {len(result)} ofertas")
        return result
    except Exception as e:
        print(f"    Fallback falló: {e}")
        return []

def _deduplicar(ofertas: list) -> list:
    vistas, unicas = set(), []
    for o in ofertas:
        url = o.get("url", "")
        if url and url not in vistas:
            vistas.add(url)
            unicas.append(o)
    return unicas

def scrape_computrabajo(palabras: list = None) -> list:
    if palabras is None:
        palabras = PALABRAS_CLAVE[:5]

    ofertas_totales = []

    with sync_playwright() as p:
        nav, ctx = _crear_navegador(p)
        pag = ctx.new_page()

        for palabra in palabras:
            slug = _palabra_a_slug(palabra)
            base_url = f"https://cl.computrabajo.com/trabajo-de-{slug}-en-remoto"

            for num_pag in range(1, PAGINAS_POR_BUSQUEDA + 1):
                url = base_url if num_pag == 1 else f"{base_url}?p={num_pag}"
                print(f"  ComputTrabajo → {url}")

                try:
                    pag.goto(url, timeout=TIMEOUT, wait_until="networkidle")
                    time.sleep(3)

                    if "404" in pag.title() or "not found" in pag.title().lower():
                        print(f"    Sin mas paginas")
                        break

                    encontradas = []

                    try:
                        tarjetas = (
                            pag.query_selector_all("article.box_offer") or
                            pag.query_selector_all("article[data-id]")
                        )
                        print(f"    Tarjetas: {len(tarjetas)}")

                        if not tarjetas:
                            print(f"    Sin tarjetas — fin")
                            break

                        for t in tarjetas[:10]:
                            try:
                                titulo_el   = t.query_selector("h2 a.js-o-link")
                                empresa_el  = t.query_selector("a[offer-grid-article-company-url]")
                                postular_el = t.query_selector("[data-href-offer-apply]")
                                fecha_el    = t.query_selector("p.fs13.fc_aux.mt15")

                                titulo      = titulo_el.inner_text().strip()  if titulo_el  else ""
                                empresa     = empresa_el.inner_text().strip() if empresa_el else ""
                                texto_fecha = fecha_el.inner_text().strip()   if fecha_el   else ""

                                # Fix: limpiar URL de tracking
                                href = titulo_el.get_attribute("href") if titulo_el else ""
                                if href and not href.startswith("http"):
                                    href = "https://cl.computrabajo.com" + href
                                if href and "#" in href:
                                    href = href.split("#")[0]

                                url_postular = (
                                    postular_el.get_attribute("data-href-offer-apply")
                                    if postular_el else ""
                                )

                                postulada_previamente = _ya_postulada(t)

                                # Fix: filtro de antiguedad max 3 dias
                                if not _es_reciente(texto_fecha):
                                    print(f"    Antigua ({texto_fecha}) — saltando")
                                    continue

                                if titulo and href:
                                    encontradas.append({
                                        "url":                   href,
                                        "url_postular":          url_postular,
                                        "portal":                "computrabajo",
                                        "titulo":                titulo,
                                        "empresa":               empresa,
                                        "ubicacion":             "Remoto",
                                        "salario":               "",
                                        "descripcion":           "",
                                        "fecha_publicacion":     texto_fecha,
                                        "postulada_previamente": postulada_previamente,
                                    })

                                    if postulada_previamente:
                                        print(f"    [ya postulada] {titulo[:45]}")

                            except Exception:
                                continue

                    except Exception as e:
                        print(f"    Error selectores: {e}")

                    if not encontradas:
                        html = pag.content()
                        fb = _fallback_ollama(html, "computrabajo")
                        for o in fb:
                            o["portal"] = "computrabajo"
                            o.setdefault("url_postular", "")
                            o.setdefault("ubicacion", "Remoto")
                            o.setdefault("postulada_previamente", False)
                            o.setdefault("fecha_publicacion", "")
                            if not o.get("url"):
                                o["url"] = url + f"#{o.get('titulo','')}"
                        encontradas = fb

                    nuevas  = [o for o in encontradas if not o.get("postulada_previamente")]
                    previas = [o for o in encontradas if o.get("postulada_previamente")]
                    print(f"    Pag {num_pag}: extraidas={len(tarjetas)} | a_verificar_BD={len(nuevas)} | postuladas_portal={len(previas)}")
                    ofertas_totales.extend(encontradas)
                    time.sleep(2)

                except PlaywrightTimeout:
                    print(f"    Timeout pag {num_pag}")
                    break
                except Exception as e:
                    print(f"    Error: {e}")
                    break

        nav.close()

    return _deduplicar(ofertas_totales)

def scrape_indeed(palabras: list = None) -> list:
    if palabras is None:
        palabras = PALABRAS_CLAVE[:5]

    ofertas_totales = []

    with sync_playwright() as p:
        nav, ctx = _crear_navegador(p)
        pag = ctx.new_page()

        for palabra in palabras:
            palabra_url = palabra.replace(" ", "+")

            for num_pag in range(1, PAGINAS_POR_BUSQUEDA + 1):
                start = (num_pag - 1) * 10
                url = f"https://cl.indeed.com/jobs?q={palabra_url}&l=Chile&remotejobs=1&start={start}"
                print(f"  Indeed → pag {num_pag}: {palabra}")

                try:
                    pag.goto(url, timeout=TIMEOUT, wait_until="networkidle")
                    time.sleep(3)

                    encontradas = []

                    try:
                        tarjetas = (
                            pag.query_selector_all(".job_seen_beacon") or
                            pag.query_selector_all("[data-testid='slider_item']")
                        )
                        print(f"    Tarjetas: {len(tarjetas)}")
                        if not tarjetas:
                            break

                        for t in tarjetas[:10]:
                            try:
                                titulo_el  = (
                                    t.query_selector("[data-testid='jobTitle'] a") or
                                    t.query_selector(".jobTitle a") or
                                    t.query_selector("h2 a")
                                )
                                empresa_el = (
                                    t.query_selector("[data-testid='company-name']") or
                                    t.query_selector(".companyName")
                                )
                                salario_el = (
                                    t.query_selector("[data-testid='attribute_snippet_testid']") or
                                    t.query_selector(".salary-snippet")
                                )

                                titulo  = titulo_el.inner_text().strip()  if titulo_el  else ""
                                empresa = empresa_el.inner_text().strip() if empresa_el else ""
                                salario = salario_el.inner_text().strip() if salario_el else ""
                                href    = titulo_el.get_attribute("href") if titulo_el  else ""

                                if href and not href.startswith("http"):
                                    href = "https://cl.indeed.com" + href
                                if href and "#" in href:
                                    href = href.split("#")[0]

                                if titulo and href:
                                    encontradas.append({
                                        "url":                   href,
                                        "url_postular":          "",
                                        "portal":                "indeed",
                                        "titulo":                titulo,
                                        "empresa":               empresa,
                                        "ubicacion":             "Remoto",
                                        "salario":               salario,
                                        "descripcion":           "",
                                        "fecha_publicacion":     "",
                                        "postulada_previamente": False,
                                    })
                            except Exception:
                                continue

                    except Exception as e:
                        print(f"    Error selectores: {e}")

                    if not encontradas:
                        html = pag.content()
                        fb = _fallback_ollama(html, "indeed")
                        for o in fb:
                            o["portal"] = "indeed"
                            o.setdefault("url_postular", "")
                            o.setdefault("ubicacion", "Remoto")
                            o.setdefault("fecha_publicacion", "")
                            o.setdefault("postulada_previamente", False)
                            if not o.get("url"):
                                o["url"] = url + f"#{o.get('titulo','')}"
                        encontradas = fb

                    print(f"    Pag {num_pag}: {len(encontradas)} ofertas")
                    ofertas_totales.extend(encontradas)
                    time.sleep(2)

                except PlaywrightTimeout:
                    print(f"    Timeout pag {num_pag}")
                    break
                except Exception as e:
                    print(f"    Error: {e}")
                    break

        nav.close()

    return _deduplicar(ofertas_totales)

def scrape_getonboard(palabras: list = None) -> list:
    if palabras is None:
        palabras = ["python", "analista datos", "automatizacion", "QA"]

    ofertas_totales = []

    with sync_playwright() as p:
        nav, ctx = _crear_navegador(p)
        pag = ctx.new_page()

        for palabra in palabras:
            palabra_url = palabra.replace(" ", "+")
            url = f"https://www.getonbrd.com/jobs?q={palabra_url}&remote=true"
            print(f"  GetOnBoard → {palabra}")

            try:
                pag.goto(url, timeout=TIMEOUT, wait_until="networkidle")
                time.sleep(2)

                encontradas = []

                try:
                    tarjetas = (
                        pag.query_selector_all("[data-gb-job]") or
                        pag.query_selector_all(".gb-results-list__item")
                    )
                    print(f"    Tarjetas: {len(tarjetas)}")

                    for t in tarjetas[:10]:
                        try:
                            titulo_el  = t.query_selector("h3 a, .gb-results-list__title a")
                            empresa_el = t.query_selector(".gb-results-list__company")
                            salario_el = t.query_selector(".gb-results-list__salary")

                            titulo  = titulo_el.inner_text().strip()  if titulo_el  else ""
                            empresa = empresa_el.inner_text().strip() if empresa_el else ""
                            salario = salario_el.inner_text().strip() if salario_el else ""
                            href    = titulo_el.get_attribute("href") if titulo_el  else ""

                            if href and not href.startswith("http"):
                                href = "https://www.getonbrd.com" + href
                            if href and "#" in href:
                                href = href.split("#")[0]

                            if titulo and href:
                                encontradas.append({
                                    "url":                   href,
                                    "url_postular":          "",
                                    "portal":                "getonboard",
                                    "titulo":                titulo,
                                    "empresa":               empresa,
                                    "ubicacion":             "Remoto",
                                    "salario":               salario,
                                    "descripcion":           "",
                                    "fecha_publicacion":     "",
                                    "postulada_previamente": False,
                                })
                        except Exception:
                            continue

                except Exception as e:
                    print(f"    Error selectores: {e}")

                if not encontradas:
                    html = pag.content()
                    fb = _fallback_ollama(html, "getonboard")
                    for o in fb:
                        o["portal"] = "getonboard"
                        o.setdefault("url_postular", "")
                        o.setdefault("ubicacion", "Remoto")
                        o.setdefault("fecha_publicacion", "")
                        o.setdefault("postulada_previamente", False)
                    encontradas = fb

                print(f"    Resultado: {len(encontradas)} ofertas")
                ofertas_totales.extend(encontradas)
                time.sleep(1)

            except PlaywrightTimeout:
                print(f"    Timeout para '{palabra}'")
            except Exception as e:
                print(f"    Error: {e}")

        nav.close()

    return _deduplicar(ofertas_totales)

def obtener_descripcion(url: str, portal: str) -> str:
    """
    Extrae la capsula de informacion relevante de una oferta.
    Busca marcadores de inicio (requisitos, perfil, etc) y
    marcadores de fin (denunciar, imprimir, etc).
    Completamente dinamico — funciona con ofertas cortas y largas.
    """
    MARCADORES_INICIO = [
        "Descripcion de la oferta",
        "Descripción de la oferta",
        "Perfil requerido",
        "Perfil del cargo",
        "Perfil buscado",
        "Requisitos",
        "Requerimientos",
        "Se solicita",
        "Se requiere",
        "Nos encontramos en busqueda",
        "Nos encontramos en búsqueda",
        "Estamos buscando",
        "Estamos en busqueda",
        "Estamos en búsqueda",
        "Buscamos",
        "Se busca",
        "Sobre el puesto",
        "Acerca del puesto",
        "Objetivo del cargo",
        "Objetivo del rol",
        "Funciones",
        "Responsabilidades",
    ]
    MARCADORES_FIN = [
        "Denunciar empleo",
        "Imprimir",
        "Ofertas similares",
        "Empleos similares",
        "Acerca de ",
        "Sobre la empresa",
        "Recibir ofertas similares",
        "Avisame con ofertas",
        "Avísame con ofertas",
        "Ver todos los avisos",
        "Busquedas relacionadas",
        "Búsquedas relacionadas",
        "Postularme",
    ]
    with sync_playwright() as p:
        nav, ctx = _crear_navegador(p)
        pag = ctx.new_page()
        try:
            pag.goto(url, timeout=TIMEOUT, wait_until="networkidle")
            time.sleep(2)
            texto = pag.inner_text("body")

            # Buscar posicion de inicio
            pos_inicio = -1
            marcador_inicio = ""
            for m in MARCADORES_INICIO:
                pos = texto.find(m)
                if pos != -1:
                    pos_inicio = pos
                    marcador_inicio = m
                    break

            if pos_inicio == -1:
                pos_inicio = 300  # fallback: saltarse menu de navegacion

            # Buscar posicion de fin — debe ser DESPUES del inicio
            pos_fin = len(texto)
            for m in MARCADORES_FIN:
                pos = texto.find(m)
                if pos != -1 and pos > pos_inicio + 100:
                    pos_fin = pos
                    break

            # Extraer capsula dinamica
            capsula = texto[pos_inicio:pos_fin].strip()
            return capsula

        except Exception as e:
            print(f"    Error descripcion: {e}")
            return ""
        finally:
            nav.close()

def buscar_todas(palabras: list = None) -> list:
    print("\n=== Busqueda remota en todos los portales ===")
    todas = []
    print("\n[1/4] ComputTrabajo (remoto)...")
    todas.extend(scrape_computrabajo(palabras))
    print("\n[2/4] Indeed (remoto)...")
    todas.extend(scrape_indeed(palabras))
    print("\n[3/4] GetOnBoard (remoto)...")
    todas.extend(scrape_getonboard())
    print("\n[4/4] Bodega/Aseo (presencial Villarrica/Temuco)...")
    todas.extend(scrape_bodega_presencial())
    resultado = _deduplicar(todas)
    nuevas  = [o for o in resultado if not o.get("postulada_previamente")]
    previas = [o for o in resultado if o.get("postulada_previamente")]
    print(f"\nTotal: {len(resultado)} | A verificar BD: {len(nuevas)} | Postuladas portal: {len(previas)}")
    return resultado


if __name__ == "__main__":
    print("Test scraper — fixes aplicados\n")
    ofertas = scrape_computrabajo(["analista de datos", "python junior"])
    print(f"\n{'='*50}")
    print(f"TOTAL: {len(ofertas)}")
    print('='*50)
    for i, o in enumerate(ofertas[:5], 1):
        print(f"\n[{i}] {o['titulo']}")
        print(f"    Empresa:  {o['empresa']}")
        print(f"    Fecha:    {o.get('fecha_publicacion', '')}")
        print(f"    URL post: {'SI' if o.get('url_postular') else 'NO'}")

def scrape_bodega_presencial(palabras: list = None, ciudades: list = None) -> list:
    """
    Busca ofertas presenciales en Villarrica/Temuco para CV bodega/aseo.
    NO usa filtro remoto — busca por ciudad explícitamente.
    URL: /trabajo-de-{slug}-en-{ciudad}
    """
    from config import PALABRAS_CLAVE_BODEGA, CIUDADES_BODEGA
    if palabras is None:
        palabras = PALABRAS_CLAVE_BODEGA
    if ciudades is None:
        ciudades = CIUDADES_BODEGA

    ofertas_totales = []

    with sync_playwright() as p:
        nav, ctx = _crear_navegador(p)
        pag = ctx.new_page()

        for ciudad in ciudades:
            for palabra in palabras:
                slug_palabra = _palabra_a_slug(palabra)
                slug_ciudad  = _palabra_a_slug(ciudad)
                url = f"https://cl.computrabajo.com/trabajo-de-{slug_palabra}-en-{slug_ciudad}"
                print(f"  Bodega/Presencial → {url}")

                try:
                    pag.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")
                    time.sleep(2)

                    if "404" in pag.title() or "not found" in pag.title().lower():
                        continue

                    encontradas = []
                    tarjetas = (
                        pag.query_selector_all("article.box_offer") or
                        pag.query_selector_all("article[data-id]")
                    )
                    print(f"    Tarjetas: {len(tarjetas)}")

                    for t in tarjetas[:5]:
                        try:
                            titulo_el    = t.query_selector("h2 a.js-o-link")
                            empresa_el   = t.query_selector("a[offer-grid-article-company-url]")
                            ubicacion_el = t.query_selector("p.fs16.fc_base.mt5:not(.dFlex) span")
                            fecha_el     = t.query_selector("p.fs13.fc_aux.mt15")
                            postular_el  = t.query_selector("[data-href-offer-apply]")

                            titulo      = titulo_el.inner_text().strip()    if titulo_el    else ""
                            empresa     = empresa_el.inner_text().strip()   if empresa_el   else ""
                            ubicacion   = ubicacion_el.inner_text().strip() if ubicacion_el else ciudad.title()
                            texto_fecha = fecha_el.inner_text().strip()     if fecha_el     else ""

                            href = titulo_el.get_attribute("href") if titulo_el else ""
                            if href and not href.startswith("http"):
                                href = "https://cl.computrabajo.com" + href
                            if href and "#" in href:
                                href = href.split("#")[0]

                            url_postular = (
                                postular_el.get_attribute("data-href-offer-apply")
                                if postular_el else ""
                            )

                            if not _es_reciente(texto_fecha):
                                continue

                            if titulo and href:
                                encontradas.append({
                                    "url":                   href,
                                    "url_postular":          url_postular,
                                    "portal":                "computrabajo",
                                    "titulo":                titulo,
                                    "empresa":               empresa,
                                    "ubicacion":             ubicacion,
                                    "salario":               "",
                                    "descripcion":           "",
                                    "fecha_publicacion":     texto_fecha,
                                    "postulada_previamente": _ya_postulada(t),
                                    "forzar_cv":             "bodega",
                                })
                        except Exception:
                            continue

                    print(f"    Resultado: {len(encontradas)} ofertas")
                    ofertas_totales.extend(encontradas)
                    time.sleep(1)

                except PlaywrightTimeout:
                    print(f"    Timeout para '{palabra}' en '{ciudad}'")
                except Exception as e:
                    print(f"    Error: {e}")

        nav.close()

    return _deduplicar(ofertas_totales)
