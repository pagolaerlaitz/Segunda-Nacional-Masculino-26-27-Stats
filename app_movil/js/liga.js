// Vistas de la liga: clasificación, partidos, equipos (stats, individuales, cuartos, plantilla), jugador y rankings.
import { estado } from "./estado.js";
import {
  META, barra, cabStat, cargar, chips, claseComparada, clasePercentil, cortoEquipo, entero, esc, escudo, foto,
  formatoPython, jugador, media, minutos, nombreEquipo, nombreJugador, nota, num, ordenDorsal, pct, pestanas, selector, signo,
  tabla, titulo, vacio, valorStat,
} from "./base.js";
import { burbujas, cartaTiro, dispersion, radar, rotacion, usoEficiencia } from "./graficos.js";
import { calcularOnOff, htmlOnOff } from "./onoff.js";

// ---------- Utilidades compartidas con la sección del Atlético ----------
const DEF_RATING = {
  ORtg: "Offensive Rating: puntos anotados por cada 100 posesiones",
  DRtg: "Defensive Rating: puntos recibidos por cada 100 posesiones (más bajo es mejor)",
  Net: "Net Rating: Offensive Rating − Defensive Rating",
};

// Cabeceras y celdas de ratings On / Off (On en verde si es mejor que Off)
export function cabecerasOnOff(sujeto) {
  return Object.entries(DEF_RATING).flatMap(([nombre, def]) => [
    { t: `${nombre} On`, def: `${def}, con ${sujeto} en pista.` }, { t: "Off", def: `${def}, sin ${sujeto} en pista.` }]);
}

export function celdasOnOff(on, off) {
  return [["ortg", true], ["drtg", false], ["netrtg", true]].flatMap(([clave, mayor]) => {
    const vOn = on?.[clave], vOff = off?.[clave];
    const comparable = !vacio(vOn) && !vacio(vOff) && vOn !== vOff;
    const clase = comparable ? (((vOn > vOff) === mayor) ? "verde" : "rojo") : "";
    const f = (v) => (clave === "netrtg" ? signo(v) : num(v));
    return [`<span class="${clase}">${f(vOn)}</span>`, `<span class="neutro">${f(vOff)}</span>`];
  });
}

// Selector de jugadores (hasta 5) con chips que se activan y desactivan
export function chipsJugadores(clave, ids, elegidos, maximo = 5) {
  return `<div class="chips" style="flex-wrap:wrap">${ids.map((id) => {
    const activo = elegidos.includes(id);
    const nuevos = activo ? elegidos.filter((j) => j !== id) : (elegidos.length < maximo ? [...elegidos, id] : elegidos);
    const j = jugador(id);
    return `<button class="chip${activo ? " activa" : ""}" data-chip="${clave}" data-valor="${nuevos.join(",")}">${esc(j.dorsal || "-")} ${esc(j.nombre.split(" ").at(-1))}</button>`;
  }).join("")}</div>`;
}

export const elegidosDe = (clave) => String(estado(clave, "")).split(",").filter(Boolean).map(Number);

// Controles de la carta de tiro (acierto / frecuencia, % / PPT, ver tiros)
export function controlesCarta(prefijo) {
  const modo = estado(`${prefijo}_modo`, "Acierto", ["Acierto", "Frecuencia"]);
  const medida = estado(`${prefijo}_medida`, "%", ["%", "PPT"]);
  const verTiros = estado(`${prefijo}_ver`, "no", ["si", "no"]) === "si";
  let html = chips(`${prefijo}_modo`, [["Acierto", "Acierto"], ["Frecuencia", "Frecuencia"]], modo);
  html += `<div class="chips">${modo === "Acierto" ? [["%", "%"], ["PPT", "PPT (puntos por tiro)"]].map(([v, t]) =>
    `<button class="chip${medida === v ? " activa" : ""}" data-chip="${prefijo}_medida" data-valor="${v}">${t}</button>`).join("") : ""}
    <button class="chip${verTiros ? " activa" : ""}" data-chip="${prefijo}_ver" data-valor="${verTiros ? "no" : "si"}">Ver tiros</button></div>`;
  return { html, opciones: { modo, medida, verTiros } };
}

// Playtypes o sistemas de las posesiones que finaliza un jugador, comparados con el PPP del equipo
export function htmlAnalisisJugador(d, columna, etiqueta) {
  const datos = d[columna];
  if (!datos?.filas.length) return `<div class="vacio">Sin posesiones etiquetadas.</div>`;
  let html = nota(`Posesiones que finaliza el jugador: ${d.n} · ${num(d.ppp, 2)} PPP. El color compara con el PPP del equipo en cada ${etiqueta.toLowerCase()}.`);
  html += tabla([etiqueta, { t: "Pos.", def: "Finales de posesión etiquetados." }, { t: "Frec.", def: "Porcentaje de sus posesiones." },
    { t: "PPP", def: "Puntos por posesión." }, { t: "PPP eq.", def: `PPP de todo el equipo en ese ${etiqueta.toLowerCase()}.` }],
  datos.filas.map((f) => {
    const ref = datos.equipo[f.g];
    return [esc(f.g), f.n, barra(f.f), `<span class="${claseComparada(f.ppp, ref, true, 0.1)}">${num(f.ppp, 2)}</span>`, num(ref, 2)];
  }));
  return html + burbujas(datos.filas, d.ppp);
}

