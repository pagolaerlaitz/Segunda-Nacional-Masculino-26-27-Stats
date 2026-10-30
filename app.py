import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import base64
import os
import re
import html
import altair as alt
import plotly.graph_objects as go
from types import SimpleNamespace

import seccion_cuartos
import seccion_partidos
import seccion_propio
from alimentar_bd import asegurar_fecha_iso

# 1. Configuración de página a ANCHO COMPLETO
st.set_page_config(page_title="Segunda Nacional Masculino 2026-27: Scouting", layout="wide")


@st.cache_resource
def preparar_base_datos():
    """Una vez por arranque: garantiza la columna fecha_iso, que usan los filtros de 'Últimos 4 partidos'."""
    conexion = sqlite3.connect("mi_liga.db")
    asegurar_fecha_iso(conexion)
    conexion.close()


preparar_base_datos()

# Tooltip con la definición de cada estadística al pasar el cursor por su nombre
st.markdown("""
<style>
.stat-tip { position: relative; cursor: help; border-bottom: 1px dotted rgba(255, 255, 255, 0.5); }
.stat-tip-texto {
    visibility: hidden; opacity: 0; transition: opacity 0.15s;
    position: absolute; left: 0; top: calc(100% + 6px); z-index: 1000;
    width: max-content; max-width: 280px; white-space: normal; pointer-events: none;
    background-color: #1A1A1A; color: #E5E5E5; border: 1px solid #F97316; border-radius: 6px;
    padding: 8px 10px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
    font-size: 0.8rem; font-weight: normal; font-style: normal; line-height: 1.35;
    text-transform: none; letter-spacing: normal; text-align: left;
}
.stat-tip:hover .stat-tip-texto { visibility: visible; opacity: 1; }
</style>
""", unsafe_allow_html=True)

# Definiciones de equipo (también valen para las tablas On/Off de jugadores y quintetos)
DEFINICIONES_STATS = {
    # Tradicionales
    'Puntos a favor': "Puntos anotados (T2 × 2 + T3 × 3 + TL).",
    'Puntos en contra': "Puntos recibidos del rival.",
    'Rebotes Defensivos': "Rebotes capturados en la propia canasta.",
    'Rebotes Ofensivos': "Rebotes capturados en la canasta rival, tras un tiro fallado propio.",
    'Rebotes totales': "Rebotes defensivos + ofensivos.",
    'Asistencias': "Pases que terminan directamente en canasta.",
    'Pérdidas': "Posesiones perdidas sin llegar a tirar.",
    'Recuperaciones': "Balones robados al rival.",
    'Tapones': "Tiros del rival taponados.",
    'T2 intentados': "Tiros de 2 puntos lanzados.",
    'T2 anotados': "Tiros de 2 puntos convertidos.",
    '%T2': "Porcentaje de acierto en tiros de 2 (anotados / intentados).",
    'T3 intentados': "Triples lanzados.",
    'T3 anotados': "Triples convertidos.",
    '%T3': "Porcentaje de acierto en triples (anotados / intentados).",
    'TL intentados': "Tiros libres lanzados.",
    'TL anotados': "Tiros libres convertidos.",
    '%TL': "Porcentaje de acierto en tiros libres (anotados / intentados).",
    'Faltas recibidas': "Faltas que le han hecho los rivales.",
    'Faltas cometidas': "Faltas cometidas, de cualquier tipo.",
    # Avanzadas
    'Ritmo': "Posesiones por cada 40 minutos.",
    'Plays': "Oportunidades de anotar por cada 40 minutos: como el ritmo, pero sin restar los rebotes ofensivos "
             "(FGA + 0,44·FTA + TOV). Es de cada equipo: no tiene por qué coincidir con el rival.",
    'Offensive Rating': "Puntos anotados por cada 100 posesiones.",
    'Defensive Rating': "Puntos recibidos por cada 100 posesiones. Cuanto más bajo, mejor.",
    'Net Rating': "Offensive Rating − Defensive Rating: diferencia de puntos por cada 100 posesiones.",
    'eFG%': "Tiro de campo efectivo: como el % de tiro, pero el triple vale 1,5 veces un tiro de 2.",
    'TS%': "Tiro verdadero: eficiencia anotadora incluyendo triples y tiros libres.",
    'FTr': "Tiros libres intentados por cada tiro de campo intentado.",
    '2PA%': "Porcentaje de los tiros de campo que son de 2.",
    '3PA%': "Porcentaje de los tiros de campo que son triples.",
    '2PAr': "Porcentaje de los tiros de campo que son de 2.",
    '3PAr': "Porcentaje de los tiros de campo que son triples.",
    'DREB%': "Porcentaje de los rebotes defensivos disponibles que se capturan.",
    'OREB%': "Porcentaje de los rebotes ofensivos disponibles que se capturan.",
    'REB%': "Porcentaje de todos los rebotes disponibles que se capturan.",
    'TOV%': "Pérdidas por cada 100 posesiones. Cuanto más bajo, mejor.",
    'AST / TO ratio': "Asistencias por cada pérdida.",
    'AST%': "Porcentaje de las canastas de campo que llegan tras una asistencia.",
}

# Definiciones individuales: amplían o sustituyen a las de equipo cuando el significado cambia
DEFINICIONES_STATS_JUGADOR = {
    'Diferencial Offensive Rating': "Offensive Rating del equipo con el jugador en pista menos sin él.",
    'Diferencial Defensive Rating': "Defensive Rating del equipo con el jugador en pista menos sin él. Negativo es mejor.",
    'Diferencial Net Rating': "Net Rating del equipo con el jugador en pista menos sin él.",
    'Minutos Totales': "Minutos jugados en total.",
    'Minutos por partido': "Minutos jugados por partido disputado.",
    '% Minutos': "Porcentaje de los minutos de su equipo (en los partidos que ha jugado) que ha estado en pista.",
    'Rating Anotación': "Nota de 0 a 10 según sus percentiles en Puntos p100 (50%), TS% (40%) y %USG (10%).",
    'Rating Rebote': "Nota de 0 a 10 según sus percentiles en DREB%, OREB% y REB%.",
    'Rating Cuidado de Balón': "Nota de 0 a 10 según sus percentiles en TOV% (70%) y AST% (30%).",
    'Puntos totales': "Puntos anotados en total.",
    'Puntos por partido': "Puntos anotados por partido disputado.",
    'Puntos p100': "Puntos anotados por cada 100 posesiones de su equipo con él en pista.",
    '2PA%': "Porcentaje de sus tiros de campo que son de 2.",
    '3PA%': "Porcentaje de sus tiros de campo que son triples.",
    '2PAr': "Porcentaje de sus tiros de campo que son de 2.",
    '3PAr': "Porcentaje de sus tiros de campo que son triples.",
    '%USG': "Uso: porcentaje de las posesiones de su equipo, con él en pista, que termina él (tiro, tiros libres o pérdida).",
    'PPP': "Puntos por cada posesión que termina él.",
    'RD pp': "Rebotes defensivos por partido.",
    'RD p100': "Rebotes defensivos por cada 100 posesiones de su equipo con él en pista.",
    'DREB%': "Porcentaje de los rebotes defensivos disponibles, con él en pista, que captura él.",
    'RO pp': "Rebotes ofensivos por partido.",
    'RO p100': "Rebotes ofensivos por cada 100 posesiones de su equipo con él en pista.",
    'OREB%': "Porcentaje de los rebotes ofensivos disponibles, con él en pista, que captura él.",
    'RT pp': "Rebotes totales por partido.",
    'RT p100': "Rebotes totales por cada 100 posesiones de su equipo con él en pista.",
    'REB%': "Porcentaje de todos los rebotes disponibles, con él en pista, que captura él.",
    'Asistencias pp': "Asistencias por partido.",
    'Asistencias p100': "Asistencias por cada 100 posesiones de su equipo con él en pista.",
    'AST%': "Porcentaje de las canastas de sus compañeros, con él en pista, que asiste él.",
    'Pérdidas pp': "Pérdidas por partido. Cuanto más bajo, mejor.",
    'Pérdidas p100': "Pérdidas por cada 100 posesiones de su equipo con él en pista. Cuanto más bajo, mejor.",
    'TOV%': "Pérdidas por cada 100 posesiones que termina él. Cuanto más bajo, mejor.",
    'AST / TO': "Asistencias por cada pérdida.",
    'Rating Defensa': "Nota de 0 a 10 según sus percentiles en STL% (50%) y BLK% (50%).",
    'STL pp': "Robos (recuperaciones) por partido.",
    'STL p100': "Robos por cada 100 posesiones de su equipo con él en pista.",
    'STL%': "Porcentaje de las posesiones del rival, con él en pista, que acaban en un robo suyo.",
    'BLK pp': "Tapones por partido.",
    'BLK p100': "Tapones por cada 100 posesiones de su equipo con él en pista.",
    'BLK%': "Porcentaje de los tiros de campo del rival, con él en pista, que tapona.",
}

def definicion_stat(nombre, jugador=False):
    if jugador and nombre in DEFINICIONES_STATS_JUGADOR:
        return DEFINICIONES_STATS_JUGADOR[nombre]
    return DEFINICIONES_STATS.get(nombre)

def etiqueta_stat(nombre, jugador=False, texto=None):
    """Nombre de la estadística con su definición como tooltip (HTML)."""
    texto = texto if texto is not None else nombre
    definicion = definicion_stat(nombre, jugador)
    if not definicion:
        return texto
    return f"<span class='stat-tip'>{texto}<span class='stat-tip-texto'>{html.escape(definicion)}</span></span>"

# Inicialización de estado de navegación
if 'menu_principal' not in st.session_state:
    st.session_state.menu_principal = "Inicio"
if 'submenu_liga' not in st.session_state:
    st.session_state.submenu_liga = 'Rankings'
if 'equipo_seleccionado' not in st.session_state:
    st.session_state.equipo_seleccionado = None
if 'jugador_seleccionado' not in st.session_state:
    st.session_state.jugador_seleccionado = None

# MANEJO DE ENLACES HTML (Parámetros URL)
if "jugador_id" in st.query_params and "equipo_id" in st.query_params:
    st.session_state.jugador_seleccionado = int(st.query_params["jugador_id"])
    st.session_state.equipo_seleccionado = int(st.query_params["equipo_id"])
    st.session_state.menu_principal = "Liga"
    st.session_state.submenu_liga = "Equipos"
    st.query_params.clear()

# Tarjetas de la lista de partidos: ?partido=<id>
if "partido" in st.query_params:
    st.session_state.menu_principal = "Partidos"
    st.session_state.partido_seleccionado = st.query_params["partido"]
    st.query_params.clear()

# Tarjetas de la portada: ?seccion=Propio / ?seccion=Liga
if st.query_params.get("seccion") in ("Propio", "Liga", "Clasificación", "Partidos"):
    st.session_state.menu_principal = st.query_params["seccion"]
    st.query_params.clear()

# 2. Funciones de Base de Datos y Assets
@st.cache_data
def obtener_escudo_base64(nombre_corto):
    ruta = f"assets/ESCUDO_{nombre_corto}.png"
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            datos = f.read()
            return base64.b64encode(datos).decode()
    return None

@st.cache_data
def obtener_foto_jugador_base64(nombre_jugador):
    nombre_archivo = str(nombre_jugador).replace(" ", "_")
    ruta = f"assets/{nombre_archivo}.png"
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            datos = f.read()
            return base64.b64encode(datos).decode()
    return None

@st.cache_data
def cargar_partidos():
    try:
        conexion = sqlite3.connect("mi_liga.db")
        query = """
            SELECT p.id_partido, p.fecha, p.jornada,
                   el.nombre AS local_nombre, p.puntos_local AS local_score,
                   ev.nombre AS visitante_nombre, p.puntos_visitante AS visitante_score
            FROM partidos p
            LEFT JOIN equipos el ON el.id_equipo = p.id_equipo_local
            LEFT JOIN equipos ev ON ev.id_equipo = p.id_equipo_visitante
        """
        df = pd.read_sql(query, conexion)
        conexion.close()

        # La fecha viene como texto ("Oct 4, 2026, 8:00:00 PM"), así que la ordenamos ya convertida
        fecha_limpia = df['fecha'].str.replace(' ', ' ').str.replace(',', '')
        df['fecha_dt'] = pd.to_datetime(fecha_limpia, format='%b %d %Y %I:%M:%S %p', errors='coerce')
        return df.sort_values('fecha_dt', ascending=False).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error al cargar partidos: {e}")
        return pd.DataFrame()

@st.cache_data
def cargar_equipos():
    try:
        conexion = sqlite3.connect("mi_liga.db")
        query = "SELECT id_equipo, nombre, nombre_corto, color FROM equipos WHERE id_equipo != 0 ORDER BY nombre ASC"
        df = pd.read_sql(query, conexion)
        conexion.close()
        return df
    except Exception:
        return pd.DataFrame()

def cargar_plantilla(id_equipo):
    try:
        conexion = sqlite3.connect("mi_liga.db")
        id_eq = int(id_equipo) 
        query = "SELECT id_jugador, dorsal, nombre FROM jugadores WHERE id_equipo = ?"
        df = pd.read_sql(query, conexion, params=(id_eq,))
        conexion.close()
        
        if not df.empty:
            df['dorsal_num'] = pd.to_numeric(df['dorsal'], errors='coerce')
            df = df.sort_values(by=['dorsal_num', 'nombre'], na_position='last')
        return df
    except Exception as e:
        st.error(f"Error de base de datos al cargar plantilla: {e}") 
        return pd.DataFrame()

@st.cache_data
def obtener_info_basica_jugador(id_jugador, id_equipo):
    try:
        conexion = sqlite3.connect("mi_liga.db")
        q_jug = "SELECT nombre, dorsal FROM jugadores WHERE id_jugador = ?"
        df_jug = pd.read_sql(q_jug, conexion, params=(int(id_jugador),))
        
        q_eq = "SELECT nombre, nombre_corto, color FROM equipos WHERE id_equipo = ?"
        df_eq = pd.read_sql(q_eq, conexion, params=(int(id_equipo),))
        
        q_pbp = """
            SELECT pb.id_partido, pb.quinteto_local, pb.quinteto_visitante, p.id_equipo_local 
            FROM play_by_play pb 
            JOIN partidos p ON pb.id_partido = p.id_partido 
            WHERE p.id_equipo_local = ? OR p.id_equipo_visitante = ?
        """
        df_pbp = pd.read_sql(q_pbp, conexion, params=(int(id_equipo), int(id_equipo)))
        conexion.close()
        
        pj = 0
        if not df_pbp.empty:
            def extraer_ids(q_str):
                if pd.isna(q_str): return []
                return [int(x) for x in re.findall(r'\d+', str(q_str))]

            def jugo(row):
                q = row['quinteto_local'] if row['id_equipo_local'] == int(id_equipo) else row['quinteto_visitante']
                ids = extraer_ids(q)
                return int(id_jugador) in ids

            df_pbp['jugo'] = df_pbp.apply(jugo, axis=1)
            pj = df_pbp[df_pbp['jugo']]['id_partido'].nunique()
            
        return {
            "nombre": df_jug.iloc[0]['nombre'] if not df_jug.empty else "Desconocido",
            "dorsal": df_jug.iloc[0]['dorsal'] if not df_jug.empty else "-",
            "equipo_nombre": df_eq.iloc[0]['nombre'] if not df_eq.empty else "",
            "equipo_corto": df_eq.iloc[0]['nombre_corto'] if not df_eq.empty else "",
            "equipo_color": df_eq.iloc[0]['color'] if not df_eq.empty else "#262626",
            "pj": pj
        }
    except Exception as e:
        st.error(f"Error cargando info jugador: {e}")
        return {"nombre": "", "dorsal": "", "equipo_nombre": "", "equipo_corto": "", "equipo_color": "#262626", "pj": 0}

