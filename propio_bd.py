import os
import sqlite3
import re
from datetime import datetime

# Se puede apuntar a otra base de datos (por ejemplo una copia de pruebas) con la variable MI_LIGA_BD
RUTA_BD = os.environ.get("MI_LIGA_BD", "mi_liga.db")
NOMBRE_EQUIPO_PROPIO = "ATLETICO SAN SEBASTIAN"

PLAYTYPES = [
    "P&R Handler", "P&R Roller", "Isolation", "Post Up", "Spot Up", "Handoff",
    "Offscreen", "Cut", "Transition", "Putback", "Misc"
]

SISTEMAS = [
    "Llegando", "Trans", "1", "4", "Palma", "Palma Abajo", "Cuernos", "Cuernos Lado", "Puño",
    "Banda 1", "Banda Palma", "Fondo 1", "Fondo 5", "Fondo Puerta"
]

TIPOS_DEFENSA = ["Man", "2-3", "3-2", "1-3-1", "Especial"]
TIPO_DEFENSA_POR_DEFECTO = "Man"

PR_DEFENSAS = ["Show", "Drop", "Under", "Switch", "Ice", "2v1"]

# Faltas con tiros libres: por bonus (sin más datos) o en acción de tiro (se etiqueta como el resto)
TIPOS_FALTA = ["De tiro", "Bonus"]

# Códigos de jugada de la federación
TIROS_CAMPO = (93, 94, 97, 98, 100)
CANASTAS_CAMPO = (93, 94, 100)
TIROS_LIBRES = (92, 96)
TL_ANOTADO = 92
VALOR_CANASTA = {93: 2, 100: 2, 94: 3}
PERDIDA = 106
FALTA_RECIBIDA = 110
# Faltas que pueden mandar al rival a la línea (las técnicas y la falta en ataque no acaban la posesión)
FALTAS_DEFENSIVAS = (159, 160, 161, 162, 166, 565, 571)
# Faltas técnicas: sus libres no pertenecen a ninguna posesión
TECNICAS = (537, 540, 544)
# Eventos que no cambian el desarrollo de la jugada: falta recibida, asistencia, cambios, tiempo muerto y técnicas
EVENTOS_NEUTROS = (110, 107, 112, 115, 113) + TECNICAS

# Columnas comunes a las dos tablas: lo que ya trae el play by play de la federación
COLUMNAS_BASE = """
    eventUuid TEXT PRIMARY KEY,
    id_partido TEXT,
    orden INTEGER,
    period INTEGER, min INTEGER, sec INTEGER,
    id_jugador INTEGER,
    idMove INTEGER, move TEXT,
    marcador_local INTEGER, marcador_visitante INTEGER,
    quinteto_propio TEXT, quinteto_rival TEXT,
    playtype TEXT, playtype_secundario TEXT,
    tipo_defensa TEXT DEFAULT 'Man',
    pr_defense TEXT,
    tipo_falta TEXT,
    puntos INTEGER,
    tiro_x REAL, tiro_y REAL,
"""


def conectar():
    conexion = sqlite3.connect(RUTA_BD)
    conexion.execute("PRAGMA foreign_keys = ON;")
    return conexion


def crear_tablas_propio(conexion):
    """Crea propio_ataque y propio_defensa. Las coordenadas del tiro van en metros:
    x de 0 a 15 (ancho), y de 0 a 14 desde la línea de fondo; el aro está en (7.5, 1.575)."""
    conexion.executescript(f'''
        CREATE TABLE IF NOT EXISTS propio_ataque (
            {COLUMNAS_BASE}
            sistema TEXT,
            pr_handler INTEGER, pr_roller INTEGER, jugador_secundario INTEGER,
            FOREIGN KEY(eventUuid) REFERENCES play_by_play(eventUuid),
            FOREIGN KEY(id_partido) REFERENCES partidos(id_partido),
            FOREIGN KEY(id_jugador) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(pr_handler) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(pr_roller) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(jugador_secundario) REFERENCES jugadores(id_jugador)
        );
        CREATE TABLE IF NOT EXISTS propio_defensa (
            {COLUMNAS_BASE}
            defensor_pr_handler INTEGER, defensor_pr_roller INTEGER, id_defensor INTEGER,
            FOREIGN KEY(eventUuid) REFERENCES play_by_play(eventUuid),
            FOREIGN KEY(id_partido) REFERENCES partidos(id_partido),
            FOREIGN KEY(id_jugador) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(defensor_pr_handler) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(defensor_pr_roller) REFERENCES jugadores(id_jugador),
            FOREIGN KEY(id_defensor) REFERENCES jugadores(id_jugador)
        );
    ''')

    # Las tablas creadas antes de añadir estas columnas no las tienen
    columnas_nuevas = {
        "tipo_defensa": f"TEXT DEFAULT '{TIPO_DEFENSA_POR_DEFECTO}'",
        "pr_defense": "TEXT",
        "tipo_falta": "TEXT",
        "puntos": "INTEGER",
    }
    for tabla in ("propio_ataque", "propio_defensa"):
        columnas = [col[1] for col in conexion.execute(f"PRAGMA table_info({tabla})")]
        for columna, definicion in columnas_nuevas.items():
            if columna not in columnas:
                conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
    conexion.commit()