// ====================================================================== CLASIFICACIÓN
export async function clasificacion() {
  const filas = await cargar("clasificacion.json");
  const html = tabla(
    ["Equipo", { t: "Pts", def: "Puntos de clasificación: 2 por victoria y 1 por derrota." },
      { t: "PJ", def: "Partidos jugados" }, { t: "V", def: "Victorias" }, { t: "D", def: "Derrotas" },
      { t: "PF", def: "Puntos a favor" }, { t: "PC", def: "Puntos en contra" },
      { t: "Dif.", def: "Diferencial de puntos (a favor − en contra)" }],
    filas.map((r) => ({
      celdas: [
        `<span class="equipo-celda"><span class="pos">${r.pos}</span>${escudo(r.id, 26)}<span>${esc(nombreEquipo(r.id))}</span></span>`,
        `<b>${r.pts}</b>`, r.pj, r.v, r.d, r.pf, r.pc,
        `<span class="${r.dif > 0 ? "verde" : r.dif < 0 ? "rojo" : ""}">${signo(r.dif, 0)}</span>`],
      clase: r.id === META.id_propio ? "destacada" : "",
      ir: `#/equipo/${r.id}`,
    })), "clasif");
  return { titulo: "Clasificación", html: html + nota("Victoria 2 puntos, derrota 1. Desempate: diferencial de puntos y enfrentamientos directos. Toca un equipo para ver su ficha.") };
}

// ====================================================================== PARTIDOS
function jornadas(lista, liga) {
  const vistas = new Map();
  lista.filter((p) => p.liga === liga).forEach((p) => {
    const actual = vistas.get(p.jornada);
    if (!actual || String(p.orden[1]) < String(actual[1])) vistas.set(p.jornada, p.orden);
  });
  return [...vistas.entries()].sort((a, b) => (a[1][0] - b[1][0]) || String(a[1][1]).localeCompare(String(b[1][1]))).map(([j]) => j);
}

function tarjetaPartido(p) {
  const jugado = !vacio(p.pl) && !vacio(p.pv);
  const ganaL = jugado && p.pl > p.pv;
  const ganaV = jugado && p.pv > p.pl;
  const propio = p.local === META.id_propio || p.visitante === META.id_propio;
  const contenido = `
    <div class="lado">${escudo(p.local, 32)}<span class="nombre">${esc(cortoEquipo(p.local))}</span></div>
    <div><div class="marcador">${jugado ? `<span class="${ganaL ? "ganador" : ""}">${p.pl}</span> - <span class="${ganaV ? "ganador" : ""}">${p.pv}</span>` : "vs"}</div>
      <div class="fecha">${esc(p.fecha)}</div></div>
    <div class="lado derecha">${escudo(p.visitante, 32)}<span class="nombre">${esc(cortoEquipo(p.visitante))}</span></div>`;
  return p.detalle
    ? `<a class="partido${propio ? " propio" : ""}" href="#/partido/${p.id}">${contenido}</a>`
    : `<div class="partido${propio ? " propio" : ""}">${contenido}</div>`;
}

export async function partidos() {
  const lista = await cargar("partidos.json");
  const hayCopa = lista.some((p) => !p.liga);
  const competicion = estado("competicion", "Liga", ["Liga", "Copa"]);
  const liga = competicion === "Liga";
  const disponibles = jornadas(lista, liga);
  // Por defecto, la última jornada con algún resultado
  const jugadas = disponibles.filter((j) => lista.some((p) => p.jornada === j && !vacio(p.pl)));
  const jornada = estado(`jornada_${competicion}`, jugadas.at(-1) ?? disponibles[0], disponibles);
  const delDia = lista.filter((p) => p.jornada === jornada && p.liga === liga)
    .sort((a, b) => String(a.fecha_iso).localeCompare(String(b.fecha_iso)));

  let html = hayCopa ? chips("competicion", [["Liga", "Liga"], ["Copa", "Copa"]], competicion) : "";
  html += selector(`jornada_${competicion}`, disponibles.map((j) => [j, liga ? `Jornada ${j}` : j]), jornada);
  html += delDia.map(tarjetaPartido).join("") || `<div class="vacio">Sin partidos.</div>`;
  return { titulo: "Partidos", html };
}

// Evolución de la diferencia en el marcador (local − visitante)
function graficoMarcador(datos, colorL, colorV) {
  const ancho = 400, alto = 200, mx = 30, my = 12;
  const puntos = datos.marcador;
  const duracion = datos.duracion;
  const maximo = Math.max(5, ...puntos.map(([, a, b]) => Math.abs(a - b))) + 2;
  const x = (t) => mx + (t / duracion) * (ancho - mx - 8);
  const y = (d) => my + ((maximo - d) / (2 * maximo)) * (alto - 2 * my);
  let linea = `M ${x(0)} ${y(0)}`;
  let anterior = 0;
  for (const [t, a, b] of puntos.slice(1)) {
    linea += ` L ${x(t)} ${y(anterior)} L ${x(t)} ${y(a - b)}`;
    anterior = a - b;
  }
  linea += ` L ${x(duracion)} ${y(anterior)}`;
  const area = `${linea} L ${x(duracion)} ${y(0)} L ${x(0)} ${y(0)} Z`;
  const cero = y(0);
  let marcas = "";
  for (let t = 600; t < duracion; t += t < 2400 ? 600 : 300) {
    marcas += `<line x1="${x(t)}" x2="${x(t)}" y1="${my}" y2="${alto - my}" stroke="#444" stroke-dasharray="3 3"/>`;
  }
  const etiquetas = [maximo - 2, 0, -(maximo - 2)].map((d) =>
    `<text x="${mx - 6}" y="${y(d) + 4}" text-anchor="end" fill="#737373" font-size="11">${d > 0 ? "+" : ""}${d}</text>`).join("");
  return `<svg class="grafico" viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Evolución del marcador">
    <defs><clipPath id="arriba"><rect x="0" y="0" width="${ancho}" height="${cero}"/></clipPath>
      <clipPath id="abajo"><rect x="0" y="${cero}" width="${ancho}" height="${alto - cero}"/></clipPath></defs>
    ${marcas}
    <path d="${area}" fill="${colorL}" opacity="0.8" clip-path="url(#arriba)"/>
    <path d="${area}" fill="${colorV}" opacity="0.8" clip-path="url(#abajo)"/>
    <line x1="${mx}" x2="${ancho - 8}" y1="${cero}" y2="${cero}" stroke="#A3A3A3"/>
    <path d="${linea}" fill="none" stroke="#FFFFFF" stroke-width="1.5"/>
    ${etiquetas}
  </svg>`;
}