@st.cache_data
def calcular_stats_avanzadas_liga(ultimos_n=None):
    try:
        conexion = sqlite3.connect("mi_liga.db")
        
        cte_limit = f"WHERE fp.rn <= {ultimos_n}" if ultimos_n else ""
        cte = """
            WITH TeamGames AS (
                SELECT id_equipo_local as id_equipo, id_partido, puntos_visitante as puntos_en_contra, fecha_iso AS fecha FROM partidos
                UNION ALL
                SELECT id_equipo_visitante as id_equipo, id_partido, puntos_local as puntos_en_contra, fecha_iso AS fecha FROM partidos
            ),
            FiltroPartidos AS (
                SELECT id_equipo, id_partido, puntos_en_contra,
                       ROW_NUMBER() OVER (PARTITION BY id_equipo ORDER BY fecha DESC) as rn
                FROM TeamGames
            )
        """
        
        query_partidos = f"""
            {cte}
            SELECT 
                fp.id_equipo, COUNT(DISTINCT fp.id_partido) as partidos_jugados, SUM(fp.puntos_en_contra) as puntos_en_contra,
                SUM(40 + CASE WHEN m.max_period > 4 THEN (m.max_period - 4) * 5 ELSE 0 END) as minutos_jugados
            FROM FiltroPartidos fp
            LEFT JOIN (SELECT id_partido, CAST(MAX(period) AS INTEGER) as max_period FROM play_by_play GROUP BY id_partido) m ON fp.id_partido = m.id_partido
            {cte_limit}
            GROUP BY fp.id_equipo
        """
        df_partidos = pd.read_sql(query_partidos, conexion)

        query_team = f"""
            {cte}
            SELECT pb.id_equipo,
                SUM(CASE WHEN pb.idMove IN (93, 100) THEN 1 ELSE 0 END) as T2_anotados,
                SUM(CASE WHEN pb.idMove IN (93, 100, 97) THEN 1 ELSE 0 END) as T2_intentados,
                SUM(CASE WHEN pb.idMove = 94 THEN 1 ELSE 0 END) as T3_anotados,
                SUM(CASE WHEN pb.idMove IN (94, 98) THEN 1 ELSE 0 END) as T3_intentados,
                SUM(CASE WHEN pb.idMove = 92 THEN 1 ELSE 0 END) as TL_anotados,
                SUM(CASE WHEN pb.idMove IN (92, 96) THEN 1 ELSE 0 END) as TL_intentados,
                SUM(CASE WHEN pb.idMove = 104 THEN 1 ELSE 0 END) as DREB,
                SUM(CASE WHEN pb.idMove = 101 THEN 1 ELSE 0 END) as OREB,
                SUM(CASE WHEN pb.idMove = 107 THEN 1 ELSE 0 END) as Asistencias,
                SUM(CASE WHEN pb.idMove = 106 THEN 1 ELSE 0 END) as Pérdidas
            FROM play_by_play pb
            INNER JOIN FiltroPartidos fp ON pb.id_equipo = fp.id_equipo AND pb.id_partido = fp.id_partido
            {cte_limit}
            GROUP BY pb.id_equipo
        """
        df_team = pd.read_sql(query_team, conexion)

        query_opp = f"""
            {cte}
            SELECT fp.id_equipo,
                SUM(CASE WHEN pb.idMove IN (93, 100, 94) AND pb.id_equipo != fp.id_equipo THEN 1 ELSE 0 END) as opp_FGM,
                SUM(CASE WHEN pb.idMove IN (93, 100, 97, 94, 98) AND pb.id_equipo != fp.id_equipo THEN 1 ELSE 0 END) as opp_FGA,
                SUM(CASE WHEN pb.idMove IN (92, 96) AND pb.id_equipo != fp.id_equipo THEN 1 ELSE 0 END) as opp_TL_intentados,
                SUM(CASE WHEN pb.idMove = 104 AND pb.id_equipo != fp.id_equipo THEN 1 ELSE 0 END) as opp_DREB,
                SUM(CASE WHEN pb.idMove = 101 AND pb.id_equipo != fp.id_equipo THEN 1 ELSE 0 END) as opp_OREB,
                SUM(CASE WHEN pb.idMove = 106 AND pb.id_equipo != fp.id_equipo THEN 1 ELSE 0 END) as opp_Pérdidas
            FROM FiltroPartidos fp
            JOIN play_by_play pb ON fp.id_partido = pb.id_partido
            {cte_limit}
            GROUP BY fp.id_equipo
        """
        df_opp = pd.read_sql(query_opp, conexion)
        conexion.close()

        df = pd.merge(df_team, df_partidos, on='id_equipo', how='inner')
        df = pd.merge(df, df_opp, on='id_equipo', how='inner')

        df['FGM'] = df['T2_anotados'] + df['T3_anotados']
        df['FGA'] = df['T2_intentados'] + df['T3_intentados']
        df['Puntos'] = (df['T2_anotados'] * 2) + (df['T3_anotados'] * 3) + df['TL_anotados']
        df['REB'] = df['DREB'] + df['OREB']
        df['opp_REB'] = df['opp_DREB'] + df['opp_OREB']

        df['Team_Poss'] = df['FGA'] + (0.44 * df['TL_intentados']) + df['Pérdidas'] - df['OREB']
        df['Opp_Poss'] = df['opp_FGA'] + (0.44 * df['opp_TL_intentados']) + df['opp_Pérdidas'] - df['opp_OREB']
        df['Posesiones_Totales'] = ((df['Team_Poss'] + df['Opp_Poss']) / 2)

        df['Ritmo'] = ((df['Posesiones_Totales'] / df['minutos_jugados'].replace(0, 1)) * 40).round(1)
        # Plays: oportunidades propias de anotar por 40 minutos (sin restar rebotes ofensivos ni promediar con el rival)
        df['Plays'] = (((df['FGA'] + 0.44 * df['TL_intentados'] + df['Pérdidas']) / df['minutos_jugados'].replace(0, 1)) * 40).round(1)
        df['Offensive Rating'] = ((df['Puntos'] / df['Posesiones_Totales'].replace(0,pd.NA)) * 100).round(1)
        df['Defensive Rating'] = ((df['puntos_en_contra'] / df['Posesiones_Totales'].replace(0,pd.NA)) * 100).round(1)
        df['Net Rating'] = (df['Offensive Rating'] - df['Defensive Rating']).round(1)
        df['eFG%'] = (((df['FGM'] + 0.5 * df['T3_anotados']) / df['FGA'].replace(0,pd.NA)) * 100).round(1)
        df['TS%'] = ((df['Puntos'] / (2 * (df['FGA'] + 0.44 * df['TL_intentados'])).replace(0,pd.NA)) * 100).round(1)
        df['FTr'] = (df['TL_intentados'] / df['FGA'].replace(0,pd.NA)).round(3)
        df['2PA%'] = ((df['T2_intentados'] / df['FGA'].replace(0,pd.NA)) * 100).round(1)
        df['3PA%'] = ((df['T3_intentados'] / df['FGA'].replace(0,pd.NA)) * 100).round(1)
        df['DREB%'] = ((df['DREB'] / (df['DREB'] + df['opp_OREB']).replace(0,pd.NA)) * 100).round(1)
        df['OREB%'] = ((df['OREB'] / (df['OREB'] + df['opp_DREB']).replace(0,pd.NA)) * 100).round(1)
        df['REB%'] = ((df['REB'] / (df['REB'] + df['opp_REB']).replace(0,pd.NA)) * 100).round(1)
        df['TOV%'] = ((df['Pérdidas'] / df['Posesiones_Totales'].replace(0,pd.NA)) * 100).round(1)
        df['AST / TO ratio'] = (df['Asistencias'] / df['Pérdidas'].replace(0,pd.NA)).round(2)
        df['AST%'] = ((df['Asistencias'] / df['FGM'].replace(0,pd.NA)) * 100).round(1)

        invertir_rank = ['Defensive Rating', 'TOV%']
        categorias = ['Ritmo', 'Plays', 'Offensive Rating', 'Defensive Rating', 'Net Rating', 'eFG%', 'TS%', 'FTr', '2PA%', '3PA%', 'DREB%', 'OREB%', 'REB%', 'TOV%', 'AST / TO ratio', 'AST%']
        
        for col in categorias:
            if col in df.columns:
                ascendente = True if col in invertir_rank else False
                df[f'{col}_rank'] = df[col].rank(ascending=ascendente, method='min').astype('Int64')
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data
def calcular_stats_individuales_liga(ultimos_n=None, periodo=None):
    """`periodo`: None (partido completo), 1-4 (un cuarto) u "OT" (prórrogas)."""
    try:
        conexion = sqlite3.connect("mi_liga.db")
        if periodo is None:
            filtro_periodo = ""
        elif periodo == "OT":
            filtro_periodo = "AND pb.period > 4"
        else:
            filtro_periodo = f"AND pb.period = {int(periodo)}"

        # 1. Filtro Partidos Válidos
        cte_limit = f"WHERE rn <= {ultimos_n}" if ultimos_n else ""
        query_valid = f"""
            WITH PartidosEquipo AS (
                SELECT id_equipo_local as id_equipo, id_partido, fecha_iso AS fecha FROM partidos
                UNION ALL
                SELECT id_equipo_visitante as id_equipo, id_partido, fecha_iso AS fecha FROM partidos
            ),
            RankedPartidos AS (
                SELECT id_equipo, id_partido, ROW_NUMBER() OVER (PARTITION BY id_equipo ORDER BY fecha DESC) as rn
                FROM PartidosEquipo
            )
            SELECT id_equipo, id_partido FROM RankedPartidos {cte_limit}
        """
        df_valid = pd.read_sql(query_valid, conexion)

        # 2. Volumen Base (Individual)
        query_pbp = f"SELECT pb.id_partido, pb.id_equipo, pb.id_jugador, pb.idMove FROM play_by_play pb WHERE pb.id_jugador IS NOT NULL {filtro_periodo}"
        df_pbp = pd.read_sql(query_pbp, conexion)
        df_pbp = df_pbp.merge(df_valid, on=['id_equipo', 'id_partido'], how='inner')

        move_map = {
            'T2_anotados': [93, 100], 'T2_intentados': [93, 100, 97],
            'T3_anotados': [94], 'T3_intentados': [94, 98],
            'TL_anotados': [92], 'TL_intentados': [92, 96],
            'Rebotes_Defensivos': [104], 'Rebotes_Ofensivos': [101],
            'Asistencias': [107], 'Pérdidas': [106],
            'Recuperaciones': [103], 'Tapones': [102]
        }

        for stat, moves in move_map.items():
            df_pbp[stat] = df_pbp['idMove'].isin(moves).astype(int)

        cols_to_sum = list(move_map.keys())
        df_indiv = df_pbp.groupby(['id_jugador', 'id_equipo'])[cols_to_sum].sum().reset_index()

        # 3. STATS EXACTAS EN PISTA Y DIFERENCIALES (Advanced Stats Base)
        query_all_pbp = f"""
            SELECT pb.id_partido, pb.idMove, pb.id_equipo, pb.quinteto_local, pb.quinteto_visitante,
                   p.id_equipo_local, p.id_equipo_visitante
            FROM play_by_play pb
            JOIN partidos p ON pb.id_partido = p.id_partido
            WHERE pb.id_equipo IS NOT NULL {filtro_periodo}
        """
        df_all_pbp = pd.read_sql(query_all_pbp, conexion)

        def extraer_ids(q_str):
            if pd.isna(q_str): return []
            return [int(x) for x in re.findall(r'\d+', str(q_str))]

        df_all_pbp['q_loc'] = df_all_pbp['quinteto_local'].apply(extraer_ids)
        df_all_pbp['q_vis'] = df_all_pbp['quinteto_visitante'].apply(extraer_ids)

        df_all_pbp['is_FGA'] = df_all_pbp['idMove'].isin([93, 100, 97, 94, 98]).astype(int)
        df_all_pbp['is_FGM'] = df_all_pbp['idMove'].isin([93, 100, 94]).astype(int)
        df_all_pbp['is_T3M'] = df_all_pbp['idMove'].eq(94).astype(int)
        df_all_pbp['is_TLM'] = df_all_pbp['idMove'].eq(92).astype(int)
        df_all_pbp['is_FTA'] = df_all_pbp['idMove'].isin([92, 96]).astype(int)
        df_all_pbp['is_TOV'] = df_all_pbp['idMove'].eq(106).astype(int)
        df_all_pbp['is_OREB'] = df_all_pbp['idMove'].eq(101).astype(int)
        df_all_pbp['is_DREB'] = df_all_pbp['idMove'].eq(104).astype(int)
        df_all_pbp['Puntos'] = (df_all_pbp['is_FGM'] - df_all_pbp['is_T3M']) * 2 + df_all_pbp['is_T3M'] * 3 + df_all_pbp['is_TLM']

        # Team On-Court events
        df_team_events = df_all_pbp.copy()
        df_team_events['jugadores'] = np.where(df_team_events['id_equipo'] == df_team_events['id_equipo_local'], df_team_events['q_loc'], df_team_events['q_vis'])
        df_team_events = df_team_events.explode('jugadores').dropna(subset=['jugadores'])
        df_team_events['id_jugador'] = df_team_events['jugadores'].astype(int)
        df_team_events = df_team_events.merge(df_valid, on=['id_equipo', 'id_partido'], how='inner')
        team_on_stats = df_team_events.groupby(['id_jugador', 'id_equipo'])[['is_FGA', 'is_FGM', 'is_FTA', 'is_TOV', 'is_OREB', 'is_DREB', 'Puntos']].sum().rename(columns=lambda x: 'team_' + x).reset_index()

        # Opponent On-Court events
        df_opp_events = df_all_pbp.copy()
        df_opp_events['id_equipo_opp'] = np.where(df_opp_events['id_equipo'] == df_opp_events['id_equipo_local'], df_opp_events['id_equipo_visitante'], df_opp_events['id_equipo_local'])
        df_opp_events['jugadores_opp'] = np.where(df_opp_events['id_equipo'] == df_opp_events['id_equipo_local'], df_opp_events['q_vis'], df_opp_events['q_loc'])
        df_opp_events = df_opp_events.explode('jugadores_opp').dropna(subset=['jugadores_opp'])
        df_opp_events['id_jugador'] = df_opp_events['jugadores_opp'].astype(int)
        df_opp_events = df_opp_events.drop(columns=['id_equipo']).rename(columns={'id_equipo_opp': 'id_equipo'})
        df_opp_events = df_opp_events.merge(df_valid, on=['id_equipo', 'id_partido'], how='inner')
        opp_on_stats = df_opp_events.groupby(['id_jugador', 'id_equipo'])[['is_FGA', 'is_FGM', 'is_FTA', 'is_TOV', 'is_OREB', 'is_DREB', 'Puntos']].sum().rename(columns=lambda x: 'opp_' + x).reset_index()

        df_final = df_indiv.merge(team_on_stats, on=['id_jugador', 'id_equipo'], how='left').fillna(0)
        df_final = df_final.merge(opp_on_stats, on=['id_jugador', 'id_equipo'], how='left').fillna(0)

        # Team Totals for differentials
        df_team_totals_base = df_all_pbp.copy()
        df_team_totals_base = df_team_totals_base.merge(df_valid, on=['id_equipo', 'id_partido'], how='inner')
        team_totals = df_team_totals_base.groupby('id_equipo')[['is_FGA', 'is_FTA', 'is_TOV', 'is_OREB', 'Puntos']].sum().rename(columns=lambda x: 'total_team_' + x).reset_index()

        df_opp_totals_base = df_all_pbp.copy()
        df_opp_totals_base['id_equipo_opp'] = np.where(df_opp_totals_base['id_equipo'] == df_opp_totals_base['id_equipo_local'], df_opp_totals_base['id_equipo_visitante'], df_opp_totals_base['id_equipo_local'])
        df_opp_totals_base = df_opp_totals_base.drop(columns=['id_equipo']).rename(columns={'id_equipo_opp': 'id_equipo'})
        df_opp_totals_base = df_opp_totals_base.merge(df_valid, on=['id_equipo', 'id_partido'], how='inner')
        opp_totals = df_opp_totals_base.groupby('id_equipo')[['is_FGA', 'is_FTA', 'is_TOV', 'is_OREB', 'Puntos']].sum().rename(columns=lambda x: 'total_opp_' + x).reset_index()

        df_final = df_final.merge(team_totals, on='id_equipo', how='left').fillna(0)
        df_final = df_final.merge(opp_totals, on='id_equipo', how='left').fillna(0)

        # 4. CÁLCULO CRONOLÓGICO DE MINUTOS REALES Y CONVOCATORIAS
        query_time = f"""
            SELECT pb.id_partido, pb.period, pb.min, pb.sec,
                   pb.quinteto_local, pb.quinteto_visitante,
                   p.id_equipo_local, p.id_equipo_visitante
            FROM play_by_play pb
            JOIN partidos p ON pb.id_partido = p.id_partido
            WHERE 1 = 1 {filtro_periodo}
        """
        df_time = pd.read_sql(query_time, conexion)
        conexion.close()

        if df_time.empty: return df_final

        df_time['min'] = df_time['min'].fillna(0).astype(int)
        df_time['sec'] = df_time['sec'].fillna(0).astype(int)
        df_time['tiempo_restante'] = df_time['min'] * 60 + df_time['sec']
        df_time = df_time.sort_values(['id_partido', 'period', 'tiempo_restante'], ascending=[True, True, False])
        df_time['tiempo_siguiente'] = df_time.groupby(['id_partido', 'period'])['tiempo_restante'].shift(-1).fillna(0)
        df_time['segundos_jugados'] = (df_time['tiempo_restante'] - df_time['tiempo_siguiente']).clip(lower=0)

        df_time['q_loc'] = df_time['quinteto_local'].apply(extraer_ids)
        df_time['q_vis'] = df_time['quinteto_visitante'].apply(extraer_ids)

        df_loc = df_time[['id_partido', 'id_equipo_local', 'q_loc', 'segundos_jugados']].rename(columns={'id_equipo_local': 'id_equipo', 'q_loc': 'jugadores'})
        df_vis = df_time[['id_partido', 'id_equipo_visitante', 'q_vis', 'segundos_jugados']].rename(columns={'id_equipo_visitante': 'id_equipo', 'q_vis': 'jugadores'})
        
        df_minutos = pd.concat([df_loc, df_vis], ignore_index=True)
        df_minutos = df_minutos.explode('jugadores').dropna(subset=['jugadores'])
        df_minutos['id_jugador'] = df_minutos['jugadores'].astype(int)
        df_minutos = df_minutos.merge(df_valid, on=['id_equipo', 'id_partido'], how='inner')

        df_team_min = df_minutos.groupby(['id_equipo', 'id_partido'])['segundos_jugados'].sum().reset_index()
        df_team_min['seg_partido'] = df_team_min['segundos_jugados'] / 5.0
        
        df_player_games = df_minutos[['id_jugador', 'id_equipo', 'id_partido']].drop_duplicates()
        df_player_avail_time = df_player_games.merge(df_team_min[['id_equipo', 'id_partido', 'seg_partido']], on=['id_equipo', 'id_partido'])
        df_player_avail_time = df_player_avail_time.groupby(['id_jugador', 'id_equipo'])['seg_partido'].sum().reset_index(name='segundos_equipo_disponibles')

        df_resumen_min = df_minutos.groupby(['id_jugador', 'id_equipo']).agg(
            segundos_totales=('segundos_jugados', 'sum'),
            PJ=('id_partido', 'nunique')
        ).reset_index()

        df_resumen_min = df_resumen_min.merge(df_player_avail_time, on=['id_jugador', 'id_equipo'], how='left')
        df_resumen_min['Minutos Totales'] = df_resumen_min['segundos_totales'] / 60.0
        df_resumen_min['Minutos por partido'] = df_resumen_min['Minutos Totales'] / df_resumen_min['PJ'].replace(0, 1)
        df_resumen_min['% Minutos'] = (df_resumen_min['segundos_totales'] / df_resumen_min['segundos_equipo_disponibles'].replace(0, 1)) * 100

        # 5. MERGE FINAL Y CÁLCULOS AVANZADOS
        df_final = df_final.merge(df_resumen_min, on=['id_jugador', 'id_equipo'], how='outer').fillna(0)

        df_final['FGA'] = df_final['T2_intentados'] + df_final['T3_intentados']
        df_final['FGM'] = df_final['T2_anotados'] + df_final['T3_anotados']
        df_final['FTA'] = df_final['TL_intentados']
        df_final['TOV'] = df_final['Pérdidas']
        df_final['AST'] = df_final['Asistencias']
        df_final['DREB'] = df_final['Rebotes_Defensivos']
        df_final['OREB'] = df_final['Rebotes_Ofensivos']
        df_final['REB'] = df_final['DREB'] + df_final['OREB']
        
        team_poss_on = df_final['team_is_FGA'] + 0.44 * df_final['team_is_FTA'] + df_final['team_is_TOV'] - df_final['team_is_OREB']
        opp_poss_on = df_final['opp_is_FGA'] + 0.44 * df_final['opp_is_FTA'] + df_final['opp_is_TOV'] - df_final['opp_is_OREB']
        poss_on = (team_poss_on + opp_poss_on) / 2
        
        team_poss_on_safe = team_poss_on.replace(0, pd.NA)
        poss_on_safe = poss_on.replace(0, pd.NA)

        df_final['Puntos totales'] = df_final['T2_anotados']*2 + df_final['T3_anotados']*3 + df_final['TL_anotados']
        df_final['Puntos por partido'] = df_final['Puntos totales'] / df_final['PJ'].replace(0, 1)
        df_final['Puntos p100'] = (df_final['Puntos totales'] / team_poss_on_safe) * 100

        df_final['%T2'] = (df_final['T2_anotados'] / df_final['T2_intentados'].replace(0, pd.NA)) * 100
        df_final['2PA%'] = (df_final['T2_intentados'] / df_final['FGA'].replace(0, pd.NA)) * 100
        df_final['%T3'] = (df_final['T3_anotados'] / df_final['T3_intentados'].replace(0, pd.NA)) * 100
        df_final['3PA%'] = (df_final['T3_intentados'] / df_final['FGA'].replace(0, pd.NA)) * 100
        df_final['%TL'] = (df_final['TL_anotados'] / df_final['TL_intentados'].replace(0, pd.NA)) * 100
        df_final['FTr'] = df_final['FTA'] / df_final['FGA'].replace(0, pd.NA)
        
        df_final['eFG%'] = ((df_final['FGM'] + 0.5 * df_final['T3_anotados']) / df_final['FGA'].replace(0, pd.NA)) * 100
        df_final['TS%'] = (df_final['Puntos totales'] / (2 * (df_final['FGA'] + 0.44 * df_final['FTA'])).replace(0, pd.NA)) * 100

        player_poss = df_final['FGA'] + 0.44 * df_final['FTA'] + df_final['TOV']
        df_final['%USG'] = (player_poss / (df_final['team_is_FGA'] + 0.44 * df_final['team_is_FTA'] + df_final['team_is_TOV']).replace(0, pd.NA)) * 100
        
        # NUEVO: Puntos por posesión generados por el jugador (SIN .round() para evitar el error con pd.NA)
        df_final['PPP'] = df_final['Puntos totales'] / player_poss.replace(0, pd.NA)

        # Rebote 
        df_final['RD pp'] = df_final['DREB'] / df_final['PJ'].replace(0, 1)
        df_final['RD p100'] = (df_final['DREB'] / team_poss_on_safe) * 100
        dreb_avail = df_final['team_is_DREB'] + df_final['opp_is_OREB']
        df_final['DREB%'] = (df_final['DREB'] / dreb_avail.replace(0, pd.NA)) * 100

        df_final['RO pp'] = df_final['OREB'] / df_final['PJ'].replace(0, 1)
        df_final['RO p100'] = (df_final['OREB'] / team_poss_on_safe) * 100
        oreb_avail = df_final['team_is_OREB'] + df_final['opp_is_DREB']
        df_final['OREB%'] = (df_final['OREB'] / oreb_avail.replace(0, pd.NA)) * 100

        df_final['RT pp'] = df_final['REB'] / df_final['PJ'].replace(0, 1)
        df_final['RT p100'] = (df_final['REB'] / team_poss_on_safe) * 100
        reb_avail = dreb_avail + oreb_avail
        df_final['REB%'] = (df_final['REB'] / reb_avail.replace(0, pd.NA)) * 100

        # Cuidado de Balón
        df_final['Asistencias pp'] = df_final['AST'] / df_final['PJ'].replace(0, 1)
        df_final['Asistencias p100'] = (df_final['AST'] / team_poss_on_safe) * 100
        team_fgm_ast_avail = df_final['team_is_FGM'] - df_final['FGM']
        df_final['AST%'] = (df_final['AST'] / team_fgm_ast_avail.replace(0, pd.NA)) * 100

        df_final['Pérdidas pp'] = df_final['TOV'] / df_final['PJ'].replace(0, 1)
        df_final['Pérdidas p100'] = (df_final['TOV'] / team_poss_on_safe) * 100
        df_final['TOV%'] = (df_final['TOV'] / player_poss.replace(0, pd.NA)) * 100
        df_final['AST / TO'] = df_final['AST'] / df_final['TOV'].replace(0, pd.NA)

        # Defensa: robos (STL) y tapones (BLK)
        df_final['STL pp'] = df_final['Recuperaciones'] / df_final['PJ'].replace(0, 1)
        df_final['STL p100'] = (df_final['Recuperaciones'] / team_poss_on_safe) * 100
        # STL%: posesiones del rival (con él en pista) que acaban en robo suyo
        df_final['STL%'] = (df_final['Recuperaciones'] / opp_poss_on.replace(0, pd.NA)) * 100
        df_final['BLK pp'] = df_final['Tapones'] / df_final['PJ'].replace(0, 1)
        df_final['BLK p100'] = (df_final['Tapones'] / team_poss_on_safe) * 100
        # BLK%: tiros de campo del rival (con él en pista) que tapona
        df_final['BLK%'] = (df_final['Tapones'] / df_final['opp_is_FGA'].replace(0, pd.NA)) * 100

        # Diferenciales On/Off
        df_final['On_OffRtg'] = (df_final['team_Puntos'] / poss_on_safe) * 100
        df_final['On_DefRtg'] = (df_final['opp_Puntos'] / poss_on_safe) * 100
        df_final['On_NetRtg'] = df_final['On_OffRtg'] - df_final['On_DefRtg']

        team_pts_off = df_final['total_team_Puntos'] - df_final['team_Puntos']
        opp_pts_off = df_final['total_opp_Puntos'] - df_final['opp_Puntos']
        
        team_poss_total = df_final['total_team_is_FGA'] + 0.44 * df_final['total_team_is_FTA'] + df_final['total_team_is_TOV'] - df_final['total_team_is_OREB']
        opp_poss_total = df_final['total_opp_is_FGA'] + 0.44 * df_final['total_opp_is_FTA'] + df_final['total_opp_is_TOV'] - df_final['total_opp_is_OREB']
        
        team_poss_off = team_poss_total - team_poss_on
        opp_poss_off = opp_poss_total - opp_poss_on
        poss_off_safe = ((team_poss_off + opp_poss_off) / 2).replace(0, pd.NA)

        df_final['Off_OffRtg'] = (team_pts_off / poss_off_safe) * 100
        df_final['Off_DefRtg'] = (opp_pts_off / poss_off_safe) * 100
        df_final['Off_NetRtg'] = df_final['Off_OffRtg'] - df_final['Off_DefRtg']

        df_final['Diferencial Offensive Rating'] = df_final['On_OffRtg'] - df_final['Off_OffRtg']
        df_final['Diferencial Defensive Rating'] = df_final['On_DefRtg'] - df_final['Off_DefRtg']
        df_final['Diferencial Net Rating'] = df_final['On_NetRtg'] - df_final['Off_NetRtg']

        # 6. PERCENTILES DE LIGA
        metrics_higher_better = [
            'Minutos Totales', 'Minutos por partido', '% Minutos',
            'Puntos totales', 'Puntos por partido', 'Puntos p100', '%T2', '2PA%',
            '%T3', '3PA%', '%TL', 'FTr', 'eFG%', 'TS%', '%USG', 'PPP',
            'RD pp', 'RD p100', 'DREB%', 'RO pp', 'RO p100', 'OREB%', 'RT pp', 'RT p100', 'REB%',
            'Asistencias pp', 'Asistencias p100', 'AST%', 'AST / TO',
            'STL pp', 'STL p100', 'STL%', 'BLK pp', 'BLK p100', 'BLK%'
        ]
        metrics_lower_better = ['Pérdidas pp', 'Pérdidas p100', 'TOV%'] 

        for m in metrics_higher_better:
            if m in df_final.columns:
                df_final[f'{m}_pct'] = df_final[m].rank(pct=True, method='min') * 100

        for m in metrics_lower_better:
            if m in df_final.columns:
                df_final[f'{m}_pct'] = df_final[m].rank(pct=True, ascending=False, method='min') * 100

        # 7. CÁLCULO DE RATINGS PONDERADOS (0 a 10)
        df_final['Rating Anotación'] = (df_final['Puntos p100_pct'].fillna(0) * 0.05) + (df_final['TS%_pct'].fillna(0) * 0.04) + (df_final['%USG_pct'].fillna(0) * 0.01)
        df_final['Rating Rebote'] = (df_final['DREB%_pct'].fillna(0) * 0.033333) + (df_final['OREB%_pct'].fillna(0) * 0.033333) + (df_final['REB%_pct'].fillna(0) * 0.033334)
        df_final['Rating Cuidado de Balón'] = (df_final['TOV%_pct'].fillna(0) * 0.07) + (df_final['AST%_pct'].fillna(0) * 0.03)

        df_final['Rating Anotación'] = df_final['Rating Anotación'].clip(upper=10.0)
        df_final['Rating Rebote'] = df_final['Rating Rebote'].clip(upper=10.0)
        df_final['Rating Cuidado de Balón'] = df_final['Rating Cuidado de Balón'].clip(upper=10.0)
        # Rating de defensa: 50% STL% y 50% BLK%
        df_final['Rating Defensa'] = ((df_final['STL%_pct'].fillna(0) * 0.05) + (df_final['BLK%_pct'].fillna(0) * 0.05)).clip(upper=10.0)

        return df_final
    except Exception as e:
        st.error(f"Error calculando stats individuales: {e}")
        return pd.DataFrame()

