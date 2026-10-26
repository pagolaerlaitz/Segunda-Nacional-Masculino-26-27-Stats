import sqlite3
import json
from datetime import datetime


def fecha_a_iso(texto):
    """'Oct 4, 2026, 8:00:00 PM' -> '2026-10-04 20:00' (texto ordenable). None si no se puede leer."""
    limpio = (texto or "").replace(" ", " ").replace(",", "")
    try:
        return datetime.strptime(limpio, "%b %d %Y %I:%M:%S %p").strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def asegurar_fecha_iso(conexion):
    """Añade a partidos la columna fecha_iso (la fecha en formato ordenable) y rellena la que falte.
    La fecha de la federación es texto en inglés y no se puede ordenar directamente en SQL."""
    columnas = [col[1] for col in conexion.execute("PRAGMA table_info(partidos)")]
    if not columnas:
        return
    if "fecha_iso" not in columnas:
        conexion.execute("ALTER TABLE partidos ADD COLUMN fecha_iso TEXT")
    pendientes = conexion.execute("SELECT id_partido, fecha FROM partidos WHERE fecha_iso IS NULL").fetchall()
    for id_partido, fecha in pendientes:
        conexion.execute("UPDATE partidos SET fecha_iso = ? WHERE id_partido = ?", (fecha_a_iso(fecha), id_partido))
    conexion.commit()