const COLUMNAS_BOX = [
  ["PTS", "Puntos"], ["MIN", "Minutos en pista"], ["TL", "Tiros libres anotados/intentados"],
  ["T2", "Tiros de 2 anotados/intentados"], ["T3", "Triples anotados/intentados"], ["FP", "Faltas personales cometidas"],
  ["FR", "Faltas recibidas"], ["AS", "Asistencias"], ["PER", "Pérdidas"], ["REC", "Recuperaciones"], ["TAP", "Tapones"],
  ["RO", "Rebotes ofensivos"], ["RD", "Rebotes defensivos"], ["RT", "Rebotes totales"],
  ["+/-", "Diferencia de puntos del equipo con el jugador en pista"],
  ["VAL", "Valoración: PTS + RT + AS + REC + TAP + FR − tiros fallados − PER − FP − tapones recibidos"],
];

const tiro = (m, a) => `${m}/${a}<span class="sub">${a ? Math.round((m / a) * 100) + "%" : "-"}</span>`;

function filaBox(r, total = false) {
  const jugo = total || r.seg > 0;
  const nombre = total ? "TOTAL" : `${esc(r.dorsal ?? "-")} · ${esc(r.nombre)}${r.titular ? ' <span class="naranja">★</span>' : ""}`;
  return {
    celdas: [nombre, `<b>${r.pts}</b>`, total ? Math.round(r.seg / 60) : (jugo ? minutos(r.seg) : "0"),
      tiro(r.tlm, r.tla), tiro(r.t2m, r.t2a), tiro(r.t3m, r.t3a), r.fp, r.fr, r.ast, r.per, r.rec, r.tap, r.ro, r.rd, r.rt,
      total || !jugo ? "" : `<span class="${r.mm > 0 ? "verde" : r.mm < 0 ? "rojo" : ""}">${signo(r.mm, 0)}</span>`,
      `<b>${r.val}</b>`],
    clase: total ? "total" : "",
  };
}

export async function partido(id, pestana = "resumen") {
  const [lista, datos] = await Promise.all([cargar("partidos.json"), cargar(`partidos/${id}.json`)]);
  const p = lista.find((x) => x.id === id);
  const colorL = META.equipos[p.local]?.color ?? "#F97316";
  let colorV = META.equipos[p.visitante]?.color ?? "#A3A3A3";
  if (colorV.toUpperCase() === colorL.toUpperCase()) colorV = "#A3A3A3";

  let html = `<div class="tarjeta cabecera-partido">
    <div class="nota">${p.liga ? `Jornada ${esc(p.jornada)}` : esc(p.jornada)} · ${esc(p.fecha)}</div>
    <div class="equipos">
      <a class="equipo" href="#/equipo/${p.local}">${escudo(p.local, 52)}<span>${esc(nombreEquipo(p.local))}</span></a>
      <div class="resultado">${entero(p.pl)} - ${entero(p.pv)}</div>
      <a class="equipo" href="#/equipo/${p.visitante}">${escudo(p.visitante, 52)}<span>${esc(nombreEquipo(p.visitante))}</span></a>
    </div></div>`;
  html += pestanas([["resumen", "Resumen"], ["boxscore", "Boxscore"], ["estadisticas", "Estadísticas"],
    ["rotacion", "Rotación"], ["quintetos", "Quintetos"]], pestana, `#/partido/${id}`);

  if (pestana === "rotacion" || pestana === "quintetos") {
    const lado = estado("box_lado", "local", ["local", "visitante"]);
    html += chips("box_lado", [["local", esc(cortoEquipo(p.local))], ["visitante", esc(cortoEquipo(p.visitante))]], lado);
    if (pestana === "rotacion") {
      const filas = datos.rotacion[lado];
      html += nota("Barras gruesas: tramos en pista. Finas: en el banquillo. Cada tramo lleva el +/- del equipo (verde positivo, rojo negativo). Toca una barra para ver el detalle.");
      html += rotacion(filas, datos.duracion);
      html += titulo("Ratings On / Off");
      html += tabla(["Jugador", "MIN", ...cabecerasOnOff("el jugador")], filas.map((f) => ({
        celdas: [esc(f.etiqueta), minutos(f.seg), ...celdasOnOff(f.on, f.off)], ir: `#/jugador/${f.id}` })));
      html += nota("Con pocos minutos en pista o en el banquillo hay pocas posesiones y los ratings varían mucho.");
    } else {
      html += nota("Todos los quintetos que han jugado, de más a menos minutos. On: con ese quinteto; Off: con cualquier otro.");
      html += tabla(["Quinteto", "MIN", ...cabecerasOnOff("este quinteto")], datos.quintetos[lado].map((q) =>
        [`<span style="white-space:normal;font-size:0.75rem">${esc(q.etiqueta)}</span>`, minutos(q.seg), ...celdasOnOff(q.on, q.off)]));
    }
  } else if (pestana === "boxscore") {
    const lado = estado("box_lado", "local", ["local", "visitante"]);
    html += chips("box_lado", [["local", esc(cortoEquipo(p.local))], ["visitante", esc(cortoEquipo(p.visitante))]], lado);
    const box = datos.boxscore[lado];
    html += tabla(["Jugador", ...COLUMNAS_BOX.map(([t, def]) => ({ t, def }))],
      [...box.jugadores.map((r) => filaBox(r)), filaBox(box.totales, true)]);
    html += nota("★ titular. Los totales incluyen las acciones del equipo sin jugador (rebotes de equipo, técnicas al banquillo...).");
  } else if (pestana === "estadisticas") {
    for (const grupo of META.tablas_estadistica) {
      html += titulo(grupo.titulo.replace("Tiro · ", ""));
      html += tabla(["Estadística", esc(cortoEquipo(p.local)), esc(cortoEquipo(p.visitante))], grupo.indicadores.map((ind) => {
        const vl = datos.estadisticas.local[ind.clave];
        const vv = datos.estadisticas.visitante[ind.clave];
        const comparable = ind.mejor !== null && !vacio(vl) && !vacio(vv) && vl !== vv;
        const mejorL = comparable && (vl > vv) === ind.mejor;
        const mejorV = comparable && !mejorL;
        return [esc(ind.nombre),
          `<span class="${mejorL ? "verde" : ""}">${formatoPython(vl, ind.formato)}</span>`,
          `<span class="${mejorV ? "verde" : ""}">${formatoPython(vv, ind.formato)}</span>`];
      }));
    }
  } else {
    const { periodos, local, visitante } = datos.parciales;
    html += titulo("Parciales");
    html += tabla(["Equipo", ...periodos, "Total"], [
      [`<span class="equipo-celda">${escudo(p.local, 22)}${esc(cortoEquipo(p.local))}</span>`, ...local, `<b>${entero(p.pl)}</b>`],
      [`<span class="equipo-celda">${escudo(p.visitante, 22)}${esc(cortoEquipo(p.visitante))}</span>`, ...visitante, `<b>${entero(p.pv)}</b>`],
    ]);
    const d = datos.datos;
    html += titulo("Evolución del marcador");
    html += `<div class="cifras">
      <div><div class="valor">${d.empates}</div><div class="etiqueta">Empates</div></div>
      <div><div class="valor"><span style="color:${colorL}">${d.ventaja_l}</span><span style="color:#555"> | </span><span style="color:${colorV}">${d.ventaja_v}</span></div><div class="etiqueta">Mayor ventaja</div></div>
      <div><div class="valor">${d.cambios}</div><div class="etiqueta">Cambios de ganador</div></div></div>`;
    html += graficoMarcador(datos, colorL, colorV);
    html += `<div class="leyenda"><span><i style="background:${colorL}"></i>${esc(cortoEquipo(p.local))} por delante</span><span><i style="background:${colorV}"></i>${esc(cortoEquipo(p.visitante))} por delante</span></div>`;
  }
  return { titulo: `${cortoEquipo(p.local)} - ${cortoEquipo(p.visitante)}`, html, volver: true };
}

