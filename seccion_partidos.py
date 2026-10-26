import base64
import html
import os
import sqlite3
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import propio_bd as bd
from seccion_propio import FORMATO_ESTADISTICA, TABLAS_ESTADISTICA, CONTEOS, _indicadores, subtitulo, tabla, tip

# Sección "Partidos": selector de partido y, para cada uno, resumen, boxscore, estadísticas de equipo y rotación.

# Códigos de jugada de la federación
T2M, T2F, T3M, T3F, TLM, TLF = (93, 100), (97,), (94,), (98,), (92,), (96,)
RO, RD, AS, PER, REC, TAP, TAP_RECIBIDO, FR = 101, 104, 107, 106, 103, 102, 105, 110
FALTAS_COMETIDAS = (109, 159, 160, 161, 162, 166, 537, 565, 571)
SUSTITUCIONES = (112, 115)
# Componentes de las posesiones (FGA + 0,44·FTA + TOV − OREB) que se cuentan en cada tramo en pista
COMPONENTES_POSESION = {"fga": T2M + T2F + T3M + T3F, "fta": TLM + TLF, "tov": (PER,), "oreb": (RO,)}
COLUMNAS_TRAMO = ["pts_l", "pts_v"] + [c + lado for c in COMPONENTES_POSESION for lado in ("_l", "_v")]


# ------------------------------------------------------------------ DATOS
def conectar():
    return sqlite3.connect(bd.RUTA_BD)


@st.cache_data
def escudo_base64(nombre_corto):
    ruta = f"assets/ESCUDO_{nombre_corto}.png"
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def escudo_html(nombre_corto, alto=40):
    b64 = escudo_base64(nombre_corto)
    if b64:
        return f'<img src="data:image/png;base64,{b64}" style="height: {alto}px; width: {alto}px; object-fit: contain; flex-shrink: 0;">'
    return (f'<span style="display: inline-flex; width: {alto}px; height: {alto}px; border-radius: 50%; background: #262626; '
            f'color: #F97316; font-weight: bold; font-size: {alto * 0.3:.0f}px; align-items: center; justify-content: center; '
            f'flex-shrink: 0;">{nombre_corto}</span>')


def cargar_partidos():
    conexion = conectar()
    df = pd.read_sql('''
        SELECT p.id_partido, p.jornada, p.fecha, p.fecha_iso, p.puntos_local, p.puntos_visitante,
               p.id_equipo_local, p.id_equipo_visitante,
               el.nombre AS local, el.nombre_corto AS local_corto, el.color AS local_color,
               ev.nombre AS visitante, ev.nombre_corto AS visitante_corto, ev.color AS visitante_color
        FROM partidos p
        JOIN equipos el ON el.id_equipo = p.id_equipo_local
        JOIN equipos ev ON ev.id_equipo = p.id_equipo_visitante
    ''', conexion)
    conexion.close()
    df["es_liga"] = df["jornada"].astype(str).str.strip().str.isdigit()
    return df


def formato_fecha(fecha_iso, fecha_original):
    if isinstance(fecha_iso, str) and fecha_iso:
        return datetime.strptime(fecha_iso, "%Y-%m-%d %H:%M").strftime("%d/%m/%Y · %H:%M")
    return fecha_original or ""


def duracion_periodo(periodo):
    return 600 if periodo <= 4 else 300


def inicio_periodo(periodo):
    """Segundos de partido transcurridos al empezar el periodo (prórrogas de 5 minutos)."""
    return sum(duracion_periodo(p) for p in range(1, periodo))


@st.cache_data(ttl=600)
def cargar_partido(id_partido):
    """Eventos del partido con el tiempo transcurrido, intervalos con los quintetos en pista y convocatorias."""
    conexion = conectar()
    eventos = pd.read_sql('''
        SELECT rowid AS orden, period, min, sec, id_equipo, id_jugador, idMove, move,
               marcador_local, marcador_visitante, quinteto_local, quinteto_visitante
        FROM play_by_play WHERE id_partido = ? ORDER BY rowid
    ''', conexion, params=(id_partido,))
    convocatorias = pd.read_sql('''
        SELECT c.id_jugador, c.id_equipo, COALESCE(NULLIF(c.dorsal, ''), j.dorsal) AS dorsal, c.titular, j.nombre
        FROM convocatorias c JOIN jugadores j ON j.id_jugador = c.id_jugador WHERE c.id_partido = ?
    ''', conexion, params=(id_partido,))
    conexion.close()

    eventos["period"] = eventos["period"].fillna(1).astype(int)
    restante = eventos["min"].fillna(0).astype(int) * 60 + eventos["sec"].fillna(0).astype(int)
    eventos["t"] = [inicio_periodo(p) + duracion_periodo(p) - r for p, r in zip(eventos["period"], restante)]
    eventos["ml"] = eventos["marcador_local"].ffill().fillna(0).astype(int)
    eventos["mv"] = eventos["marcador_visitante"].ffill().fillna(0).astype(int)
    return eventos, convocatorias


