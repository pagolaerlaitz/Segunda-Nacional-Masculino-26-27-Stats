import math
from functools import lru_cache

import numpy as np

# Media cancha FIBA en metros: x de 0 a 15 (ancho), y de 0 (línea de fondo) a 14 (medio campo)
ARO = (7.5, 1.575)
COLOR_LINEAS = "#D4D4D4"


def _arco(cx, cy, r, ang_ini, ang_fin, n=60):
    angulos = np.linspace(ang_ini, ang_fin, n)
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angulos]


def _path(puntos):
    return "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in puntos)


@lru_cache(maxsize=1)
def _lineas():
    t0 = math.asin((6.75 ** 2 - 6.6 ** 2) ** 0.5 / 6.75)  # ángulo donde el arco de 6,75 m toca la recta de la esquina
    y_esquina = ARO[1] + 6.75 * math.sin(t0)
    triple = [(0.9, 0), (0.9, y_esquina)] + _arco(*ARO, 6.75, math.pi - t0, t0) + [(14.1, y_esquina), (14.1, 0)]
    semicirculo = [(6.25, 1.2), (6.25, ARO[1])] + _arco(*ARO, 1.25, math.pi, 0) + [(8.75, 1.2)]
    circulo_central = _arco(7.5, 14, 1.8, math.pi, 2 * math.pi)

    estilo = dict(color=COLOR_LINEAS, width=2)
    return (
        dict(type="rect", x0=0, y0=0, x1=15, y1=14, line=estilo),
        dict(type="rect", x0=5.05, y0=0, x1=9.95, y1=5.8, line=estilo),
        dict(type="circle", x0=5.7, y0=4.0, x1=9.3, y1=7.6, line=estilo),
        dict(type="path", path=_path(triple), line=estilo),
        dict(type="path", path=_path(semicirculo), line=estilo),
        dict(type="path", path=_path(circulo_central), line=estilo),
        dict(type="line", x0=6.6, y0=1.2, x1=8.4, y1=1.2, line=dict(color=COLOR_LINEAS, width=3)),
        dict(type="circle", x0=ARO[0] - 0.225, y0=ARO[1] - 0.225, x1=ARO[0] + 0.225, y1=ARO[1] + 0.225,
             line=dict(color="#F97316", width=2)),
    )


# ------------------------------------------------------------------ ZONAS DE TIRO
# 14 zonas: restringida, media distancia corta (MDC), media distancia larga (MDL) y triples.
R_RESTRINGIDA = 2.0     # radio de la zona restringida alrededor del aro
R_MEDIA_CORTA = 4.9     # radio que separa la media distancia corta de la larga
PINTURA = (5.05, 9.95, 5.8)  # x mínima, x máxima, y máxima de la zona
_T0 = math.degrees(math.asin((6.75 ** 2 - 6.6 ** 2) ** 0.5 / 6.75))  # ángulo donde el arco toca la recta de la esquina
Y_ESQUINA = ARO[1] + 6.75 * math.sin(math.radians(_T0))
Y_MAX_ZONAS = 10.5      # hasta dónde se dibuja la cancha en la carta por zonas

ZONAS_TIRO = [
    "Restringida", "MDC Central", "MDC Izq", "MDC Dcha",
    "MDL Esq Izq", "MDL Codo Izq", "MDL Central", "MDL Codo Dcha", "MDL Esq Dcha",
    "Esq Izq", "Ala Izq", "Top", "Ala Dcha", "Esq Dcha",
]
ZONAS_TRIPLE = {"Esq Izq", "Ala Izq", "Top", "Ala Dcha", "Esq Dcha"}
# Dónde se escribe el resultado de cada zona
POSICION_ETIQUETA = {
    "Restringida": (7.5, 1.0), "MDC Central": (7.5, 4.5), "MDC Izq": (3.7, 2.4), "MDC Dcha": (11.3, 2.4),
    "MDL Esq Izq": (1.9, 1.2), "MDL Codo Izq": (3.6, 6.1), "MDL Central": (7.5, 7.3),
    "MDL Codo Dcha": (11.4, 6.1), "MDL Esq Dcha": (13.1, 1.2),
    "Esq Izq": (0.45, 1.4), "Ala Izq": (1.9, 8.3), "Top": (7.5, 9.4), "Ala Dcha": (13.1, 8.3), "Esq Dcha": (14.55, 1.4),
}
# Rayos (en grados, 0 = hacia la derecha) que separan las zonas de media distancia larga y de triple
_RAYOS_MDL = (30, 70, 110, 150)
_RAYOS_TRIPLE = (70, 110)