// ====================================================================== EQUIPOS
export async function equipos() {
  const html = `<div class="rejilla">${META.lista_equipos.slice().sort((a, b) => a.nombre.localeCompare(b.nombre)).map((e) =>
    `<a class="tarjeta-equipo" href="#/equipo/${e.id}">${escudo(e.id, 56)}<span class="nombre">${esc(e.nombre)}</span></a>`).join("")}</div>`;
  return { titulo: "Equipos", html };
}

// Estadística de equipo (ataque / defensa) con la posición en la liga
export function htmlEstadistica(datos, nombre = "el equipo") {
  if (!datos.estadistica?.ataque) return `<div class="vacio">Sin estadísticas del equipo.</div>`;
  const fase = estado("eq_fase", "ataque", ["ataque", "defensa"]);
  let html = chips("eq_fase", [["ataque", "⚔️ Ataque"], ["defensa", "🛡️ Defensa"]], fase);
  html += nota(fase === "ataque" ? `Estadísticas de ${esc(nombre)} (play by play de la federación). Pos.: posición en la liga.`
    : `Los mismos indicadores, pero de los rivales contra ${esc(nombre)}. La posición premia que los rivales tengan valores bajos.`);
  for (const grupo of META.tablas_estadistica) {
    html += titulo(grupo.titulo.replace("Tiro · ", ""));
    html += tabla(["Estadística", "Valor", { t: "Pos.", def: "Posición en la liga (1º = mejor). En los indicadores neutros, 1º = valor más alto." }],
      grupo.indicadores.map((ind) => {
        const [valor, posicion] = datos.estadistica[fase][ind.clave];
        const neutro = ind.mejor === null;
        const pos = vacio(posicion) ? "-" : `<span class="${!neutro && posicion === 1 ? "verde" : ""}">${posicion}º${!neutro && posicion === 1 ? " ⭐" : ""}</span>`;
        return [esc(ind.nombre), `<b>${formatoPython(valor, ind.formato)}</b>`, pos];
      }));
  }
  return html + nota("Toca el nombre de una columna para ver su definición.");
}

function htmlIndividuales(datos) {
  const tablas = META.tablas_individuales;
  const categoria = estado("indiv_cat", tablas[1].titulo, tablas.map((t) => t.titulo));
  const config = tablas.find((t) => t.titulo === categoria);
  let html = chips("indiv_cat", tablas.map((t) => [t.titulo, t.titulo]), categoria);
  html += nota("Entre paréntesis, el percentil en la liga. Colores: <span class='pct-rojo'>0-25</span> · <span class='pct-naranja'>25-50</span> · <span class='pct-amarillo'>50-75</span> · <span class='pct-verde'>75-95</span> · <span class='pct-verde-oscuro'>95-100</span>. El rating va de 0 a 10.");
  const orden = config.rating ?? "% Minutos";
  const filas = datos.individuales.slice().sort((a, b) => (config.rating ? (b.r[orden] ?? -1) - (a.r[orden] ?? -1) : (b.v[orden][0] ?? -1) - (a.v[orden][0] ?? -1)));
  const cabeceras = ["Jugador", ...(config.rating ? [cabStat(config.rating, true, "Rating")] : []), ...config.columnas.map(([c]) => cabStat(c))];
  html += tabla(cabeceras, filas.map((f) => ({
    celdas: [esc(nombreJugador(f.id)),
      ...(config.rating ? [`<span class="estrellas">${num(f.r[config.rating])}</span>`] : []),
      ...config.columnas.map(([c, esPct]) => {
        const [v, p] = f.v[c];
        if (vacio(v) || vacio(p)) return "-";
        return `<span class="${clasePercentil(p)}"><b>${valorStat(v, c, esPct)}</b> <small>(${Math.round(p)})</small></span>`;
      })],
    ir: `#/jugador/${f.id}`,
  })));
  return html;
}

