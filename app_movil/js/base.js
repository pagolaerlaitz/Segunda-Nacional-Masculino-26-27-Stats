// Utilidades comunes: carga de datos, formato de números, colores, tablas, escudos y fotos.

const cache = new Map();

export function cargar(ruta) {
  if (!cache.has(ruta)) {
    cache.set(ruta, fetch(`data/${ruta}`).then((r) => {
      if (!r.ok) throw new Error(`No se pudo cargar ${ruta}`);
      return r.json();
    }).catch((e) => { cache.delete(ruta); throw e; }));
  }
  return cache.get(ruta);
}

export const META = { equipos: {}, jugadores: {} };

export async function iniciarMeta() {
  const [meta, jugadores] = await Promise.all([cargar("meta.json"), cargar("jugadores.json")]);
  Object.assign(META, meta);
  META.equipos = Object.fromEntries(meta.equipos.map((e) => [e.id, e]));
  META.lista_equipos = meta.equipos;
  META.jugadores = jugadores;
}

// ---------- Texto y números ----------
export function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export const vacio = (v) => v === null || v === undefined || Number.isNaN(v);

export function num(v, dec = 1) {
  if (vacio(v)) return "-";
  return Number(v).toFixed(dec);
}

export function entero(v) {
  return vacio(v) ? "-" : String(Math.round(v));
}

export function pct(v, dec = 1) {
  return vacio(v) ? "-" : `${Number(v).toFixed(dec)}%`;
}

export function signo(v, dec = 1) {
  if (vacio(v)) return "-";
  const t = Number(v).toFixed(dec);
  return v > 0 ? `+${t}` : t;
}

// Formatos de Python ("{:.1f}%", "{:+.1f}", "{:.3f}"...) usados en las tablas de estadística
export function formatoPython(v, formato) {
  if (vacio(v)) return "-";
  const m = /\{:(\+)?\.(\d)f\}(%?)/.exec(formato);
  if (!m) return num(v);
  const texto = Number(v).toFixed(Number(m[2]));
  return (m[1] && v > 0 ? "+" : "") + texto + m[3];
}

// Valor de una estadística individual con el mismo formato que en la app de escritorio
export function valorStat(v, nombre, esPorcentaje) {
  if (vacio(v)) return "-";
  if (esPorcentaje) return pct(v);
  if (nombre === "FTr") return num(v, 3);
  if (nombre === "AST / TO" || nombre === "PPP" || nombre === "AST / TO ratio") return num(v, 2);
  return Number.isInteger(v) ? String(v) : num(v);
}

