// Gráficos en SVG pensados para el móvil. Los elementos con data-info muestran su detalle al tocarlos.
import { META, esc, jugador, num, signo, vacio } from "./base.js";

const ANCHO = 400;
const FONDO = "#141414";
const info = (texto) => `data-info="${esc(texto)}"`;

function escala(min, max, desde, hasta) {
  const rango = max - min || 1;
  return (v) => desde + ((v - min) / rango) * (hasta - desde);
}

function limites(valores, margen = 0.1) {
  const v = valores.filter((x) => !vacio(x));
  let min = Math.min(...v), max = Math.max(...v);
  if (min === max) { min -= 1; max += 1; }
  const m = (max - min) * margen;
  return [min - m, max + m];
}

function marcasEje(min, max, n = 4) {
  const paso = (max - min) / n;
  return Array.from({ length: n + 1 }, (_, i) => min + i * paso);
}

// ---------- Burbujas: frecuencia (x) frente a PPP (y); tamaño según posesiones ----------
export function burbujas(filas, pppRef, ejeY = "PPP") {
  const datos = (filas ?? []).filter((f) => !vacio(f.ppp));
  if (datos.length < 2) return "";
  const alto = 260, izq = 34, der = 12, arriba = 14, abajo = 30;
  const [x0, x1] = limites(datos.map((f) => f.f), 0.12);
  const [y0, y1] = limites(datos.map((f) => f.ppp).concat([pppRef]), 0.15);
  const x = escala(Math.max(0, x0), x1, izq, ANCHO - der);
  const y = escala(y0, y1, alto - abajo, arriba);
  const maxN = Math.max(...datos.map((f) => f.n));
  let svg = marcasEje(y0, y1).map((v) => `<line x1="${izq}" x2="${ANCHO - der}" y1="${y(v)}" y2="${y(v)}" stroke="#262626"/>
    <text x="${izq - 4}" y="${y(v) + 3}" text-anchor="end" fill="#737373" font-size="9">${num(v, 2)}</text>`).join("");
  svg += `<line x1="${izq}" x2="${ANCHO - der}" y1="${y(pppRef)}" y2="${y(pppRef)}" stroke="#D4D4D4" stroke-dasharray="4 3"/>
    <text x="${ANCHO - der}" y="${y(pppRef) - 4}" text-anchor="end" fill="#D4D4D4" font-size="9">Media ${num(pppRef, 2)}</text>`;
  for (const f of datos.slice().sort((a, b) => b.n - a.n)) {
    const r = 5 + 13 * Math.sqrt(f.n / maxN);
    svg += `<g ${info(`${f.g}: ${num(f.f)}% de frecuencia · ${num(f.ppp, 2)} ${ejeY} · ${f.n} posesiones`)}>
      <circle cx="${x(f.f)}" cy="${y(f.ppp)}" r="${r}" fill="#F97316" fill-opacity="0.65" stroke="#FFFFFF" stroke-width="1"/>
      <text x="${x(f.f)}" y="${y(f.ppp) - r - 3}" text-anchor="middle" fill="#E5E5E5" font-size="9">${esc(f.g)}</text></g>`;
  }
  svg += `<text x="${(izq + ANCHO) / 2}" y="${alto - 6}" text-anchor="middle" fill="#A3A3A3" font-size="10">Frecuencia (%)</text>
    <text x="10" y="${arriba + 2}" fill="#A3A3A3" font-size="10">${esc(ejeY)}</text>`;
  return `<svg class="grafico" viewBox="0 0 ${ANCHO} ${alto}">${svg}</svg>`;
}