def obtener_id_equipo_propio(conexion):
    fila = conexion.execute("SELECT id_equipo FROM equipos WHERE nombre = ?", (NOMBRE_EQUIPO_PROPIO,)).fetchone()
    return fila[0] if fila else None


def finales_de_posesion(conexion, id_partido):
    """Devuelve las jugadas que terminan una posesión: tiros de campo, pérdidas y faltas
    que mandan a la línea de tiros libres (sin contar los 2+1, que ya cuentan con la canasta)."""
    eventos = conexion.execute('''
        SELECT rowid, eventUuid, period, min, sec, id_equipo, id_jugador, idMove, move,
               marcador_local, marcador_visitante, quinteto_local, quinteto_visitante
        FROM play_by_play WHERE id_partido = ? ORDER BY rowid
    ''', (id_partido,)).fetchall()
    id_local, id_visitante = conexion.execute(
        "SELECT id_equipo_local, id_equipo_visitante FROM partidos WHERE id_partido = ?", (id_partido,)
    ).fetchone()

    finales = []
    for i, ev in enumerate(eventos):
        rowid, uuid, period, minuto, segundo, id_equipo, id_jugador, id_move, move = ev[:9]
        if id_equipo is None:
            continue

        if id_move in TIROS_CAMPO or id_move == PERDIDA:
            puntos = VALOR_CANASTA.get(id_move, 0)
            if id_move in CANASTAS_CAMPO:
                # 2+1 / 3+1: falta del rival en el mismo instante y tiro libre adicional
                j, siguiente = next(((j, e) for j, e in enumerate(eventos[i + 1:], i + 1)
                                     if e[7] not in EVENTOS_NEUTROS), (None, None))
                if siguiente is not None and siguiente[7] in FALTAS_DEFENSIVAS and siguiente[5] != id_equipo \
                        and siguiente[2:5] == ev[2:5]:
                    puntos += libres_anotados(eventos, j + 1, id_equipo)
            finales.append({"evento": ev, "equipo_ataque": id_equipo, "id_jugador": id_jugador, "puntos": puntos})

        elif id_move in FALTAS_DEFENSIVAS:
            equipo_ataque = id_visitante if id_equipo == id_local else id_local
            # Tanda de libres tras la falta (a veces se anotan unos segundos después). Si todos los libres
            # se explican por faltas técnicas intercaladas, la falta en sí no mandó a la línea.
            n_libres, _, n_tecnicas = tanda_libres(eventos, i + 1, equipo_ataque)
            tira_libres = n_libres > n_tecnicas
            # 2+1: la acción anterior es una canasta del atacante en el mismo instante
            anterior = next((e for e in reversed(eventos[:i]) if e[7] not in EVENTOS_NEUTROS), None)
            es_2_mas_1 = (anterior is not None and anterior[5] == equipo_ataque and anterior[7] in CANASTAS_CAMPO
                          and anterior[2:5] == ev[2:5])
            if tira_libres and not es_2_mas_1:
                # El jugador que termina la posesión es el que recibe la falta
                recibida = next((e for e in eventos[i + 1:] if e[5] == equipo_ataque and e[7] == FALTA_RECIBIDA), None)
                finales.append({
                    "evento": ev,
                    "equipo_ataque": equipo_ataque,
                    "id_jugador": recibida[6] if recibida else None,
                    "puntos": libres_anotados(eventos, i + 1, equipo_ataque),
                })

    return finales, id_local


def tanda_libres(eventos, desde, equipo_ataque):
    """Recorre la tanda de tiros libres del atacante que empieza en la posición `desde`.
    Devuelve (libres lanzados, libres anotados, faltas técnicas intercaladas)."""
    lanzados = anotados = tecnicas = 0
    for e in eventos[desde:]:
        if e[7] in TECNICAS:
            tecnicas += 1
            continue
        if e[7] in EVENTOS_NEUTROS:
            continue
        if e[5] != equipo_ataque or e[7] not in TIROS_LIBRES:
            break
        lanzados += 1
        anotados += e[7] == TL_ANOTADO
    return lanzados, anotados, tecnicas