// ---------- Cuartos ----------
// "1er cuarto" -> "1º", "Prórroga" -> "Prórroga"
export const periodoCorto = (p) => p.replace(/^(\d)\D*cuarto$/, "$1º");
const NEUTRAS = new Set(["2PA%", "3PA%"]);
const MENOR_ES_MEJOR = new Set(["Pérdidas pp", "Pérdidas p100", "TOV%"]);

function celdaComparada(v, ref, columna, esPct) {
  if (vacio(v)) return "-";
  const margen = vacio(ref) ? 0.01 : Math.max(Math.abs(ref) * 0.05, 0.01);
  const clase = NEUTRAS.has(columna) ? "neutro" : claseComparada(v, ref, !MENOR_ES_MEJOR.has(columna), margen);
  return `<span class="${clase}">${valorStat(v, columna, esPct)}</span>${media(vacio(ref) ? "-" : valorStat(ref, columna, esPct))}`;
}

function graficoRatings(rendimiento) {
  const periodos = rendimiento.filter((r) => r.periodo !== "Partido");
  const partido = rendimiento.find((r) => r.periodo === "Partido");
  const ancho = 400, alto = 230, mx = 10, abajo = 40, arriba = 26;
  const valores = periodos.flatMap((r) => [r.ortg, r.drtg]).filter((v) => !vacio(v)).concat([partido.ortg, partido.drtg]);
  // El eje no empieza en 0 para que se vean las diferencias entre cuartos
  const min = Math.max(0, Math.floor((Math.min(...valores) * 0.85) / 10) * 10);
  const max = Math.max(...valores) * 1.05;
  const y = (v) => arriba + (1 - (v - min) / (max - min)) * (alto - arriba - abajo);
  const anchoGrupo = (ancho - mx - 10) / periodos.length;
  let barras = "";
  periodos.forEach((r, i) => {
    const x0 = mx + i * anchoGrupo + anchoGrupo * 0.15;
    const w = anchoGrupo * 0.33;
    barras += `<rect x="${x0}" y="${y(r.ortg)}" width="${w}" height="${alto - abajo - y(r.ortg)}" fill="#F97316" rx="3"/>`;
    barras += `<rect x="${x0 + w + 4}" y="${y(r.drtg)}" width="${w}" height="${alto - abajo - y(r.drtg)}" fill="#737373" rx="3"/>`;
    barras += `<text x="${x0 + w + 2}" y="${alto - abajo + 16}" text-anchor="middle" fill="#D4D4D4" font-size="12">${esc(periodoCorto(r.periodo))}</text>`;
    barras += `<text x="${x0 + w + 2}" y="${alto - 6}" text-anchor="middle" font-size="12" font-weight="700" fill="${r.net >= 0 ? "#4ADE80" : "#F87171"}">${signo(r.net)}</text>`;
  });
  const lineaMedia = (v, color, texto) => `<line x1="${mx}" x2="${ancho - 10}" y1="${y(v)}" y2="${y(v)}" stroke="${color}" stroke-dasharray="5 4"/>
    <text x="${ancho - 12}" y="${y(v) - 4}" text-anchor="end" fill="${color}" font-size="11" paint-order="stroke" stroke="#141414" stroke-width="3">${texto} ${num(v)}</text>`;
  return `<svg class="grafico" viewBox="0 0 ${ancho} ${alto}">${barras}
    ${lineaMedia(partido.ortg, "#F97316", "ORtg medio")}${lineaMedia(partido.drtg, "#A3A3A3", "DRtg medio")}</svg>
    <div class="leyenda"><span><i style="background:#F97316"></i>Offensive Rating</span><span><i style="background:#737373"></i>Defensive Rating</span><span>Abajo: Net Rating</span></div>`;
}