// ---------- Dispersión con fotos o escudos (uso vs eficiencia, mapa de eficiencia) ----------
// puntos: [{x, y, img, texto, info}]; cuadrantes: [arriba-izq, arriba-dcha, abajo-izq, abajo-dcha] como [texto, color]
export function dispersion(puntos, { ejeX, ejeY, invertirY = false, cuadrantes = [], formatoX = (v) => num(v), formatoY = (v) => num(v, 2), tam = 26 }) {
  const datos = puntos.filter((p) => !vacio(p.x) && !vacio(p.y));
  if (!datos.length) return `<div class="vacio">Sin datos.</div>`;
  const alto = 380, izq = 36, der = 14, arriba = 30, abajo = 34;
  const [x0, x1] = limites(datos.map((p) => p.x), 0.12);
  const [y0, y1] = limites(datos.map((p) => p.y), 0.12);
  const x = escala(x0, x1, izq, ANCHO - der);
  const y = invertirY ? escala(y0, y1, arriba, alto - abajo) : escala(y0, y1, alto - abajo, arriba);
  const mediaX = datos.reduce((s, p) => s + p.x, 0) / datos.length;
  const mediaY = datos.reduce((s, p) => s + p.y, 0) / datos.length;
  let svg = `<rect x="${izq}" y="${arriba}" width="${ANCHO - izq - der}" height="${alto - arriba - abajo}" fill="${FONDO}"/>`;
  svg += marcasEje(y0, y1).map((v) => `<text x="${izq - 4}" y="${y(v) + 3}" text-anchor="end" fill="#737373" font-size="9">${formatoY(v)}</text>`).join("");
  svg += marcasEje(x0, x1).map((v) => `<text x="${x(v)}" y="${alto - abajo + 12}" text-anchor="middle" fill="#737373" font-size="9">${formatoX(v)}</text>`).join("");
  svg += `<line x1="${x(mediaX)}" x2="${x(mediaX)}" y1="${arriba}" y2="${alto - abajo}" stroke="#D4D4D4" stroke-width="0.8"/>
    <line x1="${izq}" x2="${ANCHO - der}" y1="${y(mediaY)}" y2="${y(mediaY)}" stroke="#D4D4D4" stroke-width="0.8"/>`;
  const posiciones = [[izq + 4, arriba + 11, "start"], [ANCHO - der - 4, arriba + 11, "end"], [izq + 4, alto - abajo - 5, "start"], [ANCHO - der - 4, alto - abajo - 5, "end"]];
  cuadrantes.forEach(([texto, color], i) => {
    const [px, py, ancla] = posiciones[i];
    svg += `<text x="${px}" y="${py}" text-anchor="${ancla}" fill="${color}" font-size="9" font-weight="700">${esc(texto)}</text>`;
  });
  datos.forEach((p, i) => {
    const cx = x(p.x), cy = y(p.y);
    const marcador = p.img
      ? `<clipPath id="c${i}"><rect x="${cx - tam / 2}" y="${cy - tam / 2}" width="${tam}" height="${tam}" rx="5"/></clipPath>
         <image href="${p.img}" x="${cx - tam / 2}" y="${cy - tam / 2}" width="${tam}" height="${tam}" preserveAspectRatio="xMidYMid ${p.recortar === false ? "meet" : "slice"}" clip-path="url(#c${i})"/>`
      : `<rect x="${cx - tam / 2}" y="${cy - tam / 2}" width="${tam}" height="${tam}" rx="5" fill="#262626" stroke="#F97316" stroke-width="1.5"/>
         <text x="${cx}" y="${cy + 3.5}" text-anchor="middle" fill="#F97316" font-size="10" font-weight="800">${esc(p.texto)}</text>`;
    svg += `<g ${info(p.info)}>${marcador}</g>`;
  });
  svg += `<text x="${(izq + ANCHO) / 2}" y="${alto - 6}" text-anchor="middle" fill="#A3A3A3" font-size="10">${esc(ejeX)} ⟶</text>
    <text x="${izq}" y="${arriba - 10}" fill="#A3A3A3" font-size="10">${esc(ejeY)}${invertirY ? " (invertido)" : ""} ⟶</text>`;
  return `<svg class="grafico" viewBox="0 0 ${ANCHO} ${alto}">${svg}</svg>`;
}

export const iniciales = (nombre) => String(nombre).replace(/-/g, " ").split(" ").filter((p) => p && !/^\d+$/.test(p)).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