def _angulo(x, y):
    a = math.degrees(math.atan2(y - ARO[1], x - ARO[0]))
    if a < 0:  # por debajo de la altura del aro: se toma la línea de fondo de su lado
        a = 0.0 if x >= ARO[0] else 180.0
    return a


def zona_de_tiro(x, y, es_triple):
    """Zona de un tiro según su posición (metros) y si fue de 3 puntos."""
    a = _angulo(x, y)
    if es_triple:
        if y <= Y_ESQUINA:
            return "Esq Izq" if x < ARO[0] else "Esq Dcha"
        return "Ala Izq" if a >= _RAYOS_TRIPLE[1] else ("Ala Dcha" if a <= _RAYOS_TRIPLE[0] else "Top")
    d = math.hypot(x - ARO[0], y - ARO[1])
    if d < R_RESTRINGIDA:
        return "Restringida"
    if PINTURA[0] <= x <= PINTURA[1] and y <= PINTURA[2]:
        return "MDC Central"
    if d < R_MEDIA_CORTA:
        return "MDC Izq" if x < ARO[0] else "MDC Dcha"
    if a < _RAYOS_MDL[0]:
        return "MDL Esq Dcha"
    if a < _RAYOS_MDL[1]:
        return "MDL Codo Dcha"
    if a <= _RAYOS_MDL[2]:
        return "MDL Central"
    if a <= _RAYOS_MDL[3]:
        return "MDL Codo Izq"
    return "MDL Esq Izq"


def _punto_linea_triple(a):
    """Punto de la línea de 3 en la dirección `a` (grados) desde el aro."""
    if _T0 <= a <= 180 - _T0:
        return ARO[0] + 6.75 * math.cos(math.radians(a)), ARO[1] + 6.75 * math.sin(math.radians(a))
    x = 14.1 if a < 90 else 0.9
    return x, ARO[1] + (x - ARO[0]) * math.tan(math.radians(a))


def _linea_triple(a1, a2, n=40):
    return [_punto_linea_triple(a) for a in np.linspace(a1, a2, n)]


def _rayo_arriba(a):
    return ARO[0] + (Y_MAX_ZONAS - ARO[1]) / math.tan(math.radians(a)), Y_MAX_ZONAS


def _arco_grados(r, a1, a2, n=60):
    return _arco(ARO[0], ARO[1], r, math.radians(a1), math.radians(a2), n)