# Tablas de estadísticas individuales: columnas (nombre, es_porcentaje), rating y orden. Las usan Individuales y Cuartos
TABLAS_INDIVIDUALES = {
    "⏳ Minutos": {
        "rating_col": None,
        "sort_col": "% Minutos",
        "columnas": [
            ("Minutos Totales", False),
            ("Minutos por partido", False),
            ("% Minutos", True)
        ]
    },
    "🎯 Anotación": {
        "rating_col": "Rating Anotación",
        "sort_col": "Rating Anotación",
        "columnas": [
            ("Puntos totales", False), ("Puntos por partido", False), ("Puntos p100", False),
            ("%T2", True), ("2PA%", True),
            ("%T3", True), ("3PA%", True),
            ("%TL", True), ("FTr", False),
            ("eFG%", True), ("TS%", True),
            ("%USG", True)
        ]
    },
    "🛡️ Rebote": {
        "rating_col": "Rating Rebote",
        "sort_col": "Rating Rebote",
        "columnas": [
            ("RD pp", False), ("RD p100", False), ("DREB%", True),
            ("RO pp", False), ("RO p100", False), ("OREB%", True),
            ("RT pp", False), ("RT p100", False), ("REB%", True)
        ]
    },
    "🧠 Cuidado de balón": {
        "rating_col": "Rating Cuidado de Balón",
        "sort_col": "Rating Cuidado de Balón",
        "columnas": [
            ("Asistencias pp", False), ("Asistencias p100", False), ("AST%", True),
            ("Pérdidas pp", False), ("Pérdidas p100", False), ("TOV%", True),
            ("AST / TO", False)
        ]
    },
    "🔒 Defensa": {
        "rating_col": "Rating Defensa",
        "sort_col": "Rating Defensa",
        "columnas": [
            ("STL pp", False), ("STL p100", False), ("STL%", True),
            ("BLK pp", False), ("BLK p100", False), ("BLK%", True)
        ]
    }
}

