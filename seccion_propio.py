import html
import math
import sqlite3
from itertools import combinations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import propio_bd as bd
import streamlit.components.v1 as components

from cancha import POSICION_ETIQUETA, Y_MAX_ZONAS, ZONAS_TIRO, ZONAS_TRIPLE, svg_lineas, svg_zonas, zona_de_tiro

# Sección "Propio" de la app: análisis del equipo propio a partir del play by play de la federación
# y del play by play avanzado (propio_ataque / propio_defensa) que se rellena con etiquetador.py.

TIROS_CAMPO = (93, 94, 97, 98, 100)
CANASTAS_CAMPO = (93, 94, 100)
TRIPLES = (94, 98)
PLAYTYPES_PR = ("P&R Handler", "P&R Roller")
APARTADOS = ["Quintetos", "Estadística", "Ataque", "Defensa", "Análisis Individual"]
ICONOS_APARTADO = {"Quintetos": "🔄", "Estadística": "📈", "Ataque": "⚔️", "Defensa": "🛡️", "Análisis Individual": "👤"}

DEF_POSESIONES = "Finales de posesión etiquetados: tiro de campo, pérdida o falta con tiros libres."
DEF_FRECUENCIA = "Porcentaje de las posesiones de este apartado que corresponden a cada fila."
DEF_PPP = "Puntos por posesión: puntos conseguidos / posesiones."
DEF_PPP_RIVAL = "Puntos por posesión permitidos al rival. Cuanto más bajo, mejor."

# Estilos de tabla comunes con el resto de la app
TH = "padding: 10px 10px; border-bottom: 2px solid #F97316; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 1px;"
TD = "padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.2);"


# ------------------------------------------------------------------ UTILIDADES
def tip(texto, definicion):
    """Texto con tooltip (usa las clases CSS .stat-tip definidas en app.py)."""
    return f"<span class='stat-tip'>{texto}<span class='stat-tip-texto'>{html.escape(definicion)}</span></span>"


def tabla(cabeceras, filas, centrar_desde=1, desplazable=False):
    """Tabla HTML con el estilo de la app. `cabeceras` y cada fila son listas de HTML.
    `desplazable` permite scroll horizontal en pantallas estrechas (recorta los tooltips de la cabecera)."""
    ths = "".join(f"<th style='{TH}{' text-align: center;' if i >= centrar_desde else ''}'>{c}</th>"
                  for i, c in enumerate(cabeceras))
    trs = ""
    for n, fila in enumerate(filas):
        fondo = "transparent" if n % 2 == 0 else "rgba(255, 255, 255, 0.05)"
        tds = "".join(f"<td style='{TD}{' text-align: center;' if i >= centrar_desde else ' font-weight: bold;'}'>{v}</td>"
                      for i, v in enumerate(fila))
        trs += f"<tr style='background-color: {fondo};'>{tds}</tr>"
    html_tabla = f"""
    <div style="border-radius: 10px; overflow: {'auto' if desplazable else 'visible'}; border: 1px solid #3F3F3F; margin: 10px 0 20px 0; max-width: 100%;">
        <table style="width: 100%; table-layout: auto; border-collapse: collapse; text-align: left; font-family: sans-serif; font-size: 0.95rem; color: #FFFFFF;">
            <thead><tr style="background-color: rgba(255, 255, 255, 0.1);">{ths}</tr></thead>
            <tbody>{trs}</tbody>
        </table>
    </div>
    """
    st.markdown(" ".join(html_tabla.split()), unsafe_allow_html=True)


def subtitulo(texto):
    st.markdown(f"<h4 style='color: #F97316; font-weight: 800; text-decoration: underline; text-underline-offset: 6px; margin-top: 25px; text-transform: uppercase;'>{texto}</h4>",
                unsafe_allow_html=True)


def color_comparado(valor, referencia, mayor_es_mejor=True, margen=0.1):
    if pd.isna(valor) or pd.isna(referencia):
        return "#FFFFFF"
    diferencia = (valor - referencia) if mayor_es_mejor else (referencia - valor)
    if diferencia > margen:
        return "#4ADE80"
    if diferencia < -margen:
        return "#F87171"
    return "#D4D4D4"  # parecido a la referencia: neutro


def barra(porcentaje):
    ancho = max(0.0, min(100.0, float(porcentaje)))
    return (f"<div style='display: flex; align-items: center; gap: 8px; justify-content: center;'>"
            f"<div style='width: 80px; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px;'>"
            f"<div style='width: {ancho}%; height: 8px; background: #F97316; border-radius: 4px;'></div></div>"
            f"<span>{porcentaje:.1f}%</span></div>")


# ------------------------------------------------------------------ DATOS
def conectar():
    return sqlite3.connect(bd.RUTA_BD)


def cargar_nombres():
    conexion = conectar()
    df = pd.read_sql("SELECT id_jugador, dorsal, nombre FROM jugadores", conexion)
    conexion.close()
    return {int(r.id_jugador): f"{r.dorsal if pd.notna(r.dorsal) and str(r.dorsal).strip() else '-'} - {r.nombre}"
            for r in df.itertuples()}


def partidos_del_equipo(id_propio, ultimos_n=None):
    """Partidos del equipo propio, del más reciente al más antiguo (todos, o solo los últimos n)."""
    conexion = conectar()
    filas = conexion.execute(
        "SELECT id_partido FROM partidos WHERE ? IN (id_equipo_local, id_equipo_visitante) ORDER BY fecha_iso DESC",
        (int(id_propio),)).fetchall()
    conexion.close()
    ids = tuple(f[0] for f in filas)
    return ids[:ultimos_n] if ultimos_n else ids


def cargar_posesiones(partidos):
    """Posesiones etiquetadas (las que tienen playtype) de ataque y defensa en los partidos indicados."""
    conexion = conectar()
    bd.crear_tablas_propio(conexion)
    marcas = ",".join("?" for _ in partidos) or "NULL"
    tablas = {}
    for fase, nombre_tabla in (("ataque", "propio_ataque"), ("defensa", "propio_defensa")):
        df = pd.read_sql(f"SELECT * FROM {nombre_tabla} WHERE playtype IS NOT NULL AND id_partido IN ({marcas}) "
                         "ORDER BY rowid", conexion, params=partidos)
        df["puntos"] = df["puntos"].fillna(0)
        df["en_pista"] = df["quinteto_propio"].apply(bd.ids_quinteto)
        tablas[fase] = df
    conexion.close()
    return tablas["ataque"], tablas["defensa"]


def resumen_por(df, columna, etiquetas=None, vacio="—"):
    """Posesiones, frecuencia, puntos y PPP agrupando por `columna`."""
    if df.empty:
        return pd.DataFrame(columns=["grupo", "posesiones", "frecuencia", "puntos", "ppp"])
    grupos = df[columna].apply(lambda v: vacio if v is None or (isinstance(v, float) and math.isnan(v)) else v)
    if etiquetas is not None:
        grupos = grupos.apply(lambda v: etiquetas(v) if v != vacio else v)
    res = df.assign(grupo=grupos).groupby("grupo").agg(posesiones=("puntos", "size"), puntos=("puntos", "sum"))
    res["frecuencia"] = res["posesiones"] / len(df) * 100
    res["ppp"] = res["puntos"] / res["posesiones"]
    return res.reset_index().sort_values(["posesiones", "ppp"], ascending=False)


def mostrar_resumen(res, titulo_grupo, ppp_referencia, mayor_es_mejor=True):
    if res.empty:
        st.info("No hay posesiones etiquetadas para este análisis.")
        return
    definicion_ppp = DEF_PPP if mayor_es_mejor else DEF_PPP_RIVAL
    cabeceras = [titulo_grupo, tip("Posesiones", DEF_POSESIONES), tip("Frecuencia", DEF_FRECUENCIA),
                 tip("Puntos", "Puntos conseguidos en esas posesiones."), tip("PPP", definicion_ppp)]
    filas = []
    for r in res.itertuples():
        color = color_comparado(r.ppp, ppp_referencia, mayor_es_mejor)
        filas.append([html.escape(str(r.grupo)), int(r.posesiones), barra(r.frecuencia), int(r.puntos),
                      f"<span style='color: {color}; font-weight: bold;'>{r.ppp:.2f}</span>"])
    tabla(cabeceras, filas)


def grafico_frecuencia_ppp(res, ppp_referencia, titulo_eje="PPP"):
    """Burbujas: frecuencia (x) frente a eficiencia (y); la línea marca el PPP medio."""
    if res.empty:
        return
    fig = go.Figure(go.Scatter(
        x=res["frecuencia"], y=res["ppp"], mode="markers+text", text=res["grupo"], textposition="top center",
        marker=dict(size=np.clip(res["posesiones"] * 2, 12, 50), color="#F97316", opacity=0.7,
                    line=dict(color="#FFFFFF", width=1)),
        hovertemplate="<b>%{text}</b><br>Frecuencia: %{x:.1f}%<br>PPP: %{y:.2f}<extra></extra>",
    ))
    fig.add_hline(y=ppp_referencia, line_dash="dash", line_color="#D4D4D4", line_width=1,
                  annotation_text=f"Media {ppp_referencia:.2f}", annotation_font_color="#D4D4D4")
    fig.update_layout(
        xaxis_title="Frecuencia (%)", yaxis_title=titulo_eje, height=420,
        plot_bgcolor="rgba(20, 20, 20, 0.85)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#D4D4D4"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"), yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        margin=dict(l=50, r=20, t=20, b=50),
    )
    st.plotly_chart(fig, use_container_width=True)


def metricas_cabecera(df):
    c1, c2 = st.columns(2)
    c1.metric("Posesiones etiquetadas", len(df))
    c2.metric("Partidos", df["id_partido"].nunique())