// %USG frente a PPP de unos jugadores [{id, usg, ppp}]
export function usoEficiencia(jugadores) {
  const puntos = jugadores.map((j) => {
    const datos = jugador(j.id);
    return { x: j.usg, y: j.ppp, img: datos.foto ? `img/jugadores/${j.id}.png` : null, texto: iniciales(datos.nombre),
      info: `${datos.nombre}: ${num(j.usg)}% USG · ${num(j.ppp, 2)} PPP` };
  });
  return dispersion(puntos, { ejeX: "%USG", ejeY: "PPP", cuadrantes: [["🎯 Poco uso, mucha eficiencia", "#4ADE80"],
    ["🌟 Mucho uso, mucha eficiencia", "#F97316"], ["🧱 Poco uso, poca eficiencia", "#A3A3A3"], ["⛔ Mucho uso, poca eficiencia", "#E53935"]] })
    + `<div class="nota">Las líneas marcan la media de los jugadores del gráfico. Toca un jugador para ver sus datos.</div>`;
}

// ---------- Barras horizontales (HTML) ----------
export function barrasH(filas, sufijo = "%") {
  if (!filas.length) return `<div class="vacio">Sin datos.</div>`;
  const max = Math.max(...filas.map((f) => f.valor));
  return `<div class="barras-h">${filas.map((f) => `<div class="fila-barra" ${f.info ? info(f.info) : ""}>
    <span class="etiqueta-barra">${esc(f.etiqueta)}</span>
    <span class="pista-barra"><span class="lleno-barra" style="width:${(f.valor / max) * 100}%"></span></span>
    <span class="valor-barra">${num(f.valor)}${sufijo}</span></div>`).join("")}</div>`;
}

// ---------- Radar (valores de 0 a 10) ----------
export function radar(categorias, valores) {
  const tam = 300, c = tam / 2, r = 100;
  const punto = (i, v) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / categorias.length;
    return [c + Math.cos(a) * r * (v / 10), c + Math.sin(a) * r * (v / 10)];
  };
  let svg = [2.5, 5, 7.5, 10].map((v) => `<polygon points="${categorias.map((_, i) => punto(i, v).join(",")).join(" ")}" fill="none" stroke="rgba(163,163,163,0.3)"/>`).join("");
  categorias.forEach((cat, i) => {
    const [px, py] = punto(i, 10);
    const [tx, ty] = punto(i, 12.6);
    svg += `<line x1="${c}" y1="${c}" x2="${px}" y2="${py}" stroke="rgba(163,163,163,0.3)"/>
      <text x="${tx}" y="${ty + 4}" text-anchor="middle" fill="#E5E5E5" font-size="12" font-weight="700">${esc(cat)}</text>`;
  });
  const puntos = valores.map((v, i) => punto(i, Math.max(0, Math.min(10, v ?? 0))));
  svg += `<polygon points="${puntos.map((p) => p.join(",")).join(" ")}" fill="rgba(249,115,22,0.4)" stroke="#F97316" stroke-width="2"/>`;
  svg += puntos.map(([px, py], i) => `<circle cx="${px}" cy="${py}" r="4" fill="#D4D4D4" ${info(`${categorias[i]}: ${num(valores[i])}`)}/>`).join("");
  return `<svg class="grafico radar" viewBox="0 0 ${tam} ${tam}">${svg}</svg>`;
}

