import html
import re
import sqlite3

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import propio_bd as bd
from seccion_propio import DEF_POSESIONES, barra, color_comparado, resumen_por, subtitulo, tabla, tip

# Periodos analizados: los cuatro cuartos y todas las prórrogas juntas
PERIODOS = [(1, "1er cuarto"), (2, "2º cuarto"), (3, "3er cuarto"), (4, "4º cuarto"), ("OT", "Prórroga")]
ETIQUETA = dict(PERIODOS)

PUNTOS_JUGADA = {92: 1, 93: 2, 100: 2, 94: 3}
TIROS_CAMPO = [93, 100, 97, 94, 98]

# Estadísticas "por partido" y su total: en un cuarto se dividen entre todos los partidos del jugador, así los cuatro
# cuartos suman el valor del partido completo y la media de un cuarto es 1/4 de ese valor
POR_PARTIDO = {"Minutos por partido": "Minutos Totales", "Puntos por partido": "Puntos totales", "RD pp": "DREB",
               "RO pp": "OREB", "RT pp": "REB", "Asistencias pp": "AST", "Pérdidas pp": "TOV",
               "STL pp": "Recuperaciones", "BLK pp": "Tapones"}
ACUMULADAS = set(POR_PARTIDO) | {"Minutos Totales", "Puntos totales"}
MENOR_ES_MEJOR = {"Pérdidas pp", "Pérdidas p100", "TOV%"}
NEUTRAS = {"2PA%", "3PA%"}  # describen el tipo de tiro, no son mejores ni peores
MINUTOS_PRORROGA = 5


def ids_quinteto(texto):
    return [int(x) for x in re.findall(r"\d+", str(texto))] if pd.notna(texto) else []


# ------------------------------------------------------------------ DATOS
@st.cache_data(ttl=600)
def cargar_eventos(id_equipo, ultimos_n=None):
    """Play by play de los partidos del equipo (todos o los últimos n), con el periodo agrupado (1-4 u "OT")."""
    conexion = sqlite3.connect(bd.RUTA_BD)
    partidos = pd.read_sql("""SELECT id_partido, id_equipo_local = ? AS es_local FROM partidos
                              WHERE ? IN (id_equipo_local, id_equipo_visitante) ORDER BY fecha_iso DESC""",
                           conexion, params=(int(id_equipo), int(id_equipo)))
    if ultimos_n:
        partidos = partidos.head(ultimos_n)
    marcas = ",".join("?" * len(partidos))
    ev = pd.read_sql(f"""SELECT id_partido, period, min, sec, idMove, id_equipo, quinteto_local, quinteto_visitante
                         FROM play_by_play WHERE id_partido IN ({marcas})""",
                     conexion, params=[int(p) for p in partidos["id_partido"]])
    conexion.close()
    ev = ev.merge(partidos, on="id_partido")
    ev["per"] = ev["period"].apply(lambda p: ETIQUETA[p if p <= 4 else "OT"])
    return ev