# ------------------------------------------------------------------ QUINTETOS: TOP COMBINACIONES
@st.cache_data(ttl=600)
def acumulados_combinaciones(id_propio, partidos):
    """Suma, para cada combinación de 1 a 5 jugadores propios, los eventos ocurridos con todos ellos en pista.
    Vector: [FGA, FTA, TOV, OREB, PTS] propios + los mismos del rival."""
    conexion = conectar()
    marcas = ",".join("?" for _ in partidos) or "NULL"
    df = pd.read_sql(f'''
        SELECT pb.idMove, pb.id_equipo, pb.quinteto_local, pb.quinteto_visitante, p.id_equipo_local
        FROM play_by_play pb JOIN partidos p ON p.id_partido = pb.id_partido
        WHERE p.id_partido IN ({marcas}) AND pb.id_equipo IS NOT NULL
    ''', conexion, params=partidos)
    conexion.close()

    m = df["idMove"]
    base = np.column_stack([
        m.isin([93, 100, 97, 94, 98]), m.isin([92, 96]), m.eq(106), m.eq(101),
        np.select([m.isin([93, 100]), m.eq(94), m.eq(92)], [2, 3, 1], 0),
    ]).astype(float)
    propio = (df["id_equipo"] == id_propio).to_numpy()
    vectores = np.zeros((len(df), 10))
    vectores[propio, :5] = base[propio]
    vectores[~propio, 5:] = base[~propio]
    quintetos = np.where(df["id_equipo_local"] == id_propio, df["quinteto_local"], df["quinteto_visitante"])

    total = vectores.sum(axis=0)
    acumulado = {}
    for quinteto, vector in zip(quintetos, vectores):
        ids = sorted(bd.ids_quinteto(quinteto))
        for k in range(1, 6):
            for combo in combinations(ids, k):
                if combo in acumulado:
                    acumulado[combo] += vector
                else:
                    acumulado[combo] = vector.copy()
    return acumulado, total


def _ratings(v):
    posesiones = ((v[0] + 0.44 * v[1] + v[2] - v[3]) + (v[5] + 0.44 * v[6] + v[7] - v[8])) / 2
    if posesiones <= 0:
        return None
    return posesiones, v[4] / posesiones * 100, v[9] / posesiones * 100


def ranking_combinaciones(id_propio, partidos, tamano, min_posesiones):
    acumulado, total = acumulados_combinaciones(id_propio, partidos)
    filas = []
    for combo, v_on in acumulado.items():
        if len(combo) != tamano:
            continue
        on, off = _ratings(v_on), _ratings(total - v_on)
        if on is None or off is None or on[0] < min_posesiones or off[0] < min_posesiones:
            continue
        filas.append({
            "combo": combo, "pos_on": on[0],
            "ORtg_on": on[1], "ORtg_off": off[1], "DRtg_on": on[2], "DRtg_off": off[2],
            "NetRtg_on": on[1] - on[2], "NetRtg_off": off[1] - off[2],
        })
    df = pd.DataFrame(filas)
    if not df.empty:
        for m in ("ORtg", "DRtg", "NetRtg"):
            df[f"{m}_dif"] = df[f"{m}_on"] - df[f"{m}_off"]
    return df


def mostrar_top_combinaciones(id_propio, partidos, nombres):
    subtitulo("🏆 Mejores y peores combinaciones")
    st.caption("Diferencial = rating del equipo con la combinación en pista menos sin ella. Pos. = posesiones con la "
               "combinación en pista. Usa el play by play de la federación de los partidos seleccionados.")
    c1, c2 = st.columns([2, 1])
    tamano = c1.radio("Jugadores en la combinación", [1, 2, 3, 4, 5], horizontal=True, index=4, key="propio_top_tamano")
    min_pos = c2.slider("Mínimo de posesiones (en pista y fuera)", 5, 100, 20, step=5, key="propio_top_min")

    df = ranking_combinaciones(id_propio, partidos, tamano, min_pos)
    if df.empty:
        st.info("No hay combinaciones con suficientes posesiones. Baja el mínimo de posesiones.")
        return

    metricas = [
        ("ORtg", "Diferencial Offensive Rating", True,
         "Offensive Rating del equipo con la combinación en pista menos sin ella. Positivo es mejor."),
        ("DRtg", "Diferencial Defensive Rating", False,
         "Defensive Rating del equipo con la combinación en pista menos sin ella. Negativo es mejor."),
        ("NetRtg", "Diferencial Net Rating", True,
         "Net Rating del equipo con la combinación en pista menos sin ella. Positivo es mejor."),
    ]
    if len(df) < 6:
        st.caption(f"Solo {len(df)} combinaciones llegan al mínimo de posesiones: las listas no repiten combinaciones.")

    def nombre_corto(id_jugador):
        # "13 - PABLO CORRAL" -> "13 CORRAL"
        dorsal, _, nombre = nombres.get(id_jugador, str(id_jugador)).partition(" - ")
        return f"{dorsal} {nombre.split()[-1] if nombre else ''}".strip()

    for clave, titulo, mayor_es_mejor, definicion in metricas:
        st.markdown(f"<h5 style='color: #E5E5E5; margin-top: 20px;'>{tip(titulo, definicion)}</h5>",
                    unsafe_allow_html=True)
        ordenado = df.sort_values(f"{clave}_dif", ascending=not mayor_es_mejor)
        mejores = ordenado.head(3)
        peores = ordenado.iloc[len(mejores):].tail(3).iloc[::-1]
        col_mejor, col_peor = st.columns(2)
        for col, nombre_lista, datos in ((col_mejor, "🟢 Mejores", mejores), (col_peor, "🔴 Peores", peores)):
            with col:
                st.markdown(f"**{nombre_lista}**")
                if datos.empty:
                    st.caption("No hay más combinaciones con el mínimo de posesiones.")
                    continue
                filas = []
                for r in datos.itertuples():
                    dif = getattr(r, f"{clave}_dif")
                    bueno = dif > 0 if mayor_es_mejor else dif < 0
                    color = "#4ADE80" if bueno else "#F87171"
                    jugadores = ", ".join(html.escape(nombre_corto(j)) for j in r.combo)
                    filas.append([f"<span style='font-size: 0.85rem;'>{jugadores}</span>", f"{r.pos_on:.0f}",
                                  f"{getattr(r, f'{clave}_on'):.1f}", f"{getattr(r, f'{clave}_off'):.1f}",
                                  f"<span style='color: {color}; font-weight: bold;'>{dif:+.1f}</span>"])
                tabla(["Jugadores", "Pos.", "On", "Off", "Dif."], filas, desplazable=True)


# ------------------------------------------------------------------ APARTADOS
def apartado_quintetos(h, id_propio, nombres, ultimos_n, partidos):
    h.mostrar_analisis_quintetos(id_propio, ultimos_n)
    st.write("---")
    mostrar_top_combinaciones(id_propio, partidos, nombres)


# ------------------------------------------------------------------ ESTADÍSTICA (ATAQUE / DEFENSA)
# Conteos por equipo y partido a partir del play by play de la federación
CONTEOS = {
    "T2M": (93, 100), "T2A": (93, 100, 97), "T3M": (94,), "T3A": (94, 98), "TLM": (92,), "TLA": (92, 96),
    "OREB": (101,), "DREB": (104,), "AST": (107,), "TOV": (106,),
}

# (clave, nombre, definición, mayor_es_mejor en ataque). En defensa el sentido se invierte salvo en los neutros (None).
TABLAS_ESTADISTICA = [
    ("Posesiones", [
        ("ritmo", "Ritmo", "Posesiones por cada 40 minutos.", None),
        ("plays", "Plays", "Oportunidades de anotar por cada 40 minutos: como el ritmo, pero sin restar los rebotes "
                           "ofensivos (FGA + 0,44·FTA + TOV). Es de cada equipo: no tiene por qué coincidir con el rival.", None),
        ("ortg", "Offensive Rating", "Puntos anotados por cada 100 posesiones.", True),
        ("drtg", "Defensive Rating", "Puntos recibidos por cada 100 posesiones.", False),
        ("netrtg", "Net Rating", "Offensive Rating − Defensive Rating.", True),
    ]),
    ("Tiro · Porcentajes", [
        ("t2", "T2%", "Acierto en tiros de 2.", True),
        ("t3", "T3%", "Acierto en triples.", True),
        ("tl", "%TL", "Acierto en tiros libres.", True),
        ("efg", "eFG%", "Tiro de campo efectivo: el triple vale 1,5 veces un tiro de 2.", True),
        ("ts", "TS%", "Tiro verdadero: eficiencia anotadora incluyendo triples y tiros libres.", True),
    ]),
    ("Tiro · Distribución de tiro", [
        ("r2pa", "2PAr", "Porcentaje de los tiros de campo que son de 2.", None),
        ("r3pa", "3PAr", "Porcentaje de los tiros de campo que son triples.", None),
        ("ftr", "FTr", "Tiros libres intentados por cada tiro de campo intentado.", True),
    ]),
    ("Rebote", [
        ("oreb", "OREB%", "Porcentaje de los rebotes ofensivos disponibles que se capturan.", True),
        ("dreb", "DREB%", "Porcentaje de los rebotes defensivos disponibles que se capturan.", True),
        ("reb", "REB%", "Porcentaje de todos los rebotes disponibles que se capturan.", True),
    ]),
    ("Cuidado de balón", [
        ("tov", "TOV%", "Pérdidas por cada 100 posesiones.", False),
        ("ast", "AST%", "Porcentaje de las canastas de campo que llegan tras una asistencia.", True),
        ("ast_tov", "AST/TOV", "Asistencias por cada pérdida.", True),
    ]),
]
FORMATO_ESTADISTICA = {"ritmo": "{:.1f}", "plays": "{:.1f}", "ortg": "{:.1f}", "drtg": "{:.1f}", "netrtg": "{:+.1f}",
                       "ftr": "{:.3f}", "ast_tov": "{:.2f}"}