@st.cache_data
def calcular_stats_quinteto(id_equipo, lista_ids_jugadores, ultimos_n=None):
    try:
        conexion = sqlite3.connect("mi_liga.db")
        
        partidos_validos = []
        if ultimos_n:
            query_ids = f"""
                SELECT id_partido FROM partidos 
                WHERE id_equipo_local = ? OR id_equipo_visitante = ?
                ORDER BY fecha_iso DESC LIMIT {ultimos_n}
            """
            df_ids = pd.read_sql(query_ids, conexion, params=(int(id_equipo), int(id_equipo)))
            partidos_validos = df_ids['id_partido'].tolist()
            if not partidos_validos:
                conexion.close()
                return {}

        query = """
            SELECT pb.id_partido, pb.idMove, pb.id_equipo, pb.quinteto_local, pb.quinteto_visitante, 
                   pb.period, pb.min, pb.sec,
                   p.id_equipo_local, p.id_equipo_visitante
            FROM play_by_play pb
            JOIN partidos p ON pb.id_partido = p.id_partido
            WHERE (p.id_equipo_local = ? OR p.id_equipo_visitante = ?)
        """
        
        if ultimos_n and partidos_validos:
            placeholders = ','.join('?' for _ in partidos_validos)
            query += f" AND p.id_partido IN ({placeholders})"
            params = (int(id_equipo), int(id_equipo)) + tuple(partidos_validos)
        else:
            params = (int(id_equipo), int(id_equipo))
            
        df_pbp = pd.read_sql(query, conexion, params=params)
        conexion.close()

        if df_pbp.empty: return {}

        df_pbp['min'] = df_pbp['min'].fillna(0).astype(int)
        df_pbp['sec'] = df_pbp['sec'].fillna(0).astype(int)
        df_pbp['tiempo_restante'] = df_pbp['min'] * 60 + df_pbp['sec']
        
        df_pbp = df_pbp.sort_values(['id_partido', 'period', 'tiempo_restante'], ascending=[True, True, False])
        df_pbp['tiempo_siguiente'] = df_pbp.groupby(['id_partido', 'period'])['tiempo_restante'].shift(-1).fillna(0)
        df_pbp['segundos_jugados'] = (df_pbp['tiempo_restante'] - df_pbp['tiempo_siguiente']).clip(lower=0)

        def extraer_ids(q_str):
            if pd.isna(q_str): return []
            return [int(x) for x in re.findall(r'\d+', str(q_str))]

        df_pbp['q_loc'] = df_pbp['quinteto_local'].apply(extraer_ids)
        df_pbp['q_vis'] = df_pbp['quinteto_visitante'].apply(extraer_ids)

        def jugadores_en_pista(row):
            en_pista = row['q_loc'] if row['id_equipo_local'] == int(id_equipo) else row['q_vis']
            return all(id_jug in en_pista for id_jug in lista_ids_jugadores)

        df_pbp['is_on'] = df_pbp.apply(jugadores_en_pista, axis=1)

        def obtener_metricas(df_subset):
            if df_subset.empty: return None
            
            mask_us = df_subset['id_equipo'] == int(id_equipo)
            mask_opp = (df_subset['id_equipo'] != int(id_equipo)) & (df_subset['id_equipo'].notna())

            FGM = df_subset[mask_us]['idMove'].isin([93, 100, 94]).sum()
            T3_anotados = df_subset[mask_us]['idMove'].eq(94).sum()
            FGA = df_subset[mask_us]['idMove'].isin([93, 100, 97, 94, 98]).sum()
            T2_intentados = df_subset[mask_us]['idMove'].isin([93, 100, 97]).sum()
            T3_intentados = df_subset[mask_us]['idMove'].isin([94, 98]).sum()
            TL_anotados = df_subset[mask_us]['idMove'].eq(92).sum()
            TL_intentados = df_subset[mask_us]['idMove'].isin([92, 96]).sum()
            DREB = df_subset[mask_us]['idMove'].eq(104).sum()
            OREB = df_subset[mask_us]['idMove'].eq(101).sum()
            AST = df_subset[mask_us]['idMove'].eq(107).sum()
            TOV = df_subset[mask_us]['idMove'].eq(106).sum()

            Puntos = (FGM - T3_anotados)*2 + T3_anotados*3 + TL_anotados
            REB = DREB + OREB

            opp_FGM = df_subset[mask_opp]['idMove'].isin([93, 100, 94]).sum()
            opp_T3_anotados = df_subset[mask_opp]['idMove'].eq(94).sum()
            opp_TL_anotados = df_subset[mask_opp]['idMove'].eq(92).sum()
            opp_FGA = df_subset[mask_opp]['idMove'].isin([93, 100, 97, 94, 98]).sum()
            opp_TL_intentados = df_subset[mask_opp]['idMove'].isin([92, 96]).sum()
            opp_DREB = df_subset[mask_opp]['idMove'].eq(104).sum()
            opp_OREB = df_subset[mask_opp]['idMove'].eq(101).sum()
            opp_TOV = df_subset[mask_opp]['idMove'].eq(106).sum()

            opp_Puntos = (opp_FGM - opp_T3_anotados)*2 + opp_T3_anotados*3 + opp_TL_anotados
            opp_REB = opp_DREB + opp_OREB

            Team_Poss = FGA + (0.44 * TL_intentados) + TOV - OREB
            Opp_Poss = opp_FGA + (0.44 * opp_TL_intentados) + opp_TOV - opp_OREB
            Posesiones = (Team_Poss + Opp_Poss) / 2
            
            Segundos_Jugados = df_subset['segundos_jugados'].sum()
            
            if Posesiones <= 0: return None
            
            div_FGA = FGA if FGA > 0 else 1
            div_TS = 2 * (FGA + 0.44 * TL_intentados) if (FGA + 0.44 * TL_intentados) > 0 else 1
            div_DREB = (DREB + opp_OREB) if (DREB + opp_OREB) > 0 else 1
            div_OREB = (OREB + opp_DREB) if (OREB + opp_DREB) > 0 else 1
            div_REB = (REB + opp_REB) if (REB + opp_REB) > 0 else 1
            div_TOV = TOV if TOV > 0 else 1
            div_FGM = FGM if FGM > 0 else 1

            return {
                'Offensive Rating': round((Puntos / Posesiones) * 100, 1),
                'Defensive Rating': round((opp_Puntos / Posesiones) * 100, 1),
                'Net Rating': round(((Puntos / Posesiones) * 100) - ((opp_Puntos / Posesiones) * 100), 1),
                'eFG%': round(((FGM + 0.5 * T3_anotados) / div_FGA) * 100, 1),
                'TS%': round((Puntos / div_TS) * 100, 1),
                'FTr': round(TL_intentados / div_FGA, 3),
                '2PA%': round((T2_intentados / div_FGA) * 100, 1),
                '3PA%': round((T3_intentados / div_FGA) * 100, 1),
                'DREB%': round((DREB / div_DREB) * 100, 1),
                'OREB%': round((OREB / div_OREB) * 100, 1),
                'REB%': round((REB / div_REB) * 100, 1),
                'TOV%': round((TOV / Posesiones) * 100, 1),
                'AST / TO ratio': round(AST / div_TOV, 2),
                'AST%': round((AST / div_FGM) * 100, 1),
                'Segundos_Totales': Segundos_Jugados
            }

        stats_on = obtener_metricas(df_pbp[df_pbp['is_on']])
        stats_off = obtener_metricas(df_pbp[~df_pbp['is_on']])
        stats_media = obtener_metricas(df_pbp)

        if not stats_media: return {}

        seg_on = stats_on['Segundos_Totales'] if stats_on else 0
        seg_media = stats_media['Segundos_Totales'] if stats_media else 1
        porcentaje_minutos = round((seg_on / seg_media) * 100, 1)

        df_pbp_on = df_pbp[df_pbp['is_on']]
        total_seg_on = df_pbp_on['segundos_jugados'].sum()
        companeros = {}
        
        if total_seg_on > 0 and len(lista_ids_jugadores) < 5:
            for _, r in df_pbp_on.iterrows():
                q = r['q_loc'] if r['id_equipo_local'] == int(id_equipo) else r['q_vis']
                for j_id in q:
                    if j_id not in lista_ids_jugadores:
                        companeros[j_id] = companeros.get(j_id, 0) + r['segundos_jugados']
            for j_id in companeros:
                companeros[j_id] = round((companeros[j_id] / total_seg_on) * 100, 1)

        return {
            'on': stats_on or {},
            'off': stats_off or {},
            'media': stats_media or {},
            'porcentaje': porcentaje_minutos,
            'companeros': companeros
        }

    except Exception as e:
        st.error(f"Error calculando stats de quinteto: {e}")
        return {}


# ------------------------------------------------------------------
# VISTAS REUTILIZABLES (Liga y Propio)
# ------------------------------------------------------------------

def grafico_uso_eficiencia(df_res):
    """Gráfico %USG vs PPP con la foto (o iniciales) de cada jugador. df_res: columnas Jugador, %USG y PPP."""
    avg_usg = df_res['%USG'].mean()
    avg_ppp = df_res['PPP'].mean()

    fig = go.Figure()

    # 1. RASTRO INVISIBLE PARA EL HOVER (Sin texto escrito)
    fig.add_trace(go.Scatter(
        x=df_res['%USG'],
        y=df_res['PPP'],
        mode='markers', # Quitamos el '+text'
        customdata=df_res['Jugador'],
        marker=dict(size=28, color='rgba(0,0,0,0)'), # Marcador transparente pero grande para que detecte el ratón
        hovertemplate="<b>%{customdata}</b><br>USG%: %{x:.1f}%<br>PPP: %{y:.2f}<extra></extra>"
    ))

    fig.add_hline(y=avg_ppp, line_dash="solid", line_color="#D4D4D4", line_width=1)
    fig.add_vline(x=avg_usg, line_dash="solid", line_color="#D4D4D4", line_width=1)

    rango_usg = df_res['%USG'].max() - df_res['%USG'].min()
    rango_ppp = df_res['PPP'].max() - df_res['PPP'].min()
    size_x = max(1.8, rango_usg * 0.15)
    size_y = max(0.1, rango_ppp * 0.15)

    for _, row in df_res.iterrows():
        img_b64 = obtener_foto_jugador_base64(row['Jugador'])
        if img_b64:
            # 2. SI HAY FOTO: Ponemos la imagen
            img_src = f"data:image/png;base64,{img_b64}"
            fig.add_layout_image(
                dict(
                    source=img_src,
                    xref="x",
                    yref="y",
                    xanchor="center",
                    yanchor="middle",
                    x=row['%USG'],
                    y=row['PPP'],
                    sizex=size_x,
                    sizey=size_y,
                    sizing="contain",
                    opacity=1,
                    layer="below" # Lo ponemos por debajo para que el hover invisible funcione perfecto
                )
            )
        else:
            # 3. SI NO HAY FOTO: Cuadrado gris con iniciales en azul marino
            nombre_limpio = str(row['Jugador']).replace("-", " ") # Por si hay dorsales en el nombre
            partes = [p for p in nombre_limpio.split() if not p.isdigit()] # Evitamos coger el número del dorsal
            iniciales = "".join([p[0] for p in partes[:2]]).upper() if partes else "?"

            fig.add_trace(go.Scatter(
                x=[row['%USG']],
                y=[row['PPP']],
                mode='markers+text',
                text=[iniciales],
                textposition="middle center",
                textfont=dict(color='#F97316', size=11, weight='bold'),
                marker=dict(symbol='square', size=50, color='#262626', line=dict(color='#F97316', width=2)),
                showlegend=False,
                hoverinfo='skip' # Saltamos el hover porque ya lo hace la capa invisible
            ))

    fig.add_annotation(x=0.01, y=0.99, xref="paper", yref="paper", text="🎯 Poco uso, mucha eficiencia", showarrow=False, font=dict(color="#4CAF50"), align="left")
    fig.add_annotation(x=0.99, y=0.99, xref="paper", yref="paper", text="🌟 Mucho uso, mucha eficiencia", showarrow=False, font=dict(color="#F97316"), align="right")
    fig.add_annotation(x=0.01, y=0.01, xref="paper", yref="paper", text="🧱 Poco uso, poca eficiencia", showarrow=False, font=dict(color="#A3A3A3"), align="left")
    fig.add_annotation(x=0.99, y=0.01, xref="paper", yref="paper", text="⛔ Mucho uso, poca eficiencia", showarrow=False, font=dict(color="#E53935"), align="right")

    fig.update_layout(
        title=dict(text="Uso vs Eficiencia (%USG vs PPP)", font=dict(color="#FFFFFF", size=24), x=0.01, y=0.98),
        xaxis_title="Usage Percentage (%USG) ⟶",
        yaxis_title="Puntos Por Posesión (PPP) ⟶",
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', zeroline=False),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', zeroline=False),
        plot_bgcolor='rgba(20, 20, 20, 0.85)', 
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#D4D4D4'),
        margin=dict(l=60, r=60, t=80, b=60),
        height=650
    )

    st.plotly_chart(fig, use_container_width=True)