def intervalos_en_pista(eventos, convocatorias, id_local, id_visitante):
    """Tramos de tiempo con el quinteto de cada equipo en pista y los puntos anotados en cada tramo.
    El quinteto guardado en cada evento es el de después del evento, así que el tramo que termina en
    el evento i se juega con el quinteto del evento anterior."""
    titulares = {eq: set(convocatorias[(convocatorias["id_equipo"] == eq) & (convocatorias["titular"] == 1)]["id_jugador"].astype(int))
                 for eq in (id_local, id_visitante)}
    pista_l = titulares[id_local] or set(bd.ids_quinteto(eventos["quinteto_local"].iloc[0]))
    pista_v = titulares[id_visitante] or set(bd.ids_quinteto(eventos["quinteto_visitante"].iloc[0]))
    tramos = []

    def nuevo_tramo(t0, t1):
        tramo = {"t0": t0, "t1": t1, "pista_l": frozenset(pista_l), "pista_v": frozenset(pista_v)}
        tramo.update({c: 0 for c in COLUMNAS_TRAMO})
        tramos.append(tramo)
        return tramo

    t_ant, periodo_ant, ml_ant, mv_ant = 0, 1, 0, 0
    for ev in eventos.itertuples():
        if ev.period != periodo_ant:
            # Lo que queda del periodo anterior tras su último evento
            fin = inicio_periodo(periodo_ant) + duracion_periodo(periodo_ant)
            if fin > t_ant:
                nuevo_tramo(t_ant, fin)
            t_ant, periodo_ant = inicio_periodo(ev.period), ev.period
        if ev.t >= t_ant:
            tramo = nuevo_tramo(t_ant, ev.t)
            t_ant = ev.t
        else:
            # Evento con un tiempo anterior al del evento previo (desorden en el play by play): se suma al último
            # tramo con duración (los de duración 0 son instantes de un cambio, con 4 jugadores)
            tramo = next((tr for tr in reversed(tramos) if tr["t1"] > tr["t0"]), tramos[-1] if tramos else nuevo_tramo(0, 0))
        # Puntos y componentes de las posesiones de cada equipo en el tramo
        tramo["pts_l"] += ev.ml - ml_ant
        tramo["pts_v"] += ev.mv - mv_ant
        if pd.notna(ev.id_equipo):
            lado = "_l" if ev.id_equipo == id_local else "_v"
            for clave, codigos in COMPONENTES_POSESION.items():
                if ev.idMove in codigos:
                    tramo[clave + lado] += 1
        ml_ant, mv_ant = ev.ml, ev.mv
        pista_l = set(bd.ids_quinteto(ev.quinteto_local)) or pista_l
        pista_v = set(bd.ids_quinteto(ev.quinteto_visitante)) or pista_v
    fin = inicio_periodo(periodo_ant) + duracion_periodo(periodo_ant)
    if fin > t_ant:
        nuevo_tramo(t_ant, fin)
    return pd.DataFrame(tramos)


# ------------------------------------------------------------------ SELECTOR DE PARTIDO
def orden_jornada(jornada, partidos):
    if str(jornada).isdigit():
        return (int(jornada), "")
    return (0, partidos[partidos["jornada"] == jornada]["fecha_iso"].min() or "")


def selector_partido():
    partidos = cargar_partidos()
    if partidos.empty:
        st.info("Todavía no hay partidos en la base de datos.")
        return

    c1, c2 = st.columns([1, 2])
    competicion = c1.radio("Competición", ["Liga", "Copa"], horizontal=True, key="partidos_competicion")
    df = partidos[partidos["es_liga"] == (competicion == "Liga")]
    if df.empty:
        st.info(f"No hay partidos de {competicion.lower()}.")
        return
    jornadas = sorted(df["jornada"].unique(), key=lambda j: orden_jornada(j, df))
    etiqueta = (lambda j: f"Jornada {j}") if competicion == "Liga" else (lambda j: j)
    jornada = c2.selectbox("Jornada", jornadas, index=len(jornadas) - 1, format_func=etiqueta, key=f"partidos_jornada_{competicion}")

    # Cada tarjeta es un enlace (?partido=...) que app.py procesa al principio del script
    tarjetas = ""
    for r in df[df["jornada"] == jornada].sort_values("fecha_iso").itertuples():
        gana_local = r.puntos_local > r.puntos_visitante
        fecha = formato_fecha(r.fecha_iso, r.fecha)
        tarjetas += f"""
        <a class="tarjeta-partido" href="?partido={r.id_partido}" target="_self">
            <div class="equipo local">
                <span style="font-weight: {'800' if gana_local else '500'}; color: {'#FFFFFF' if gana_local else '#A3A3A3'};">{html.escape(r.local)}</span>
                {escudo_html(r.local_corto, 38)}
            </div>
            <div class="marcador">
                <div style="font-size: 1.6rem; font-weight: 900; color: #FFFFFF;">{r.puntos_local} - {r.puntos_visitante}</div>
                <div style="font-size: 0.75rem; color: #A3A3A3;">{fecha}</div>
            </div>
            <div class="equipo">
                {escudo_html(r.visitante_corto, 38)}
                <span style="font-weight: {'500' if gana_local else '800'}; color: {'#A3A3A3' if gana_local else '#FFFFFF'};">{html.escape(r.visitante)}</span>
            </div>
        </a>"""
    estilos = """
    <style>
    .tarjeta-partido { display: flex; align-items: center; gap: 14px; background: #111111; border: 1px solid #333;
                       border-left: 4px solid #F97316; border-radius: 12px; padding: 12px 18px; margin-bottom: 10px;
                       text-decoration: none !important; transition: transform 0.12s, border-color 0.12s, background 0.12s; }
    .tarjeta-partido:hover { transform: translateX(4px); border-color: #F97316; background: #1A1A1A; }
    .tarjeta-partido .equipo { flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; line-height: 1.2; }
    .tarjeta-partido .equipo.local { justify-content: flex-end; text-align: right; }
    .tarjeta-partido .marcador { min-width: 110px; text-align: center; }
    </style>"""
    st.caption("Pulsa en un partido para ver su ficha.")
    st.markdown(" ".join((estilos + tarjetas).split()), unsafe_allow_html=True)


