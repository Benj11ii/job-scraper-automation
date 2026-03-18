import sqlite3
import json
from datetime import datetime
from config import ESTADOS

DB_PATH = "jobs.db"

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    return conn, cursor

def crear_tablas():
    conn, cursor = conectar()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ofertas (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            url                  TEXT UNIQUE NOT NULL,
            url_postular         TEXT,
            portal               TEXT,
            titulo               TEXT,
            empresa              TEXT,
            ubicacion            TEXT,
            salario              TEXT,
            descripcion          TEXT,
            fecha_publicacion    TEXT,
            score_automatizacion REAL,
            score_analista       REAL,
            score_desarrollador  REAL,
            score_callcenter     REAL,
            score_bodega         REAL,
            mejor_cv             TEXT,
            mejor_score          REAL,
            cv_usado             TEXT,
            estado               TEXT DEFAULT 'nueva',
            notas                TEXT,
            fecha_encontrada     TEXT,
            fecha_postulada      TEXT,
            fecha_actualizacion  TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_eventos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            oferta_id INTEGER,
            evento    TEXT,
            detalle   TEXT,
            fecha     TEXT,
            FOREIGN KEY (oferta_id) REFERENCES ofertas(id)
        )
    """)
    conn.commit()
    conn.close()
    print("Base de datos lista.")

def guardar_oferta(datos: dict) -> int | None:
    conn, cursor = conectar()
    try:
        cursor.execute("""
            INSERT INTO ofertas (
                url, url_postular, portal, titulo, empresa,
                ubicacion, salario, descripcion, fecha_publicacion,
                estado, fecha_encontrada, fecha_actualizacion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'nueva', ?, ?)
        """, (
            datos["url"],
            datos.get("url_postular", ""),
            datos.get("portal", ""),
            datos.get("titulo", ""),
            datos.get("empresa", ""),
            datos.get("ubicacion", ""),
            datos.get("salario", ""),
            datos.get("descripcion", ""),
            datos.get("fecha_publicacion", ""),
            datetime.now().isoformat(),
            datetime.now().isoformat(),
        ))
        conn.commit()
        oferta_id = cursor.lastrowid
        registrar_evento(oferta_id, "encontrada", f"Portal: {datos.get('portal')}")
        return oferta_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def existe_por_titulo_empresa(titulo: str, empresa: str) -> bool:
    """
    Deduplicacion secundaria — detecta si ya existe una oferta
    con el mismo titulo y empresa aunque la URL sea diferente.
    Resuelve el problema de Indeed que cambia URLs con tracking.
    """
    if not titulo or not empresa:
        return False
    conn, cursor = conectar()
    cursor.execute(
        "SELECT id FROM ofertas WHERE titulo=? AND empresa=?",
        (titulo.strip(), empresa.strip())
    )
    existe = cursor.fetchone() is not None
    conn.close()
    return existe

def guardar_scores(oferta_id: int, scores: dict, mejor_cv: str, mejor_score: float):
    conn, cursor = conectar()
    cursor.execute("""
        UPDATE ofertas SET
            score_automatizacion = ?,
            score_analista       = ?,
            score_desarrollador  = ?,
            score_callcenter     = ?,
            score_bodega         = ?,
            mejor_cv             = ?,
            mejor_score          = ?,
            fecha_actualizacion  = ?
        WHERE id = ?
    """, (
        scores.get("automatizacion"),
        scores.get("analista"),
        scores.get("desarrollador"),
        scores.get("callcenter"),
        scores.get("bodega"),
        mejor_cv,
        mejor_score,
        datetime.now().isoformat(),
        oferta_id,
    ))
    conn.commit()
    conn.close()
    registrar_evento(oferta_id, "evaluada",
                     f"Mejor CV: {mejor_cv} score {mejor_score}")

def marcar_postulada(oferta_id: int, cv_usado: str):
    conn, cursor = conectar()
    cursor.execute("""
        UPDATE ofertas SET
            estado              = 'postulada',
            cv_usado            = ?,
            fecha_postulada     = ?,
            fecha_actualizacion = ?
        WHERE id = ?
    """, (cv_usado, datetime.now().isoformat(), datetime.now().isoformat(), oferta_id))
    conn.commit()
    conn.close()
    registrar_evento(oferta_id, "postulada", f"CV: {cv_usado}")

def cambiar_estado(oferta_id: int, nuevo_estado: str, notas: str = ""):
    if nuevo_estado not in ESTADOS:
        print(f"Estado '{nuevo_estado}' no valido")
        return
    conn, cursor = conectar()
    cursor.execute("""
        UPDATE ofertas SET
            estado              = ?,
            notas               = ?,
            fecha_actualizacion = ?
        WHERE id = ?
    """, (nuevo_estado, notas, datetime.now().isoformat(), oferta_id))
    conn.commit()
    conn.close()
    registrar_evento(oferta_id, nuevo_estado, notas)

def existe_url(url: str) -> bool:
    conn, cursor = conectar()
    cursor.execute("SELECT id FROM ofertas WHERE url = ?", (url,))
    existe = cursor.fetchone() is not None
    conn.close()
    return existe

def obtener_ofertas_hoy() -> list:
    hoy = datetime.now().strftime("%Y-%m-%d")
    conn, cursor = conectar()
    cursor.execute("""
        SELECT * FROM ofertas
        WHERE fecha_encontrada LIKE ?
        ORDER BY mejor_score DESC
    """, (f"{hoy}%",))
    filas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return filas

def obtener_pendientes() -> list:
    conn, cursor = conectar()
    cursor.execute("""
        SELECT * FROM ofertas WHERE estado = 'pendiente'
        ORDER BY mejor_score DESC
    """)
    filas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return filas

def obtener_postuladas() -> list:
    conn, cursor = conectar()
    cursor.execute("""
        SELECT * FROM ofertas WHERE estado = 'postulada'
        ORDER BY fecha_postulada DESC
    """)
    filas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return filas

def resumen_del_dia() -> dict:
    hoy = datetime.now().strftime("%Y-%m-%d")
    conn, cursor = conectar()
    cursor.execute("SELECT COUNT(*) FROM ofertas WHERE fecha_encontrada LIKE ?", (f"{hoy}%",))
    total_encontradas = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM ofertas
        WHERE fecha_encontrada LIKE ? AND mejor_score >= 7.0
    """, (f"{hoy}%",))
    total_relevantes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ofertas WHERE fecha_postulada LIKE ?", (f"{hoy}%",))
    total_postuladas = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ofertas WHERE estado = 'pendiente'")
    total_pendientes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ofertas WHERE estado = 'postulada'")
    total_historico = cursor.fetchone()[0]
    conn.close()
    return {
        "encontradas": total_encontradas,
        "relevantes":  total_relevantes,
        "postuladas":  total_postuladas,
        "pendientes":  total_pendientes,
        "historico":   total_historico,
        "busquedas":   0,
    }

def registrar_evento(oferta_id: int, evento: str, detalle: str = ""):
    conn, cursor = conectar()
    cursor.execute("""
        INSERT INTO log_eventos (oferta_id, evento, detalle, fecha)
        VALUES (?, ?, ?, ?)
    """, (oferta_id, evento, detalle, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def ver_historial(oferta_id: int) -> list:
    conn, cursor = conectar()
    cursor.execute("""
        SELECT evento, detalle, fecha FROM log_eventos
        WHERE oferta_id = ? ORDER BY fecha ASC
    """, (oferta_id,))
    eventos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return eventos

if __name__ == "__main__":
    crear_tablas()
    print("BD lista y schema actualizado.")