def mostrar_perfil_jugador(id_jugador, ultimos_n=None):
    """Radar de impacto y tablas de percentiles del jugador frente a toda la liga."""
    df_indiv_liga = calcular_stats_individuales_liga(ultimos_n=ultimos_n)

    if not df_indiv_liga.empty:
        df_jug = df_indiv_liga[df_indiv_liga['id_jugador'] == id_jugador]
        if not df_jug.empty:
            row_jug = df_jug.iloc[0]

            val_rol = (row_jug.get('% Minutos_pct', 0) / 10.0) if pd.notna(row_jug.get('% Minutos_pct', 0)) else 0
            val_anotacion = row_jug.get('Rating Anotación', 0)
            val_rebote = row_jug.get('Rating Rebote', 0)
            val_cuidado = row_jug.get('Rating Cuidado de Balón', 0)
            val_defensa = row_jug.get('Rating Defensa', 0)

            categorias_radar = ['Rol', 'Anotación', 'Rebote', 'Cuidado de Balón', 'Defensa']
            valores_radar = [val_rol, val_anotacion, val_rebote, val_cuidado, val_defensa]

            categorias_cerrado = categorias_radar + [categorias_radar[0]]
            valores_cerrado = valores_radar + [valores_radar[0]]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=valores_cerrado,
                theta=categorias_cerrado,
                fill='toself',
                fillcolor='rgba(249, 115, 22, 0.4)',
                line=dict(color='#F97316', width=2),
                marker=dict(color='#D4D4D4', size=6),
                name='Perfil del Jugador'
            ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 10],
                        showticklabels=False,
                        gridcolor='rgba(163, 163, 163, 0.3)',
                        linecolor='rgba(163, 163, 163, 0.3)'
                    ),
                    angularaxis=dict(
                        gridcolor='rgba(163, 163, 163, 0.3)',
                        linecolor='rgba(163, 163, 163, 0.3)',
                        tickfont=dict(color='#E5E5E5', size=14, weight='bold')
                    ),
                    bgcolor='rgba(0,0,0,0)'
                ),
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=40, r=40, t=30, b=30),
                height=350
            )

            st.markdown("<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 15px; margin-bottom: 10px; text-transform: uppercase; text-align: center;'>Impacto Global en Liga</h4>", unsafe_allow_html=True)
            col_g1, col_g2, col_g3 = st.columns([1, 2, 1])
            with col_g2:
                st.plotly_chart(fig, use_container_width=True)

            st.write("---")

            tablas_individuales = {
                "⏳ Minutos": {
                    "rating_col": None,
                    "columnas": [
                        ("Minutos Totales", False),
                        ("Minutos por partido", False),
                        ("% Minutos", True)
                    ]
                },
                "🎯 Anotación": {
                    "rating_col": "Rating Anotación",
                    "columnas": [
                        ("Puntos totales", False), ("Puntos por partido", False), ("Puntos p100", False),
                        ("%T2", True), ("2PA%", True), 
                        ("%T3", True), ("3PA%", True), 
                        ("%TL", True), ("FTr", False), 
                        ("eFG%", True), ("TS%", True),
                        ("%USG", True), ("PPP", False)
                    ]
                },
                "🛡️ Rebote": {
                    "rating_col": "Rating Rebote",
                    "columnas": [
                        ("RD pp", False), ("RD p100", False), ("DREB%", True),
                        ("RO pp", False), ("RO p100", False), ("OREB%", True),
                        ("RT pp", False), ("RT p100", False), ("REB%", True)
                    ]
                },
                "🧠 Cuidado de balón": {
                    "rating_col": "Rating Cuidado de Balón",
                    "columnas": [
                        ("Asistencias pp", False), ("Asistencias p100", False), ("AST%", True),
                        ("Pérdidas pp", False), ("Pérdidas p100", False), ("TOV%", True),
                        ("AST / TO", False)
                    ]
                },
                "🔒 Defensa": {
                    "rating_col": "Rating Defensa",
                    "columnas": [
                        ("STL pp", False), ("STL p100", False), ("STL%", True),
                        ("BLK pp", False), ("BLK p100", False), ("BLK%", True)
                    ]
                }
            }

            def render_table(titulo, config, row):
                config_stats = config["columnas"]
                rating_col = config.get("rating_col")

                titulo_html = f"<span>{titulo}</span>"
                if rating_col:
                    rating_val = row.get(rating_col, 0)
                    if pd.isna(rating_val): rating_val = 0
                    stars_num = np.floor(rating_val) / 2.0
                    stars_pct = (stars_num / 5.0) * 100
                    stars_html = f'''
                    <span style="display: flex; align-items: center; margin-left: 15px;">
                        <span style="position: relative; color: #525252; font-size: 1.1em; letter-spacing: 2px;">
                            ★★★★★
                            <span style="position: absolute; top: 0; left: 0; white-space: nowrap; overflow: hidden; width: {stars_pct}%; color: #F97316;">
                                ★★★★★
                            </span>
                        </span>
                        <span style="font-size: 0.9em; color: #E5E5E5; margin-left: 8px; font-weight: bold;">{rating_val:.1f}</span>
                    </span>
                    '''
                    titulo_html += stars_html
                elif "Minutos" in titulo:
                    pct_min = row.get("% Minutos", 0)
                    if pd.isna(pct_min): pct_min = 0
                    if pct_min <= 25: rol = "Secundario"
                    elif pct_min <= 50: rol = "Rotación"
                    elif pct_min <= 75: rol = "Importante"
                    else: rol = "Clave"
                    titulo_html = f"<span>⏳ ROL: {rol}</span>"

                ths = "<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 40%;'>Estadística</th>" \
                      "<th style='padding: 12px 10px; border-bottom: 2px solid #F97316; text-align: center; width: 30%;'>Valor</th>" \
                      "<th style='padding: 12px 10px; border-bottom: 2px solid #F97316; text-align: center; width: 30%;'>Percentil</th>"

                trs = ""
                for i, (col_name, is_pct) in enumerate(config_stats):
                    bg_color = "transparent" if i % 2 == 0 else "rgba(255, 255, 255, 0.05)"
                    display_name = col_name.replace("_", " ")

                    val = row.get(col_name)
                    pct = row.get(f"{col_name}_pct")

                    if pd.isna(val) or pd.isna(pct) or str(val) == "" or str(pct) == "":
                        val_html = "-"
                        pct_html = "-"
                    else:
                        try:
                            if is_pct: val_str = f"{float(val):.1f}%"
                            elif col_name in ['FTr', 'PPP']: val_str = f"{float(val):.2f}"
                            elif col_name == 'AST / TO': val_str = f"{float(val):.2f}"
                            else: val_str = str(int(val)) if float(val) == int(val) else f"{float(val):.1f}"
                        except:
                            val_str = "-"

                        try:
                            color = "#E53935" # Rojo (0-25)
                            if float(pct) >= 95: color = "#16A34A" # Verde Oscuro
                            elif float(pct) >= 75: color = "#4ADE80" # Verde Claro
                            elif float(pct) >= 50: color = "#FACC15" # Amarillo
                            elif float(pct) >= 25: color = "#F59E0B" # Naranja

                            val_html = f"<span style='color: {color}; font-weight: bold;'>{val_str}</span>"
                            pct_html = f"<span style='color: {color}; font-weight: bold;'>{int(float(pct))}</span>"
                        except:
                            val_html = val_str
                            pct_html = "-"

                    tds = f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #FFF; font-weight: 500;'>{etiqueta_stat(col_name, jugador=True, texto=display_name)}</td>" \
                          f"<td style='padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.2); text-align: center;'>{val_html}</td>" \
                          f"<td style='padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.2); text-align: center;'>{pct_html}</td>"

                    trs += f"<tr style='background-color: {bg_color};'>{tds}</tr>"

                html = f'''
                <h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 15px; text-transform: uppercase; display: flex; align-items: center;'>{titulo_html}</h4>
                <div style="border-radius: 10px; overflow: visible; border: 1px solid #3F3F3F; margin-bottom: 20px; background-color: transparent;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif; font-size: 0.95rem;">
                        <thead>
                            <tr style="background-color: rgba(255, 255, 255, 0.1); color: #FFFFFF;">
                                {ths}
                            </tr>
                        </thead>
                        <tbody>
                            {trs}
                        </tbody>
                    </table>
                </div>
                '''
                st.markdown(html, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                render_table("⏳ Minutos", tablas_individuales["⏳ Minutos"], row_jug)
                render_table("🛡️ Rebote", tablas_individuales["🛡️ Rebote"], row_jug)
                render_table("🔒 Defensa", tablas_individuales["🔒 Defensa"], row_jug)
            with col2:
                render_table("🎯 Anotación", tablas_individuales["🎯 Anotación"], row_jug)
                render_table("🧠 Cuidado de balón", tablas_individuales["🧠 Cuidado de balón"], row_jug)
        else:
            st.warning("El jugador no registra estadísticas en la muestra seleccionada.")
    else:
        st.warning("No hay datos de liga disponibles.")


def mostrar_impacto_jugador(id_jugador, id_equipo, ultimos_n=None):
    """Impacto On/Off del jugador y compañeros con los que más comparte pista."""
    df_plantilla = cargar_plantilla(id_equipo)
    ids_seleccionados = [id_jugador]
    datos_q = calcular_stats_quinteto(id_equipo, ids_seleccionados, ultimos_n=ultimos_n)

    if datos_q and datos_q.get('media'):
        porcentaje = datos_q['porcentaje']

        # Uno debajo del otro, a todo el ancho: primero el % de minutos y después el gráfico de compañeros
        col_g1, col_g2 = st.container(), st.container()

        with col_g1:
            st.markdown(f"""
            <div style="background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; border: 1px solid #3F3F3F; margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <h4 style="margin: 0; color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; text-transform: uppercase;">⏱ Minutos en Pista</h4>
                    <p style="margin: 5px 0 0 0; color: #D4D4D4; font-size: 0.85rem;">% del total de minutos jugados por su equipo.</p>
                </div>
                <span style="color: #FFFFFF; font-size: 2.2rem; font-weight: bold;">{porcentaje}%</span>
            </div>
            """, unsafe_allow_html=True)

        with col_g2:
            st.markdown("<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 15px; text-transform: uppercase;'>🤝 Compañeros Más Frecuentes</h4>", unsafe_allow_html=True)

            nombres_comp = []
            pcts_comp = []
            dict_comp = datos_q.get('companeros', {})
            for _, row_jug in df_plantilla.iterrows():
                j_id = int(row_jug['id_jugador'])
                if j_id != id_jugador:
                    dorsal = row_jug['dorsal'] if pd.notna(row_jug['dorsal']) and str(row_jug['dorsal']).strip() != '' else '-'
                    nombres_comp.append(f"{dorsal} - {row_jug['nombre']}")
                    pcts_comp.append(dict_comp.get(j_id, 0.0))

            df_grafico = pd.DataFrame({"Jugador": nombres_comp, "% Minutos Compartidos": pcts_comp})
            df_grafico = df_grafico[df_grafico['% Minutos Compartidos'] > 0]

            if not df_grafico.empty:
                # A todo el ancho caben todos los nombres: sin recortarlos ni ocultar los que se solapan
                grafico_alt = alt.Chart(df_grafico).mark_bar(color='#F97316', opacity=0.85).encode(
                    x=alt.X('Jugador', sort='-y', axis=alt.Axis(labelAngle=-35, labelColor='#FFFFFF', titleColor='#FFFFFF',
                                                                labelLimit=250, labelOverlap=False)),
                    y=alt.Y('% Minutos Compartidos', axis=alt.Axis(labelColor='#FFFFFF', titleColor='#FFFFFF')),
                    tooltip=['Jugador', '% Minutos Compartidos']
                ).properties(height=380).configure_view(strokeWidth=0).configure_axis(grid=False)
                st.altair_chart(grafico_alt, use_container_width=True)
            else:
                st.info("No hay datos suficientes de compañeros.")

        st.write("---")

        bloques_avanzados_q = {
            "Eficiencia Ofensiva / Defensiva": ['Offensive Rating', 'Defensive Rating', 'Net Rating'],
            "Tiro": ['eFG%', 'TS%', 'FTr', '2PA%', '3PA%'],
            "Rebote": ['DREB%', 'OREB%', 'REB%'],
            "Cuidado de balón": ['TOV%', 'AST / TO ratio', 'AST%']
        }
        menor_es_mejor = ['Defensive Rating', 'TOV%']

        for titulo, variables in bloques_avanzados_q.items():
            st.markdown(f"<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 35px; text-transform: uppercase;'>{titulo}</h4>", unsafe_allow_html=True)
            filas_html = ""
            for i, cat in enumerate(variables):
                val_on = datos_q['on'].get(cat) if datos_q['on'] else None
                val_off = datos_q['off'].get(cat) if datos_q['off'] else None
                val_media = datos_q['media'].get(cat) if datos_q['media'] else None

                diff_html = "-"
                if val_on is not None and val_off is not None:
                    try:
                        diff_val = float(val_on) - float(val_off)
                        if cat in menor_es_mejor:
                            c_diff = "#4CAF50" if diff_val < 0 else "#F87171"
                        else:
                            c_diff = "#4CAF50" if diff_val > 0 else "#F87171"

                        diff_str = f"+{diff_val:.1f}" if diff_val > 0 else f"{diff_val:.1f}"
                        if '%' in cat: diff_str += "%"
                        diff_html = f"<span style='color: {c_diff}; font-weight: bold;'>{diff_str}</span>"
                    except: pass

                def fmt(v, c):
                    if v is None: return "-"
                    s = str(v)
                    if '%' in c: return s + "%"
                    if c == 'Net Rating' and float(v) > 0: return "+" + s
                    return s

                str_on = fmt(val_on, cat)
                str_off = fmt(val_off, cat)
                str_media = fmt(val_media, cat)

                bg_color = "transparent" if i % 2 == 0 else "rgba(255, 255, 255, 0.05)"

                filas_html += f"""
                <tr style="background-color: {bg_color}; border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                    <td style="padding: 12px 20px; font-weight: bold; color: #FFFFFF;">{etiqueta_stat(cat)}</td>
                    <td style="padding: 12px 20px; color: #FFFFFF; font-weight: bold; text-align: center; font-size: 1.1rem;">{str_on}</td>
                    <td style="padding: 12px 20px; color: #D4D4D4; font-weight: bold; text-align: center;">{str_off}</td>
                    <td style="padding: 12px 20px; text-align: center; font-size: 1.1rem; background-color: rgba(255,255,255,0.02);">{diff_html}</td>
                    <td style="padding: 12px 20px; color: #A3A3A3; font-style: italic; text-align: center; opacity: 0.8;">{str_media}</td>
                </tr>
                """

            tabla_bloque = f"""
            <div style="border-radius: 10px; overflow: visible; border: 1px solid #3F3F3F; margin-top: 10px; background-color: transparent;">
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif;">
                    <thead>
                        <tr style="background-color: rgba(255, 255, 255, 0.1); color: #FFFFFF; border-bottom: 2px solid #F97316;">
                            <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; width: 30%;">Estadística</th>
                            <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 17%;">On</th>
                            <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 17%;">Off</th>
                            <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 19%; background-color: rgba(255,255,255,0.05);">Diferencial</th>
                            <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 17%;">Media Equipo</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_html}
                    </tbody>
                </table>
            </div>
            """
            st.markdown(" ".join(tabla_bloque.split()), unsafe_allow_html=True)
    else:
        st.warning("El jugador no registra minutos en la muestra seleccionada para evaluar su impacto.")


def mostrar_analisis_quintetos(id_equipo, ultimos_n=None):
    """Configurador de combinaciones en pista: stats On / Off frente a la media del equipo."""
    df_plantilla = cargar_plantilla(id_equipo)

    if not df_plantilla.empty:
        mapeo_jugadores = {}
        opciones_jugadores = []
        for _, row in df_plantilla.iterrows():
            dorsal = row['dorsal'] if pd.notna(row['dorsal']) and str(row['dorsal']).strip() != '' else '-'
            etiqueta = f"{dorsal} - {row['nombre']}"
            opciones_jugadores.append(etiqueta)
            mapeo_jugadores[etiqueta] = int(row['id_jugador'])

        st.markdown("""
        <div style="background-color: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; border: 1px solid #3F3F3F; margin-bottom: 20px;">
            <h4 style="color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 0; margin-bottom: 15px; font-size: 1.1rem; text-transform: uppercase;">Configurador de Combinaciones en Pista</h4>
            <p style="color: #FFFFFF; font-size: 0.9rem; margin-bottom: 10px;">Selecciona entre 1 y 5 jugadores para comparar su impacto <b>On / Off</b> respecto a la Media general del equipo.</p>
        </div>
        """, unsafe_allow_html=True)

        jugadores_seleccionados = st.multiselect(
            "Selecciona jugadores:",
            options=opciones_jugadores,
            default=[],
            max_selections=5,
            label_visibility="collapsed"
        )

        if len(jugadores_seleccionados) > 0:
            ids_seleccionados = [mapeo_jugadores[jug] for jug in jugadores_seleccionados]
            datos_q = calcular_stats_quinteto(id_equipo, ids_seleccionados, ultimos_n=ultimos_n)

            if datos_q and datos_q.get('media'):
                porcentaje = datos_q['porcentaje']

                st.markdown(f"""
                <div style="background-color: #1A1A1A; border-left: 5px solid #F97316; padding: 15px; border-radius: 5px; margin-bottom: 25px;">
                    <h4 style="margin: 0; color: #FFFFFF;">⏱ Minutos del Equipo: <span style="color: #F97316;">{porcentaje}%</span></h4>
                    <p style="margin: 5px 0 0 0; color: #D4D4D4; font-size: 0.9rem;">Esta combinación consume aproximadamente un {porcentaje}% del tiempo en pista del equipo.</p>
                </div>
                """, unsafe_allow_html=True)

                if len(jugadores_seleccionados) < 5 and datos_q.get('companeros') is not None:
                    st.markdown("<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 10px; margin-bottom: 5px; text-transform: uppercase;'>🤝 ¿Con quién comparten estos minutos?</h4>", unsafe_allow_html=True)
                    st.markdown("<p style='color: #D4D4D4; font-size: 0.9rem; margin-bottom: 20px;'>* Solo se muestran los jugadores con los que han coincidido en pista (> 0%).</p>", unsafe_allow_html=True)

                    nombres_comp = []
                    pcts_comp = []
                    dict_comp = datos_q.get('companeros', {})

                    for _, row_jug in df_plantilla.iterrows():
                        j_id = int(row_jug['id_jugador'])
                        if j_id not in ids_seleccionados:
                            dorsal = row_jug['dorsal'] if pd.notna(row_jug['dorsal']) and str(row_jug['dorsal']).strip() != '' else '-'
                            nombres_comp.append(f"{dorsal} - {row_jug['nombre']}")
                            pcts_comp.append(dict_comp.get(j_id, 0.0))

                    df_grafico = pd.DataFrame({
                        "Jugador": nombres_comp,
                        "% Minutos Compartidos": pcts_comp
                    })

                    df_grafico = df_grafico[df_grafico['% Minutos Compartidos'] > 0]

                    if not df_grafico.empty:
                        grafico_alt = alt.Chart(df_grafico).mark_bar(color='#F97316', opacity=0.85).encode(
                            x=alt.X('Jugador', sort='-y', axis=alt.Axis(labelAngle=-45, labelColor='#FFFFFF', titleColor='#FFFFFF')),
                            y=alt.Y('% Minutos Compartidos', axis=alt.Axis(labelColor='#FFFFFF', titleColor='#FFFFFF')),
                            tooltip=['Jugador', '% Minutos Compartidos']
                        ).properties(height=350).configure_view(strokeWidth=0).configure_axis(grid=False)

                        st.altair_chart(grafico_alt, use_container_width=True)
                    else:
                        st.info("No hay otros jugadores en la plantilla que hayan coincidido con esta combinación en pista.")

                bloques_avanzados_q = {
                    "Eficiencia Ofensiva / Defensiva": ['Offensive Rating', 'Defensive Rating', 'Net Rating'],
                    "Tiro": ['eFG%', 'TS%', 'FTr', '2PA%', '3PA%'],
                    "Rebote": ['DREB%', 'OREB%', 'REB%'],
                    "Cuidado de balón": ['TOV%', 'AST / TO ratio', 'AST%']
                }
                menor_es_mejor = ['Defensive Rating', 'TOV%']

                for titulo, variables in bloques_avanzados_q.items():
                    st.markdown(f"<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 35px; text-transform: uppercase;'>{titulo}</h4>", unsafe_allow_html=True)
                    filas_html = ""

                    for i, cat in enumerate(variables):
                        val_on_raw = datos_q['on'].get(cat) if datos_q['on'] else None
                        val_off_raw = datos_q['off'].get(cat) if datos_q['off'] else None

                        c_on = "#FFFFFF"
                        c_off = "#FFFFFF"

                        if val_on_raw is not None and val_off_raw is not None:
                            try:
                                num_on = float(val_on_raw)
                                num_off = float(val_off_raw)

                                if cat in menor_es_mejor:
                                    if num_on < num_off: c_on, c_off = "#4CAF50", "#F87171"
                                    elif num_on > num_off: c_on, c_off = "#F87171", "#4CAF50"
                                else:
                                    if num_on > num_off: c_on, c_off = "#4CAF50", "#F87171"
                                    elif num_on < num_off: c_on, c_off = "#F87171", "#4CAF50"
                            except ValueError:
                                pass

                        def formatear_valor(dict_stats, categoria):
                            if not dict_stats: return "-"
                            val = dict_stats.get(categoria, "-")
                            if val == "-": return "-"
                            if '%' in categoria: return f"{val}%"
                            if categoria == 'Net Rating' and float(val) > 0: return f"+{val}"
                            return str(val)

                        v_on = formatear_valor(datos_q['on'], cat)
                        v_off = formatear_valor(datos_q['off'], cat)
                        v_media = formatear_valor(datos_q['media'], cat)

                        bg_color = "transparent" if i % 2 == 0 else "rgba(255, 255, 255, 0.05)"

                        filas_html += f"""
                        <tr style="background-color: {bg_color}; border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                            <td style="padding: 12px 20px; font-weight: bold; color: #FFFFFF;">{etiqueta_stat(cat)}</td>
                            <td style="padding: 12px 20px; color: {c_on}; font-weight: bold; text-align: center; font-size: 1.1rem;">{v_on}</td>
                            <td style="padding: 12px 20px; color: {c_off}; font-weight: bold; text-align: center;">{v_off}</td>
                            <td style="padding: 12px 20px; color: #FFFFFF; font-style: italic; text-align: center; opacity: 0.8;">{v_media}</td>
                        </tr>
                        """

                    tabla_bloque = f"""
                    <div style="border-radius: 10px; overflow: visible; border: 1px solid #3F3F3F; margin-top: 10px; background-color: transparent;">
                        <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif;">
                            <thead>
                                <tr style="background-color: rgba(255, 255, 255, 0.1); color: #FFFFFF; border-bottom: 2px solid #F97316;">
                                    <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; width: 40%;">Estadística</th>
                                    <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 20%;">On</th>
                                    <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 20%;">Off</th>
                                    <th style="padding: 15px 20px; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; text-align: center; width: 20%;">Media Equipo</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas_html}
                            </tbody>
                        </table>
                    </div>
                    """
                    st.markdown(" ".join(tabla_bloque.split()), unsafe_allow_html=True)
            else:
                st.warning("Estos jugadores nunca han coincidido en pista juntos en la muestra seleccionada.")
        else:
            st.info("👆 Usa el desplegable superior para añadir jugadores al análisis.")
    else:
        st.warning("No hay jugadores registrados para este equipo.")


def ir_a(seccion):
    st.session_state.menu_principal = seccion


# ------------------------------------------------------------------
# CLASIFICACIÓN
# ------------------------------------------------------------------
def calcular_clasificacion():
    """Clasificación de liga (sin partidos de copa). Victoria = 2 puntos, derrota = 1.
    Desempate: diferencial de puntos y, si sigue el empate, enfrentamientos directos entre los empatados."""
    conexion = sqlite3.connect("mi_liga.db")
    partidos = pd.read_sql("SELECT id_equipo_local, id_equipo_visitante, puntos_local, puntos_visitante, jornada "
                           "FROM partidos", conexion)
    equipos = pd.read_sql("SELECT id_equipo, nombre, nombre_corto FROM equipos", conexion)
    conexion.close()

    # Solo liga: las jornadas de liga son números; las de copa son texto ("Octavos Copa"...)
    todos = partidos
    partidos = partidos[partidos["jornada"].astype(str).str.strip().str.isdigit()]

    filas = []
    for local, visitante, pl, pv in partidos[["id_equipo_local", "id_equipo_visitante", "puntos_local", "puntos_visitante"]].itertuples(index=False):
        filas.append((local, pl, pv))
        filas.append((visitante, pv, pl))
    df = pd.DataFrame(filas, columns=["id_equipo", "pf", "pc"])
    df["v"] = (df["pf"] > df["pc"]).astype(int)
    df["d"] = (df["pf"] < df["pc"]).astype(int)
    tabla_c = df.groupby("id_equipo").agg(pj=("pf", "size"), v=("v", "sum"), d=("d", "sum"),
                                          pf=("pf", "sum"), pc=("pc", "sum")).reset_index()
    # Todos los equipos de la competición, aunque aún no hayan jugado en liga
    en_competicion = set(todos["id_equipo_local"]) | set(todos["id_equipo_visitante"])
    tabla_c = equipos[equipos["id_equipo"].isin(en_competicion)].merge(tabla_c, on="id_equipo", how="left")
    columnas_num = ["pj", "v", "d", "pf", "pc"]
    tabla_c[columnas_num] = tabla_c[columnas_num].fillna(0).astype(int)
    tabla_c["dif"] = tabla_c["pf"] - tabla_c["pc"]
    tabla_c["pts"] = 2 * tabla_c["v"] + tabla_c["d"]

    def enfrentamientos_directos(ids):
        """Victorias y diferencial de cada equipo solo en los partidos entre los equipos empatados."""
        entre = partidos[partidos["id_equipo_local"].isin(ids) & partidos["id_equipo_visitante"].isin(ids)]
        res = {i: [0, 0] for i in ids}
        for local, visitante, pl, pv in entre[["id_equipo_local", "id_equipo_visitante", "puntos_local", "puntos_visitante"]].itertuples(index=False):
            res[local][0] += pl > pv
            res[visitante][0] += pv > pl
            res[local][1] += pl - pv
            res[visitante][1] += pv - pl
        return res

    tabla_c = tabla_c.sort_values(["pts", "dif"], ascending=False).reset_index(drop=True)
    orden = []
    for _, grupo in tabla_c.groupby(["pts", "dif"], sort=False):
        ids = grupo["id_equipo"].tolist()
        if len(ids) > 1:
            directos = enfrentamientos_directos(ids)
            ids.sort(key=lambda i: (directos[i][0], directos[i][1]), reverse=True)
        orden += ids
    tabla_c = tabla_c.set_index("id_equipo").loc[orden].reset_index()
    tabla_c.insert(0, "posicion", range(1, len(tabla_c) + 1))
    return tabla_c, len(partidos)


def mostrar_clasificacion():
    st.markdown("### 🏆 Clasificación")
    tabla_c, _ = calcular_clasificacion()
    if tabla_c.empty:
        st.info("Todavía no hay partidos de liga en la base de datos.")
        return

    estilo_th = "padding: 12px 10px; border-bottom: 2px solid #F97316; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 1px; text-align: center;"
    cabeceras = [("#", ""), ("Equipo", "text-align: left;"), ("Pts", ""), ("PJ", ""), ("V", ""), ("D", ""),
                 ("PF", ""), ("PC", ""), ("Dif.", "")]
    definiciones = {"Pts": "Puntos de clasificación: 2 por victoria y 1 por derrota.", "PJ": "Partidos jugados",
                    "V": "Victorias", "D": "Derrotas", "PF": "Puntos a favor", "PC": "Puntos en contra",
                    "Dif.": "Diferencial de puntos (a favor − en contra)"}
    ths = "".join(f"<th style='{estilo_th} {extra}'>"
                  f"{seccion_propio.tip(c, definiciones[c]) if c in definiciones else c}</th>"
                  for c, extra in cabeceras)
    trs = ""
    for i, r in enumerate(tabla_c.itertuples()):
        es_propio = r.nombre == seccion_propio.bd.NOMBRE_EQUIPO_PROPIO
        fondo = "rgba(249, 115, 22, 0.15)" if es_propio else ("transparent" if i % 2 == 0 else "rgba(255, 255, 255, 0.05)")
        escudo = obtener_escudo_base64(r.nombre_corto)
        img = (f'<img src="data:image/png;base64,{escudo}" style="height: 34px; width: 34px; flex-shrink: 0; object-fit: contain; margin-right: 12px;">'
               if escudo else
               f'<span style="display: inline-flex; flex-shrink: 0; width: 34px; height: 34px; margin-right: 12px; border-radius: 50%; background: #262626; color: #F97316; font-size: 0.75rem; font-weight: bold; align-items: center; justify-content: center; vertical-align: middle;">{r.nombre_corto}</span>')
        color_dif = "#4ADE80" if r.dif > 0 else ("#F87171" if r.dif < 0 else "#FFFFFF")
        td = "padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.2); text-align: center;"
        trs += (f"<tr style='background-color: {fondo};'>"
                f"<td style='{td} font-weight: bold; color: #F97316;'>{r.posicion}</td>"
                f"<td style='{td} text-align: left; font-weight: bold;'>"
                f"<div style='display: flex; align-items: center;'>{img}<span>{r.nombre}</span></div></td>"
                f"<td style='{td} font-weight: 800; font-size: 1.1rem;'>{r.pts}</td>"
                f"<td style='{td}'>{r.pj}</td><td style='{td}'>{r.v}</td><td style='{td}'>{r.d}</td>"
                f"<td style='{td}'>{r.pf}</td><td style='{td}'>{r.pc}</td>"
                f"<td style='{td} color: {color_dif}; font-weight: bold;'>{r.dif:+d}</td></tr>")
    tabla_html = f"""
    <div style="border-radius: 10px; overflow: visible; border: 1px solid #3F3F3F; margin-top: 10px;">
        <table style="width: 100%; border-collapse: collapse; color: #FFFFFF; font-size: 0.95rem;">
            <thead><tr style="background-color: rgba(255, 255, 255, 0.1);">{ths}</tr></thead>
            <tbody>{trs}</tbody>
        </table>
    </div>
    """
    st.markdown(" ".join(tabla_html.split()), unsafe_allow_html=True)


def resumen_portada():
    """Cifras de la portada: partidos, equipos y posesiones etiquetadas."""
    conexion = sqlite3.connect("mi_liga.db")
    partidos = conexion.execute("SELECT COUNT(*) FROM partidos").fetchone()[0]
    # Equipos que han jugado algún partido, en casa o fuera
    equipos = conexion.execute("SELECT COUNT(*) FROM (SELECT id_equipo_local FROM partidos "
                               "UNION SELECT id_equipo_visitante FROM partidos)").fetchone()[0]
    try:
        etiquetadas = sum(conexion.execute(f"SELECT COUNT(playtype) FROM {t}").fetchone()[0]
                          for t in ("propio_ataque", "propio_defensa"))
    except sqlite3.OperationalError:  # todavía no se ha abierto el etiquetador
        etiquetadas = 0
    conexion.close()
    return partidos, equipos, etiquetadas


def mostrar_portada():
    """Pantalla de bienvenida: escudo, nombre de la app y botones para elegir sección."""
    # En la portada no hace falta la barra lateral
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
                "[data-testid='stExpandSidebarButton'] {display: none;}</style>", unsafe_allow_html=True)

    escudo = obtener_escudo_base64("ATL")
    escudo_html = (f'<img src="data:image/png;base64,{escudo}" style="height: 130px; border-radius: 14px; box-shadow: 0 0 35px rgba(249,115,22,0.55);">'
                   if escudo else '<div style="font-size: 6rem;">🏀</div>')
    partidos, equipos, etiquetadas = resumen_portada()

    portada = f"""
    <div style="text-align: center; padding: 0 10px 0 10px;">
        {escudo_html}
        <p style="color: #F97316; font-weight: 700; letter-spacing: 6px; text-transform: uppercase; margin: 20px 0 5px 0; font-size: 0.9rem;">Ongi etorri · Te damos la bienvenida</p>
        <h1 style="color: #FFFFFF; font-size: 2.7rem; font-weight: 900; margin: 0; padding: 0; line-height: 1.1; text-transform: uppercase;">Segunda Nacional Masculino</h1>
        <p style="color: #D4D4D4; font-size: 1.2rem; margin: 6px 0 0 0; letter-spacing: 2px;">Temporada 2026-27 · Scouting del Atlético San Sebastián</p>
        <div style="display: flex; justify-content: center; gap: 40px; margin: 20px auto 5px auto; flex-wrap: wrap;">
            <div><div style="color: #FFFFFF; font-size: 2rem; font-weight: 800;">{partidos}</div><div style="color: #A3A3A3; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px;">Partidos</div></div>
            <div><div style="color: #FFFFFF; font-size: 2rem; font-weight: 800;">{equipos}</div><div style="color: #A3A3A3; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px;">Equipos</div></div>
            <div><div style="color: #FFFFFF; font-size: 2rem; font-weight: 800;">{etiquetadas}</div><div style="color: #A3A3A3; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px;">Posesiones etiquetadas</div></div>
        </div>
        <p style="color: #A3A3A3; margin: 15px 0 5px 0; font-size: 1.05rem;">¿A qué sección quieres ir?</p>
    </div>
    """
    st.markdown(" ".join(portada.split()), unsafe_allow_html=True)

    tarjetas = {
        "Propio": ("⚔️", "Atlético San Sebastián",
                   "Quintetos, estadística, ataque, defensa y análisis individual de nuestro equipo."),
        "Liga": ("🏆", "Segunda Nacional",
                 "Rankings, gráficos y fichas de todos los equipos y jugadores de la liga."),
        "Clasificación": ("📋", "Tabla de liga",
                          "Victorias, derrotas, puntos a favor y en contra de todos los equipos."),
        "Partidos": ("🗓️", "Liga y copa",
                     "Resumen, boxscore, estadísticas y rotaciones de cada partido."),
    }
    # Las dos tarjetas van en una misma rejilla para que siempre midan lo mismo; cada tarjeta es un enlace
    # (?seccion=...) que se procesa al principio del script, igual que los enlaces a las fichas de jugador.
    html_tarjetas = ""
    for seccion, (icono, subtitulo, descripcion) in tarjetas.items():
        html_tarjetas += f"""
        <a class="tarjeta-portada" href="?seccion={seccion}" target="_self">
            <div style="font-size: 3rem;">{icono}</div>
            <h2>{seccion}</h2>
            <p class="subtitulo">{subtitulo}</p>
            <p class="descripcion">{descripcion}</p>
            <span class="boton">Entrar en {seccion}</span>
        </a>
        """
    st.markdown("""
    <style>
    .rejilla-portada { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px;
                       max-width: 1240px; margin: 10px auto 0 auto; }
    .tarjeta-portada { display: flex; flex-direction: column; align-items: center; text-align: center;
                       background: linear-gradient(160deg, #1A1A1A 0%, #0B0B0B 100%); border: 1px solid #333333;
                       border-top: 4px solid #F97316; border-radius: 16px; padding: 24px 25px;
                       box-shadow: 0 10px 30px rgba(0,0,0,0.6); text-decoration: none !important;
                       transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s; }
    .tarjeta-portada:hover { transform: translateY(-4px); border-color: #F97316;
                             box-shadow: 0 14px 35px rgba(249,115,22,0.25); }
    .tarjeta-portada h2 { color: #FFFFFF; margin: 10px 0 0 0; padding: 0; font-size: clamp(1.25rem, 1.6vw, 2rem);
                          text-transform: uppercase; letter-spacing: 2px; white-space: nowrap; }
    .tarjeta-portada .subtitulo { color: #F97316; font-weight: 700; margin: 4px 0 12px 0; letter-spacing: 1px; }
    .tarjeta-portada .descripcion { color: #D4D4D4; margin: 0 0 20px 0; font-size: 0.95rem; }
    .tarjeta-portada .boton { margin-top: auto; width: 100%; background: #F97316; color: #FFFFFF; font-weight: 600;
                              padding: 10px 0; border-radius: 8px; }
    .tarjeta-portada:hover .boton { background: #FB923C; }
    </style>
    """.replace("\n", " ") + " ".join(f'<div class="rejilla-portada">{html_tarjetas}</div>'.split()),
                unsafe_allow_html=True)