# ------------------------------------------------------------------ RESUMEN
def cabecera_partido(p):
    gana_local = p.puntos_local > p.puntos_visitante
    fecha = formato_fecha(p.fecha_iso, p.fecha)
    competicion = f"Liga · Jornada {p.jornada}" if p.es_liga else p.jornada
    st.markdown(" ".join(f"""
    <div style="background: linear-gradient(135deg, #1A1A1A 0%, #0B0B0B 100%); border: 1px solid #333; border-top: 4px solid #F97316;
                border-radius: 16px; padding: 25px; margin-bottom: 20px; text-align: center;">
        <div style="color: #F97316; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; font-size: 0.85rem;">{competicion}</div>
        <div style="color: #A3A3A3; font-size: 0.85rem; margin-bottom: 15px;">{fecha}</div>
        <div style="display: flex; align-items: center; justify-content: center; gap: 30px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 180px; display: flex; flex-direction: column; align-items: center; gap: 10px;">
                {escudo_html(p.local_corto, 90)}
                <span style="font-weight: 800; font-size: 1.1rem; color: #FFFFFF; text-transform: uppercase;">{html.escape(p.local)}</span>
            </div>
            <div style="font-size: 3.5rem; font-weight: 900; color: #FFFFFF; white-space: nowrap;">
                <span style="color: {'#FFFFFF' if gana_local else '#A3A3A3'};">{p.puntos_local}</span>
                <span style="color: #555;"> - </span>
                <span style="color: {'#A3A3A3' if gana_local else '#FFFFFF'};">{p.puntos_visitante}</span>
            </div>
            <div style="flex: 1; min-width: 180px; display: flex; flex-direction: column; align-items: center; gap: 10px;">
                {escudo_html(p.visitante_corto, 90)}
                <span style="font-weight: 800; font-size: 1.1rem; color: #FFFFFF; text-transform: uppercase;">{html.escape(p.visitante)}</span>
            </div>
        </div>
    </div>""".split()), unsafe_allow_html=True)


def color_valido(color, defecto):
    """Color del equipo si es válido y se ve sobre fondo oscuro; si no, el color por defecto."""
    if not (isinstance(color, str) and color.startswith("#") and len(color) in (4, 7)):
        return defecto
    hexa = color[1:] if len(color) == 7 else "".join(c * 2 for c in color[1:])
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))
    luminancia = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return color if luminancia > 0.2 else defecto


def datos_marcador(diferencias):
    """A partir de la diferencia en el marcador (local − visitante) a lo largo del partido devuelve:
    nº de empates (sin contar el 0-0 inicial), mayor ventaja local, mayor ventaja visitante y nº de cambios
    de ganador (veces que pasa a mandar el otro equipo, aunque haya un empate entre medias)."""
    empates, cambios = 0, 0
    anterior, ultimo_lider = 0, 0
    for dif in diferencias:
        signo = (dif > 0) - (dif < 0)
        if dif == 0 and anterior != 0:
            empates += 1
        if signo != 0:
            if ultimo_lider != 0 and signo != ultimo_lider:
                cambios += 1
            ultimo_lider = signo
        anterior = dif
    return empates, max(0, int(diferencias.max())), max(0, int(-diferencias.min())), cambios


def pestana_resumen(p, eventos):
    # Parciales por cuarto: marcador al final de cada periodo
    finales = eventos.groupby("period")[["ml", "mv"]].max()
    finales = finales.cummax()
    parciales = finales.diff().fillna(finales).astype(int)
    nombres_periodo = {1: "1º", 2: "2º", 3: "3º", 4: "4º"}
    columnas = [nombres_periodo.get(per, f"Prórroga {per - 4}" if per > 5 else "Prórroga") for per in parciales.index]
    filas = []
    for corto, nombre, col in ((p.local_corto, p.local, "ml"), (p.visitante_corto, p.visitante, "mv")):
        equipo = f"<div style='display: flex; align-items: center; gap: 10px;'>{escudo_html(corto, 28)}<span>{html.escape(nombre)}</span></div>"
        filas.append([equipo] + [int(v) for v in parciales[col]] + [f"<b>{int(finales[col].iloc[-1])}</b>"])
    subtitulo("Parciales por cuarto")
    tabla(["Equipo"] + columnas + ["Total"], filas)

    # Evolución de la diferencia en el marcador
    subtitulo("Evolución del marcador")
    puntos = pd.concat([pd.DataFrame({"t": [0], "ml": [0], "mv": [0]}), eventos[["t", "ml", "mv"]]])
    puntos["dif"] = puntos["ml"] - puntos["mv"]
    puntos["min"] = puntos["t"] / 60
    color_l = color_valido(p.local_color, "#F97316")
    color_v = color_valido(p.visitante_color, "#A3A3A3")
    if color_l.upper() == color_v.upper():
        color_v = "#A3A3A3"

    empates, ventaja_l, ventaja_v, cambios = datos_marcador(puntos["dif"])
    bloque = lambda valor, titulo: (f"<div style='flex: 1; text-align: center;'><div style='font-size: 2rem; font-weight: 900; "
                                    f"color: #FFFFFF; line-height: 1.1;'>{valor}</div><div style='color: #D4D4D4; "
                                    f"text-transform: uppercase; letter-spacing: 1px; font-size: 0.85rem;'>{titulo}</div></div>")
    ventaja = (f"<span style='color: {color_l};' title='{html.escape(p.local)}'>{ventaja_l}</span>"
               f"<span style='color: #555;'> | </span>"
               f"<span style='color: {color_v};' title='{html.escape(p.visitante)}'>{ventaja_v}</span>")
    st.markdown(" ".join(f"""
    <div style="display: flex; justify-content: space-around; align-items: flex-end; gap: 20px; margin: 10px 0 5px 0; flex-wrap: wrap;">
        {bloque(empates, "Empates")}
        {bloque(ventaja, f"Mayor ventaja <span style='font-size: 0.75rem; color: #A3A3A3;'>({p.local_corto} | {p.visitante_corto})</span>")}
        {bloque(cambios, "Cambios de ganador")}
    </div>""".split()), unsafe_allow_html=True)

    texto = [f"{m:.1f}' · {a}-{b}" for m, a, b in zip(puntos["min"], puntos["ml"], puntos["mv"])]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=puntos["min"], y=puntos["dif"].clip(lower=0), mode="lines", line=dict(shape="hv", width=0),
                             fill="tozeroy", fillcolor=color_l, opacity=0.8, name=p.local, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=puntos["min"], y=puntos["dif"].clip(upper=0), mode="lines", line=dict(shape="hv", width=0),
                             fill="tozeroy", fillcolor=color_v, opacity=0.8, name=p.visitante, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=puntos["min"], y=puntos["dif"], mode="lines", line=dict(shape="hv", color="#FFFFFF", width=1.5),
                             text=texto, hovertemplate="%{text}<br>Diferencia: %{y:+d}<extra></extra>", showlegend=False))
    duracion = inicio_periodo(int(eventos["period"].max()) + 1) / 60
    for per in range(1, int(eventos["period"].max())):
        fig.add_vline(x=inicio_periodo(per + 1) / 60, line_dash="dot", line_color="#555")
    maximo = max(5, int(puntos["dif"].abs().max()) + 2)
    fig.update_layout(
        height=380, plot_bgcolor="rgba(20, 20, 20, 0.85)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#D4D4D4"),
        xaxis=dict(title="Minuto", range=[0, duracion], gridcolor="rgba(255,255,255,0.05)", dtick=5),
        yaxis=dict(title=f"Diferencia ({p.local_corto} − {p.visitante_corto})", range=[-maximo, maximo],
                   gridcolor="rgba(255,255,255,0.05)", zerolinecolor="#A3A3A3"),
        legend=dict(orientation="h", y=1.1), margin=dict(l=60, r=20, t=30, b=50), hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ------------------------------------------------------------------ BOXSCORE