def libres_anotados(eventos, desde, equipo_ataque):
    """Tiros libres anotados por el atacante en la tanda (incluidos los de una técnica intercalada)."""
    return tanda_libres(eventos, desde, equipo_ataque)[1]


def preparar_partido(conexion, id_partido):
    """Copia los finales de posesión del partido a propio_ataque / propio_defensa.
    Es seguro repetirlo: no toca las filas que ya existen ni sus etiquetas."""
    crear_tablas_propio(conexion)
    id_propio = obtener_id_equipo_propio(conexion)
    finales, id_local = finales_de_posesion(conexion, id_partido)
    cambios_antes = conexion.total_changes

    for final in finales:
        ev = final["evento"]
        rowid, uuid, period, minuto, segundo, _, _, id_move, move, m_local, m_visitante, q_local, q_visitante = ev
        propio_es_local = id_local == id_propio
        quinteto_propio = q_local if propio_es_local else q_visitante
        quinteto_rival = q_visitante if propio_es_local else q_local
        tabla = "propio_ataque" if final["equipo_ataque"] == id_propio else "propio_defensa"

        conexion.execute(f'''
            INSERT OR IGNORE INTO {tabla}
            (eventUuid, id_partido, orden, period, min, sec, id_jugador, idMove, move,
             marcador_local, marcador_visitante, quinteto_propio, quinteto_rival)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (uuid, id_partido, rowid, period, minuto, segundo, final["id_jugador"], id_move, move,
              m_local, m_visitante, quinteto_propio, quinteto_rival))

    if conexion.total_changes > cambios_antes:
        # Ha entrado un partido nuevo: se recolocan las filas en orden cronológico
        ordenar_tablas_propio(conexion)

    # Los puntos salen del play by play: se recalculan siempre (también rellena las filas antiguas)
    for final in finales:
        tabla = "propio_ataque" if final["equipo_ataque"] == id_propio else "propio_defensa"
        conexion.execute(f"UPDATE {tabla} SET puntos = ? WHERE eventUuid = ?", (final["puntos"], final["evento"][1]))
    conexion.commit()


def ordenar_tablas_propio(conexion):
    """Reescribe propio_ataque y propio_defensa para que sus filas queden guardadas en orden:
    partidos por fecha y, dentro de cada partido, jugadas en el orden del play by play.
    Las etiquetas no cambian: solo se reordenan las filas."""
    partidos = conexion.execute("SELECT id_partido, fecha FROM partidos").fetchall()

    def clave_fecha(fila):
        texto = (fila[1] or "").replace(" ", " ").replace(",", "")
        try:
            return datetime.strptime(texto, "%b %d %Y %I:%M:%S %p")
        except ValueError:
            return datetime.max

    posiciones = {id_partido: pos for pos, (id_partido, _) in enumerate(sorted(partidos, key=clave_fecha))}
    conexion.execute("CREATE TEMP TABLE IF NOT EXISTS orden_partidos (id_partido TEXT PRIMARY KEY, pos INTEGER)")
    conexion.execute("DELETE FROM orden_partidos")
    conexion.executemany("INSERT INTO orden_partidos VALUES (?, ?)", posiciones.items())

    for tabla in ("propio_ataque", "propio_defensa"):
        conexion.execute(f"CREATE TEMP TABLE copia_{tabla} AS SELECT * FROM {tabla}")
        conexion.execute(f"DELETE FROM {tabla}")
        conexion.execute(f'''
            INSERT INTO {tabla}
            SELECT c.* FROM copia_{tabla} c
            LEFT JOIN orden_partidos o ON o.id_partido = c.id_partido
            ORDER BY o.pos, c.orden
        ''')
        conexion.execute(f"DROP TABLE copia_{tabla}")
    conexion.execute("DROP TABLE orden_partidos")


def ids_quinteto(texto):
    if not texto:
        return []
    return [int(x) for x in re.findall(r"\d+", str(texto))]


if __name__ == "__main__":
    # Prepara todos los partidos del equipo propio que haya en la base de datos
    conexion = conectar()
    id_propio = obtener_id_equipo_propio(conexion)
    partidos = conexion.execute(
        "SELECT id_partido FROM partidos WHERE ? IN (id_equipo_local, id_equipo_visitante)", (id_propio,)
    ).fetchall()
    for (id_partido,) in partidos:
        preparar_partido(conexion, id_partido)
    # Por si las filas ya existían pero en desorden
    ordenar_tablas_propio(conexion)
    conexion.commit()
    for tabla in ("propio_ataque", "propio_defensa"):
        print(tabla, conexion.execute(
            f"SELECT id_partido, COUNT(*), MIN(rowid) FROM {tabla} GROUP BY id_partido ORDER BY MIN(rowid)").fetchall())
    conexion.close()