def ratings_por_periodo(ev, id_equipo):
    """Puntos, posesiones y ratings del equipo y de sus rivales en cada periodo y en el partido completo."""
    ev = ev[ev["id_equipo"].notna()].assign(
        propio=lambda d: d["id_equipo"] == id_equipo,
        puntos=lambda d: d["idMove"].map(PUNTOS_JUGADA).fillna(0),
        fga=lambda d: d["idMove"].isin(TIROS_CAMPO), fta=lambda d: d["idMove"].isin([92, 96]),
        tov=lambda d: d["idMove"].eq(106), oreb=lambda d: d["idMove"].eq(101))

    def resumen(d):
        lado = d.groupby("propio")[["puntos", "fga", "fta", "tov", "oreb"]].sum().reindex([True, False], fill_value=0)
        poss = lado["fga"] + 0.44 * lado["fta"] + lado["tov"] - lado["oreb"]
        posesiones = poss.mean()  # media de las posesiones de ambos equipos
        partidos = d["id_partido"].nunique()
        # Minutos jugados: 10 por cuarto y 5 por prórroga
        periodos = d[["id_partido", "period"]].drop_duplicates()["period"]
        minutos = np.where(periodos <= 4, 10, MINUTOS_PRORROGA).sum()
        ortg = lado.loc[True, "puntos"] / posesiones * 100 if posesiones else np.nan
        drtg = lado.loc[False, "puntos"] / posesiones * 100 if posesiones else np.nan
        return {"partidos": partidos, "pf": lado.loc[True, "puntos"] / partidos, "pc": lado.loc[False, "puntos"] / partidos,
                "ritmo": posesiones / minutos * 40, "ortg": ortg, "drtg": drtg, "net": ortg - drtg}

    filas = {e: resumen(ev[ev["per"] == e]) for _, e in PERIODOS if (ev["per"] == e).any()}
    filas["Partido"] = resumen(ev)
    return pd.DataFrame(filas).T


def minutos_por_periodo(ev):
    """% de los minutos del equipo en cada periodo que juega cada jugador, contando solo los partidos en los que juega."""
    t = ev.copy()
    t["restante"] = t["min"].fillna(0).astype(int) * 60 + t["sec"].fillna(0).astype(int)
    t = t.sort_values(["id_partido", "period", "restante"], ascending=[True, True, False])
    siguiente = t.groupby(["id_partido", "period"])["restante"].shift(-1).fillna(0)
    t["seg"] = (t["restante"] - siguiente).clip(lower=0)
    t["jugadores"] = np.where(t["es_local"] == 1, t["quinteto_local"], t["quinteto_visitante"])
    t["jugadores"] = t["jugadores"].apply(ids_quinteto)

    seg_equipo = t.groupby(["id_partido", "per"])["seg"].sum().rename("seg_equipo").reset_index()
    en_pista = t.explode("jugadores").dropna(subset=["jugadores"]).astype({"jugadores": int})
    seg_jugador = en_pista.groupby(["jugadores", "per"])["seg"].sum()
    # Tiempo disponible: el del equipo en ese periodo en los partidos que juega el jugador
    partidos_jugador = en_pista[["jugadores", "id_partido"]].drop_duplicates()
    disponible = partidos_jugador.merge(seg_equipo, on="id_partido").groupby(["jugadores", "per"])["seg_equipo"].sum()
    pct = (seg_jugador.reindex(disponible.index, fill_value=0) / disponible.replace(0, np.nan) * 100).unstack("per")
    total = en_pista.groupby("jugadores")["seg"].sum() / partidos_jugador.merge(
        seg_equipo, on="id_partido").groupby("jugadores")["seg_equipo"].sum() * 100
    pct["Partido"] = total
    return pct


def stats_periodo(h, id_equipo, ultimos_n, periodo, base):
    """Estadísticas individuales de un periodo, con las "por partido" divididas entre todos los partidos del jugador
    (en las prórrogas, entre los partidos con prórroga que juega)."""
    df = h.calcular_stats_individuales_liga(ultimos_n=ultimos_n, periodo=periodo)
    if df.empty:
        return df
    df = df[df["id_equipo"] == id_equipo].copy()
    if periodo != "OT":
        df = df.merge(base[["id_jugador", "PJ"]].rename(columns={"PJ": "PJ_total"}), on="id_jugador", how="left")
        for por_partido, total in POR_PARTIDO.items():
            df[por_partido] = df[total] / df["PJ_total"].replace(0, np.nan)
    return df


def referencia(base, periodo):
    """Media del jugador con la que se compara un periodo: su valor del partido completo en las estadísticas de
    ritmo y porcentaje; en las acumuladas, lo que le corresponde a un cuarto (1/4) o a una prórroga (5 de 40 min)."""
    ref = base.set_index("id_jugador")
    factor = 0.25 if periodo != "OT" else MINUTOS_PRORROGA / 40
    escaladas = ref.copy()
    for col in ACUMULADAS:
        if col in escaladas:
            escaladas[col] = ref[col] * factor
    return escaladas