@lru_cache(maxsize=1)
def _poligonos_zonas():
    aro = [ARO]
    abajo_rc = math.degrees(math.asin(ARO[1] / R_RESTRINGIDA))  # ángulo donde cada círculo corta la línea de fondo
    abajo_mc = math.degrees(math.asin(ARO[1] / R_MEDIA_CORTA))
    x_mc = math.sqrt(R_MEDIA_CORTA ** 2 - ARO[1] ** 2)
    # Orden de dibujo: de las zonas grandes a las pequeñas (cada una tapa a la anterior donde se solapan)
    return (
        ("Ala Izq", aro + [(0, Y_ESQUINA), (0, Y_MAX_ZONAS), _rayo_arriba(_RAYOS_TRIPLE[1])]),
        ("Top", aro + [_rayo_arriba(_RAYOS_TRIPLE[1]), _rayo_arriba(_RAYOS_TRIPLE[0])]),
        ("Ala Dcha", aro + [_rayo_arriba(_RAYOS_TRIPLE[0]), (15, Y_MAX_ZONAS), (15, Y_ESQUINA)]),
        ("Esq Izq", [(0, 0), (0.9, 0), (0.9, Y_ESQUINA), (0, Y_ESQUINA)]),
        ("Esq Dcha", [(14.1, 0), (15, 0), (15, Y_ESQUINA), (14.1, Y_ESQUINA)]),
        ("MDL Esq Dcha", [(ARO[0], 0), (14.1, 0)] + _linea_triple(0, _RAYOS_MDL[0]) + aro),
        ("MDL Codo Dcha", aro + _linea_triple(_RAYOS_MDL[0], _RAYOS_MDL[1])),
        ("MDL Central", aro + _linea_triple(_RAYOS_MDL[1], _RAYOS_MDL[2])),
        ("MDL Codo Izq", aro + _linea_triple(_RAYOS_MDL[2], _RAYOS_MDL[3])),
        ("MDL Esq Izq", aro + _linea_triple(_RAYOS_MDL[3], 180) + [(0.9, 0), (ARO[0], 0)]),
        ("MDC Dcha", [(ARO[0], 0), (ARO[0] + x_mc, 0)] + _arco_grados(R_MEDIA_CORTA, -abajo_mc, 90)),
        ("MDC Izq", [(ARO[0], 0), (ARO[0], ARO[1] + R_MEDIA_CORTA)]
         + _arco_grados(R_MEDIA_CORTA, 90, 180 + abajo_mc)),
        ("MDC Central", [(PINTURA[0], 0), (PINTURA[1], 0), (PINTURA[1], PINTURA[2]), (PINTURA[0], PINTURA[2])]),
        ("Restringida", _arco_grados(R_RESTRINGIDA, -abajo_rc, 180 + abajo_rc)),
    )


def svg_zonas(colores):
    """Polígonos SVG de las zonas (coordenadas en metros, para un grupo con el eje y invertido).
    Cada polígono lleva data-zona para poder resaltarlo desde la tabla."""
    elementos = []
    for nombre, puntos in _poligonos_zonas():
        pts = " ".join(f"{x:.3f},{y:.3f}" for x, y in puntos)
        elementos.append(f'<polygon class="zona" data-zona="{nombre}" points="{pts}" '
                         f'fill="{colores.get(nombre, "none")}"/>')
    return "\n".join(elementos)


def svg_lineas(color=COLOR_LINEAS):
    """Líneas de la cancha en SVG (metros, para un grupo con el eje y invertido)."""
    elementos = []
    for s in _lineas():
        c = color if s["line"]["color"] == COLOR_LINEAS else s["line"]["color"]  # el aro mantiene su naranja
        trazo = (f'fill="none" stroke="{c}" stroke-width="{s["line"]["width"]}" '
                 'vector-effect="non-scaling-stroke"')
        if s["type"] == "rect":
            elementos.append(f'<rect x="{s["x0"]}" y="{s["y0"]}" width="{s["x1"] - s["x0"]}" '
                             f'height="{s["y1"] - s["y0"]}" {trazo}/>')
        elif s["type"] == "circle":
            cx, cy = (s["x0"] + s["x1"]) / 2, (s["y0"] + s["y1"]) / 2
            elementos.append(f'<circle cx="{cx}" cy="{cy}" r="{(s["x1"] - s["x0"]) / 2}" {trazo}/>')
        elif s["type"] == "line":
            elementos.append(f'<line x1="{s["x0"]}" y1="{s["y0"]}" x2="{s["x1"]}" y2="{s["y1"]}" {trazo}/>')
        elif s["type"] == "path":
            elementos.append(f'<path d="{s["path"]}" {trazo}/>')
    return "\n".join(elementos)


def lineas_cancha():
    """Líneas de la cancha como shapes de plotly (copias nuevas, para que plotly pueda modificarlas)."""
    return [dict(s) for s in _lineas()]


def layout_cancha(fig, height=520):
    """Aplica a una figura de plotly los ejes, el fondo y las líneas de la media cancha."""
    fig.update_layout(
        shapes=lineas_cancha(),
        xaxis=dict(range=[-0.3, 15.3], visible=False, fixedrange=True),
        yaxis=dict(range=[-0.3, 14.3], visible=False, fixedrange=True, scaleanchor="x", scaleratio=1),
        plot_bgcolor="#141414", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0), height=height,
    )
    return fig