// ---------- Rotación: tramos en pista (barras gruesas) y en el banquillo (finas) con el +/- ----------
export function rotacion(filas, duracion) {
  if (!filas.length) return `<div class="vacio">Sin datos de rotación.</div>`;
  const izq = 78, der = 6, altoFila = 24, arriba = 6, abajo = 22;
  const alto = arriba + filas.length * altoFila + abajo;
  const x = escala(0, duracion, izq, ANCHO - der);
  const color = (dif, enPista) => (enPista ? (dif > 0 ? "#16A34A" : dif < 0 ? "#DC2626" : "#737373")
    : (dif > 0 ? "rgba(22,163,74,0.35)" : dif < 0 ? "rgba(220,38,38,0.35)" : "rgba(163,163,163,0.15)"));
  let svg = "";
  for (let t = 600; t < duracion; t += t < 2400 ? 600 : 300) {
    svg += `<line x1="${x(t)}" x2="${x(t)}" y1="${arriba}" y2="${alto - abajo}" stroke="#555" stroke-dasharray="2 2"/>`;
  }
  filas.forEach((f, i) => {
    const yc = arriba + i * altoFila + altoFila / 2;
    const partes = f.etiqueta.split(" - ");
    const corto = `${partes[0]} ${(partes[1] ?? "").split(" ").at(-1)}`;
    svg += `<text x="${izq - 4}" y="${yc + 3.5}" text-anchor="end" fill="#E5E5E5" font-size="10" font-weight="700">${esc(corto)}</text>`;
    for (const [t0, t1, enPista, dif] of f.stints) {
      const grosor = enPista ? 16 : 5;
      const ancho = Math.max(0.5, x(t1) - x(t0));
      const minuto = (t) => `${Math.floor(t / 60)}'`;
      svg += `<rect x="${x(t0)}" y="${yc - grosor / 2}" width="${ancho}" height="${grosor}" fill="${color(dif, enPista)}" ${enPista ? 'stroke="#0B0B0B" stroke-width="0.6"' : ""}
        ${info(`${f.etiqueta} · ${enPista ? "En pista" : "Banquillo"} del ${minuto(t0)} al ${minuto(t1)} · +/- ${signo(dif, 0)}`)}/>`;
      if (enPista && t1 - t0 >= 90) {
        svg += `<text x="${x(t0) + ancho / 2}" y="${yc + 3}" text-anchor="middle" fill="#FFFFFF" font-size="8.5" pointer-events="none">${signo(dif, 0)}</text>`;
      } else if (!enPista && t1 - t0 >= 90) {
        // En el banquillo la barra es fina: el +/- va en color sobre ella, con un contorno del color del fondo para que se lea
        const colorTexto = dif > 0 ? "#4ADE80" : dif < 0 ? "#F87171" : "#A3A3A3";
        svg += `<text x="${x(t0) + ancho / 2}" y="${yc + 3}" text-anchor="middle" fill="${colorTexto}" font-size="8.5" font-weight="700"
          paint-order="stroke" stroke="${FONDO}" stroke-width="3" pointer-events="none">${signo(dif, 0)}</text>`;
      }
    }
  });
  for (let t = 0; t <= duracion; t += 600) {
    svg += `<text x="${x(t)}" y="${alto - 8}" text-anchor="middle" fill="#737373" font-size="9">${t / 60}'</text>`;
  }
  return `<svg class="grafico" viewBox="0 0 ${ANCHO} ${alto}">${svg}</svg>`;
}

// ---------- Mapa de calor (PPP por jugador y categoría) ----------
function colorPPP(v, centro, max) {
  // Rojo -> amarillo -> verde, centrado en el PPP de referencia
  const rojo = [215, 48, 39], amarillo = [254, 224, 139], verde = [26, 152, 80];
  const mezcla = (a, b, t) => a.map((c, i) => Math.round(c + (b[i] - c) * t));
  const rgb = v <= centro ? mezcla(rojo, amarillo, Math.max(0, v) / (centro || 1)) : mezcla(amarillo, verde, Math.min(1, (v - centro) / ((max - centro) || 1)));
  return `rgb(${rgb.join(",")})`;
}

export function mapaCalor(mapa, pppRef) {
  const max = Math.max(2, ...mapa.ppp.flat().filter((v) => !vacio(v)));
  const cabecera = `<tr><th>Jugador</th>${mapa.columnas.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>`;
  const filas = mapa.filas.map((fila, i) => `<tr><td>${esc(fila)}</td>${mapa.columnas.map((col, j) => {
    const v = mapa.ppp[i][j], n = mapa.n[i][j];
    if (vacio(n)) return "<td></td>";
    return `<td style="background:${colorPPP(v, pppRef, max)};color:#111;font-weight:700" ${info(`${fila} · ${col}: ${num(v, 2)} PPP en ${n} posesiones`)}>${num(v, 2)}<span class="sub" style="color:#333">(${n})</span></td>`;
  }).join("")}</tr>`).join("");
  return `<div class="tabla-scroll"><table class="mapa-calor"><thead>${cabecera}</thead><tbody>${filas}</tbody></table></div>`;
}