# ------------------------------------------------------------------ VISTA
def formato(valor, columna, es_porcentaje):
    if pd.isna(valor):
        return "-"
    if es_porcentaje:
        return f"{float(valor):.1f}%"
    if columna == "FTr":
        return f"{float(valor):.3f}"
    if columna == "AST / TO":
        return f"{float(valor):.2f}"
    return str(int(valor)) if float(valor) == int(valor) else f"{float(valor):.1f}"


def celda_comparada(valor, ref, columna, es_porcentaje):
    if pd.isna(valor):
        return "-"
    if columna in NEUTRAS:
        color = "#D4D4D4"
    else:
        margen = max(abs(ref) * 0.05, 0.01) if pd.notna(ref) else 0.01
        color = color_comparado(valor, ref, columna not in MENOR_ES_MEJOR, margen=margen)
    media = formato(ref, columna, es_porcentaje) if pd.notna(ref) else "-"
    return (f"<span style='color: {color}; font-weight: bold;'>{formato(valor, columna, es_porcentaje)}</span> "
            f"<span style='color: #737373; font-size: 0.8em;'>({media})</span>")


def mostrar_rendimiento(ratings):
    subtitulo("Rendimiento del equipo")
    partido = ratings.loc["Partido"]
    filas = []
    for nombre, r in ratings.iterrows():
        es_partido = nombre == "Partido"
        def valor_comparado(columna, mayor_es_mejor=True, signo=False, neutro=False):
            formato_num = "{:+.1f}" if signo else "{:.1f}"
            texto = formato_num.format(r[columna])
            if es_partido:
                return f"<b style='color: #F97316;'>{texto}</b>"
            color = "#D4D4D4" if neutro else color_comparado(r[columna], partido[columna], mayor_es_mejor, margen=1.0)
            return (f"<span style='color: {color}; font-weight: bold;'>{texto}</span> "
                    f"<span style='color: #737373; font-size: 0.8em;'>({formato_num.format(partido[columna])})</span>")
        etiqueta = "<span style='color: #F97316;'>Media del partido</span>" if es_partido else nombre
        filas.append([etiqueta, int(r["partidos"]), f"{r['pf']:.1f} - {r['pc']:.1f}", valor_comparado("ritmo", neutro=True),
                      valor_comparado("ortg"), valor_comparado("drtg", mayor_es_mejor=False),
                      valor_comparado("net", signo=True)])
    tabla(["Periodo", tip("Partidos", "Partidos del equipo en la muestra que tienen ese periodo."),
           tip("Parcial medio", "Puntos a favor - en contra por partido en ese periodo."),
           tip("Ritmo", "Posesiones por cada 40 minutos en ese periodo (media de las de ambos equipos)."),
           tip("Offensive Rating", "Puntos anotados cada 100 posesiones."),
           tip("Defensive Rating", "Puntos recibidos cada 100 posesiones."),
           tip("Net Rating", "Offensive Rating - Defensive Rating.")], filas)
    st.caption("Entre paréntesis, la media del equipo en el partido completo (última fila). El color compara cada "
               "periodo con esa media: verde mejor, rojo peor (en el Defensive Rating, más bajo es mejor).")

    periodos = ratings.drop(index="Partido")
    fig = go.Figure()
    fig.add_bar(x=periodos.index, y=periodos["ortg"], name="Offensive Rating", marker_color="#F97316")
    fig.add_bar(x=periodos.index, y=periodos["drtg"], name="Defensive Rating", marker_color="#737373")
    # Ratings medios del partido como referencia
    fig.add_hline(y=partido["ortg"], line_dash="dash", line_color="#F97316", line_width=1,
                  annotation_text=f"ORtg medio {partido['ortg']:.1f}", annotation_font_color="#F97316",
                  annotation_position="top left")
    fig.add_hline(y=partido["drtg"], line_dash="dash", line_color="#A3A3A3", line_width=1,
                  annotation_text=f"DRtg medio {partido['drtg']:.1f}", annotation_font_color="#A3A3A3",
                  annotation_position="bottom left")
    fig.add_scatter(x=periodos.index, y=periodos["net"], name="Net Rating", mode="lines+markers+text",
                    text=[f"{v:+.1f}" for v in periodos["net"]], textposition="top center", yaxis="y2",
                    line=dict(color="#FFFFFF", width=2), marker=dict(
                        size=10, color=["#4ADE80" if v >= 0 else "#F87171" for v in periodos["net"]]))
    fig.update_layout(
        barmode="group", height=380, plot_bgcolor="rgba(20, 20, 20, 0.85)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D4D4D4"), margin=dict(l=50, r=50, t=30, b=40),
        legend=dict(orientation="h", y=1.12, x=0),
        yaxis=dict(title="Rating", gridcolor="rgba(255,255,255,0.05)"),
        yaxis2=dict(title="Net Rating", overlaying="y", side="right", showgrid=False, zeroline=True,
                    zerolinecolor="rgba(255,255,255,0.2)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def nombre_jugador(fila):
    dorsal = fila["dorsal"] if pd.notna(fila["dorsal"]) and str(fila["dorsal"]).strip() else "-"
    enlace = f"/?jugador_id={int(fila['id_jugador'])}&equipo_id={int(fila['id_equipo'])}"
    texto = html.escape(f"{dorsal} - {fila['nombre']}")
    return f"<a href='{enlace}' target='_self' style='color: #FFFFFF; text-decoration: none;'>{texto}</a>"


def mostrar_quien_juega(minutos, plantilla, id_equipo):
    subtitulo("Quién juega cada cuarto")
    df = minutos.reset_index().rename(columns={"jugadores": "id_jugador"}).merge(plantilla, on="id_jugador")
    df["id_equipo"] = id_equipo
    df = df.sort_values("Partido", ascending=False)
    columnas = [c for c in [e for _, e in PERIODOS] + ["Partido"] if c in df]

    def celda(valor, es_partido):
        if pd.isna(valor):
            return "-"
        if es_partido:
            return f"<b>{valor:.1f}%</b>"
        # Más intenso cuanto más juega
        alfa = 0.08 + 0.6 * min(valor, 100) / 100
        return (f"<div style='background: rgba(249, 115, 22, {alfa:.2f}); border-radius: 6px; padding: 4px 0;'>"
                f"{valor:.1f}%</div>")

    filas = [[nombre_jugador(r)] + [celda(r[c], c == "Partido") for c in columnas] for _, r in df.iterrows()]
    tabla(["Jugador"] + [tip(c, f"% de los minutos del equipo en {'el partido' if c == 'Partido' else 'ese periodo'} "
                            "que juega, en los partidos en los que juega.") for c in columnas], filas)
    st.caption("% de minutos: de los minutos del equipo en ese periodo (solo en los partidos que juega el jugador), "
               "cuántos está en pista. En la prórroga, solo cuentan los partidos con prórroga.")


def datos_individuales(h, id_equipo, ultimos_n, periodo, etiqueta, base, minutos, plantilla):
    df = stats_periodo(h, id_equipo, ultimos_n, periodo, base)
    if df.empty:
        return df
    # % de minutos con el mismo criterio que la tabla de quién juega cada cuarto
    df["% Minutos"] = df["id_jugador"].map(minutos[etiqueta]) if etiqueta in minutos else np.nan
    return df.merge(plantilla, on="id_jugador").sort_values("Minutos Totales", ascending=False)


def valor_referencia(ref, jugador, columna):
    return ref.at[jugador, columna] if jugador in ref.index and columna in ref else np.nan


def mostrar_individuales(h, df, ref, periodo):
    subtitulo("Estadísticas individuales por cuarto")
    if df.empty:
        st.info("No hay datos de este periodo.")
        return

    if periodo == "OT":
        minutos_ref = ("En la tabla de minutos, los totales y por partido se comparan con lo que le corresponde a 5 "
                       "minutos de prórroga (por partido: entre los partidos con prórroga que juega).")
    else:
        minutos_ref = ("En la tabla de minutos, los totales y por partido se comparan con la cuarta parte de su media "
                       "(por partido: entre todos los partidos que juega, así los cuatro cuartos suman su media).")
    st.caption("Cada valor se compara con la media del jugador en el partido completo (entre paréntesis): verde por "
               f"encima, rojo por debajo. {minutos_ref}")

    for titulo, config in h.tablas_individuales.items():
        # Totales y "por partido" solo en la tabla de minutos; en el resto, porcentajes, p100 y ratios
        columnas = [(c, p) for c, p in config["columnas"] if titulo == "⏳ Minutos" or c not in ACUMULADAS]
        subtitulo(titulo)
        cabeceras = ["Jugador"] + [h.etiqueta_stat(c, jugador=True, texto=c.replace("_", " ")) for c, _ in columnas]
        filas = []
        for _, r in df.iterrows():
            jugador = int(r["id_jugador"])
            fila = [nombre_jugador(r)]
            for columna, es_porcentaje in columnas:
                media = valor_referencia(ref, jugador, columna)
                fila.append(celda_comparada(r.get(columna), media, columna, es_porcentaje))
            filas.append(fila)
        tabla(cabeceras, filas, desplazable=True)


# ------------------------------------------------------------------ PROPIO: POSESIONES ETIQUETADAS POR CUARTO
def tabla_por_cuarto(df_q, df_total, columna, titulo, vacio="—"):
    """Frecuencia y PPP de cada grupo en el cuarto, con su frecuencia y PPP en todos los cuartos entre paréntesis."""
    res = resumen_por(df_q, columna, vacio=vacio)
    if res.empty:
        st.info("No hay posesiones etiquetadas en este periodo.")
        return
    total = resumen_por(df_total, columna, vacio=vacio).set_index("grupo")
    gris = lambda texto: f" <span style='color: #737373; font-size: 0.8em;'>({texto})</span>"
    filas = []
    for r in res.itertuples():
        freq_total = total["frecuencia"].get(r.grupo, 0.0)
        ppp_total = total["ppp"].get(r.grupo, np.nan)
        color = color_comparado(r.ppp, ppp_total)
        filas.append([html.escape(str(r.grupo)), int(r.posesiones),
                      f"{barra(r.frecuencia)}<div style='text-align: center;'>{gris(f'{freq_total:.1f}%')}</div>",
                      f"<span style='color: {color}; font-weight: bold;'>{r.ppp:.2f}</span>"
                      + gris("-" if pd.isna(ppp_total) else f"{ppp_total:.2f}")])
    tabla([titulo, tip("Posesiones", DEF_POSESIONES),
           tip("Frecuencia", "% de las posesiones etiquetadas del periodo (entre paréntesis, en todo el partido)."),
           tip("PPP", "Puntos por posesión en el periodo (entre paréntesis, en todo el partido).")], filas)


def tabla_uso(h, df, ref):
    """Uso y eficiencia de cada jugador en el cuarto (play by play de la federación), comparados con su partido."""
    columnas = [("%USG", True), ("PPP", False), ("TS%", True), ("Puntos p100", False)]
    df = df[df["%USG"].notna() & (df["%USG"] > 0)].sort_values("%USG", ascending=False)
    if df.empty:
        st.info("No hay jugadores con uso en este periodo.")
        return
    filas = []
    for _, r in df.iterrows():
        jugador = int(r["id_jugador"])
        filas.append([nombre_jugador(r)] + [
            celda_comparada(r[c], valor_referencia(ref, jugador, c), c, p) if c != "PPP"
            else celda_ppp(r[c], valor_referencia(ref, jugador, c)) for c, p in columnas])
    tabla(["Jugador"] + [h.etiqueta_stat(c, jugador=True) for c, _ in columnas], filas)
    st.caption("Calculado con el play by play de la federación (no depende del etiquetado). Entre paréntesis, la media "
               "del jugador en el partido completo: verde por encima, rojo por debajo.")
    grafico = df.rename(columns={"nombre": "Jugador"}).dropna(subset=["%USG", "PPP"])
    grafico = grafico.assign(**{"%USG": grafico["%USG"].astype(float), "PPP": grafico["PPP"].astype(float)})
    if len(grafico) > 1:
        h.grafico_uso_eficiencia(grafico)


def celda_ppp(valor, ref):
    if pd.isna(valor):
        return "-"
    color = color_comparado(valor, ref, margen=0.05)
    media = "-" if pd.isna(ref) else f"{ref:.2f}"
    return (f"<span style='color: {color}; font-weight: bold;'>{valor:.2f}</span> "
            f"<span style='color: #737373; font-size: 0.8em;'>({media})</span>")


def propio_por_cuarto(h, df_at):
    """Tablas del equipo propio para el cuarto elegido: sistemas, playtypes y uso de jugadores."""
    def mostrar(periodo, etiqueta, df, ref):
        df_q = df_at[df_at["period"] > 4] if periodo == "OT" else df_at[df_at["period"] == periodo]
        if df_at.empty:
            st.info("Todavía no hay posesiones etiquetadas.")
        else:
            ppp_q = df_q["puntos"].sum() / len(df_q) if len(df_q) else np.nan
            ppp_total = df_at["puntos"].sum() / len(df_at)
            st.caption(f"{etiqueta}: {len(df_q)} posesiones etiquetadas"
                       + (f" · {ppp_q:.2f} PPP (en todo el partido: {ppp_total:.2f})." if len(df_q) else "."))
            subtitulo("Sistemas: frecuencia y eficiencia")
            tabla_por_cuarto(df_q, df_at, "sistema", "Sistema", vacio="Sin sistema")
            subtitulo("Playtypes: frecuencia y eficiencia")
            tabla_por_cuarto(df_q, df_at, "playtype", "Playtype")
        subtitulo("Jugadores: uso y eficiencia")
        if df.empty:
            st.info("No hay datos de este periodo.")
        else:
            tabla_uso(h, df, ref)
    return mostrar


def mostrar_cuartos(h, id_equipo, ultimos_n=None, por_periodo=None):
    """Análisis por cuartos. `por_periodo(periodo, etiqueta, df, ref)` añade tablas propias del cuarto elegido
    (lo usa la sección Propio) antes de las estadísticas individuales."""
    id_equipo = int(id_equipo)
    ev = cargar_eventos(id_equipo, ultimos_n)
    if ev.empty:
        st.info("No hay jugadas registradas de este equipo.")
        return
    plantilla = h.cargar_plantilla(id_equipo)
    base = h.calcular_stats_individuales_liga(ultimos_n=ultimos_n)
    base = base[base["id_equipo"] == id_equipo] if not base.empty else base

    mostrar_rendimiento(ratings_por_periodo(ev, id_equipo))
    minutos = minutos_por_periodo(ev)
    mostrar_quien_juega(minutos, plantilla, id_equipo)

    subtitulo("Análisis por cuarto")
    disponibles = set(ev["per"])
    etiqueta = st.radio("Periodo", [e for _, e in PERIODOS if e in disponibles], horizontal=True, key="cuartos_periodo")
    periodo = next(p for p, e in PERIODOS if e == etiqueta)
    df = datos_individuales(h, id_equipo, ultimos_n, periodo, etiqueta, base, minutos, plantilla)
    ref = referencia(base, periodo)
    if por_periodo:
        por_periodo(periodo, etiqueta, df, ref)
    mostrar_individuales(h, df, ref, periodo)