def estadisticas_jugadores(eventos, convocatorias, tramos, id_equipo, es_local):
    ev = eventos[eventos["id_equipo"] == id_equipo]
    jugadores = convocatorias[convocatorias["id_equipo"] == id_equipo].copy()
    extra = set(ev["id_jugador"].dropna().astype(int)) - set(jugadores["id_jugador"])
    if extra:  # jugadores que aparecen en el play by play pero no en la convocatoria
        conexion = conectar()
        nuevos = pd.read_sql(f"SELECT id_jugador, dorsal, nombre FROM jugadores WHERE id_jugador IN ({','.join(map(str, extra))})", conexion)
        conexion.close()
        jugadores = pd.concat([jugadores, nuevos.assign(id_equipo=id_equipo, titular=0)], ignore_index=True)

    col_pista, pts_pro, pts_con = ("pista_l", "pts_l", "pts_v") if es_local else ("pista_v", "pts_v", "pts_l")
    filas = []
    for j in jugadores.itertuples():
        e = ev[ev["id_jugador"] == j.id_jugador]
        cuenta = lambda codigos: int(e["idMove"].isin(codigos if isinstance(codigos, tuple) else (codigos,)).sum())
        en_pista = tramos[tramos[col_pista].apply(lambda s: j.id_jugador in s)]
        fila = {
            "id_jugador": j.id_jugador, "dorsal": j.dorsal, "nombre": j.nombre, "titular": bool(j.titular),
            "seg": float((en_pista["t1"] - en_pista["t0"]).sum()),
            "tlm": cuenta(TLM), "tla": cuenta(TLM + TLF), "t2m": cuenta(T2M), "t2a": cuenta(T2M + T2F),
            "t3m": cuenta(T3M), "t3a": cuenta(T3M + T3F), "fp": cuenta(FALTAS_COMETIDAS), "fr": cuenta(FR),
            "ast": cuenta(AS), "per": cuenta(PER), "rec": cuenta(REC), "tap": cuenta(TAP), "tap_rec": cuenta(TAP_RECIBIDO),
            "ro": cuenta(RO), "rd": cuenta(RD), "mas_menos": int((en_pista[pts_pro] - en_pista[pts_con]).sum()),
        }
        filas.append(fila)
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["pts"] = df["tlm"] + 2 * df["t2m"] + 3 * df["t3m"]
    df["rt"] = df["ro"] + df["rd"]
    # Valoración: positivos menos tiros fallados, pérdidas, faltas cometidas y tapones recibidos
    df["val"] = (df["pts"] + df["rt"] + df["ast"] + df["rec"] + df["tap"] + df["fr"]
                 - (df["t2a"] - df["t2m"]) - (df["t3a"] - df["t3m"]) - (df["tla"] - df["tlm"])
                 - df["per"] - df["fp"] - df["tap_rec"])
    df["dorsal_num"] = pd.to_numeric(df["dorsal"], errors="coerce")
    return df.sort_values(["dorsal_num", "nombre"]).reset_index(drop=True)


def totales_equipo(eventos, id_equipo, df_jug):
    """Totales del equipo: incluye las acciones sin jugador (rebotes de equipo, técnicas de banquillo...)."""
    ev = eventos[eventos["id_equipo"] == id_equipo]
    cuenta = lambda codigos: int(ev["idMove"].isin(codigos if isinstance(codigos, tuple) else (codigos,)).sum())
    t = {"tlm": cuenta(TLM), "tla": cuenta(TLM + TLF), "t2m": cuenta(T2M), "t2a": cuenta(T2M + T2F), "t3m": cuenta(T3M),
         "t3a": cuenta(T3M + T3F), "fp": cuenta(FALTAS_COMETIDAS + (540, 544)), "fr": cuenta(FR), "ast": cuenta(AS),
         "per": cuenta(PER), "rec": cuenta(REC), "tap": cuenta(TAP), "tap_rec": cuenta(TAP_RECIBIDO), "ro": cuenta(RO), "rd": cuenta(RD)}
    t["pts"] = t["tlm"] + 2 * t["t2m"] + 3 * t["t3m"]
    t["rt"] = t["ro"] + t["rd"]
    t["val"] = (t["pts"] + t["rt"] + t["ast"] + t["rec"] + t["tap"] + t["fr"] - (t["t2a"] - t["t2m"]) - (t["t3a"] - t["t3m"])
                - (t["tla"] - t["tlm"]) - t["per"] - t["fp"] - t["tap_rec"])
    t["seg"] = df_jug["seg"].sum() if not df_jug.empty else 0
    return t