export function minutos(segundos) {
  if (!segundos) return "0";
  const s = Math.round(segundos);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// ---------- Colores ----------
// Verde si es mejor que la referencia, rojo si es peor, gris si es parecido
export function claseComparada(v, ref, mayorEsMejor = true, margen = 0.1) {
  if (vacio(v) || vacio(ref)) return "neutro";
  const diferencia = mayorEsMejor ? v - ref : ref - v;
  if (diferencia > margen) return "verde";
  if (diferencia < -margen) return "rojo";
  return "neutro";
}

export function clasePercentil(p) {
  if (vacio(p)) return "";
  if (p >= 95) return "pct-verde-oscuro";
  if (p >= 75) return "pct-verde";
  if (p >= 50) return "pct-amarillo";
  if (p >= 25) return "pct-naranja";
  return "pct-rojo";
}

export function ppp(v, ref, mayorEsMejor = true) {
  if (vacio(v)) return "-";
  return `<span class="${claseComparada(v, ref, mayorEsMejor, 0.05)}">${num(v, 2)}</span>`;
}

export function barra(porcentaje) {
  if (vacio(porcentaje)) return "-";
  const ancho = Math.max(0, Math.min(100, porcentaje));
  return `<span class="barra"><span class="pista"><span class="lleno" style="width:${ancho}%"></span></span>${num(porcentaje)}%</span>`;
}

// Media de referencia, en pequeño debajo del valor (así las columnas son más estrechas en el móvil)
export const media = (texto) => `<span class="sub">(${texto})</span>`;

// ---------- Tablas ----------
// cabeceras: textos o {t, def}; filas: arrays de celdas (HTML) o {celdas, clase, ir}
export function tabla(cabeceras, filas, clase = "") {
  if (!filas.length) return `<div class="vacio">Sin datos.</div>`;
  const ths = cabeceras.map((c) => {
    const { t, def } = typeof c === "string" ? { t: c } : c;
    return def ? `<th data-def="${esc(def)}" data-nombre="${esc(t)}">${t}</th>` : `<th>${t}</th>`;
  }).join("");
  const trs = filas.map((f) => {
    const { celdas, clase: cf, ir } = Array.isArray(f) ? { celdas: f } : f;
    const atributos = (cf ? ` class="${cf}"` : "") + (ir ? ` data-ir="${ir}"` : "");
    return `<tr${atributos}>${celdas.map((c) => `<td>${c}</td>`).join("")}</tr>`;
  }).join("");
  return `<div class="tabla-scroll"><table class="${clase}"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table></div>`;
}

export const titulo = (texto) => `<div class="titulo-seccion">${texto}</div>`;
export const nota = (texto) => `<div class="nota">${texto}</div>`;

export function pestanas(opciones, activa, base) {
  return `<div class="pestanas">${opciones.map(([clave, texto]) =>
    `<a class="pestana${clave === activa ? " activa" : ""}" href="${base}/${encodeURIComponent(clave)}">${texto}</a>`).join("")}</div>`;
}

// Chips que cambian un estado de la vista (data-chip="grupo:valor")
export function chips(grupo, opciones, activa) {
  return `<div class="chips">${opciones.map(([valor, texto]) =>
    `<button class="chip${valor === activa ? " activa" : ""}" data-chip="${esc(grupo)}" data-valor="${esc(valor)}">${texto}</button>`).join("")}</div>`;
}

export function selector(grupo, opciones, activa) {
  return `<select data-select="${esc(grupo)}">${opciones.map(([valor, texto]) =>
    `<option value="${esc(valor)}"${valor === activa ? " selected" : ""}>${esc(texto)}</option>`).join("")}</select>`;
}

// ---------- Equipos y jugadores ----------
export function escudo(idEquipo, tam = 28) {
  const e = META.equipos[idEquipo];
  if (!e) return "";
  if (e.escudo) return `<img class="escudo" src="img/escudos/${esc(e.corto)}.png" alt="" style="width:${tam}px;height:${tam}px" loading="lazy">`;
  return `<span class="escudo-texto" style="width:${tam}px;height:${tam}px">${esc(e.corto)}</span>`;
}

// Para ordenar por dorsal (el 0 va primero; sin dorsal, al final)
export function ordenDorsal(dorsal) {
  const n = parseInt(dorsal, 10);
  return Number.isNaN(n) ? 999 : n;
}

export const nombreEquipo = (id) => META.equipos[id]?.nombre ?? "—";
export const cortoEquipo = (id) => META.equipos[id]?.corto ?? "—";

export function jugador(id) {
  const j = META.jugadores[id];
  return j ? { id, dorsal: j[0], nombre: j[1], equipo: j[2], foto: j[3] } : { id, dorsal: "", nombre: "Desconocido" };
}

export function nombreJugador(id) {
  const j = jugador(id);
  return `${j.dorsal !== "" ? j.dorsal : "-"} - ${j.nombre}`;
}

export function foto(id, tam = 44) {
  const j = jugador(id);
  if (j.foto) return `<img class="foto" src="img/jugadores/${id}.png" alt="" style="width:${tam}px;height:${tam}px" loading="lazy">`;
  const iniciales = j.nombre.split(" ").slice(0, 2).map((p) => p[0] ?? "").join("");
  return `<span class="foto" style="width:${tam}px;height:${tam}px;font-size:${tam * 0.35}px">${esc(iniciales)}</span>`;
}

export function definicion(nombre, deJugador = false) {
  const defs = deJugador ? META.def_jugador : META.def_equipo;
  return defs?.[nombre] ?? (deJugador ? META.def_equipo?.[nombre] : null) ?? null;
}

export function cabStat(nombre, deJugador = true, texto = null) {
  const def = definicion(nombre, deJugador);
  return def ? { t: texto ?? nombre, def } : (texto ?? nombre);
}