// `extra(etiqueta)` añade tablas propias del periodo elegido (las usa la sección del Atlético)
export function htmlCuartos(datos, extra = null) {
  const c = datos.cuartos;
  if (!c) return `<div class="vacio">Sin jugadas registradas.</div>`;
  const partido = c.rendimiento.find((r) => r.periodo === "Partido");
  const comparado = (r, clave, mayor = true, conSigno = false, neutro = false) => {
    const texto = conSigno ? signo(r[clave]) : num(r[clave]);
    if (r.periodo === "Partido") return `<b class="naranja">${texto}</b>`;
    const clase = neutro ? "neutro" : claseComparada(r[clave], partido[clave], mayor, 1.0);
    return `<span class="${clase}">${texto}</span>${media(conSigno ? signo(partido[clave]) : num(partido[clave]))}`;
  };
  let html = titulo("Rendimiento del equipo");
  html += tabla(["Periodo", { t: "Parcial", def: "Puntos a favor - en contra por partido en ese periodo." },
    { t: "Ritmo", def: "Posesiones por cada 40 minutos (media de las de ambos equipos)." },
    { t: "ORtg", def: "Offensive Rating: puntos anotados cada 100 posesiones." },
    { t: "DRtg", def: "Defensive Rating: puntos recibidos cada 100 posesiones." },
    { t: "Net", def: "Net Rating: Offensive Rating − Defensive Rating." }],
  c.rendimiento.map((r) => ({
    celdas: [r.periodo === "Partido" ? '<span class="naranja">Media</span>' : esc(periodoCorto(r.periodo)),
      `${num(r.pf)} - ${num(r.pc)}<span class="sub">${entero(r.partidos)} PJ</span>`, comparado(r, "ritmo", true, false, true), comparado(r, "ortg"),
      comparado(r, "drtg", false), comparado(r, "net", true, true)],
  })));
  html += nota("Entre paréntesis, la media del partido completo. Verde mejor, rojo peor (en el DRtg, más bajo es mejor).");
  html += graficoRatings(c.rendimiento);

  // Quién juega cada cuarto
  const periodos = Object.keys(c.periodos);
  html += titulo("Quién juega cada cuarto");
  const minutosOrdenados = c.minutos.slice().sort((a, b) => (b.Partido ?? 0) - (a.Partido ?? 0));
  html += tabla(["Jugador", ...periodos.map(periodoCorto), "Partido"], minutosOrdenados.map((f) => ({
    celdas: [esc(nombreJugador(f.id)), ...periodos.map((p) => {
      const v = f[p];
      if (vacio(v)) return "-";
      return `<span style="display:block;border-radius:6px;padding:3px 0;background:rgba(249,115,22,${(0.08 + 0.6 * Math.min(v, 100) / 100).toFixed(2)})">${num(v)}%</span>`;
    }), `<b>${pct(f.Partido)}</b>`],
    ir: `#/jugador/${f.id}`,
  })));
  html += nota("% de los minutos del equipo en ese periodo que juega, en los partidos en los que juega. En la prórroga, solo partidos con prórroga.");

  // Análisis del periodo elegido
  html += titulo("Análisis por cuarto");
  const etiqueta = estado("cuarto", periodos[0], periodos);
  html += chips("cuarto", periodos.map((p) => [p, periodoCorto(p)]), etiqueta);
  if (extra) html += extra(etiqueta, c.periodos[etiqueta]);

  html += titulo("Estadísticas individuales");
  const tablas = META.tablas_individuales;
  const categoria = estado("cuarto_cat", tablas[0].titulo, tablas.map((t) => t.titulo));
  html += chips("cuarto_cat", tablas.map((t) => [t.titulo, t.titulo]), categoria);
  const filas = c.periodos[etiqueta] ?? [];
  const columnas = tablas.find((t) => t.titulo === categoria).columnas.filter(([col]) => filas.some((f) => col in f.v));
  html += tabla(["Jugador", ...columnas.map(([col]) => cabStat(col))], filas.map((f) => ({
    celdas: [esc(nombreJugador(f.id)), ...columnas.map(([col, esPct]) => celdaComparada(f.v[col]?.[0], f.v[col]?.[1], col, esPct))],
    ir: `#/jugador/${f.id}`,
  })));
  html += nota(etiqueta === "Prórroga"
    ? "Entre paréntesis, la media del jugador en el partido completo. En minutos, lo que le corresponde a 5 minutos de prórroga."
    : "Entre paréntesis, la media del jugador en el partido completo. En minutos totales y por partido, la cuarta parte.");
  return html;
}

function htmlPlantilla(datos) {
  return `<div class="lista-jugadores">${datos.plantilla.slice().sort((a, b) => ordenDorsal(a.dorsal) - ordenDorsal(b.dorsal)).map((j) =>
    `<a class="jugador" href="#/jugador/${j.id}">${foto(j.id)}<span class="dorsal">${esc(j.dorsal ?? "-")}</span><span class="nombre">${esc(j.nombre)}</span></a>`).join("")}</div>`;
}

// Configurador de combinaciones en pista: On / Off frente a la media del equipo
export function htmlQuintetos(datos, idEquipo) {
  if (!datos.en_pista) return `<div class="vacio">Sin jugadas registradas.</div>`;
  const clave = `quinteto_${idEquipo}`;
  const elegidos = elegidosDe(clave);
  const enPista = new Set(datos.en_pista.quintetos.flat());
  const ids = datos.plantilla.filter((j) => enPista.has(j.id)).sort((a, b) => ordenDorsal(a.dorsal) - ordenDorsal(b.dorsal)).map((j) => j.id);
  let html = nota("Elige entre 1 y 5 jugadores para ver su impacto On / Off frente a la media del equipo.");
  html += chipsJugadores(clave, ids, elegidos);
  if (!elegidos.length) return html;
  return html + htmlOnOff(calcularOnOff(datos.en_pista, elegidos), elegidos,
    { textoMinutos: "Parte del tiempo en pista del equipo que juega esta combinación.", conDiferencial: false });
}

async function htmlPartidosEquipo(id) {
  const lista = await cargar("partidos.json");
  const suyos = lista.filter((p) => p.local === id || p.visitante === id).sort((a, b) => String(b.fecha_iso).localeCompare(String(a.fecha_iso)));
  return suyos.map(tarjetaPartido).join("") || `<div class="vacio">Sin partidos.</div>`;
}

export async function equipo(id, pestana = "stats") {
  const datos = await cargar(`equipos/${id}.json`);
  const e = META.equipos[id];
  let html = `<div class="cabecera-equipo">${escudo(id, 56)}<div><h2>${esc(e.nombre)}</h2><div class="nota">${esc(e.corto)}</div></div></div>`;
  html += pestanas([["stats", "📈 Stats"], ["individuales", "👤 Individuales"], ["quintetos", "🔄 Quintetos"],
    ["cuartos", "⏱️ Cuartos"], ["plantilla", "👥 Plantilla"], ["partidos", "📅 Partidos"]], pestana, `#/equipo/${id}`);
  if (pestana === "individuales") html += htmlIndividuales(datos);
  else if (pestana === "quintetos") html += htmlQuintetos(datos, id);
  else if (pestana === "cuartos") html += htmlCuartos(datos);
  else if (pestana === "plantilla") html += htmlPlantilla(datos);
  else if (pestana === "partidos") html += await htmlPartidosEquipo(id);
  else html += htmlEstadistica(datos, e.nombre);
  return { titulo: e.corto, html, volver: true };
}