def cargar_datos_relacionales(jornada_asignada="Desconocida", id_externo=None):
    conexion = sqlite3.connect("mi_liga.db")
    conexion.execute("PRAGMA foreign_keys = ON;")
    cursor = conexion.cursor()
    
    # 1. CREAR LAS TABLAS (Con AUTOINCREMENT para generar nuestros propios IDs)
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS equipos (
            id_equipo INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT UNIQUE, 
            nombre_corto TEXT, 
            color TEXT
        );
        CREATE TABLE IF NOT EXISTS jugadores (
            id_jugador INTEGER PRIMARY KEY AUTOINCREMENT, 
            dorsal TEXT, 
            nombre TEXT, 
            id_equipo INTEGER,
            FOREIGN KEY(id_equipo) REFERENCES equipos(id_equipo),
            UNIQUE(nombre, id_equipo)
        );
        CREATE TABLE IF NOT EXISTS partidos (
            id_partido TEXT PRIMARY KEY, id_equipo_local INTEGER, id_equipo_visitante INTEGER,
            fecha TEXT, jornada TEXT, puntos_local INTEGER, puntos_visitante INTEGER,
            id_externo TEXT,
            FOREIGN KEY(id_equipo_local) REFERENCES equipos(id_equipo),
            FOREIGN KEY(id_equipo_visitante) REFERENCES equipos(id_equipo)
        );
        CREATE TABLE IF NOT EXISTS convocatorias (
            id_partido TEXT, id_jugador INTEGER, id_equipo INTEGER, dorsal TEXT, titular BOOLEAN,
            PRIMARY KEY (id_partido, id_jugador),
            FOREIGN KEY(id_partido) REFERENCES partidos(id_partido),
            FOREIGN KEY(id_jugador) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(id_equipo) REFERENCES equipos(id_equipo)
        );
        CREATE TABLE IF NOT EXISTS play_by_play (
            eventUuid TEXT PRIMARY KEY, id_partido TEXT, period INTEGER, min INTEGER, sec INTEGER,
            id_equipo INTEGER, id_jugador INTEGER, idMove INTEGER, move TEXT,
            marcador_local INTEGER, marcador_visitante INTEGER, quinteto_local TEXT, quinteto_visitante TEXT,
            FOREIGN KEY(id_partido) REFERENCES partidos(id_partido),
            FOREIGN KEY(id_equipo) REFERENCES equipos(id_equipo),
            FOREIGN KEY(id_jugador) REFERENCES jugadores(id_jugador)
        );
    ''')

    # Las bases de datos antiguas no tienen la columna id_externo (ID de la URL de la federación)
    columnas_partidos = [col[1] for col in cursor.execute("PRAGMA table_info(partidos)")]
    if "id_externo" not in columnas_partidos:
        cursor.execute("ALTER TABLE partidos ADD COLUMN id_externo TEXT")

    # 2. PROCESAR JSON MAESTRO
    with open("plantillas_prueba.json", "r", encoding="utf-8") as f:
        maestro = json.load(f)
        
    id_partido = str(maestro.get("idMatchIntern", "partido_default"))
    
    # DICCIONARIOS DE MEMORIA PARA TRADUCIR EL ID FALSO DE HOY A NUESTRO ID REAL
    traductor_equipos = {}
    traductor_jugadores = {}
    
    equipos = maestro.get("teams", [])
    if isinstance(equipos, dict): equipos = equipos.values()
    
    # --- PASO A: EQUIPOS Y JUGADORES (Convocados) ---
    # --- PASO A: EQUIPOS Y JUGADORES (Convocados) ---
    for equipo in equipos:
        id_eq_falso = equipo.get("teamIdIntern")
        nombre_eq = equipo.get("name", "Equipo Desconocido").strip()
        
        # --- PARCHE DE PATROCINADORES / CAMBIOS DE NOMBRE ---
        # Si la federación cambia el nombre de un equipo, añade el nombre nuevo aquí
        CORRECCIONES_EQUIPOS = {
            "WHAT´S UP BARAKALDO SALESIANOS": "SALESIANOS"
            # "NUEVO NOMBRE FEDERACION": "TU NOMBRE ORIGINAL",
        }
        nombre_eq = CORRECCIONES_EQUIPOS.get(nombre_eq, nombre_eq)
        # ----------------------------------------------------
        
        # Insertamos si no existe (el UNIQUE evita duplicados por nombre)
        cursor.execute('''
            INSERT OR IGNORE INTO equipos (nombre, nombre_corto, color)
            VALUES (?, ?, ?)
        ''', (nombre_eq, equipo.get("shortName", "UNK"), equipo.get("colorRgb", "#CCCCCC")))
        
        # Obtenemos nuestro ID real autogenerado
        cursor.execute("SELECT id_equipo FROM equipos WHERE nombre = ?", (nombre_eq,))
        id_eq_real = cursor.fetchone()[0]
        
        traductor_equipos[id_eq_falso] = id_eq_real
        
        for jugador in equipo.get("players", []):
            id_jug_falso = jugador.get("actorId")
            dorsal = jugador.get("dorsal")
            
            # Recortamos los apellidos muy largos
            nombre_crudo = jugador.get("name", "").strip()
            partes_nombre = nombre_crudo.split()
            if len(partes_nombre) > 2:
                nombre_final = " ".join(partes_nombre[:-1])
            else:
                nombre_final = nombre_crudo
            
            # Insertamos si no existe (UNIQUE por nombre e id_equipo real)
            cursor.execute('''
                INSERT OR IGNORE INTO jugadores (dorsal, nombre, id_equipo) 
                VALUES (?, ?, ?)
            ''', (dorsal, nombre_final, id_eq_real))
            
            # Si ya existía pero cambió de dorsal en este partido, lo actualizamos
            cursor.execute('''
                UPDATE jugadores SET dorsal = ? WHERE nombre = ? AND id_equipo = ?
            ''', (dorsal, nombre_final, id_eq_real))
            
            # Obtenemos nuestro ID real
            cursor.execute("SELECT id_jugador FROM jugadores WHERE nombre = ? AND id_equipo = ?", (nombre_final, id_eq_real))
            id_jug_real = cursor.fetchone()[0]
            
            traductor_jugadores[id_jug_falso] = id_jug_real

    # --- PASO B: PARTIDO ---
    id_local_falso = maestro.get("localId")
    id_visitante_falso = maestro.get("visitId")
    
    id_local_real = traductor_equipos.get(id_local_falso)
    id_visitante_real = traductor_equipos.get(id_visitante_falso)
    
    cursor.execute('''
        INSERT OR IGNORE INTO partidos (id_partido, id_equipo_local, id_equipo_visitante, fecha, jornada, puntos_local, puntos_visitante)
        VALUES (?, ?, ?, ?, ?, 0, 0)
    ''', (id_partido, id_local_real, id_visitante_real, maestro.get("time", "Desconocida"), jornada_asignada))

    # Guardamos el ID de la URL para que el actualizador sepa que este partido ya está descargado
    if id_externo:
        cursor.execute("UPDATE partidos SET id_externo = ? WHERE id_partido = ?", (id_externo, id_partido))

    # --- PASO C: CONVOCATORIAS ---
    for equipo in equipos:
        id_eq_real = traductor_equipos.get(equipo.get("teamIdIntern"))
        for jugador in equipo.get("players", []):
            id_jug_real = traductor_jugadores.get(jugador.get("actorId"))
            titular = jugador.get("starting") == True
            
            if id_jug_real and id_eq_real:
                cursor.execute('''
                    INSERT OR IGNORE INTO convocatorias (id_partido, id_jugador, id_equipo, dorsal, titular)
                    VALUES (?, ?, ?, ?, ?)
                ''', (id_partido, id_jug_real, id_eq_real, jugador.get("dorsal"), titular))

    # --- PREPARAR QUINTETOS INICIALES ---
    pista_local = set()
    pista_visitante = set()
    
    for equipo in equipos:
        id_eq_falso = equipo.get("teamIdIntern")
        for jugador in equipo.get("players", []):
            if jugador.get("starting") == True:
                id_jug_real = traductor_jugadores.get(jugador.get("actorId"))
                if id_eq_falso == id_local_falso:
                    pista_local.add(id_jug_real)
                elif id_eq_falso == id_visitante_falso:
                    pista_visitante.add(id_jug_real)

    # 3. PROCESAR PLAY-BY-PLAY
    with open("partido_prueba.json", "r", encoding="utf-8") as f:
        jugadas = json.load(f)
        
    puntos_fin_local = 0
    puntos_fin_visitante = 0
    
    for jugada in jugadas:
        id_mov = jugada.get("idMove")
        
        # TRADUCIR EL ID FALSO AL REAL
        id_eq_falso_accion = jugada.get("idTeam")
        id_eq_real_accion = traductor_equipos.get(id_eq_falso_accion)
        
        id_jug_falso_accion = jugada.get("actorId")
        id_jug_real_accion = traductor_jugadores.get(id_jug_falso_accion)
        
        # --- ESCUDO PROTECTOR PARA JUGADORES QUE NO ESTABAN EN LA PLANTILLA ---
        if id_eq_falso_accion and not id_eq_real_accion:
            cursor.execute('''
                INSERT OR IGNORE INTO equipos (nombre, nombre_corto, color) 
                VALUES ('Equipo Genérico', 'UNK', '#CCCCCC')
            ''')
            cursor.execute("SELECT id_equipo FROM equipos WHERE nombre = 'Equipo Genérico'")
            id_eq_real_accion = cursor.fetchone()[0]
            traductor_equipos[id_eq_falso_accion] = id_eq_real_accion
            
        if id_jug_falso_accion and not id_jug_real_accion and id_eq_real_accion:
            nombre_acta = jugada.get("actorName", "Desconocido").strip()
            partes_acta = nombre_acta.split()
            if len(partes_acta) > 2:
                nombre_acta_final = " ".join(partes_acta[:-1])
            else:
                nombre_acta_final = nombre_acta
            
            cursor.execute('''
                INSERT OR IGNORE INTO jugadores (nombre, id_equipo) 
                VALUES (?, ?)
            ''', (nombre_acta_final, id_eq_real_accion))
            cursor.execute("SELECT id_jugador FROM jugadores WHERE nombre = ? AND id_equipo = ?", (nombre_acta_final, id_eq_real_accion))
            id_jug_real_accion = cursor.fetchone()[0]
            traductor_jugadores[id_jug_falso_accion] = id_jug_real_accion
        # ----------------------------------------------------------------------
        
        texto_marcador = jugada.get("score", "0-0")
        if "-" in texto_marcador:
            try:
                m_local, m_visitante = map(int, texto_marcador.split("-"))
                puntos_fin_local, puntos_fin_visitante = m_local, m_visitante 
            except:
                m_local, m_visitante = puntos_fin_local, puntos_fin_visitante
        else:
            m_local, m_visitante = puntos_fin_local, puntos_fin_visitante
            
        # Control de cambios de jugadores en pista
        if id_mov == 112 and id_jug_real_accion: # Entra
            if id_eq_real_accion == id_local_real: pista_local.add(id_jug_real_accion)
            elif id_eq_real_accion == id_visitante_real: pista_visitante.add(id_jug_real_accion)
        elif id_mov == 115 and id_jug_real_accion: # Sale
            if id_eq_real_accion == id_local_real: pista_local.discard(id_jug_real_accion)
            elif id_eq_real_accion == id_visitante_real: pista_visitante.discard(id_jug_real_accion)
            
        # GUARDAMOS LA JUGADA CON LOS IDs INTERNOS
        cursor.execute('''
            INSERT OR IGNORE INTO play_by_play 
            (eventUuid, id_partido, period, min, sec, id_equipo, id_jugador, idMove, move, marcador_local, marcador_visitante, quinteto_local, quinteto_visitante)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            jugada.get("eventUuid"), id_partido, jugada.get("period"), jugada.get("min"), jugada.get("sec"),
            id_eq_real_accion, id_jug_real_accion, id_mov, jugada.get("move"), m_local, m_visitante,
            str(sorted(list(pista_local))), str(sorted(list(pista_visitante)))
        ))

    # 4. ACTUALIZAR MARCADOR FINAL
    cursor.execute('''
        UPDATE partidos SET puntos_local = ?, puntos_visitante = ? WHERE id_partido = ?
    ''', (puntos_fin_local, puntos_fin_visitante, id_partido))
    
    conexion.commit()
    asegurar_fecha_iso(conexion)
    conexion.close()
    print("¡Base de datos alimentada usando IDs internos propios basados en nombres!")

if __name__ == "__main__":
    cargar_datos_relacionales()