// ---------- Carta de tiro por zonas ----------
const VERDE = "rgba(74,222,128,0.65)", ROJO = "rgba(248,113,113,0.65)", NEUTRO = "rgba(163,163,163,0.45)", VACIO = "rgba(255,255,255,0.06)";

function estadisticasZonas(tiros, cancha) {
  const res = {};
  for (const [, , zona, anotado, triple] of tiros) {
    const nombre = cancha.orden[zona];
    res[nombre] ??= { intentos: 0, anotados: 0, puntos: 0 };
    res[nombre].intentos += 1;
    res[nombre].anotados += anotado;
    res[nombre].puntos += anotado ? (triple ? 3 : 2) : 0;
  }
  const total = { intentos: tiros.length, anotados: 0, puntos: 0 };
  for (const r of Object.values(res)) {
    total.anotados += r.anotados;
    total.puntos += r.puntos;
  }
  res.Total = total;
  for (const r of Object.values(res)) {
    r.pct = r.intentos ? (r.anotados / r.intentos) * 100 : NaN;
    r.ppt = r.intentos ? r.puntos / r.intentos : NaN;
    r.frecuencia = tiros.length ? (r.intentos / tiros.length) * 100 : 0;
  }
  return res;
}

// tirosOff: grupo con el que se compara (si no hay, cada zona se compara con un acierto típico)
export function cartaTiro(cancha, tirosOn, tirosOff, { modo = "Acierto", medida = "%", verTiros = false, mayorEsMejor = true, etiquetaOn = "On", etiquetaOff = "Off" } = {}) {
  if (!tirosOn.length) return `<div class="vacio">No hay tiros con localización para esta selección.</div>`;
  const res = estadisticasZonas(tirosOn, cancha);
  const hayOff = tirosOff && tirosOff.length;
  const off = hayOff ? estadisticasZonas(tirosOff, cancha) : null;
  const referencia = (zona) => {
    if (hayOff) return off[zona] ? [off[zona].pct, off[zona].ppt] : [NaN, NaN];
    const pct = cancha.esperado[zona];
    return vacio(pct) ? [NaN, NaN] : [pct, (pct / 100) * (cancha.triples.includes(zona) ? 3 : 2)];
  };
  const comparar = (v, ref, margen) => {
    if (vacio(v) || vacio(ref)) return "neutro";
    const d = mayorEsMejor ? v - ref : ref - v;
    return d > margen ? "verde" : d < -margen ? "rojo" : "neutro";
  };
  const maxFrec = Math.max(...cancha.orden.map((z) => res[z]?.frecuencia ?? 0));
  const yMax = cancha.y_max;
  let zonas = "", etiquetas = "";
  const colores = {};
  for (const zona of cancha.orden) {
    const r = res[zona];
    let l1, l2 = "";
    if (!r) {
      colores[zona] = VACIO;
      l1 = modo === "Acierto" ? "0/0" : "0";
    } else if (modo === "Frecuencia") {
      colores[zona] = `rgba(249,115,22,${(0.15 + (0.6 * r.frecuencia) / maxFrec).toFixed(2)})`;
      l1 = String(r.intentos);
      l2 = `${Math.round(r.frecuencia)}%`;
    } else {
      const [pctRef, pptRef] = referencia(zona);
      const tono = medida === "%" ? comparar(r.pct, pctRef, 5) : comparar(r.ppt, pptRef, 0.1);
      colores[zona] = tono === "verde" ? VERDE : tono === "rojo" ? ROJO : NEUTRO;
      l1 = `${r.anotados}/${r.intentos}`;
      l2 = medida === "%" ? `${Math.round(r.pct)}%` : num(r.ppt, 2);
    }
    const [ex, ey] = cancha.etiquetas[zona];
    const t = zona.startsWith("Esq ") ? 0.36 : 0.5;
    const ys = yMax + 0.2 - ey;
    etiquetas += `<text x="${ex + 0.3}" y="${ys - 0.05}" font-size="${t}" fill="#FFFFFF" font-weight="700" text-anchor="middle" pointer-events="none">
      <tspan x="${ex + 0.3}">${l1}</tspan><tspan x="${ex + 0.3}" dy="${t * 1.1}">${l2}</tspan></text>`;
  }
  for (const [zona, puntos] of cancha.zonas) {
    const r = res[zona];
    const detalle = r ? `${zona}: ${r.anotados}/${r.intentos} (${num(r.pct)}%) · ${num(r.frecuencia, 0)}% de los tiros` : `${zona}: sin tiros`;
    zonas += `<polygon points="${puntos}" fill="${colores[zona]}" stroke="rgba(255,255,255,0.35)" stroke-width="1" vector-effect="non-scaling-stroke" ${info(detalle)}/>`;
  }
  let puntosTiro = "";
  if (verTiros) {
    for (const [tx, ty, , anotado] of tirosOn) {
      const d = 0.13;
      puntosTiro += anotado
        ? `<circle cx="${tx}" cy="${ty}" r="0.13" fill="#4CAF50" stroke="#FFFFFF" stroke-width="1" vector-effect="non-scaling-stroke" pointer-events="none"/>`
        : `<path d="M ${tx - d},${ty - d} L ${tx + d},${ty + d} M ${tx - d},${ty + d} L ${tx + d},${ty - d}" stroke="#E53935" stroke-width="2" vector-effect="non-scaling-stroke" pointer-events="none"/>`;
    }
  }
  const altoSvg = yMax + 0.5;
  const svg = `<svg class="grafico" viewBox="0 0 15.6 ${altoSvg}">
    <defs><clipPath id="corte-cancha"><rect x="0" y="-0.3" width="15" height="${yMax + 0.3}"/></clipPath></defs>
    <rect x="0" y="0" width="15.6" height="${altoSvg}" fill="${FONDO}"/>
    <g transform="translate(0.3, ${yMax + 0.2}) scale(1,-1)" clip-path="url(#corte-cancha)">${zonas}<g pointer-events="none">${cancha.lineas}</g>${puntosTiro}</g>
    ${etiquetas}</svg>`;

  // Tabla por zonas
  const sufijo = hayOff ? ` ${etiquetaOn}` : "";
  const cabeceras = ["Zona", `Tiros${sufijo}`, `%${sufijo}`, ...(hayOff ? [`% ${etiquetaOff}`] : []), `Frec.${sufijo}`, ...(hayOff ? [`Frec. ${etiquetaOff}`] : [])];
  const filas = [];
  for (const zona of [...cancha.orden, "Total"]) {
    const r = res[zona], ro = off?.[zona];
    if (!r && !ro) continue;
    const refPct = zona === "Total" ? (hayOff ? off.Total.pct : NaN) : referencia(zona)[0];
    filas.push(`<tr${zona === "Total" ? ' class="total"' : ""}><td>${zona}</td><td>${r ? `${r.anotados}/${r.intentos}` : "0/0"}</td>
      <td><span class="${r ? comparar(r.pct, refPct, 5) : ""}">${r ? `${num(r.pct)}%` : "-"}</span></td>
      ${hayOff ? `<td>${ro ? `${num(ro.pct)}%` : "-"}</td>` : ""}<td>${r ? `${Math.round(r.frecuencia)}%` : "0%"}</td>
      ${hayOff ? `<td>${ro ? `${Math.round(ro.frecuencia)}%` : "0%"}</td>` : ""}</tr>`);
  }
  const tabla = `<div class="tabla-scroll"><table><thead><tr>${cabeceras.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${filas.join("")}</tbody></table></div>`;
  const texto = hayOff ? `acierto ${etiquetaOn} comparado con ${etiquetaOff}` : "acierto comparado con un acierto típico de cada zona";
  return `${svg}<div class="nota">Color de cada zona: ${texto}: verde mejor, rojo peor${mayorEsMejor ? "" : " (desde el punto de vista de la defensa)"}. Toca una zona para ver su detalle.</div>${tabla}`;
}