// ====================================================================== FICHA DE JUGADOR
const COLOR_PERCENTIL = { "pct-rojo": "#E53935", "pct-naranja": "#F59E0B", "pct-amarillo": "#FACC15", "pct-verde": "#4ADE80", "pct-verde-oscuro": "#16A34A" };

function barraPercentil(p) {
  if (vacio(p)) return "-";
  const clase = clasePercentil(p);
  return `<span class="barra ${clase}"><span class="pista"><span class="lleno" style="width:${Math.max(0, Math.min(100, p))}%;background:${COLOR_PERCENTIL[clase]}"></span></span><b>${Math.round(p)}</b></span>`;
}

export async function fichaJugador(id, pestana = "perfil") {
  const j = jugador(id);
  const datos = j.equipo ? await cargar(`equipos/${j.equipo}.json`) : null;
  const fila = datos?.individuales.find((f) => f.id === id);
  let html = `<div class="tarjeta cabecera-equipo">${foto(id, 84)}<div>
    <div class="nota">${escudo(j.equipo, 20)} ${esc(nombreEquipo(j.equipo))}</div>
    <h2><span class="naranja">#${esc(j.dorsal || "-")}</span> ${esc(j.nombre)}</h2>
    ${fila ? `<div class="nota">${num(fila.v["Minutos por partido"][0])} min por partido · ${pct(fila.v["% Minutos"][0])} de los minutos</div>` : ""}</div></div>`;
  if (!fila) return { titulo: j.nombre, html: html + `<div class="vacio">Sin estadísticas en la liga.</div>`, volver: true };

  // Pestañas: perfil e impacto para todos; carta de tiro, playtypes y sistemas para el Atlético (posesiones etiquetadas)
  const propio = j.equipo === META.id_propio ? await cargar("propio.json") : null;
  const etiquetado = propio?.jugadores?.[id];
  const opciones = [["perfil", "👤 Perfil"], ["impacto", "💥 Impacto"]];
  if (propio) opciones.push(["tiro", "🎯 Carta de tiro"]);
  if (etiquetado) opciones.push(["playtypes", "📋 Playtypes"], ["sistemas", "🧩 Sistemas"]);
  html += pestanas(opciones, pestana, `#/jugador/${id}`);

  if (pestana === "impacto") {
    html += htmlOnOff(calcularOnOff(datos.en_pista, [id]), [id], { textoMinutos: "% del total de minutos jugados por su equipo." });
    return { titulo: j.nombre, html, volver: true };
  }
  if (pestana === "tiro" && propio) {
    const cancha = await cargar("cancha.json");
    const { html: controles, opciones: op } = controlesCarta("jug_carta");
    const suyos = (propio.ataque?.tiros ?? []).filter((t) => t[5] === id);
    html += controles + nota(`${suyos.length} tiros de campo con localización (partidos etiquetados).`) + cartaTiro(cancha, suyos, null, op);
    return { titulo: j.nombre, html, volver: true };
  }
  if ((pestana === "playtypes" || pestana === "sistemas") && etiquetado) {
    html += pestana === "playtypes" ? htmlAnalisisJugador(etiquetado, "playtype", "Playtype") : htmlAnalisisJugador(etiquetado, "sistema", "Sistema");
    return { titulo: j.nombre, html, volver: true };
  }

  html += titulo("Impacto global en liga");
  html += radar(["Rol", "Anotación", "Rebote", "Cuidado", "Defensa"],
    [(fila.v["% Minutos"][1] ?? 0) / 10, fila.r["Rating Anotación"], fila.r["Rating Rebote"], fila.r["Rating Cuidado de Balón"], fila.r["Rating Defensa"]]);
  html += nota("Rol: percentil de % de minutos / 10. El resto, los ratings de 0 a 10.");
  html += titulo("Ratings (0-10)");
  html += tabla(["Categoría", "Rating"], Object.entries(fila.r).map(([c, v]) =>
    [esc(c.replace("Rating ", "")), `<span class="estrellas">${num(v)}</span> ${"★".repeat(Math.floor((v ?? 0) / 2))}<span style="color:#525252">${"★".repeat(5 - Math.floor((v ?? 0) / 2))}</span>`]));
  for (const t of META.tablas_individuales) {
    html += titulo(t.titulo);
    html += tabla(["Estadística", "Valor", "Percentil"], t.columnas.map(([c, esPct]) => {
      const [v, p] = fila.v[c];
      return [esc(c), `<b>${valorStat(v, c, esPct)}</b>`, barraPercentil(p)];
    }));
  }
  html += nota("Percentil: posición respecto a todos los jugadores de la liga (100 = el mejor).");
  return { titulo: j.nombre, html, volver: true };
}

// ====================================================================== RANKINGS
const NOMBRE_RANKING = { "2PA%": "2PAr", "3PA%": "3PAr" };