def tiro(m, a):
    pct = f"{m / a * 100:.0f}%" if a else "-"
    return f"{m}/{a}<br><span style='color: #A3A3A3; font-size: 0.8rem;'>{pct}</span>"


def tabla_boxscore(df, totales, nombre, corto):
    st.markdown(f"<div style='display: flex; align-items: center; gap: 12px; margin-top: 25px;'>{escudo_html(corto, 40)}"
                f"<h4 style='margin: 0; color: #FFFFFF; text-transform: uppercase;'>{html.escape(nombre)}</h4></div>",
                unsafe_allow_html=True)
    definiciones = {
        "PTS": "Puntos", "MIN": "Minutos en pista", "TL": "Tiros libres anotados/intentados", "T2": "Tiros de 2 anotados/intentados",
        "T3": "Triples anotados/intentados", "FP": "Faltas personales cometidas", "FR": "Faltas recibidas", "AS": "Asistencias",
        "PER": "Pérdidas", "REC": "Recuperaciones", "TAP": "Tapones", "RO": "Rebotes ofensivos", "RD": "Rebotes defensivos",
        "RT": "Rebotes totales", "+/-": "Diferencia de puntos del equipo con el jugador en pista",
        "VAL": "Valoración: PTS + RT + AS + REC + TAP + FR − tiros fallados − PER − FP − tapones recibidos",
    }
    cabeceras = ["", "#", "Jugador"] + [tip(c, d) for c, d in definiciones.items()]
    filas = []
    for r in df.itertuples():
        jugo = r.seg > 0
        mm = f"{int(r.seg // 60)}:{int(r.seg % 60):02d}" if jugo else "0"
        color_mm = "#4ADE80" if r.mas_menos > 0 else ("#F87171" if r.mas_menos < 0 else "#FFFFFF")
        filas.append([
            "✓" if jugo else "", f"<b>{r.dorsal if pd.notna(r.dorsal) else '-'}</b>",
            f"<b>{html.escape(r.nombre)}</b>{' <span style=\"color: #F97316;\">★</span>' if r.titular else ''}",
            f"<b style='font-size: 1.05rem;'>{r.pts}</b>", mm, tiro(r.tlm, r.tla), tiro(r.t2m, r.t2a), tiro(r.t3m, r.t3a),
            r.fp, r.fr, r.ast, r.per, r.rec, r.tap, r.ro, r.rd, r.rt,
            f"<span style='color: {color_mm}; font-weight: bold;'>{r.mas_menos:+d}</span>" if jugo else "",
            f"<b>{r.val}</b>",
        ])
    t = totales
    filas.append(["", "", "<b>TOTAL</b>", f"<b>{t['pts']}</b>", f"{int(round(t['seg'] / 60))}", tiro(t["tlm"], t["tla"]),
                  tiro(t["t2m"], t["t2a"]), tiro(t["t3m"], t["t3a"]), t["fp"], t["fr"], t["ast"], t["per"], t["rec"],
                  t["tap"], t["ro"], t["rd"], t["rt"], "", f"<b>{t['val']}</b>"])
    tabla(cabeceras, filas, centrar_desde=3, desplazable=True)


def pestana_boxscore(p, eventos, convocatorias, tramos):
    st.caption("★ titular · ✓ ha jugado. Los totales incluyen las acciones del equipo sin jugador asignado "
               "(rebotes de equipo, técnicas al banquillo...).")
    for id_eq, nombre, corto, es_local in ((p.id_equipo_local, p.local, p.local_corto, True),
                                           (p.id_equipo_visitante, p.visitante, p.visitante_corto, False)):
        df = estadisticas_jugadores(eventos, convocatorias, tramos, id_eq, es_local)
        tabla_boxscore(df, totales_equipo(eventos, id_eq, df), nombre, corto)