def _indicadores(a, b, minutos):
    """Indicadores del equipo `a` jugando contra `b` (conteos acumulados) en `minutos` jugados."""
    fga, fgm = a["T2A"] + a["T3A"], a["T2M"] + a["T3M"]
    pts_a = 2 * a["T2M"] + 3 * a["T3M"] + a["TLM"]
    pts_b = 2 * b["T2M"] + 3 * b["T3M"] + b["TLM"]
    pos_a = fga + 0.44 * a["TLA"] + a["TOV"] - a["OREB"]
    pos_b = b["T2A"] + b["T3A"] + 0.44 * b["TLA"] + b["TOV"] - b["OREB"]
    pos = (pos_a + pos_b) / 2
    div = lambda x, y: x / y if y else float("nan")
    return {
        "ritmo": div(pos, minutos) * 40,
        # Plays: oportunidades propias de anotar (sin restar rebotes ofensivos ni promediar con el rival)
        "plays": div(fga + 0.44 * a["TLA"] + a["TOV"], minutos) * 40,
        "ortg": div(pts_a, pos) * 100, "drtg": div(pts_b, pos) * 100,
        "netrtg": div(pts_a - pts_b, pos) * 100,
        "t2": div(a["T2M"], a["T2A"]) * 100, "t3": div(a["T3M"], a["T3A"]) * 100, "tl": div(a["TLM"], a["TLA"]) * 100,
        "efg": div(fgm + 0.5 * a["T3M"], fga) * 100, "ts": div(pts_a, 2 * (fga + 0.44 * a["TLA"])) * 100,
        "r2pa": div(a["T2A"], fga) * 100, "r3pa": div(a["T3A"], fga) * 100, "ftr": div(a["TLA"], fga),
        "oreb": div(a["OREB"], a["OREB"] + b["DREB"]) * 100, "dreb": div(a["DREB"], a["DREB"] + b["OREB"]) * 100,
        "reb": div(a["OREB"] + a["DREB"], a["OREB"] + a["DREB"] + b["OREB"] + b["DREB"]) * 100,
        "tov": div(a["TOV"], pos) * 100, "ast": div(a["AST"], fgm) * 100, "ast_tov": div(a["AST"], a["TOV"]),
    }


@st.cache_data(ttl=600)
def estadistica_liga(ultimos_n=None):
    """Para cada equipo: sus indicadores (ataque) y los de sus rivales contra él (defensa).
    Con ultimos_n, solo cuenta los últimos n partidos de cada equipo."""
    conexion = conectar()
    partidos = pd.read_sql("SELECT id_partido, id_equipo_local, id_equipo_visitante, fecha_iso FROM partidos", conexion)
    pbp = pd.read_sql("SELECT id_partido, id_equipo, idMove, period FROM play_by_play", conexion)
    conexion.close()

    conteos = pbp[pbp["id_equipo"].notna()].copy()
    for clave, movimientos in CONTEOS.items():
        conteos[clave] = conteos["idMove"].isin(movimientos).astype(int)
    conteos = conteos.groupby(["id_partido", "id_equipo"])[list(CONTEOS)].sum()
    max_periodo = pbp.groupby("id_partido")["period"].max()

    juegos = pd.concat([
        partidos.rename(columns={"id_equipo_local": "equipo", "id_equipo_visitante": "rival"}),
        partidos.rename(columns={"id_equipo_visitante": "equipo", "id_equipo_local": "rival"}),
    ])[["id_partido", "equipo", "rival", "fecha_iso"]]
    juegos = juegos.sort_values("fecha_iso", ascending=False)
    if ultimos_n:
        juegos = juegos.groupby("equipo").head(ultimos_n)

    vacio = pd.Series(0, index=list(CONTEOS))
    filas = []
    for equipo, grupo in juegos.groupby("equipo"):
        propios, rivales, minutos = vacio.copy(), vacio.copy(), 0
        for r in grupo.itertuples():
            propios += conteos.loc[(r.id_partido, r.equipo)] if (r.id_partido, r.equipo) in conteos.index else 0
            rivales += conteos.loc[(r.id_partido, r.rival)] if (r.id_partido, r.rival) in conteos.index else 0
            periodos = max_periodo.get(r.id_partido, 4)
            minutos += 40 + max(0, periodos - 4) * 5
        fila = {"id_equipo": equipo}
        fila.update({f"ataque_{k}": v for k, v in _indicadores(propios, rivales, minutos).items()})
        fila.update({f"defensa_{k}": v for k, v in _indicadores(rivales, propios, minutos).items()})
        filas.append(fila)
    return pd.DataFrame(filas)


def tabla_estadistica(df, fila_equipo, fase):
    for titulo, indicadores in TABLAS_ESTADISTICA:
        subtitulo(titulo)
        filas = []
        for clave, nombre_ind, definicion, mayor_es_mejor in indicadores:
            columna = f"{fase}_{clave}"
            valor = fila_equipo[columna]
            # En defensa se miden los rivales: lo bueno es que su indicador sea bajo (salvo los neutros)
            sentido = mayor_es_mejor if fase == "ataque" or mayor_es_mejor is None else not mayor_es_mejor
            ranking = df[columna].rank(ascending=sentido is False, method="min")
            posicion = ranking[df["id_equipo"] == fila_equipo["id_equipo"]].iloc[0]
            if pd.isna(valor):
                texto, txt_pos = "-", "-"
            else:
                formato = FORMATO_ESTADISTICA.get(clave, "{:.1f}%")
                texto = formato.format(valor)
                pos = int(posicion)
                color = "#4CAF50" if pos == 1 and sentido is not None else "#FFFFFF"
                estrella = " ⭐" if pos == 1 and sentido is not None else ""
                txt_pos = f"<span style='color: {color}; font-weight: {'bold' if pos <= 3 else 'normal'};'>{pos}º{estrella}</span>"
            filas.append([tip(nombre_ind, definicion), f"<span style='font-size: 1.05rem;'>{texto}</span>", txt_pos])
        tabla(["Estadística", "Valor", tip("Posición en liga", "1º = mejor de la liga. En Ritmo, 2PAr y 3PAr "
                                           "(indicadores neutros) 1º = valor más alto.")], filas)


def mostrar_estadistica_equipo(id_equipo, ultimos_n=None, nombre_equipo="el equipo"):
    """Tablas de Ataque y Defensa (stats del equipo y de sus rivales contra él) con la posición en la liga.
    Se usa en la sección Propio y en la ficha de cada equipo de la sección Liga."""
    df = estadistica_liga(ultimos_n)
    if df.empty or id_equipo not in set(df["id_equipo"]):
        st.info("No hay estadísticas del equipo en los partidos seleccionados.")
        return
    fila = df[df["id_equipo"] == id_equipo].iloc[0]
    tab_ataque, tab_defensa = st.tabs(["⚔️ Ataque", "🛡️ Defensa"])
    with tab_ataque:
        st.caption(f"Estadísticas de {nombre_equipo} (calculadas con el play by play de la federación).")
        tabla_estadistica(df, fila, "ataque")
    with tab_defensa:
        st.caption(f"Los mismos indicadores, pero de los rivales cuando juegan contra {nombre_equipo} (por ejemplo, "
                   "el eFG% acumulado de los rivales). La posición en liga premia que los rivales tengan valores bajos.")
        tabla_estadistica(df, fila, "defensa")


def apartado_estadistica(id_propio, ultimos_n):
    mostrar_estadistica_equipo(id_propio, ultimos_n, "el Atlético")