if st.session_state.menu_principal not in ("Inicio", "Propio", "Liga", "Clasificación", "Partidos"):
    st.session_state.menu_principal = "Inicio"  # sesiones antiguas que estaban en secciones eliminadas

if st.session_state.menu_principal == "Inicio":
    mostrar_portada()
    st.stop()

# Menú de Navegación Lateral (fuera de la portada)
with st.sidebar:
    escudo_lateral = obtener_escudo_base64("ATL")
    if escudo_lateral:
        st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{escudo_lateral}" style="height: 80px;"></div>',
                    unsafe_allow_html=True)
    st.header("Navegación")
    st.button("🏠 Inicio", use_container_width=True, on_click=ir_a, args=("Inicio",))
    opciones_menu = ["Propio", "Liga", "Clasificación", "Partidos"]
    menu = st.radio("Selecciona una vista:", opciones_menu, index=opciones_menu.index(st.session_state.menu_principal))
    st.session_state.menu_principal = menu

en_ficha_equipo = (st.session_state.menu_principal == "Liga" and st.session_state.submenu_liga == "Equipos" and st.session_state.equipo_seleccionado is not None)

if not en_ficha_equipo:
    st.title("🏀 Segunda Nacional Masculino 2026-27: Scouting")


# Enrutador Principal
if st.session_state.menu_principal == "Clasificación":
    mostrar_clasificacion()

elif st.session_state.menu_principal == "Partidos":
    seccion_partidos.mostrar_partidos()

elif st.session_state.menu_principal == "Propio":
    # La sección Propio vive en seccion_propio.py y reutiliza estas vistas de la liga
    seccion_propio.mostrar_propio(SimpleNamespace(
        mostrar_analisis_quintetos=mostrar_analisis_quintetos,
        mostrar_perfil_jugador=mostrar_perfil_jugador,
        mostrar_impacto_jugador=mostrar_impacto_jugador,
        cargar_plantilla=cargar_plantilla,
        obtener_foto_jugador_base64=obtener_foto_jugador_base64,
        calcular_stats_individuales_liga=calcular_stats_individuales_liga,
        grafico_uso_eficiencia=grafico_uso_eficiencia,
        etiqueta_stat=etiqueta_stat,
        tablas_individuales=TABLAS_INDIVIDUALES,
    ))