# ------------------------------------------------------------------ ESTADÍSTICAS DE EQUIPO
def pestana_estadisticas(p, eventos):
    conteos = {}
    for id_eq in (p.id_equipo_local, p.id_equipo_visitante):
        ev = eventos[eventos["id_equipo"] == id_eq]
        conteos[id_eq] = pd.Series({k: int(ev["idMove"].isin(m).sum()) for k, m in CONTEOS.items()})
    minutos = inicio_periodo(int(eventos["period"].max()) + 1) / 60
    ind_l = _indicadores(conteos[p.id_equipo_local], conteos[p.id_equipo_visitante], minutos)
    ind_v = _indicadores(conteos[p.id_equipo_visitante], conteos[p.id_equipo_local], minutos)

    cab_equipo = lambda corto, nombre: (f"<div style='display: flex; align-items: center; justify-content: center; gap: 8px;'>"
                                        f"{escudo_html(corto, 26)}<span>{html.escape(nombre)}</span></div>")
    titulos = {"Posesiones": "Posesiones", "Tiro · Porcentajes": "Porcentajes de tiro",
               "Tiro · Distribución de tiro": "Distribución de tiro", "Rebote": "Rebote", "Cuidado de balón": "Cuidado de balón"}
    for titulo, indicadores in TABLAS_ESTADISTICA:
        subtitulo(titulos.get(titulo, titulo))
        filas = []
        for clave, nombre_ind, definicion, mayor_es_mejor in indicadores:
            vl, vv = ind_l[clave], ind_v[clave]
            formato = FORMATO_ESTADISTICA.get(clave, "{:.1f}%")
            texto = lambda v: "-" if pd.isna(v) else formato.format(v)
            # Se resalta el mejor valor (en los indicadores neutros no se resalta ninguno)
            mejor_l = mayor_es_mejor is not None and pd.notna(vl) and pd.notna(vv) and vl != vv and ((vl > vv) == mayor_es_mejor)
            mejor_v = mayor_es_mejor is not None and pd.notna(vl) and pd.notna(vv) and vl != vv and not mejor_l
            estilo = lambda mejor: "color: #4ADE80; font-weight: 800;" if mejor else ""
            filas.append([tip(nombre_ind, definicion),
                          f"<span style='{estilo(mejor_l)}'>{texto(vl)}</span>",
                          f"<span style='{estilo(mejor_v)}'>{texto(vv)}</span>"])
        tabla(["Estadística", cab_equipo(p.local_corto, p.local), cab_equipo(p.visitante_corto, p.visitante)], filas)


# ------------------------------------------------------------------ ROTACIÓN E IMPACTO
def stints(tramos, col_pista, pts_pro, pts_con, id_jugador):
    """Tramos seguidos con el jugador en pista y fuera de ella, con el +/- del equipo en cada uno."""
    resultado = []
    for r in tramos.itertuples():
        en_pista = id_jugador in getattr(r, col_pista)
        dif = getattr(r, pts_pro) - getattr(r, pts_con)
        if resultado and resultado[-1][2] == en_pista and resultado[-1][1] == r.t0:
            t0, _, _, acumulado = resultado[-1]
            resultado[-1] = (t0, r.t1, en_pista, acumulado + dif)
        else:
            resultado.append((r.t0, r.t1, en_pista, dif))
    return [s for s in resultado if s[1] > s[0]]