def analisis_por_finalizador(df_at, nombre, ppp_equipo):
    """Eficiencia de cada playtype o sistema según el jugador que finaliza la posesión."""
    dimension = st.radio("Analizar", ["Playtype", "Sistema"], horizontal=True, key="propio_fin_dimension")
    columna = "playtype" if dimension == "Playtype" else "sistema"
    df = df_at.assign(
        categoria=df_at[columna].fillna("Sin sistema"),
        finalizador=[nombre(j) if pd.notna(j) else "Sin jugador" for j in df_at["id_jugador"]],
    )

    subtitulo(f"PPP por {dimension.lower()} y jugador que finaliza")
    st.caption("Cada casilla: PPP de ese jugador en ese " + dimension.lower() + " (posesiones entre paréntesis). "
               f"Verde por encima de la media del equipo ({ppp_equipo:.2f}), rojo por debajo.")
    agrupado = df.groupby(["finalizador", "categoria"])["puntos"].agg(["size", "sum"])
    agrupado["ppp"] = agrupado["sum"] / agrupado["size"]
    orden_filas = df["finalizador"].value_counts().index.tolist()
    orden_cols = df["categoria"].value_counts().index.tolist()
    ppp = agrupado["ppp"].unstack().reindex(index=orden_filas, columns=orden_cols)
    n = agrupado["size"].unstack().reindex(index=orden_filas, columns=orden_cols)
    texto = [[f"{p:.2f}<br>({int(k)})" if pd.notna(k) else "" for p, k in zip(fp, fn)]
             for fp, fn in zip(ppp.to_numpy(), n.to_numpy())]
    fig = go.Figure(go.Heatmap(
        z=ppp.to_numpy(), x=orden_cols, y=orden_filas, text=texto, texttemplate="%{text}",
        colorscale="RdYlGn", zmid=ppp_equipo, zmin=0, zmax=max(2.0, float(np.nanmax(ppp.to_numpy()))),
        hovertemplate="%{y}<br>%{x}<br>PPP: %{z:.2f}<extra></extra>", colorbar=dict(title="PPP"),
    ))
    fig.update_layout(
        height=max(300, 45 * len(orden_filas) + 120), yaxis=dict(autorange="reversed"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#D4D4D4"),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    subtitulo(f"Detalle de un {dimension.lower()}")
    categoria = st.selectbox(dimension, orden_cols, key="propio_fin_categoria")
    df_cat = df[df["categoria"] == categoria]
    ppp_cat = df_cat["puntos"].sum() / len(df_cat)
    st.caption(f"{len(df_cat)} posesiones de {categoria} · {ppp_cat:.2f} PPP. Frecuencia: % de esas posesiones que "
               "finaliza cada jugador. El color compara con el PPP de ese " + dimension.lower() + ".")
    mostrar_resumen(resumen_por(df_cat, "finalizador"), "Finaliza", ppp_cat)


def uso_vs_eficiencia(h, id_propio, ultimos_n):
    """El gráfico %USG vs PPP de la sección Liga, solo con los jugadores del equipo propio."""
    st.caption("Igual que en Liga: calculado con el play by play de la federación (no depende del etiquetado). "
               "Las líneas marcan la media de los jugadores del equipo.")
    df_indiv = h.calcular_stats_individuales_liga(ultimos_n=ultimos_n)
    if df_indiv.empty or "PPP" not in df_indiv.columns:
        st.warning("No hay datos suficientes de jugadores.")
        return
    conexion = conectar()
    df_nombres = pd.read_sql("SELECT id_jugador, nombre AS Jugador FROM jugadores", conexion)
    conexion.close()
    df_res = df_indiv[df_indiv["id_equipo"] == id_propio].merge(df_nombres, on="id_jugador", how="inner")
    df_res = df_res.dropna(subset=["%USG", "PPP"])
    if df_res.empty:
        st.warning("No hay datos suficientes de jugadores.")
        return
    h.grafico_uso_eficiencia(df_res)


# ------------------------------------------------------------------ P&R (ATAQUE Y DEFENSA)
ACABA = (("P&R Handler", "Acaba el manejador", "manejador"), ("P&R Roller", "Acaba el bloqueador", "bloqueador"))

# Textos de cada fase: en defensa los jugadores son los defensores del manejador / bloqueador del rival
TEXTOS_PR = {
    "ataque": {
        "manejador": "Manejador", "bloqueador": "Bloqueador", "manejadores": "Manejadores",
        "bloqueadores": "Bloqueadores", "parejas": "Parejas manejador - bloqueador",
        "rol_manejador": "Manejador", "rol_bloqueador": "Bloqueador",
        "con_bloqueador": "Con {} de bloqueador", "con_manejador": "Con {} de manejador",
        "resumen": "{n} posesiones de P&R (playtype P&R Handler o P&R Roller) · {ppp:.2f} PPP.",
    },
    "defensa": {
        "manejador": "Defensor del manejador", "bloqueador": "Defensor del bloqueador",
        "manejadores": "Defensores del manejador", "bloqueadores": "Defensores del bloqueador",
        "parejas": "Parejas de defensores (manejador - bloqueador)",
        "rol_manejador": "Defiende al manejador", "rol_bloqueador": "Defiende al bloqueador",
        "con_bloqueador": "Con {} defendiendo al bloqueador", "con_manejador": "Con {} defendiendo al manejador",
        "resumen": "{n} posesiones de P&R del rival · {ppp:.2f} PPP permitido.",
    },
}


def tabla_pr(df_pr, grupos, titulo_grupo, ppp_ref, mayor_es_mejor=True):
    """Una fila por grupo: nº de P&R, frecuencia, PPP y cómo acaba (manejador / bloqueador).
    `grupos` es una serie alineada con df_pr con la etiqueta de cada posesión."""
    datos = df_pr.assign(grupo=grupos)
    rival = "" if mayor_es_mejor else " del rival"
    cabeceras = [titulo_grupo, tip("P&R", "Posesiones de P&R."), tip("Frecuencia", DEF_FRECUENCIA),
                 tip("PPP", DEF_PPP if mayor_es_mejor else DEF_PPP_RIVAL)]
    for playtype, texto, rol in ACABA:
        cabeceras += [tip(f"{texto}<br>%", f"Porcentaje de esos P&R que finaliza el {rol}{rival} (playtype {playtype})."),
                      tip(f"{texto}<br>PPP", f"PPP cuando el P&R lo finaliza el {rol}{rival}.")]
    color = lambda v: f"<span style='color: {color_comparado(v, ppp_ref, mayor_es_mejor)}; font-weight: bold;'>{v:.2f}</span>"
    filas = []
    resumen = datos.groupby("grupo")["puntos"].agg(["size", "sum"]).sort_values("size", ascending=False)
    for grupo, r in resumen.iterrows():
        sub = datos[datos["grupo"] == grupo]
        fila = [html.escape(str(grupo)), int(r["size"]), barra(r["size"] / len(datos) * 100), color(r["sum"] / r["size"])]
        for playtype, _, _ in ACABA:
            acaba = sub[sub["playtype"] == playtype]
            fila += (["0%", "-"] if acaba.empty else
                     [f"{len(acaba) / len(sub) * 100:.0f}%", color(acaba["puntos"].sum() / len(acaba))])
        filas.append(fila)
    tabla(cabeceras, filas, desplazable=True)


def analisis_pr(df_pr, nombre, fase="ataque"):
    """Tablas de P&R por manejador, bloqueador, pareja y defensa del P&R, más un analizador individual.
    En defensa se usan los defensores del manejador y del bloqueador, y un PPP bajo es bueno."""
    t = TEXTOS_PR[fase]
    mayor_es_mejor = fase == "ataque"
    col_manejador, col_bloqueador = ("pr_handler", "pr_roller") if mayor_es_mejor else ("defensor_pr_handler", "defensor_pr_roller")
    if df_pr.empty:
        st.info("Sin posesiones de P&R etiquetadas.")
        return
    ppp_pr = df_pr["puntos"].sum() / len(df_pr)
    st.caption(t["resumen"].format(n=len(df_pr), ppp=ppp_pr) +
               " Frecuencia: % del total de P&R. El color del PPP compara con el PPP medio en P&R"
               f"{'' if mayor_es_mejor else ' (verde = el rival anota menos)'}.")
    jugador = lambda j: nombre(j) if pd.notna(j) else "Sin indicar"
    manejadores = df_pr[col_manejador].apply(jugador)
    bloqueadores = df_pr[col_bloqueador].apply(jugador)

    subtitulo(t["manejadores"])
    tabla_pr(df_pr, manejadores, t["manejador"], ppp_pr, mayor_es_mejor)
    subtitulo(t["bloqueadores"])
    tabla_pr(df_pr, bloqueadores, t["bloqueador"], ppp_pr, mayor_es_mejor)
    subtitulo(t["parejas"])
    tabla_pr(df_pr, manejadores + " - " + bloqueadores, f"{t['manejador']} - {t['bloqueador']}", ppp_pr, mayor_es_mejor)
    subtitulo("Uso por tipo de defensa del P&R")
    tabla_pr(df_pr, df_pr["pr_defense"].fillna("Sin indicar"), "Defensa del P&R", ppp_pr, mayor_es_mejor)

    # Analizador individual
    subtitulo("🔍 Analizador individual")
    ids = pd.concat([df_pr[col_manejador], df_pr[col_bloqueador]]).dropna().astype(int)
    if ids.empty:
        st.info("Ningún P&R tiene indicado a los jugadores.")
        return
    id_jugador = st.selectbox("Jugador", ids.value_counts().index.tolist(), format_func=nombre,
                              key=f"propio_pr_jugador_{fase}")  # los que más P&R juegan, primero
    es_manejador = df_pr[col_manejador] == id_jugador
    es_bloqueador = df_pr[col_bloqueador] == id_jugador
    df_jug = df_pr[es_manejador | es_bloqueador]
    ppp_jug = df_jug["puntos"].sum() / len(df_jug)
    st.caption(f"{nombre(id_jugador)} participa en {len(df_jug)} P&R ({len(df_jug) / len(df_pr) * 100:.0f}% del total) "
               f"· {ppp_jug:.2f} PPP{'' if mayor_es_mejor else ' permitido'}. "
               "En estas tablas la frecuencia es sobre sus P&R.")

    st.markdown("**Rol en el P&R**")
    rol = pd.Series(np.where(es_manejador[df_jug.index], t["rol_manejador"], t["rol_bloqueador"]), index=df_jug.index)
    tabla_pr(df_jug, rol, "Rol", ppp_pr, mayor_es_mejor)

    st.markdown("**Parejas**")
    companero = pd.Series([t["con_bloqueador"].format(bloqueadores[i]) if es_manejador[i]
                           else t["con_manejador"].format(manejadores[i]) for i in df_jug.index], index=df_jug.index)
    tabla_pr(df_jug, companero, "Pareja", ppp_pr, mayor_es_mejor)

    st.markdown("**Ante cada tipo de defensa del P&R**")
    tabla_pr(df_jug, df_jug["pr_defense"].fillna("Sin indicar"), "Defensa del P&R", ppp_pr, mayor_es_mejor)


# Quién genera cada secondary playtype: el campo del etiquetador que lo registra
GENERADOR_SECUNDARIO = {"P&R Handler": "pr_handler", "P&R Roller": "pr_roller",
                        "Isolation": "jugador_secundario", "Post Up": "jugador_secundario"}


def generadores(df, nombre):
    """Jugador que genera el secondary playtype de cada posesión ("Sin indicar" si no se registra)."""
    def generador(fila):
        columna = GENERADOR_SECUNDARIO.get(fila["playtype_secundario"])
        valor = fila[columna] if columna else None
        return nombre(valor) if pd.notna(valor) else "Sin indicar"
    return df.apply(generador, axis=1)


def tabla_secundarios(df, ppp_referencia, nombre, clave, referencia="el PPP del sistema"):
    """Para cada secondary playtype: frecuencia, PPP y quién lo genera (protagonistas), y debajo los playtypes
    principales a los que lleva. Después, el detalle de quién genera cada playtype principal con ese secondary."""
    con_secundario = df[df["playtype_secundario"].notna()]
    if con_secundario.empty:
        st.info("No hay posesiones con secondary playtype en esta selección.")
        return
    con_secundario = con_secundario.assign(generador=generadores(con_secundario, nombre))
    color = lambda v: f"<span style='color: {color_comparado(v, ppp_referencia)}; font-weight: bold;'>{v:.2f}</span>"
    corto = lambda texto: texto.partition(" - ")[2].split()[0].title() if " - " in texto else texto

    filas = []
    por_secundario = con_secundario.groupby("playtype_secundario")["puntos"].agg(["size", "sum"])
    for secundario, r in por_secundario.sort_values("size", ascending=False).iterrows():
        sub = con_secundario[con_secundario["playtype_secundario"] == secundario]
        # Los 3 jugadores que más generan este secondary playtype
        top = sub["generador"].value_counts().head(3)
        protagonistas = " · ".join(f"{html.escape(corto(g))} ×{n}" for g, n in top.items())
        filas.append([f"<b style='color: #F97316;'>{html.escape(secundario)}</b>", f"<b>{int(r['size'])}</b>",
                      f"<b>{r['size'] / len(df) * 100:.1f}%</b>", "",
                      f"<span style='font-size: 0.85rem;'>{protagonistas}</span>", color(r["sum"] / r["size"])])
        por_principal = sub.groupby("playtype")["puntos"].agg(["size", "sum"]).sort_values("size", ascending=False)
        for principal, rp in por_principal.iterrows():
            filas.append([f"<span style='padding-left: 22px; color: #D4D4D4;'>↳ {html.escape(principal)}</span>",
                          int(rp["size"]), "", barra(rp["size"] / r["size"] * 100), "", color(rp["sum"] / rp["size"])])
    tabla(["Secondary playtype → Playtype principal", tip("Posesiones", DEF_POSESIONES),
           tip("% del total", "Porcentaje de las posesiones de la selección en las que aparece ese secondary playtype."),
           tip("% dentro del secondary", "De las posesiones con ese secondary playtype, qué % acaba en cada playtype principal."),
           tip("Protagonistas", "Jugadores que más generan ese secondary playtype (handler en P&R Handler, roller en "
                                "P&R Roller y secondary player en Isolation y Post Up), con el nº de veces."),
           tip("PPP", DEF_PPP)], filas, desplazable=True)
    st.caption(f"{len(con_secundario)} de {len(df)} posesiones ({len(con_secundario) / len(df) * 100:.0f}%) tienen secondary "
               f"playtype. El color del PPP compara con {referencia} ({ppp_referencia:.2f}).")

    # Detalle a demanda: quién genera, y qué playtype principal produce
    # Solo los secondary playtypes en los que se registra quién genera
    secundarios = [s for s in por_secundario.sort_values("size", ascending=False).index if s in GENERADOR_SECUNDARIO]
    if not secundarios:
        return
    elegido = st.selectbox("Ver quién genera…", secundarios, key=f"{clave}_secundario_detalle")
    sub = con_secundario[con_secundario["playtype_secundario"] == elegido]
    sub = sub.assign(genera=[f"{g} → {p}" for g, p in zip(sub["generador"], sub["playtype"])])
    st.caption(f"{len(sub)} posesiones con {elegido} de secondary playtype. Frecuencia: % de esas posesiones.")
    mostrar_resumen(resumen_por(sub, "genera"), "Genera → Playtype principal", ppp_referencia)


def carta_de_tiro_equipo(df_at, nombre):
    """Carta de tiro de todo el equipo o, si se elige, de un jugador concreto."""
    tiros = df_at[df_at["idMove"].isin(TIROS_CAMPO) & df_at["tiro_x"].notna()]
    if tiros.empty:
        st.info("No hay tiros con la localización marcada en el etiquetador.")
        return
    # Opciones: todo el equipo y, después, los jugadores con más tiros localizados
    tiradores = tiros["id_jugador"].dropna().astype(int).value_counts()
    opciones = [None] + tiradores.index.tolist()
    elegido = st.selectbox("Jugador", opciones, key="propio_carta_jugador",
                           format_func=lambda j: "Todo el equipo" if j is None else f"{nombre(j)} ({tiradores[j]} tiros)")
    df_tiros = tiros if elegido is None else tiros[tiros["id_jugador"] == elegido]
    st.caption(f"{'Todo el equipo' if elegido is None else nombre(elegido)}: {len(df_tiros)} tiros de campo con localización.")
    carta_de_tiro(df_tiros, clave="ataque_tiro", mensaje_vacio="Este jugador no tiene tiros con localización registrada.")


def apartado_ataque(h, id_propio, ultimos_n, df_at, nombres):
    if df_at.empty:
        st.info("No hay posesiones de ataque etiquetadas en los partidos seleccionados. Se rellenan con etiquetador.py.")
        subtitulo("📊 Uso vs Eficiencia")
        uso_vs_eficiencia(h, id_propio, ultimos_n)
        return
    ppp_equipo = df_at["puntos"].sum() / len(df_at)
    metricas_cabecera(df_at)
    nombre = lambda j: nombres.get(int(j), str(j))

    tab_sis, tab_pt, tab_pr, tab_def, tab_fin, tab_tiro, tab_uso = st.tabs(
        ["🧩 Sistemas", "🎯 Playtypes", "🤝 P&R", "🧱 Tipo de defensa", "👤 Por finalizador", "🏀 Carta de tiro",
         "📊 Uso vs Eficiencia"])

    with tab_def:
        subtitulo("Frecuencia y eficiencia contra cada tipo de defensa")
        st.caption("Frecuencia: % de nuestras posesiones etiquetadas contra cada defensa del rival. "
                   "El color del PPP compara con el PPP medio del equipo.")
        res_def = resumen_por(df_at, "tipo_defensa", vacio="Sin indicar")
        mostrar_resumen(res_def, "Tipo de defensa", ppp_equipo)
        grafico_frecuencia_ppp(res_def, ppp_equipo)

    with tab_uso:
        uso_vs_eficiencia(h, id_propio, ultimos_n)

    with tab_tiro:
        carta_de_tiro_equipo(df_at, nombre)

    with tab_fin:
        analisis_por_finalizador(df_at, nombre, ppp_equipo)

    with tab_sis:
        subtitulo("Frecuencia y eficiencia por sistema")
        st.caption("Frecuencia: % de las posesiones etiquetadas en las que se juega ese sistema.")
        res = resumen_por(df_at, "sistema", vacio="Sin sistema")
        mostrar_resumen(res, "Sistema", ppp_equipo)

        subtitulo("¿Cómo se finaliza cada sistema?")
        sistemas = res["grupo"].tolist()  # incluye "Sin sistema" (posesiones sin sistema etiquetado)
        if sistemas:
            sistema = st.selectbox("Sistema", sistemas, key="propio_sistema")
            sin_sistema = sistema == "Sin sistema"
            df_sis = df_at[df_at["sistema"].isna()] if sin_sistema else df_at[df_at["sistema"] == sistema]
            ppp_sis = df_sis["puntos"].sum() / len(df_sis)
            descripcion = "sin sistema" if sin_sistema else f"con {sistema}"
            st.caption(f"{len(df_sis)} posesiones {descripcion} · {ppp_sis:.2f} PPP. En las tres tablas, Frecuencia es "
                       "el % de esas posesiones y el color compara con el PPP del sistema.")
            st.markdown("**Con qué playtype**")
            mostrar_resumen(resumen_por(df_sis, "playtype"), "Playtype final", ppp_sis)

            st.markdown("**Quién lo finaliza**")
            finalizador = [nombre(j) if pd.notna(j) else "Sin jugador" for j in df_sis["id_jugador"]]
            df_fin = df_sis.assign(finalizador=finalizador,
                                   jugador_playtype=[f"{f} · {p}" for f, p in zip(finalizador, df_sis["playtype"])])
            mostrar_resumen(resumen_por(df_fin, "finalizador"), "Finaliza", ppp_sis)

            st.markdown("**Quién lo finaliza y con qué playtype**")
            mostrar_resumen(resumen_por(df_fin, "jugador_playtype"), "Jugador · Playtype", ppp_sis)

            st.markdown("**Secondary playtypes: qué playtype principal generan**")
            tabla_secundarios(df_sis, ppp_sis, nombre, clave="sistemas")
        else:
            st.info("Todavía no hay posesiones con sistema.")

    with tab_pt:
        subtitulo("Playtypes: frecuencia y eficiencia")
        conteo = st.radio("Contar", ["Solo principal", "Principal + secundario"], horizontal=True,
                          key="playtypes_conteo")
        if conteo == "Solo principal":
            res = resumen_por(df_at, "playtype")
        else:
            # Cada posesión cuenta en su playtype principal y también en el secundario (una sola vez si coinciden)
            secundarias = df_at[df_at["playtype_secundario"].notna()
                                & (df_at["playtype_secundario"] != df_at["playtype"])]
            res = resumen_por(pd.concat([df_at, secundarias.assign(playtype=secundarias["playtype_secundario"])]),
                              "playtype")
            res["frecuencia"] = res["posesiones"] / len(df_at) * 100
            st.caption("Una posesión cuenta en su playtype principal y en el secundario, así que las frecuencias "
                       "suman más del 100%: indican en qué % de posesiones aparece cada playtype. El PPP es el de "
                       "esas posesiones.")
        mostrar_resumen(res, "Playtype", ppp_equipo)
        grafico_frecuencia_ppp(res, ppp_equipo)

        subtitulo("Secondary playtypes")
        tabla_secundarios(df_at, ppp_equipo, nombre, clave="playtypes", referencia="el PPP medio del equipo")

    with tab_pr:
        # De momento el secondary playtype no entra en ningún cálculo: solo cuenta el principal
        analisis_pr(df_at[df_at["playtype"].isin(PLAYTYPES_PR)], nombre, "ataque")


def tabla_defensores_1c1(df_def, playtype, nombre):
    """Defensores directos (dPlayer) de un playtype del rival: acciones defendidas, % sobre las posesiones del rival
    con el jugador en pista y PPP encajados."""
    subtitulo(playtype)
    acciones = df_def[(df_def["playtype"] == playtype) & df_def["id_defensor"].notna()]
    if acciones.empty:
        st.info(f"Ninguna posesión de {playtype} del rival tiene indicado el dPlayer.")
        return
    ppp_equipo = df_def[df_def["playtype"] == playtype]["puntos"].mean()
    filas = []
    resumen = acciones.groupby(acciones["id_defensor"].astype(int))["puntos"].agg(["size", "sum"])
    for id_jugador, r in resumen.sort_values(["size", "sum"], ascending=[False, True]).iterrows():
        # Posesiones del rival (etiquetadas) con el jugador en pista
        en_pista = int(df_def["en_pista"].apply(lambda ids, j=id_jugador: j in ids).sum())
        ppp = r["sum"] / r["size"]
        color = color_comparado(ppp, ppp_equipo, mayor_es_mejor=False)
        filas.append([html.escape(nombre(id_jugador)), int(r["size"]), en_pista,
                      barra(r["size"] / en_pista * 100) if en_pista else "-", int(r["sum"]),
                      f"<span style='color: {color}; font-weight: bold;'>{ppp:.2f}</span>"])
    tabla(["Defensor", tip("Acciones", f"Posesiones de {playtype} del rival en las que fue el dPlayer."),
           tip("Pos. en pista", "Posesiones del rival (etiquetadas) con el jugador en pista."),
           tip("% defendidas", f"Porcentaje de esas posesiones en las que le tocó defender un {playtype}."),
           tip("Puntos", "Puntos encajados en esas acciones."),
           tip("PPP encajados", "Puntos por posesión encajados en esas acciones. Cuanto más bajo, mejor.")], filas)
    st.caption(f"{len(acciones)} posesiones de {playtype} con dPlayer · PPP del rival en {playtype} contra todo el "
               f"equipo: {ppp_equipo:.2f}.")


def apartado_defensa(df_def, nombres, plantilla):
    if df_def.empty:
        st.info("No hay posesiones de defensa etiquetadas en los partidos seleccionados. Se rellenan con etiquetador.py.")
        return
    ppp_rival = df_def["puntos"].sum() / len(df_def)
    metricas_cabecera(df_def)
    nombre = lambda j: nombres.get(int(j), str(j))

    tab_q, tab_tiro, tab_pr, tab_uno, tab_tipo = st.tabs(
        ["🔄 Playtypes por quinteto", "🎯 Carta de tiro rival", "🤝 P&R defensivo", "🧍 Isolation y Post Up",
         "🧱 Tipo de defensa"])

    with tab_uno:
        st.caption("Para cada jugador que ha sido el defensor directo (dPlayer) al menos una vez: cuántas veces, en qué "
                   "% de las posesiones del rival con él en pista le ha tocado defender esa acción y los PPP que encaja. "
                   "El color compara con el PPP del rival en esa acción contra todo el equipo (verde = encaja menos).")
        for playtype in ("Isolation", "Post Up"):
            tabla_defensores_1c1(df_def, playtype, nombre)

    with tab_tiro:
        subtitulo("¿Desde dónde nos tiran según quién está en pista?")
        seleccion_tiro = st.multiselect("Jugadores en pista (vacío = todo el equipo)", plantilla, max_selections=5,
                                        format_func=nombre, key="propio_def_tiro")
        tiros_rival = df_def[df_def["idMove"].isin(TIROS_CAMPO) & df_def["tiro_x"].notna()]
        tiros_sel = tiros_rival[tiros_rival["en_pista"].apply(lambda ids: all(j in ids for j in seleccion_tiro))]
        if seleccion_tiro:
            st.caption(f"{len(tiros_sel)} tiros del rival con ellos en pista (On) y {len(tiros_rival) - len(tiros_sel)} "
                       "sin ellos (Off).")
        tiros_off = tiros_rival.drop(tiros_sel.index) if seleccion_tiro else None
        carta_de_tiro(tiros_sel, df_off=tiros_off, etiqueta_on="On", etiqueta_off="Off", mayor_es_mejor=False,
                      mensaje_vacio="No hay tiros del rival con localización para esta selección.", clave="def_tiro")

    with tab_q:
        subtitulo("¿Cómo nos anotan según quién está en pista?")
        seleccion = st.multiselect("Jugadores en pista (vacío = todo el equipo)", plantilla, max_selections=5,
                                   format_func=nombre, key="propio_def_quinteto")
        df_sel = df_def[df_def["en_pista"].apply(lambda ids: all(j in ids for j in seleccion))]
        if seleccion:
            ppp_sel = df_sel["puntos"].sum() / len(df_sel) if len(df_sel) else float("nan")
            color = color_comparado(ppp_sel, ppp_rival, mayor_es_mejor=False)
            st.markdown(f"Con ellos en pista: **{len(df_sel)} posesiones**, "
                        f"<span style='color: {color}; font-weight: bold;'>{ppp_sel:.2f} PPP permitido</span> "
                        f"(equipo: {ppp_rival:.2f}).", unsafe_allow_html=True)
        res = resumen_por(df_sel, "playtype")
        mostrar_resumen(res, "Playtype del rival", ppp_rival, mayor_es_mejor=False)
        grafico_frecuencia_ppp(res, ppp_rival, "PPP permitido")

    with tab_pr:
        analisis_pr(df_def[df_def["playtype"].isin(PLAYTYPES_PR)], nombre, "defensa")

    with tab_tipo:
        subtitulo("Eficiencia del rival por tipo de defensa")
        mostrar_resumen(resumen_por(df_def, "tipo_defensa", vacio="Sin indicar"), "Tipo de defensa", ppp_rival, False)


# ------------------------------------------------------------------ ANÁLISIS INDIVIDUAL
# Acierto de referencia por zona cuando no hay otro grupo con el que comparar (valores típicos aproximados)
ACIERTO_ESPERADO = {
    "Restringida": 58, "MDC Central": 42, "MDC Izq": 40, "MDC Dcha": 40,
    "MDL Esq Izq": 37, "MDL Codo Izq": 37, "MDL Central": 37, "MDL Codo Dcha": 37, "MDL Esq Dcha": 37,
    "Esq Izq": 36, "Esq Dcha": 36, "Ala Izq": 33, "Top": 33, "Ala Dcha": 33,
}
VERDE, ROJO, NEUTRO, VACIO = "rgba(74,222,128,0.65)", "rgba(248,113,113,0.65)", "rgba(163,163,163,0.45)", "rgba(255,255,255,0.06)"


def estadisticas_zonas(df_tiros):
    """DataFrame por zona: intentos, anotados, % de acierto, PPT (puntos por tiro) y frecuencia."""
    if df_tiros.empty:
        return pd.DataFrame(columns=["intentos", "anotados", "pct", "ppt", "frecuencia"])
    df = df_tiros.assign(
        zona=[zona_de_tiro(x, y, m in TRIPLES) for x, y, m in zip(df_tiros["tiro_x"], df_tiros["tiro_y"], df_tiros["idMove"])],
        anotado=df_tiros["idMove"].isin(CANASTAS_CAMPO),
    )
    df["puntos_tiro"] = np.where(df["anotado"], np.where(df["idMove"].isin(TRIPLES), 3, 2), 0)
    res = df.groupby("zona").agg(intentos=("anotado", "size"), anotados=("anotado", "sum"), puntos=("puntos_tiro", "sum"))
    res.loc["Total"] = res.sum()
    res["pct"] = res["anotados"] / res["intentos"] * 100
    res["ppt"] = res["puntos"] / res["intentos"]
    res["frecuencia"] = res["intentos"] / len(df) * 100
    return res


def carta_de_tiro(df_on, df_off=None, etiqueta_on="On", etiqueta_off="Off", mayor_es_mejor=True,
                  mensaje_vacio="Este jugador no tiene tiros con localización registrada.", clave="carta"):
    """Carta de tiro por zonas con su tabla, en un único componente HTML (SVG + tabla) para que al pasar el
    cursor por una zona se resalte su fila y viceversa.
    df_on / df_off: los dos grupos que se comparan (p. ej. con unos jugadores en pista y sin ellos).
    Sin df_off, cada zona se compara con un acierto típico. mayor_es_mejor=False invierte los colores (defensa)."""
    if df_on.empty:
        st.info(mensaje_vacio)
        return

    c1, c2, c3 = st.columns([2, 2, 1])
    modo = c1.radio("Ver", ["Acierto", "Frecuencia"], horizontal=True, key=f"{clave}_modo")
    medida = c2.radio("Medida", ["%", "PPT"], horizontal=True, key=f"{clave}_medida",
                      help="PPT: puntos por tiro (2 o 3 puntos × acierto).", disabled=modo == "Frecuencia")
    ver_tiros = c3.checkbox("Ver tiros", key=f"{clave}_puntos")

    res = estadisticas_zonas(df_on)
    hay_off = df_off is not None and not df_off.empty
    off = estadisticas_zonas(df_off) if hay_off else None

    def referencia(zona):
        if hay_off:
            if zona in off.index:
                return off.loc[zona, "pct"], off.loc[zona, "ppt"]
            return float("nan"), float("nan")
        if zona in ACIERTO_ESPERADO:
            pct = ACIERTO_ESPERADO[zona]
            return pct, pct / 100 * (3 if zona in ZONAS_TRIPLE else 2)
        return float("nan"), float("nan")

    # Color y texto de cada zona
    colores, etiquetas_svg = {}, []
    max_freq = res.drop(index="Total")["frecuencia"].max()
    for zona in ZONAS_TIRO:
        if zona not in res.index:
            colores[zona], linea1, linea2 = VACIO, "0/0" if modo == "Acierto" else "0", ""
        else:
            r = res.loc[zona]
            if modo == "Frecuencia":
                colores[zona] = f"rgba(249,115,22,{0.15 + 0.6 * r.frecuencia / max_freq:.2f})"
                linea1, linea2 = f"{int(r.intentos)}", f"{r.frecuencia:.0f}%"
            else:
                pct_ref, ppt_ref = referencia(zona)
                if medida == "%":
                    valor, valor_ref, margen, linea2 = r.pct, pct_ref, 5, f"{r.pct:.0f}%"
                else:
                    valor, valor_ref, margen, linea2 = r.ppt, ppt_ref, 0.1, f"{r.ppt:.2f}"
                tono = color_comparado(valor, valor_ref, mayor_es_mejor, margen)
                colores[zona] = {"#4ADE80": VERDE, "#F87171": ROJO}.get(tono, NEUTRO)
                linea1 = f"{int(r.anotados)}/{int(r.intentos)}"
        x, y = POSICION_ETIQUETA[zona]
        tamano = 0.36 if zona in ("Esq Izq", "Esq Dcha") else 0.5
        # Las etiquetas van fuera del grupo invertido: y en pantalla = Y_MAX - y
        ys = Y_MAX_ZONAS + 0.2 - y
        etiquetas_svg.append(
            f'<text class="etiqueta" data-zona="{zona}" x="{x + 0.3:.2f}" y="{ys - 0.05:.2f}" font-size="{tamano}">'
            f'<tspan x="{x + 0.3:.2f}">{linea1}</tspan><tspan x="{x + 0.3:.2f}" dy="{tamano * 1.1:.2f}">{linea2}</tspan></text>')

    tiros_svg = ""
    if ver_tiros:
        for x, y, m in zip(df_on["tiro_x"], df_on["tiro_y"], df_on["idMove"]):
            if m in CANASTAS_CAMPO:
                tiros_svg += f'<circle cx="{x}" cy="{y}" r="0.13" fill="#4CAF50" stroke="#FFFFFF" stroke-width="1" vector-effect="non-scaling-stroke"/>'
            else:
                d = 0.13
                tiros_svg += (f'<path d="M {x - d},{y - d} L {x + d},{y + d} M {x - d},{y + d} L {x + d},{y - d}" '
                              'stroke="#E53935" stroke-width="2.5" vector-effect="non-scaling-stroke"/>')

    alto_svg = Y_MAX_ZONAS + 0.5
    svg = f"""
    <svg viewBox="0 0 15.6 {alto_svg:.1f}" xmlns="http://www.w3.org/2000/svg">
      <defs><clipPath id="corte"><rect x="0" y="-0.3" width="15" height="{Y_MAX_ZONAS + 0.3}"/></clipPath></defs>
      <rect x="0" y="0" width="15.6" height="{alto_svg:.1f}" fill="#141414"/>
      <g transform="translate(0.3, {Y_MAX_ZONAS + 0.2}) scale(1,-1)" clip-path="url(#corte)">
        {svg_zonas(colores)}
        {svg_lineas()}
        {tiros_svg}
      </g>
      {''.join(etiquetas_svg)}
    </svg>"""

    # Tabla con las columnas On / Off
    def celda_pct(zona, r):
        if r is None:
            return "-"
        pct_ref = referencia(zona)[0] if zona != "Total" else (off.loc["Total", "pct"] if hay_off else float("nan"))
        color = color_comparado(r.pct, pct_ref, mayor_es_mejor, margen=5)
        return f"<span style='color: {color}; font-weight: bold;'>{r.pct:.1f}%</span>"

    sufijo_on = f" {etiqueta_on}" if hay_off else ""  # sin grupo Off no hay nada que distinguir
    cabeceras = ["Zona", f"Tiros{sufijo_on}", f"%{sufijo_on}"]
    if hay_off:
        cabeceras += [f"% {etiqueta_off}"]
    cabeceras += [f"Frec.{sufijo_on}"] + ([f"Frec. {etiqueta_off}"] if hay_off else [])
    filas_html = ""
    for zona in ZONAS_TIRO + ["Total"]:
        r = res.loc[zona] if zona in res.index else None
        r_off = off.loc[zona] if hay_off and zona in off.index else None
        if r is None and r_off is None:
            continue
        celdas = [f"<b>{zona}</b>" if zona == "Total" else zona,
                  f"{int(r.anotados)}/{int(r.intentos)}" if r is not None else "0/0",
                  celda_pct(zona, r)]
        if hay_off:
            celdas.append(f"{r_off.pct:.1f}%" if r_off is not None else "-")
        celdas.append(f"{r.frecuencia:.0f}%" if r is not None else "0%")
        if hay_off:
            celdas.append(f"{r_off.frecuencia:.0f}%" if r_off is not None else "0%")
        atributo = f' data-zona="{zona}"' if zona != "Total" else ' class="total"'
        filas_html += f"<tr{atributo}>" + "".join(f"<td>{c}</td>" for c in celdas) + "</tr>"
    tabla_html = ("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cabeceras) + "</tr></thead>"
                  f"<tbody>{filas_html}</tbody></table>")

    contenido = f"""
    <style>
      body {{ margin: 0; font-family: "Source Sans Pro", sans-serif; color: #FAFAFA; background: transparent; }}
      .carta {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }}
      .cancha {{ flex: 3 1 380px; }}
      .cancha svg {{ width: 100%; height: auto; display: block; border-radius: 8px; }}
      .tabla {{ flex: 2 1 300px; border: 1px solid #3F3F3F; border-radius: 10px; overflow: hidden; }}
      .zona {{ stroke: rgba(255,255,255,0.35); stroke-width: 1; vector-effect: non-scaling-stroke; cursor: pointer;
               transition: filter 0.1s; }}
      .zona.activa {{ stroke: #FFFFFF; stroke-width: 3; filter: brightness(1.45); }}
      .etiqueta {{ fill: #FFFFFF; font-weight: 700; text-anchor: middle; pointer-events: none; }}
      table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
      th {{ background: rgba(255,255,255,0.1); text-transform: uppercase; font-size: 0.7rem; letter-spacing: 1px;
            padding: 8px 6px; border-bottom: 2px solid #F97316; text-align: center; }}
      th:first-child, td:first-child {{ text-align: left; padding-left: 10px; }}
      td {{ padding: 6px; border-bottom: 1px solid rgba(255,255,255,0.2); text-align: center; }}
      tr[data-zona] {{ cursor: pointer; transition: background 0.1s; }}
      tr.activa {{ background: rgba(255,255,255,0.18); }}
      tr.total td {{ border-bottom: none; }}
    </style>
    <div class="carta">
      <div class="cancha">{svg}</div>
      <div class="tabla">{tabla_html}</div>
    </div>
    <script>
      // Resaltado cruzado: zona de la cancha <-> fila de la tabla
      const marcar = (zona, activa) => document.querySelectorAll('[data-zona="' + zona + '"]')
          .forEach(el => el.classList.toggle('activa', activa));
      document.querySelectorAll('.zona, tr[data-zona]').forEach(el => {{
        el.addEventListener('mouseenter', () => marcar(el.dataset.zona, true));
        el.addEventListener('mouseleave', () => marcar(el.dataset.zona, false));
      }});
    </script>
    """
    components.html(contenido, height=560, scrolling=True)

    if hay_off:
        texto_ref = f"acierto {etiqueta_on} comparado con {etiqueta_off}"
    else:
        texto_ref = "acierto comparado con un acierto típico de cada zona"
    st.caption(f"Color de cada zona: {texto_ref} — verde mejor, rojo peor"
               f"{', desde el punto de vista de la defensa' if not mayor_es_mejor else ''}. "
               "Pasa el cursor por una zona o por una fila para resaltarlas. "
               "Solo tiros de campo con la localización marcada en el etiquetador.")


def ficha_jugador(h, id_jugador, id_propio, nombres, df_at, ultimos_n):
    if st.button("⬅️ Volver a la plantilla", key="propio_volver"):
        st.session_state.propio_jugador = None
        st.rerun()

    nombre = nombres.get(id_jugador, "Desconocido")
    dorsal, _, nombre_corto = nombre.partition(" - ")
    foto = h.obtener_foto_jugador_base64(nombre_corto)
    if foto:
        img = f'<img src="data:image/png;base64,{foto}" style="width: 110px; height: 110px; object-fit: cover; border-radius: 12px; border: 3px solid #D4D4D4;">'
    else:
        iniciales = "".join(p[0] for p in nombre_corto.split()[:2]).upper()
        img = f'<div style="width: 110px; height: 110px; background-color: #262626; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #F97316; font-weight: bold; font-size: 2.5rem;">{iniciales}</div>'
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #262626 0%, #0B0B0B 100%); border-radius: 15px; padding: 25px; display: flex; align-items: center; gap: 25px; margin-bottom: 20px; border: 1px solid #333333; border-left: 5px solid #F97316;">
        {img}
        <div>
            <span style="color: #A3A3A3; font-size: 2.2rem; font-weight: 800; margin-right: 12px;">#{dorsal}</span>
            <span style="color: #FFFFFF; font-size: 2.2rem; font-weight: 800; text-transform: uppercase;">{html.escape(nombre_corto)}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_perfil, tab_impacto, tab_tiro, tab_pt, tab_sis = st.tabs(
        ["👤 Perfil", "💥 Impacto", "🎯 Carta de tiro", "📋 Playtypes", "🧩 Sistemas"])
    with tab_perfil:
        h.mostrar_perfil_jugador(id_jugador, ultimos_n)
    with tab_impacto:
        h.mostrar_impacto_jugador(id_jugador, id_propio, ultimos_n)
    with tab_tiro:
        tiros_equipo = df_at[df_at["idMove"].isin(TIROS_CAMPO) & df_at["tiro_x"].notna()]
        # Solo los tiros del jugador (acierto y frecuencia), sin comparación On/Off
        carta_de_tiro(tiros_equipo[tiros_equipo["id_jugador"] == id_jugador], clave="jug_tiro")
    with tab_pt:
        analisis_jugador_por(df_at, id_jugador, "playtype", "Playtype")
        subtitulo("Como generador: secondary playtypes")
        tabla_generador_jugador(df_at, id_jugador)
    with tab_sis:
        analisis_jugador_por(df_at, id_jugador, "sistema", "Sistema", vacio="Sin sistema")


def analisis_jugador_por(df_at, id_jugador, columna, etiqueta, vacio="—"):
    """Frecuencia y PPP de las posesiones que finaliza el jugador agrupadas por `columna` (playtype o sistema),
    comparadas con el PPP de todo el equipo en cada grupo."""
    df_jug = df_at[df_at["id_jugador"] == id_jugador]
    if df_jug.empty:
        st.info("Este jugador no finaliza ninguna posesión etiquetada.")
        return
    ppp_jug = df_jug["puntos"].sum() / len(df_jug)
    nombre = etiqueta.lower()
    st.caption(f"Posesiones que finaliza el jugador: {len(df_jug)} · {ppp_jug:.2f} PPP. "
               f"El color compara con el PPP del equipo en cada {nombre}.")
    res = resumen_por(df_jug, columna, vacio=vacio)
    grupos_equipo = df_at[columna].fillna(vacio)
    ppp_equipo = df_at.groupby(grupos_equipo)["puntos"].sum() / df_at.groupby(grupos_equipo).size()
    cabeceras = [etiqueta, tip("Posesiones", DEF_POSESIONES), tip("Frecuencia", DEF_FRECUENCIA),
                 tip("PPP", DEF_PPP), tip("PPP equipo", f"PPP de todo el equipo en ese {nombre}.")]
    filas = []
    for r in res.itertuples():
        ref = ppp_equipo.get(r.grupo, float("nan"))
        color = color_comparado(r.ppp, ref)
        filas.append([html.escape(str(r.grupo)), int(r.posesiones), barra(r.frecuencia),
                      f"<span style='color: {color}; font-weight: bold;'>{r.ppp:.2f}</span>", f"{ref:.2f}"])
    tabla(cabeceras, filas)
    grafico_frecuencia_ppp(res, ppp_jug)


def tabla_generador_jugador(df_at, id_jugador):
    """Posesiones en las que el jugador genera el secondary playtype (handler, roller o secondary player):
    frecuencia, cómo acaban (playtype principal) y PPP, comparado con el PPP del equipo en ese secondary."""
    con_secundario = df_at[df_at["playtype_secundario"].isin(GENERADOR_SECUNDARIO)]
    genera = con_secundario.apply(lambda f: f[GENERADOR_SECUNDARIO[f["playtype_secundario"]]] == id_jugador, axis=1)
    df_gen = con_secundario[genera.astype(bool)] if not con_secundario.empty else con_secundario
    if df_gen.empty:
        st.info("Este jugador no genera ningún secondary playtype en las posesiones etiquetadas.")
        return
    ppp_equipo = con_secundario.groupby("playtype_secundario")["puntos"].mean()
    color = lambda v, ref: f"<span style='color: {color_comparado(v, ref)}; font-weight: bold;'>{v:.2f}</span>"

    filas = []
    por_secundario = df_gen.groupby("playtype_secundario")["puntos"].agg(["size", "sum"])
    for secundario, r in por_secundario.sort_values("size", ascending=False).iterrows():
        ref = ppp_equipo[secundario]
        filas.append([f"<b style='color: #F97316;'>{html.escape(secundario)}</b>", f"<b>{int(r['size'])}</b>",
                      barra(r["size"] / len(df_gen) * 100), color(r["sum"] / r["size"], ref), f"{ref:.2f}"])
        sub = df_gen[df_gen["playtype_secundario"] == secundario]
        por_principal = sub.groupby("playtype")["puntos"].agg(["size", "sum"]).sort_values("size", ascending=False)
        for principal, rp in por_principal.iterrows():
            filas.append([f"<span style='padding-left: 22px; color: #D4D4D4;'>↳ {html.escape(principal)}</span>",
                          int(rp["size"]), barra(rp["size"] / r["size"] * 100), color(rp["sum"] / rp["size"], ref), ""])
    tabla(["Secondary playtype → Cómo acaba", tip("Posesiones", DEF_POSESIONES),
           tip("Frecuencia", "En el secondary playtype: % de las posesiones que genera el jugador. En cada ↳: % de "
                             "las posesiones de ese secondary que acaban en ese playtype principal."),
           tip("PPP", DEF_PPP), tip("PPP equipo", "PPP de todo el equipo con ese secondary playtype.")], filas)
    ppp_gen = df_gen["puntos"].sum() / len(df_gen)
    st.caption(f"Posesiones que genera el jugador: {len(df_gen)} · {ppp_gen:.2f} PPP (como handler en P&R Handler, "
               "roller en P&R Roller y secondary player en Isolation y Post Up). "
               "El color compara con el PPP del equipo en ese secondary playtype.")


def apartado_individual(h, id_propio, nombres, df_at, ultimos_n):
    if st.session_state.get("propio_jugador") is not None:
        ficha_jugador(h, st.session_state.propio_jugador, id_propio, nombres, df_at, ultimos_n)
        return

    df_plantilla = h.cargar_plantilla(id_propio)
    if df_plantilla.empty:
        st.warning("No hay jugadores registrados para el equipo propio.")
        return
    num_columnas = 4
    for i in range(0, len(df_plantilla), num_columnas):
        columnas = st.columns(num_columnas)
        for j, columna in enumerate(columnas):
            if i + j >= len(df_plantilla):
                continue
            jugador = df_plantilla.iloc[i + j]
            with columna:
                nombre_jugador = jugador["nombre"]
                dorsal = jugador["dorsal"] if pd.notna(jugador["dorsal"]) and str(jugador["dorsal"]).strip() else "-"
                foto = h.obtener_foto_jugador_base64(nombre_jugador)
                if foto:
                    grafico = f'<img src="data:image/png;base64,{foto}" style="width: 100%; height: 200px; object-fit: cover; border-radius: 10px 10px 0 0;">'
                else:
                    iniciales = "".join(p[0] for p in nombre_jugador.split()[:2]).upper()
                    grafico = f'<div style="width: 100%; height: 200px; background-color: #262626; border-radius: 10px 10px 0 0; display: flex; align-items: center; justify-content: center; color: #F97316; font-weight: bold; font-size: 3rem;">{iniciales}</div>'
                tarjeta = f"""
                <div style="background-color: #1A1A1A; border: 1px solid #333333; border-radius: 10px; display: flex; flex-direction: column; align-items: center; margin-bottom: 10px;">
                    {grafico}
                    <div style="width: 100%; padding: 20px 15px; text-align: center; position: relative;">
                        <div style="position: absolute; top: -20px; right: 15px; background-color: #F97316; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 3px solid #1A1A1A;">{dorsal}</div>
                        <h4 style="color: #F97316; margin: 0; font-size: 1rem; line-height: 1.2;">{html.escape(nombre_jugador)}</h4>
                    </div>
                </div>
                """
                st.markdown(" ".join(tarjeta.split()), unsafe_allow_html=True)
                if st.button("Ver jugador", key=f"propio_jug_{jugador['id_jugador']}", use_container_width=True):
                    st.session_state.propio_jugador = int(jugador["id_jugador"])
                    st.rerun()


# ------------------------------------------------------------------ ENTRADA
def mostrar_propio(h):
    """Dibuja la sección Propio. `h` agrupa las vistas y utilidades de app.py que se reutilizan."""
    conexion = conectar()
    id_propio = bd.obtener_id_equipo_propio(conexion)
    conexion.close()
    if id_propio is None:
        st.error(f"No se encuentra el equipo '{bd.NOMBRE_EQUIPO_PROPIO}' en la base de datos.")
        return

    if "submenu_propio" not in st.session_state:
        st.session_state.submenu_propio = "Quintetos"

    en_ficha = st.session_state.submenu_propio == "Análisis Individual" and st.session_state.get("propio_jugador") is not None
    col_titulo, col_filtro = st.columns([3, 1])
    if not en_ficha:
        col_titulo.markdown("### Atlético San Sebastián")
    # Filtro común a todos los apartados (la clave mantiene la elección al cambiar de apartado)
    col_filtro.write("")
    solo_ultimos = col_filtro.checkbox("Últimos 4 partidos", key="propio_ultimos4")
    ultimos_n = 4 if solo_ultimos else None
    partidos = partidos_del_equipo(id_propio, ultimos_n)

    if not en_ficha:
        columnas = st.columns(len(APARTADOS))
        for columna, apartado in zip(columnas, APARTADOS):
            tipo = "primary" if st.session_state.submenu_propio == apartado else "secondary"
            if columna.button(f"{ICONOS_APARTADO[apartado]} {apartado}", key=f"btn_propio_{apartado}",
                              use_container_width=True, type=tipo):
                st.session_state.submenu_propio = apartado
                st.session_state.propio_jugador = None
                st.rerun()
        st.write("---")

    nombres = cargar_nombres()
    apartado = st.session_state.submenu_propio
    if apartado == "Quintetos":
        apartado_quintetos(h, id_propio, nombres, ultimos_n, partidos)
    elif apartado == "Estadística":
        apartado_estadistica(id_propio, ultimos_n)
    else:
        df_at, df_def = cargar_posesiones(partidos)
        if apartado == "Ataque":
            apartado_ataque(h, id_propio, ultimos_n, df_at, nombres)
        elif apartado == "Defensa":
            plantilla = h.cargar_plantilla(id_propio)["id_jugador"].astype(int).tolist()
            apartado_defensa(df_def, nombres, plantilla)
        else:
            apartado_individual(h, id_propio, nombres, df_at, ultimos_n)