elif st.session_state.menu_principal == "Liga":
    if not en_ficha_equipo:
        st.markdown("### Visión General de la Liga")
            
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📊 Rankings", use_container_width=True, type="primary" if st.session_state.submenu_liga == 'Rankings' else "secondary"):
                st.session_state.submenu_liga = 'Rankings'
                st.rerun()
        with col_btn2:
            if st.button("🛡️ Equipos", use_container_width=True, type="primary" if st.session_state.submenu_liga == 'Equipos' else "secondary"):
                st.session_state.submenu_liga = 'Equipos'
                st.rerun()
                
        st.write("---")
    
    if st.session_state.submenu_liga == "Rankings":
        st.markdown("#### Buscador de Estadísticas y Rankings")
        
        st.markdown("""
        <div style="background-color: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; border: 1px solid #3F3F3F; margin-bottom: 20px;">
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        tipo_stat = col1.selectbox("Tipo de Estadística", ["Individual", "Equipo", "Gráfico"])
        
        dict_stats_indiv = {
            "Impacto": ['Diferencial Offensive Rating', 'Diferencial Defensive Rating', 'Diferencial Net Rating'],
            "Minutos": ['Minutos Totales', 'Minutos por partido', '% Minutos'],
            "Anotación": ['Rating Anotación', 'Puntos totales', 'Puntos por partido', 'Puntos p100', '%T2', '2PAr', '%T3', '3PAr', '%TL', 'FTr', 'eFG%', 'TS%', '%USG', 'PPP'],
            "Rebote": ['Rating Rebote', 'RD pp', 'RD p100', 'DREB%', 'RO pp', 'RO p100', 'OREB%', 'RT pp', 'RT p100', 'REB%'],
            "Cuidado de balón": ['Rating Cuidado de Balón', 'Asistencias pp', 'Asistencias p100', 'AST%', 'Pérdidas pp', 'Pérdidas p100', 'TOV%', 'AST / TO'],
            "Defensa": ['Rating Defensa', 'STL pp', 'STL p100', 'STL%', 'BLK pp', 'BLK p100', 'BLK%']
        }
        
        dict_stats_eq = {
            "Posesiones": ['Ritmo', 'Plays', 'Offensive Rating', 'Defensive Rating', 'Net Rating'],
            "Tiro": ['eFG%', 'TS%', 'FTr', '2PAr', '3PAr'],
            "Rebote": ['DREB%', 'OREB%', 'REB%'],
            "Cuidado de balón": ['TOV%', 'AST / TO ratio', 'AST%']
        }
        # En Rankings, 2PAr y 3PAr son los nombres que se muestran de las columnas 2PA% y 3PA%
        COLUMNA_RANKING = {'2PAr': '2PA%', '3PAr': '3PA%'}
        
        stat_seleccionada = None
        grafico_seleccionado = None
        
        if tipo_stat == "Individual":
            apartado = col2.selectbox("Apartado", list(dict_stats_indiv.keys()))
            opciones_stat = dict_stats_indiv[apartado]
            stat_seleccionada = col3.selectbox("Estadística", opciones_stat)
            if definicion_stat(stat_seleccionada, jugador=True):
                col3.caption(definicion_stat(stat_seleccionada, jugador=True))
        elif tipo_stat == "Equipo":
            apartado = col2.selectbox("Apartado", list(dict_stats_eq.keys()))
            opciones_stat = dict_stats_eq[apartado]
            stat_seleccionada = col3.selectbox("Estadística", opciones_stat)
            if definicion_stat(stat_seleccionada):
                col3.caption(definicion_stat(stat_seleccionada))
        else:
            opciones_graficos = ["Mapa de Eficiencia (Off/Def Rtg)", "Uso vs Eficiencia (%USG vs PPP)"]
            grafico_seleccionado = col2.selectbox("Selecciona un gráfico", opciones_graficos)
        
        filtro_rango = None
        equipo_filtro = None
        filtro_rango_grafico = None
        equipo_filtro_grafico = None
        
        if tipo_stat == "Individual":
            st.markdown("<hr style='margin: 10px 0; border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                filtro_rango = st.radio("Mostrar:", ["Top 10", "Top 50", "Top 100", "Todos", "Por Equipo"], horizontal=True)
            if filtro_rango == "Por Equipo":
                df_eq_options = cargar_equipos()
                if not df_eq_options.empty:
                    eq_nombres = df_eq_options['nombre'].tolist()
                    with col_f2:
                        equipo_filtro = st.selectbox("Selecciona equipo", eq_nombres, label_visibility="collapsed")
                        
        elif tipo_stat == "Gráfico" and grafico_seleccionado == "Uso vs Eficiencia (%USG vs PPP)":
            st.markdown("<hr style='margin: 10px 0; border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                filtro_rango_grafico = st.radio(
                    "Mostrar:", 
                    ["Top 10 más usados", "Top 20 más usados", "Top 10 más eficientes", "Top 20 más eficientes", "Todos", "Por Equipo"], 
                    horizontal=True
                )
            if filtro_rango_grafico == "Por Equipo":
                df_eq_options = cargar_equipos()
                if not df_eq_options.empty:
                    eq_nombres = df_eq_options['nombre'].tolist()
                    with col_f2:
                        equipo_filtro_grafico = st.selectbox("Selecciona equipo para gráfico", eq_nombres, label_visibility="collapsed")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        def format_stat_value(val, stat_name):
            if pd.isna(val): return "-"
            if 'Diferencial' in stat_name:
                if float(val) > 0: return f"+{float(val):.1f}"
                return f"{float(val):.1f}"
            if '%' in stat_name or stat_name in ['eFG%', 'TS%', 'DREB%', 'OREB%', 'REB%', 'TOV%', 'AST%', '2PAr', '3PAr']:
                return f"{float(val):.1f}%"
            if 'Rating' in stat_name:
                return f"{float(val):.1f}"
            if stat_name in ['FTr', 'AST / TO', 'AST / TO ratio']:
                return f"{float(val):.2f}"
            if float(val).is_integer():
                return str(int(val))
            return f"{float(val):.1f}"

        if tipo_stat == "Gráfico":
            if grafico_seleccionado == "Mapa de Eficiencia (Off/Def Rtg)":
                df_eq_stats = calcular_stats_avanzadas_liga()
                if not df_eq_stats.empty:
                    df_eq_nombres = cargar_equipos()
                    df_res = df_eq_stats.merge(df_eq_nombres, on="id_equipo", how="inner")
                    
                    avg_off = df_res['Offensive Rating'].mean()
                    avg_def = df_res['Defensive Rating'].mean()
                    
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=df_res['Offensive Rating'],
                        y=df_res['Defensive Rating'],
                        mode='markers+text',
                        text=df_res['nombre_corto'],
                        textposition="bottom center",
                        marker=dict(size=1, color='rgba(0,0,0,0)'),
                        hovertemplate="<b>%{text}</b><br>Off Rtg: %{x}<br>Def Rtg: %{y}<extra></extra>"
                    ))
                    
                    fig.add_hline(y=avg_def, line_dash="solid", line_color="#D4D4D4", line_width=1)
                    fig.add_vline(x=avg_off, line_dash="solid", line_color="#D4D4D4", line_width=1)
                    
                    rango_off = df_res['Offensive Rating'].max() - df_res['Offensive Rating'].min()
                    rango_def = df_res['Defensive Rating'].max() - df_res['Defensive Rating'].min()
                    size_x = max(1.5, rango_off * 0.08)
                    size_y = max(1.5, rango_def * 0.08)
                    
                    for _, row in df_res.iterrows():
                        img_b64 = obtener_escudo_base64(row['nombre_corto'])
                        if img_b64:
                            img_src = f"data:image/png;base64,{img_b64}"
                            fig.add_layout_image(
                                dict(
                                    source=img_src,
                                    xref="x",
                                    yref="y",
                                    xanchor="center",
                                    yanchor="middle",
                                    x=row['Offensive Rating'],
                                    y=row['Defensive Rating'],
                                    sizex=size_x,
                                    sizey=size_y,
                                    sizing="contain",
                                    opacity=1,
                                    layer="above"
                                )
                            )
                        else:
                            fig.add_trace(go.Scatter(
                                x=[row['Offensive Rating']],
                                y=[row['Defensive Rating']],
                                mode='markers+text',
                                text=[row['nombre_corto']],
                                textposition="top center",
                                marker=dict(size=10, color='#F97316'),
                                showlegend=False,
                                hoverinfo='skip'
                            ))
                            
                    fig.add_annotation(x=0.01, y=0.99, xref="paper", yref="paper", text="🛡️ Mejor Defensa<br>🧱 Peor Ataque", showarrow=False, font=dict(color="#A3A3A3"), align="left")
                    fig.add_annotation(x=0.99, y=0.99, xref="paper", yref="paper", text="⚔️ Mejor Ataque<br>🛡️ Mejor Defensa", showarrow=False, font=dict(color="#4CAF50"), align="right")
                    fig.add_annotation(x=0.01, y=0.01, xref="paper", yref="paper", text="🧱 Peor Ataque<br>🛑 Peor Defensa", showarrow=False, font=dict(color="#E53935"), align="left")
                    fig.add_annotation(x=0.99, y=0.01, xref="paper", yref="paper", text="⚔️ Mejor Ataque<br>🛑 Peor Defensa", showarrow=False, font=dict(color="#A3A3A3"), align="right")

                    fig.update_layout(
                        title=dict(text="Efficiency Landscape", font=dict(color="#FFFFFF", size=24), x=0.01, y=0.98),
                        xaxis_title="Offensive Rating ⟶",
                        yaxis_title="Defensive Rating ⟶ (Invertido)",
                        yaxis=dict(autorange="reversed", gridcolor='rgba(255,255,255,0.05)', zeroline=False),
                        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', zeroline=False),
                        plot_bgcolor='rgba(20, 20, 20, 0.85)', 
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#D4D4D4'),
                        margin=dict(l=60, r=60, t=80, b=60),
                        height=650
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No hay datos suficientes de equipo.")
                    
            elif grafico_seleccionado == "Uso vs Eficiencia (%USG vs PPP)":
                df_indiv = calcular_stats_individuales_liga()
                if not df_indiv.empty and 'PPP' in df_indiv.columns:
                    conn = sqlite3.connect("mi_liga.db")
                    df_jug_nombres = pd.read_sql("SELECT id_jugador, nombre as Jugador FROM jugadores", conn)
                    df_eq_nombres = pd.read_sql("SELECT id_equipo, nombre_corto as Equipo FROM equipos", conn)
                    conn.close()
                    
                    df_res = df_indiv.merge(df_jug_nombres, on="id_jugador", how="inner")
                    df_res = df_res.merge(df_eq_nombres, on="id_equipo", how="inner")
                    
                    df_res = df_res.dropna(subset=['%USG', 'PPP'])
                    
                    if filtro_rango_grafico == "Por Equipo" and equipo_filtro_grafico:
                        conn = sqlite3.connect("mi_liga.db")
                        eq_selec_id = pd.read_sql("SELECT id_equipo FROM equipos WHERE nombre = ?", conn, params=(equipo_filtro_grafico,))
                        conn.close()
                        if not eq_selec_id.empty:
                            df_res = df_res[df_res['id_equipo'] == eq_selec_id.iloc[0]['id_equipo']]
                    elif filtro_rango_grafico == "Top 10 más usados":
                        df_res = df_res.sort_values(by='%USG', ascending=False).head(10)
                    elif filtro_rango_grafico == "Top 20 más usados":
                        df_res = df_res.sort_values(by='%USG', ascending=False).head(20)
                    elif filtro_rango_grafico == "Top 10 más eficientes":
                        df_res = df_res.sort_values(by='PPP', ascending=False).head(10)
                    elif filtro_rango_grafico == "Top 20 más eficientes":
                        df_res = df_res.sort_values(by='PPP', ascending=False).head(20)
                        
                    grafico_uso_eficiencia(df_res)
                else:
                    st.warning("No hay datos suficientes de jugadores.")

        elif tipo_stat == "Individual":
            df_indiv = calcular_stats_individuales_liga()
            if not df_indiv.empty:
                conn = sqlite3.connect("mi_liga.db")
                df_jug_nombres = pd.read_sql("SELECT id_jugador, nombre as Jugador FROM jugadores", conn)
                df_eq_nombres = pd.read_sql("SELECT id_equipo, nombre_corto as Equipo FROM equipos", conn)
                conn.close()
                
                df_res = df_indiv.merge(df_jug_nombres, on="id_jugador", how="inner")
                df_res = df_res.merge(df_eq_nombres, on="id_equipo", how="inner")
                
                if filtro_rango == "Por Equipo" and equipo_filtro:
                    conn = sqlite3.connect("mi_liga.db")
                    eq_selec_id = pd.read_sql("SELECT id_equipo FROM equipos WHERE nombre = ?", conn, params=(equipo_filtro,))
                    conn.close()
                    if not eq_selec_id.empty:
                        df_res = df_res[df_res['id_equipo'] == eq_selec_id.iloc[0]['id_equipo']]
                
                ascendente = True if stat_seleccionada in ['Pérdidas pp', 'Pérdidas p100', 'TOV%', 'Diferencial Defensive Rating'] else False
                df_res = df_res.sort_values(by=COLUMNA_RANKING.get(stat_seleccionada, stat_seleccionada), ascending=ascendente)

                if filtro_rango == "Top 10": df_res = df_res.head(10)
                elif filtro_rango == "Top 50": df_res = df_res.head(50)
                elif filtro_rango == "Top 100": df_res = df_res.head(100)
                
                ths = f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 10%; text-align: center;'># Rank</th>" \
                      f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 40%;'>Jugador</th>" \
                      f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 25%; text-align: center;'>Equipo</th>" \
                      f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 25%; text-align: center;'>{etiqueta_stat(stat_seleccionada, jugador=True)}</th>"
                
                trs = ""
                for idx, (i, row) in enumerate(df_res.iterrows()):
                    bg_color = "transparent" if idx % 2 == 0 else "rgba(255, 255, 255, 0.05)"
                    
                    j_id = row['id_jugador']
                    eq_id = row['id_equipo']
                    enlace = f"/?jugador_id={j_id}&equipo_id={eq_id}"
                    
                    jug_name = f"<a href='{enlace}' target='_self' style='color: #FFFFFF; text-decoration: none; transition: color 0.2s;' onmouseover=\"this.style.color='#F97316'\" onmouseout=\"this.style.color='#FFFFFF'\">{row['Jugador']}</a>"
                    
                    val_str = format_stat_value(row.get(COLUMNA_RANKING.get(stat_seleccionada, stat_seleccionada)), stat_seleccionada)
                    
                    tds = f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #F97316; font-weight: bold; text-align: center;'>{idx + 1}</td>" \
                          f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); font-weight: bold;'>{jug_name}</td>" \
                          f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #D4D4D4; text-align: center;'>{row['Equipo']}</td>" \
                          f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #FFFFFF; font-size: 1.1rem; font-weight: bold; text-align: center;'>{val_str}</td>"
                    
                    trs += f"<tr style='background-color: {bg_color};'>{tds}</tr>"

                tabla_html = f'''
                <div style="border-radius: 10px; overflow: visible; border: 1px solid #3F3F3F; background-color: transparent;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif; font-size: 1rem;">
                        <thead>
                            <tr style="background-color: rgba(255, 255, 255, 0.1); color: #FFFFFF;">
                                {ths}
                            </tr>
                        </thead>
                        <tbody>
                            {trs}
                        </tbody>
                    </table>
                </div>
                '''
                st.markdown(tabla_html, unsafe_allow_html=True)
            else:
                st.warning("No hay datos individuales disponibles.")
                
        elif tipo_stat == "Equipo":
            df_eq_stats = calcular_stats_avanzadas_liga()
            if not df_eq_stats.empty:
                df_eq_nombres = cargar_equipos()
                df_res = df_eq_stats.merge(df_eq_nombres, on="id_equipo", how="inner")
                
                ascendente = True if stat_seleccionada in ['Defensive Rating', 'TOV%'] else False
                df_res = df_res.sort_values(by=COLUMNA_RANKING.get(stat_seleccionada, stat_seleccionada), ascending=ascendente)
                
                ths = f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 10%; text-align: center;'># Rank</th>" \
                      f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 50%;'>Equipo</th>" \
                      f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 40%; text-align: center;'>{etiqueta_stat(stat_seleccionada)}</th>"
                
                trs = ""
                for idx, (i, row) in enumerate(df_res.iterrows()):
                    bg_color = "transparent" if idx % 2 == 0 else "rgba(255, 255, 255, 0.05)"
                    
                    val_str = format_stat_value(row.get(COLUMNA_RANKING.get(stat_seleccionada, stat_seleccionada)), stat_seleccionada)
                    
                    tds = f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #F97316; font-weight: bold; text-align: center;'>{idx + 1}</td>" \
                          f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #FFFFFF; font-weight: bold;'>{row['nombre']}</td>" \
                          f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); color: #FFFFFF; font-size: 1.1rem; font-weight: bold; text-align: center;'>{val_str}</td>"
                    
                    trs += f"<tr style='background-color: {bg_color};'>{tds}</tr>"

                tabla_html = f'''
                <div style="border-radius: 10px; overflow: visible; border: 1px solid #3F3F3F; background-color: transparent;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif; font-size: 1rem;">
                        <thead>
                            <tr style="background-color: rgba(255, 255, 255, 0.1); color: #FFFFFF;">
                                {ths}
                            </tr>
                        </thead>
                        <tbody>
                            {trs}
                        </tbody>
                    </table>
                </div>
                '''
                st.markdown(tabla_html, unsafe_allow_html=True)
            else:
                st.warning("No hay datos de equipo disponibles.")

    elif st.session_state.submenu_liga == "Equipos":
        if not en_ficha_equipo:
            st.markdown("#### Directorio de Equipos")
            df_equipos = cargar_equipos()

            if not df_equipos.empty:
                num_columnas = 4 
                for i in range(0, len(df_equipos), num_columnas):
                    columnas = st.columns(num_columnas)
                    for j in range(num_columnas):
                        if i + j < len(df_equipos):
                            equipo = df_equipos.iloc[i + j]
                            with columnas[j]:
                                nombre_corto = equipo['nombre_corto']
                                img_base64 = obtener_escudo_base64(nombre_corto)
                                if img_base64:
                                    grafico_equipo = f'<img src="data:image/png;base64,{img_base64}" style="max-width: 90px; max-height: 90px; object-fit: contain;">'
                                else:
                                    grafico_equipo = f'<div style="width: 80px; height: 80px; background-color: #262626; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #F97316; font-weight: bold; font-size: 1.4rem; border: 2px solid #3F3F3F;">{nombre_corto[:3]}</div>'

                                st.markdown(f"""
                                <div style="background-color: #1A1A1A; border: 1px solid #333333; border-radius: 10px 10px 0 0; padding: 25px 15px 15px 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; aspect-ratio: 1 / 1; border-bottom: none;">
                                    <div style="flex-grow: 1; display: flex; align-items: center; justify-content: center; width: 100%;">
                                        {grafico_equipo}
                                    </div>
                                    <div style="width: 100%; text-align: center; margin-top: 15px;">
                                        <h4 style="color: #F97316; margin: 0 0 5px 0; font-size: 0.85rem; text-transform: uppercase; line-height: 1.2;">{equipo['nombre']}</h4>
                                        <p style="color: #A3A3A3; margin: 0; font-size: 0.9rem; font-weight: bold;">{nombre_corto}</p>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                if st.button(f"Entrar", key=f"btn_eq_{equipo['id_equipo']}", use_container_width=True):
                                    st.session_state.equipo_seleccionado = equipo['id_equipo']
                                    st.rerun()
            else:
                st.info("No hay equipos registrados en la base de datos.")

        else:
            if st.session_state.jugador_seleccionado is not None:
                # --- FICHA INDIVIDUAL DE JUGADOR ---
                if st.button("⬅️ Volver a la Plantilla"):
                    st.session_state.jugador_seleccionado = None
                    st.rerun()
                
                info_jug = obtener_info_basica_jugador(st.session_state.jugador_seleccionado, st.session_state.equipo_seleccionado)
                
                foto_base64 = obtener_foto_jugador_base64(info_jug['nombre'])
                if foto_base64:
                    img_html = f'<img src="data:image/png;base64,{foto_base64}" style="width: 130px; height: 130px; object-fit: cover; border-radius: 12px; border: 3px solid #D4D4D4; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">'
                else:
                    iniciales = "".join([p[0] for p in info_jug['nombre'].split()[:2]]).upper() if info_jug['nombre'] else "?"
                    img_html = f'<div style="width: 130px; height: 130px; background-color: #262626; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #F97316; font-weight: bold; font-size: 3rem; border: 3px solid #FFFFFF; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">{iniciales}</div>'
                
                escudo_base64 = obtener_escudo_base64(info_jug['equipo_corto'])
                if escudo_base64:
                    escudo_html = f'<img src="data:image/png;base64,{escudo_base64}" style="height: 25px; margin-left: 8px; vertical-align: middle;">'
                else:
                    escudo_html = f'<span style="background-color: #FFFFFF; color: #F97316; padding: 2px 6px; border-radius: 4px; margin-left: 8px; font-weight: bold; font-size: 0.8rem;">{info_jug["equipo_corto"]}</span>'
                    
                color_fondo = info_jug['equipo_color'] if pd.notna(info_jug['equipo_color']) and str(info_jug['equipo_color']).strip() else "#262626"
                
                header_html = f"""
                <div style="background: linear-gradient(135deg, #262626 0%, #0B0B0B 100%); border-radius: 15px; padding: 30px; display: flex; align-items: center; margin-bottom: 30px; border: 1px solid #333333; border-left: 5px solid #F97316; box-shadow: 0 8px 16px rgba(0,0,0,0.3);">
                    <div style="margin-right: 30px; flex-shrink: 0;">
                        {img_html}
                    </div>
                    <div style="flex-grow: 1; display: flex; flex-direction: column; justify-content: center;">
                        <div style="display: flex; align-items: baseline; margin-bottom: 5px;">
                            <span style="color: #A3A3A3; font-size: 2.5rem; font-weight: 800; margin-right: 15px; letter-spacing: -1px;">#{info_jug['dorsal']}</span>
                            <span style="color: #FFFFFF; font-size: 2.5rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">{info_jug['nombre']}</span>
                        </div>
                        <div style="display: flex; align-items: center; margin-bottom: 12px; background-color: rgba(255,255,255,0.1); padding: 5px 15px; border-radius: 20px; width: fit-content;">
                            <span style="color: #E5E5E5; font-size: 1.1rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;">{info_jug['equipo_nombre']}</span>
                            {escudo_html}
                        </div>
                        <div style="display: flex; align-items: center;">
                            <span style="background-color: rgba(249, 115, 22, 0.15); border: 1px solid #F97316; color: #E5E5E5; padding: 4px 12px; border-radius: 6px; font-size: 0.95rem; font-weight: 500;">
                                🏀 Partidos jugados: <span style="color: #FFFFFF; font-weight: 800; font-size: 1.1rem; margin-left: 5px;">{info_jug['pj']}</span>
                            </span>
                        </div>
                    </div>
                </div>
                """
                st.markdown(header_html, unsafe_allow_html=True)

                col_menu, col_filt = st.columns([3, 1])
                with col_menu:
                    if 'sub_vista_jugador' not in st.session_state:
                        st.session_state.sub_vista_jugador = 'Perfil'
                    
                    btn1, btn2, _, _ = st.columns(4)
                    with btn1:
                        if st.button("👤 Perfil", use_container_width=True, type="primary" if st.session_state.sub_vista_jugador == 'Perfil' else "secondary"): 
                            st.session_state.sub_vista_jugador = 'Perfil'
                            st.rerun()
                    with btn2:
                        if st.button("💥 Impacto", use_container_width=True, type="primary" if st.session_state.sub_vista_jugador == 'Impacto' else "secondary"): 
                            st.session_state.sub_vista_jugador = 'Impacto'
                            st.rerun()
                
                with col_filt:
                    st.write("")
                    filtro_4_jug = st.checkbox("Últimos 4 partidos", key="chk_4_jug", value=False)
                
                ultimos_n_jug = 4 if filtro_4_jug else None

                if st.session_state.sub_vista_jugador == 'Perfil':
                    mostrar_perfil_jugador(st.session_state.jugador_seleccionado, ultimos_n_jug)
                
                # ----------------------- VISTA: IMPACTO -----------------------
                elif st.session_state.sub_vista_jugador == 'Impacto':
                    mostrar_impacto_jugador(st.session_state.jugador_seleccionado, st.session_state.equipo_seleccionado, ultimos_n_jug)

            else:
                # --- FICHA DE EQUIPO NORMAL ---
                if st.button("⬅️ Volver al Directorio"):
                    st.session_state.equipo_seleccionado = None
                    st.rerun()
                
                df_equipos = cargar_equipos()
                equipo_actual = df_equipos[df_equipos['id_equipo'] == st.session_state.equipo_seleccionado].iloc[0]
                nombre_corto = equipo_actual['nombre_corto']
                img_base64 = obtener_escudo_base64(nombre_corto)
                color_equipo = equipo_actual['color'] if pd.notna(equipo_actual['color']) and str(equipo_actual['color']).strip() else "#262626"
                
                if img_base64:
                    escudo_header = f'<img src="data:image/png;base64,{img_base64}" style="max-height: 80px; margin-right: 20px;">'
                else:
                    escudo_header = f'<div style="width: 70px; height: 70px; background-color: #FFFFFF; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #F97316; font-weight: bold; font-size: 1.2rem; margin-right: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">{nombre_corto[:3]}</div>'

                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #262626 0%, #0B0B0B 100%); border: 1px solid #333333; border-left: 5px solid #F97316; border-radius: 12px; padding: 25px; display: flex; align-items: center; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    {escudo_header}
                    <div>
                        <h1 style="color: #FFFFFF; margin: 0; font-size: 2rem; text-transform: uppercase; text-shadow: 1px 1px 3px rgba(0,0,0,0.5);">{equipo_actual['nombre']}</h1>
                        <span style="color: #FFFFFF; font-size: 1.1rem; font-weight: 600; letter-spacing: 2px; text-shadow: 1px 1px 3px rgba(0,0,0,0.5); opacity: 0.9;">{nombre_corto}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if 'vista_equipo' not in st.session_state:
                    st.session_state.vista_equipo = 'Plantilla'
                    
                col_stats, col_plantilla = st.columns(2)
                with col_stats:
                    if st.button("📊 Stats", key="btn_stats_eq", use_container_width=True, type="primary" if st.session_state.vista_equipo == 'Stats' else "secondary"):
                        st.session_state.vista_equipo = 'Stats'
                        st.rerun()
                with col_plantilla:
                    if st.button("👥 Plantilla", key="btn_plantilla_eq", use_container_width=True, type="primary" if st.session_state.vista_equipo == 'Plantilla' else "secondary"):
                        st.session_state.vista_equipo = 'Plantilla'
                        st.rerun()
                        
                st.write("---")
                
                if st.session_state.vista_equipo == 'Stats':
                    
                    # "Stats" reúne las antiguas vistas de stats tradicionales y avanzadas
                    if st.session_state.get('sub_vista_stats') in (None, 'Stats tradicionales', 'Stats avanzadas', 'Estado de Forma'):
                        st.session_state.sub_vista_stats = 'Stats'

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        if st.button("📈 Stats", use_container_width=True, type="primary" if st.session_state.sub_vista_stats == 'Stats' else "secondary"):
                            st.session_state.sub_vista_stats = 'Stats'
                            st.rerun()
                    with c2:
                        if st.button("👤 Individuales", use_container_width=True, type="primary" if st.session_state.sub_vista_stats == 'Stats individuales' else "secondary"):
                            st.session_state.sub_vista_stats = 'Stats individuales'
                            st.rerun()
                    with c3:
                        if st.button("🔄 Quintetos", use_container_width=True, type="primary" if st.session_state.sub_vista_stats == 'Análisis de Quintetos' else "secondary"):
                            st.session_state.sub_vista_stats = 'Análisis de Quintetos'
                            st.rerun()
                    with c4:
                        if st.button("⏱️ Cuartos", use_container_width=True, type="primary" if st.session_state.sub_vista_stats == 'Cuartos' else "secondary"):
                            st.session_state.sub_vista_stats = 'Cuartos'
                            st.rerun()

                    col_title, col_filter = st.columns([3, 1])
                    with col_title:
                        st.markdown(f"### {st.session_state.sub_vista_stats}")
                    with col_filter:
                        st.write("")
                        st.write("")
                        filtro_4 = st.checkbox("Últimos 4 partidos", value=False)

                    ultimos_n_val = 4 if filtro_4 else None

                    # ----------------------- STATS (ATAQUE / DEFENSA) -----------------------
                    if st.session_state.sub_vista_stats == 'Stats':
                        seccion_propio.mostrar_estadistica_equipo(st.session_state.equipo_seleccionado, ultimos_n_val, equipo_actual['nombre'])

                    # ----------------------- STATS INDIVIDUALES EQUIPO -----------------------
                    elif st.session_state.sub_vista_stats == 'Stats individuales':
                        df_indiv_liga = calcular_stats_individuales_liga(ultimos_n=ultimos_n_val)

                        if not df_indiv_liga.empty:
                            df_indiv_equipo = df_indiv_liga[df_indiv_liga['id_equipo'] == st.session_state.equipo_seleccionado]
                            df_plantilla = cargar_plantilla(st.session_state.equipo_seleccionado)

                            if not df_indiv_equipo.empty and not df_plantilla.empty:
                                df_indiv_equipo = df_indiv_equipo.merge(df_plantilla, on='id_jugador', how='inner')

                                st.markdown("""
                                <div style="background-color: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; border: 1px solid #3F3F3F; margin-bottom: 20px;">
                                    <h4 style="color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 0; margin-bottom: 10px; font-size: 1.1rem; text-transform: uppercase;">Estadísticas Individuales & Ratings de Liga</h4>
                                    <p style="color: #FFFFFF; font-size: 0.9rem; margin-bottom: 0;">El <b>Rating</b> evalúa el nivel del jugador del 0 al 10 en base a sus percentiles (que se indican entre paréntesis). Colores percentil: <span style="color: #E53935; font-weight:bold;">0-25</span> | <span style="color: #F59E0B; font-weight:bold;">25-50</span> | <span style="color: #FACC15; font-weight:bold;">50-75</span> | <span style="color: #4ADE80; font-weight:bold;">75-95</span> | <span style="color: #16A34A; font-weight:bold;">95-100</span></p>
                                </div>
                                """, unsafe_allow_html=True)

                                tablas_individuales = TABLAS_INDIVIDUALES

                                def format_val_pct(val, pct, col_name, is_percent=False):
                                    if pd.isna(val) or pd.isna(pct) or str(val) == "" or str(pct) == "": return "-"
                                    try:
                                        if is_percent: val_str = f"{float(val):.1f}%"
                                        elif col_name == 'FTr': val_str = f"{float(val):.3f}"
                                        elif col_name == 'AST / TO': val_str = f"{float(val):.2f}"
                                        else: val_str = str(int(val)) if float(val) == int(val) else f"{float(val):.1f}"
                                    except: return "-"

                                    color = "#E53935" # Rojo (0-25)
                                    if pct >= 95: color = "#16A34A" # Verde Oscuro
                                    elif pct >= 75: color = "#4ADE80" # Verde Claro
                                    elif pct >= 50: color = "#FACC15" # Amarillo
                                    elif pct >= 25: color = "#F59E0B" # Naranja

                                    return f"<span style='color: {color}; font-weight: bold;'>{val_str} <span style='font-size: 0.85em; opacity: 0.9;'>({int(pct)})</span></span>"

                                for titulo, config in tablas_individuales.items():
                                    st.markdown(f"<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 30px; text-transform: uppercase;'>{titulo}</h4>", unsafe_allow_html=True)
                                    
                                    df_sorted = df_indiv_equipo.sort_values(by=config["sort_col"], ascending=False)

                                    ths = f"<th style='padding: 12px 15px; border-bottom: 2px solid #F97316; width: 15%;'>Jugador</th>"
                                    if config["rating_col"]:
                                        ths += f"<th style='padding: 12px 10px; border-bottom: 2px solid #F97316; text-align: center; width: 12%;'>{etiqueta_stat(config['rating_col'], jugador=True, texto='Rating')}</th>"

                                    for col_name, _ in config["columnas"]:
                                        display_name = col_name.replace("_", " ")
                                        ths += f"<th style='padding: 12px 10px; border-bottom: 2px solid #F97316; text-align: center;'>{etiqueta_stat(col_name, jugador=True, texto=display_name)}</th>"

                                    trs = ""
                                    for idx, (i, row) in enumerate(df_sorted.iterrows()):
                                        bg_color = "transparent" if idx % 2 == 0 else "rgba(255, 255, 255, 0.05)"
                                        dorsal = row['dorsal'] if pd.notna(row['dorsal']) and str(row['dorsal']).strip() != '' else "-"
                                        jugador_str = f"{dorsal} - {row['nombre']}"
                                        
                                        j_id = row['id_jugador']
                                        eq_id = row['id_equipo']
                                        enlace = f"/?jugador_id={j_id}&equipo_id={eq_id}"
                                        
                                        tds = f"<td style='padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.2); font-weight: bold; white-space: nowrap; vertical-align: middle;'><a href='{enlace}' target='_self' style='color: #FFFFFF; text-decoration: none; transition: color 0.2s;' onmouseover=\"this.style.color='#F97316'\" onmouseout=\"this.style.color='#FFFFFF'\">{jugador_str}</a></td>"

                                        if config["rating_col"]:
                                            rating_val = row.get(config["rating_col"], 0)
                                            stars_num = np.floor(rating_val) / 2.0
                                            stars_pct = (stars_num / 5.0) * 100
                                            
                                            stars_html = f'''
                                            <div style="display: flex; flex-direction: column; align-items: center;">
                                                <span style="font-weight: bold; font-size: 1.05em; color: #F97316;">{rating_val:.1f}</span>
                                                <div style="display: inline-block; position: relative; color: #525252; font-size: 1.2em; letter-spacing: 2px;">
                                                    ★★★★★
                                                    <div style="position: absolute; top: 0; left: 0; white-space: nowrap; overflow: hidden; width: {stars_pct}%; color: #F97316;">
                                                        ★★★★★
                                                    </div>
                                                </div>
                                            </div>
                                            '''
                                            tds += f"<td style='padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.2); text-align: center; vertical-align: middle;'>{stars_html}</td>"

                                        for col_name, is_pct in config["columnas"]:
                                            val = row.get(col_name)
                                            pct_val = row.get(f"{col_name}_pct")
                                            tds += f"<td style='padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.2); text-align: center; white-space: nowrap; vertical-align: middle;'>{format_val_pct(val, pct_val, col_name, is_pct)}</td>"

                                        trs += f"<tr style='background-color: {bg_color};'>{tds}</tr>"

                                    tabla_html = f'''
                                    <div style="border-radius: 10px; overflow: hidden; border: 1px solid #3F3F3F; margin-top: 10px; background-color: transparent; overflow-x: auto;">
                                        <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif; font-size: 0.9rem;">
                                            <thead>
                                                <tr style="background-color: rgba(255, 255, 255, 0.1); color: #FFFFFF;">
                                                    {ths}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {trs}
                                            </tbody>
                                        </table>
                                    </div>
                                    '''
                                    st.markdown(" ".join(tabla_html.split()), unsafe_allow_html=True)
                            else:
                                st.warning("Los jugadores de este equipo no han pisado la pista en la muestra seleccionada.")
                        else:
                            st.warning("No hay estadísticas individuales disponibles para esta liga.")

                    # ----------------------- ANÁLISIS DE QUINTETOS (ON / OFF + GRÁFICO TOTAL) -----------------------
                    elif st.session_state.sub_vista_stats == 'Análisis de Quintetos':
                        mostrar_analisis_quintetos(st.session_state.equipo_seleccionado, ultimos_n_val)

                    # ----------------------- ANÁLISIS POR CUARTOS -----------------------
                    elif st.session_state.sub_vista_stats == 'Cuartos':
                        seccion_cuartos.mostrar_cuartos(SimpleNamespace(
                            calcular_stats_individuales_liga=calcular_stats_individuales_liga,
                            cargar_plantilla=cargar_plantilla,
                            etiqueta_stat=etiqueta_stat,
                            tablas_individuales=TABLAS_INDIVIDUALES,
                        ), st.session_state.equipo_seleccionado, ultimos_n_val)

                    else:
                        st.info(f"Sección en construcción: Datos de {st.session_state.sub_vista_stats.lower()}.")
                        
                elif st.session_state.vista_equipo == 'Plantilla':
                    df_plantilla = cargar_plantilla(st.session_state.equipo_seleccionado)
                    
                    if not df_plantilla.empty:
                        num_columnas = 4
                        for i in range(0, len(df_plantilla), num_columnas):
                            columnas = st.columns(num_columnas)
                            for j in range(num_columnas):
                                if i + j < len(df_plantilla):
                                    jugador = df_plantilla.iloc[i + j]
                                    with columnas[j]:
                                        nombre_jugador = jugador['nombre']
                                        dorsal = jugador['dorsal'] if pd.notna(jugador['dorsal']) and str(jugador['dorsal']).strip() != '' else '-'
                                        foto_base64 = obtener_foto_jugador_base64(nombre_jugador)
                                        
                                        if foto_base64:
                                            grafico_jugador = f'<img src="data:image/png;base64,{foto_base64}" style="width: 100%; height: 200px; object-fit: cover; border-radius: 10px 10px 0 0;">'
                                        else:
                                            iniciales = "".join([p[0] for p in nombre_jugador.split()[:2]]).upper()
                                            grafico_jugador = f'<div style="width: 100%; height: 200px; background-color: #262626; border-radius: 10px 10px 0 0; display: flex; align-items: center; justify-content: center; color: #F97316; font-weight: bold; font-size: 3rem;">{iniciales}</div>'
                                        
                                        tarjeta_html = f"""
                                        <div style="background-color: #1A1A1A; border: 1px solid #333333; border-radius: 10px; display: flex; flex-direction: column; align-items: center; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                                            {grafico_jugador}
                                            <div style="width: 100%; padding: 20px 15px; text-align: center; position: relative;">
                                                <div style="position: absolute; top: -20px; right: 15px; background-color: #F97316; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 3px solid #1A1A1A; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">{dorsal}</div>
                                                <h4 style="color: #F97316; margin: 0; font-size: 1rem; line-height: 1.2;">{nombre_jugador}</h4>
                                            </div>
                                        </div>
                                        """
                                        st.markdown(" ".join(tarjeta_html.split()), unsafe_allow_html=True)
                                        
                                        if st.button("Ver Perfil", key=f"btn_jug_{jugador['id_jugador']}", use_container_width=True):
                                            st.session_state.jugador_seleccionado = jugador['id_jugador']
                                            st.rerun()
                    else:
                        st.warning("No se han encontrado jugadores para este equipo en la base de datos.")