def grafico_rotacion(p, tramos, convocatorias, id_equipo, es_local, df_jug):
    col_pista, pts_pro, pts_con = ("pista_l", "pts_l", "pts_v") if es_local else ("pista_v", "pts_v", "pts_l")
    duracion = tramos["t1"].max()
    jugadores = df_jug[df_jug["seg"] > 0].sort_values("dorsal_num", ascending=False)  # el dorsal más bajo, arriba
    if jugadores.empty:
        st.info("Sin datos de rotación.")
        return
    etiquetas = {r.id_jugador: f"{r.dorsal} - {r.nombre}" for r in jugadores.itertuples()}

    # Colores según el signo del +/-: intensos en pista, suaves (barra fina) en el banquillo
    COLOR_PISTA = {1: "#16A34A", -1: "#DC2626", 0: "#737373"}
    COLOR_BANQUILLO = {1: "rgba(22,163,74,0.35)", -1: "rgba(220,38,38,0.35)", 0: "rgba(163,163,163,0.15)"}
    COLOR_TEXTO_BANQUILLO = {1: "#4ADE80", -1: "#F87171", 0: "#A3A3A3"}
    signo = lambda v: (v > 0) - (v < 0)

    barras = {fase: dict(x=[], base=[], y=[], text=[], color=[], datos=[]) for fase in ("on", "off")}
    etiquetas_banquillo = dict(x=[], y=[], text=[], color=[])
    for r in jugadores.itertuples():
        for t0, t1, en_pista, dif in stints(tramos, col_pista, pts_pro, pts_con, r.id_jugador):
            destino = barras["on" if en_pista else "off"]
            destino["x"].append((t1 - t0) / 60)
            destino["base"].append(t0 / 60)
            destino["y"].append(etiquetas[r.id_jugador])
            destino["datos"].append([t1 / 60, f"{dif:+d}"])
            if en_pista:
                destino["text"].append(f"{dif:+d}" if (t1 - t0) >= 60 else "")
                destino["color"].append(COLOR_PISTA[signo(dif)])
            else:
                destino["color"].append(COLOR_BANQUILLO[signo(dif)])
                # El texto del banquillo va aparte (una barra fina encogería la letra hasta hacerla ilegible)
                if t1 - t0 >= 60:
                    etiquetas_banquillo["x"].append((t0 + t1) / 120)
                    etiquetas_banquillo["y"].append(etiquetas[r.id_jugador])
                    etiquetas_banquillo["text"].append(f"<b>{dif:+d}</b>")
                    etiquetas_banquillo["color"].append(COLOR_TEXTO_BANQUILLO[signo(dif)])

    fig = go.Figure()
    fig.add_trace(go.Bar(orientation="h", x=barras["off"]["x"], base=barras["off"]["base"], y=barras["off"]["y"],
                         marker=dict(color=barras["off"]["color"], line=dict(width=0)), width=0.3, name="En el banquillo",
                         customdata=barras["off"]["datos"],
                         hovertemplate="Banquillo · %{base:.1f}' a %{customdata[0]:.1f}'<br>+/- %{customdata[1]}<extra></extra>"))
    fig.add_trace(go.Bar(orientation="h", x=barras["on"]["x"], base=barras["on"]["base"], y=barras["on"]["y"],
                         text=barras["on"]["text"], textposition="inside", insidetextanchor="middle",
                         marker=dict(color=barras["on"]["color"], line=dict(color="#0B0B0B", width=1)), width=0.75,
                         textfont=dict(color="#FFFFFF", size=11), textangle=0, name="En pista",
                         customdata=barras["on"]["datos"],
                         hovertemplate="En pista · %{base:.1f}' a %{customdata[0]:.1f}'<br>+/- %{customdata[1]}<extra></extra>"))
    fig.add_trace(go.Scatter(x=etiquetas_banquillo["x"], y=etiquetas_banquillo["y"], text=etiquetas_banquillo["text"],
                             mode="text", textfont=dict(color=etiquetas_banquillo["color"], size=12), hoverinfo="skip"))
    for per in range(1, int(round(duracion)) // 600 + 1):
        fig.add_vline(x=inicio_periodo(per + 1) / 60, line_dash="dot", line_color="#555")
    fig.update_layout(
        barmode="overlay", height=max(320, 42 * len(jugadores) + 90), showlegend=False,
        plot_bgcolor="rgba(20, 20, 20, 0.85)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#D4D4D4"),
        xaxis=dict(title="Minuto", range=[0, duracion / 60], dtick=5, gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(categoryorder="array", categoryarray=[etiquetas[i] for i in jugadores["id_jugador"]]),
        margin=dict(l=10, r=10, t=10, b=50),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Resumen de impacto: ratings del equipo con el jugador en pista (On) y en el banquillo (Off)
    propio, rival = ("_l", "_v") if es_local else ("_v", "_l")
    filas = []
    for r in jugadores.sort_values("dorsal_num").itertuples():
        en_pista = tramos[col_pista].apply(lambda s, j=r.id_jugador: j in s)
        on, off = ratings_tramos(tramos[en_pista], propio, rival), ratings_tramos(tramos[~en_pista], propio, rival)
        fila = [html.escape(etiquetas[r.id_jugador]), f"{int(r.seg // 60)}:{int(r.seg % 60):02d}"]
        for clave, mayor_es_mejor in (("ortg", True), ("drtg", False), ("netrtg", True)):
            v_on, v_off = on[clave], off[clave]
            formato = "{:+.1f}" if clave == "netrtg" else "{:.1f}"
            mejor = pd.notna(v_on) and pd.notna(v_off) and v_on != v_off and ((v_on > v_off) == mayor_es_mejor)
            peor = pd.notna(v_on) and pd.notna(v_off) and v_on != v_off and not mejor
            color = "#4ADE80" if mejor else ("#F87171" if peor else "#FFFFFF")
            fila += [f"<span style='color: {color}; font-weight: bold;'>{'-' if pd.isna(v_on) else formato.format(v_on)}</span>",
                     f"<span style='color: #D4D4D4;'>{'-' if pd.isna(v_off) else formato.format(v_off)}</span>"]
        filas.append(fila)
    definiciones = {
        "ORtg": "Offensive Rating: puntos anotados por el equipo por cada 100 posesiones",
        "DRtg": "Defensive Rating: puntos recibidos por el equipo por cada 100 posesiones (más bajo es mejor)",
        "Net": "Net Rating: Offensive Rating − Defensive Rating",
    }
    cabeceras = ["Jugador", "MIN"]
    for nombre_r, definicion in definiciones.items():
        cabeceras += [tip(f"{nombre_r}<br>On", f"{definicion}, con el jugador en pista."),
                      tip(f"{nombre_r}<br>Off", f"{definicion}, con el jugador en el banquillo.")]
    tabla(cabeceras, filas, desplazable=True)
    st.caption("On en verde si es mejor que Off, en rojo si es peor. Con pocos minutos en pista o en el banquillo, "
               "las posesiones son pocas y los ratings varían mucho.")


def ratings_tramos(tramos, propio, rival):
    """Offensive, Defensive y Net Rating del equipo en un conjunto de tramos."""
    if tramos.empty:
        return {"ortg": float("nan"), "drtg": float("nan"), "netrtg": float("nan")}
    s = tramos.sum(numeric_only=True)
    posesiones = lambda lado: s["fga" + lado] + 0.44 * s["fta" + lado] + s["tov" + lado] - s["oreb" + lado]
    pos = (posesiones(propio) + posesiones(rival)) / 2
    if pos <= 0:
        return {"ortg": float("nan"), "drtg": float("nan"), "netrtg": float("nan")}
    ortg, drtg = s["pts" + propio] / pos * 100, s["pts" + rival] / pos * 100
    return {"ortg": ortg, "drtg": drtg, "netrtg": ortg - drtg}


def pestana_rotacion(p, eventos, convocatorias, tramos):
    st.caption("Barras gruesas: tramos del jugador en pista. Barras finas: tramos en el banquillo. Cada una lleva el +/- "
               "del equipo en ese tramo, en verde si es positivo y en rojo si es negativo (gris si es 0).")
    for id_eq, nombre, corto, es_local in ((p.id_equipo_local, p.local, p.local_corto, True),
                                           (p.id_equipo_visitante, p.visitante, p.visitante_corto, False)):
        st.markdown(f"<div style='display: flex; align-items: center; gap: 12px; margin-top: 25px;'>{escudo_html(corto, 40)}"
                    f"<h4 style='margin: 0; color: #FFFFFF; text-transform: uppercase;'>{html.escape(nombre)}</h4></div>",
                    unsafe_allow_html=True)
        df = estadisticas_jugadores(eventos, convocatorias, tramos, id_eq, es_local)
        grafico_rotacion(p, tramos, convocatorias, id_eq, es_local, df)


# ------------------------------------------------------------------ QUINTETOS
def tabla_quintetos(tramos, convocatorias, id_equipo, es_local):
    col_pista = "pista_l" if es_local else "pista_v"
    propio, rival = ("_l", "_v") if es_local else ("_v", "_l")
    jugadores = convocatorias[convocatorias["id_equipo"] == id_equipo]
    dorsales = {int(r.id_jugador): r.dorsal for r in jugadores.itertuples()}

    def nombre_corto(id_jugador):
        # "13 CORRAL": dorsal y última palabra del nombre
        fila = jugadores[jugadores["id_jugador"] == id_jugador]
        apellido = fila["nombre"].iloc[0].split()[-1] if not fila.empty else str(id_jugador)
        return f"{dorsales.get(id_jugador, '-')} {apellido}"

    duracion = tramos["t1"] - tramos["t0"]
    # Solo quintetos completos con tiempo en pista (los de 4 jugadores son instantes de un cambio)
    validos = tramos[(tramos[col_pista].apply(len) == 5) & (duracion > 0)]
    segundos = validos.assign(seg=duracion).groupby(col_pista)["seg"].sum().sort_values(ascending=False)
    filas = []
    for quinteto, seg in segundos.items():
        en_pista = tramos[col_pista].apply(lambda s, q=quinteto: s == q)
        on, off = ratings_tramos(tramos[en_pista], propio, rival), ratings_tramos(tramos[~en_pista], propio, rival)
        orden = sorted(quinteto, key=lambda j: (int(dorsales[j]) if str(dorsales.get(j, "")).isdigit() else 999, j))
        fila = [f"<span style='font-size: 0.85rem;'>{html.escape(', '.join(nombre_corto(j) for j in orden))}</span>",
                f"{int(seg // 60)}:{int(seg % 60):02d}"]
        for clave, mayor_es_mejor in (("ortg", True), ("drtg", False), ("netrtg", True)):
            v_on, v_off = on[clave], off[clave]
            formato = "{:+.1f}" if clave == "netrtg" else "{:.1f}"
            mejor = pd.notna(v_on) and pd.notna(v_off) and v_on != v_off and ((v_on > v_off) == mayor_es_mejor)
            peor = pd.notna(v_on) and pd.notna(v_off) and v_on != v_off and not mejor
            color = "#4ADE80" if mejor else ("#F87171" if peor else "#FFFFFF")
            fila += [f"<span style='color: {color}; font-weight: bold;'>{'-' if pd.isna(v_on) else formato.format(v_on)}</span>",
                     f"<span style='color: #D4D4D4;'>{'-' if pd.isna(v_off) else formato.format(v_off)}</span>"]
        filas.append(fila)
    if not filas:
        st.info("Sin datos de quintetos.")
        return
    definiciones = {
        "ORtg": "Offensive Rating: puntos anotados por el equipo por cada 100 posesiones",
        "DRtg": "Defensive Rating: puntos recibidos por el equipo por cada 100 posesiones (más bajo es mejor)",
        "Net": "Net Rating: Offensive Rating − Defensive Rating",
    }
    cabeceras = ["Quinteto", "MIN"]
    for nombre_r, definicion in definiciones.items():
        cabeceras += [tip(f"{nombre_r}<br>On", f"{definicion}, con este quinteto en pista."),
                      tip(f"{nombre_r}<br>Off", f"{definicion}, con cualquier otro quinteto en pista.")]
    tabla(cabeceras, filas, desplazable=True)


def pestana_quintetos(p, convocatorias, tramos):
    st.caption("Todos los quintetos que han jugado, de más a menos minutos. On: con ese quinteto en pista; Off: con "
               "cualquier otro. On en verde si es mejor que Off y en rojo si es peor. Los quintetos con pocos minutos "
               "tienen pocas posesiones y sus ratings varían mucho.")
    for id_eq, nombre, corto, es_local in ((p.id_equipo_local, p.local, p.local_corto, True),
                                           (p.id_equipo_visitante, p.visitante, p.visitante_corto, False)):
        st.markdown(f"<div style='display: flex; align-items: center; gap: 12px; margin-top: 25px;'>{escudo_html(corto, 40)}"
                    f"<h4 style='margin: 0; color: #FFFFFF; text-transform: uppercase;'>{html.escape(nombre)}</h4></div>",
                    unsafe_allow_html=True)
        tabla_quintetos(tramos, convocatorias, id_eq, es_local)


# ------------------------------------------------------------------ ENTRADA
def mostrar_partidos():
    st.markdown("### 🗓️ Partidos")
    id_partido = st.session_state.get("partido_seleccionado")
    if id_partido is None:
        selector_partido()
        return

    partidos = cargar_partidos()
    fila = partidos[partidos["id_partido"] == id_partido]
    if fila.empty:
        st.session_state.partido_seleccionado = None
        st.rerun()
    p = fila.iloc[0]
    # Al volver, la lista se abre en la competición y la jornada de este partido
    competicion = "Liga" if p.es_liga else "Copa"
    st.session_state["partidos_competicion"] = competicion
    st.session_state[f"partidos_jornada_{competicion}"] = p.jornada
    if st.button("⬅️ Volver a la lista de partidos", key="volver_partidos"):
        st.session_state.partido_seleccionado = None
        st.rerun()

    eventos, convocatorias = cargar_partido(id_partido)
    cabecera_partido(p)
    if eventos.empty:
        st.info("Este partido no tiene play by play.")
        return
    tramos = intervalos_en_pista(eventos, convocatorias, p.id_equipo_local, p.id_equipo_visitante)

    tab_res, tab_box, tab_est, tab_rot, tab_qui = st.tabs(
        ["📋 Resumen", "📊 Boxscore", "📈 Estadísticas de equipo", "🔄 Rotación e Impacto", "🖐️ Quintetos"])
    with tab_res:
        pestana_resumen(p, eventos)
    with tab_box:
        pestana_boxscore(p, eventos, convocatorias, tramos)
    with tab_est:
        pestana_estadisticas(p, eventos)
    with tab_rot:
        pestana_rotacion(p, eventos, convocatorias, tramos)
    with tab_qui:
        pestana_quintetos(p, convocatorias, tramos)