// Mapa de eficiencia de los equipos y uso vs eficiencia de los jugadores
function graficosRanking(datos) {
  const grafico = estado("rk_grafico", "mapa", ["mapa", "uso"]);
  let html = selector("rk_grafico", [["mapa", "Mapa de eficiencia (Off / Def Rtg)"], ["uso", "Uso vs eficiencia (%USG vs PPP)"]], grafico);
  if (grafico === "mapa") {
    const io = datos.stats_eq.indexOf("Offensive Rating"), id = datos.stats_eq.indexOf("Defensive Rating");
    const puntos = datos.equipos.map((e) => {
      const eq = META.equipos[e.eq];
      return { x: e.v[io], y: e.v[id], img: eq?.escudo ? `img/escudos/${eq.corto}.png` : null, recortar: false, texto: eq?.corto ?? "",
        info: `${eq?.nombre}: ${num(e.v[io])} Off Rtg · ${num(e.v[id])} Def Rtg` };
    });
    html += dispersion(puntos, { ejeX: "Offensive Rating", ejeY: "Defensive Rating", invertirY: true, formatoY: (v) => num(v, 0), formatoX: (v) => num(v, 0),
      cuadrantes: [["🛡️ Buena defensa, peor ataque", "#A3A3A3"], ["⚔️🛡️ Mejor ataque y defensa", "#4ADE80"], ["🧱 Peor ataque y defensa", "#E53935"], ["⚔️ Buen ataque, peor defensa", "#A3A3A3"]] });
    return html + nota("El eje vertical está invertido: arriba, las mejores defensas. Las líneas marcan la media de la liga. Toca un escudo para ver sus ratings.");
  }
  const iu = datos.stats.indexOf("%USG"), ip = datos.stats.indexOf("PPP");
  let jugadores = datos.jugadores.filter((j) => !vacio(j.v[iu]) && !vacio(j.v[ip])).map((j) => ({ id: j.id, eq: j.eq, usg: j.v[iu], ppp: j.v[ip] }));
  const filtro = estado("rk_uso", "uso10", ["uso10", "uso20", "efi10", "efi20", "todos", "equipo"]);
  html += chips("rk_uso", [["uso10", "Top 10 uso"], ["uso20", "Top 20 uso"], ["efi10", "Top 10 eficiencia"], ["efi20", "Top 20 eficiencia"], ["todos", "Todos"], ["equipo", "Por equipo"]], filtro);
  if (filtro === "equipo") {
    const equipo = estado("rk_uso_equipo", String(META.id_propio), META.lista_equipos.map((e) => String(e.id)));
    html += selector("rk_uso_equipo", META.lista_equipos.map((e) => [String(e.id), e.nombre]), equipo);
    jugadores = jugadores.filter((j) => j.eq === Number(equipo));
  } else if (filtro !== "todos") {
    const clave = filtro.startsWith("uso") ? "usg" : "ppp";
    jugadores = jugadores.sort((a, b) => b[clave] - a[clave]).slice(0, Number(filtro.slice(3)));
  }
  return html + usoEficiencia(jugadores);
}

export async function rankings() {
  const datos = await cargar("rankings.json");
  const tipo = estado("rk_tipo", "Individual", ["Individual", "Equipo", "Grafico"]);
  const individual = tipo === "Individual";
  const grupos = individual ? datos.individual : datos.equipo;
  const apartado = estado(`rk_apartado_${tipo}`, Object.keys(grupos)[individual ? 2 : 0], Object.keys(grupos));
  const stats = grupos[apartado];
  const stat = estado(`rk_stat_${tipo}_${apartado}`, stats[0], stats);
  const nombreStat = (s) => NOMBRE_RANKING[s] ?? s;

  let html = chips("rk_tipo", [["Individual", "👤 Jugadores"], ["Equipo", "🛡️ Equipos"], ["Grafico", "📈 Gráficos"]], tipo);
  if (tipo === "Grafico") return { titulo: "Rankings", html: html + graficosRanking(datos) };
  html += `<div class="fila-selects">${selector(`rk_apartado_${tipo}`, Object.keys(grupos).map((g) => [g, g]), apartado)}
    ${selector(`rk_stat_${tipo}_${apartado}`, stats.map((s) => [s, nombreStat(s)]), stat)}</div>`;
  const def = individual ? META.def_jugador?.[stat] ?? META.def_equipo?.[stat] : META.def_equipo?.[stat];
  if (def) html += nota(esc(def));

  const ascendente = datos.menor_es_mejor.includes(stat);
  const indice = (individual ? datos.stats : datos.stats_eq).indexOf(stat);
  let filas = (individual ? datos.jugadores : datos.equipos).filter((f) => !vacio(f.v[indice]));
  if (individual) {
    const equipo = estado("rk_equipo", "todos");
    html += selector("rk_equipo", [["todos", "Todos los equipos"], ...META.lista_equipos.map((e) => [String(e.id), e.nombre])], equipo);
    if (equipo !== "todos") filas = filas.filter((f) => f.eq === Number(equipo));
  }
  filas.sort((a, b) => (ascendente ? a.v[indice] - b.v[indice] : b.v[indice] - a.v[indice]));
  const top = estado("rk_top", "25", ["25", "50", "todos"]);
  if (individual) {
    html += chips("rk_top", [["25", "Top 25"], ["50", "Top 50"], ["todos", "Todos"]], top);
    if (top !== "todos") filas = filas.slice(0, Number(top));
  }
  const esPct = /%/.test(stat);
  html += tabla([individual ? "Jugador" : "Equipo", ...(individual ? ["Eq."] : []), nombreStat(stat)], filas.map((f, i) => ({
    celdas: [individual ? `<span class="pos">${i + 1}</span> ${esc(jugador(f.id).nombre)}`
      : `<span class="equipo-celda"><span class="pos">${i + 1}</span>${escudo(f.eq, 22)}${esc(nombreEquipo(f.eq))}</span>`,
      ...(individual ? [`<span class="equipo-celda">${escudo(f.eq, 18)}${esc(cortoEquipo(f.eq))}</span>`] : []),
      `<b>${valorStat(f.v[indice], stat, esPct)}</b>`],
    clase: f.eq === META.id_propio ? "destacada" : "",
    ir: individual ? `#/jugador/${f.id}` : `#/equipo/${f.eq}`,
  })));
  return { titulo: "Rankings", html };
}
