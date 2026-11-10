// Arranque, navegación por secciones (#/seccion/...) y gestos comunes (definiciones, chips, selectores).
import { ESTADO } from "./estado.js";
import { META, esc, iniciarMeta } from "./base.js";
import * as liga from "./liga.js";
import * as propio from "./propio.js";

const RUTAS = {
  clasificacion: () => liga.clasificacion(),
  partidos: () => liga.partidos(),
  partido: ([id, pestana]) => liga.partido(Number(id), pestana),
  equipos: () => liga.equipos(),
  equipo: ([id, pestana]) => liga.equipo(Number(id), pestana),
  jugador: ([id, pestana]) => liga.fichaJugador(Number(id), pestana),
  rankings: () => liga.rankings(),
  propio: ([apartado, sub, extra]) => propio.propio(apartado, sub, extra),
};
// Sección de la barra inferior a la que pertenece cada ruta
const SECCION = { partido: "partidos", equipo: "equipos", jugador: "equipos" };

const vista = document.getElementById("vista");
const tituloCabecera = document.getElementById("titulo");
const botonVolver = document.getElementById("volver");

function rutaActual() {
  const partes = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent).filter(Boolean);
  return { nombre: RUTAS[partes[0]] ? partes[0] : "clasificacion", params: partes.slice(1) };
}

let ultimaRuta = "";

async function mostrar({ conservarScroll = false } = {}) {
  const { nombre, params } = rutaActual();
  const clave = location.hash;
  const scroll = window.scrollY;
  try {
    const { titulo, html, volver } = await RUTAS[nombre](params);
    if (clave !== location.hash) return; // el usuario ya ha navegado a otra parte
    tituloCabecera.textContent = titulo;
    document.title = `${titulo} · 2ª Nacional`;
    botonVolver.hidden = !volver;
    vista.innerHTML = html;
  } catch (error) {
    console.error(error);
    vista.innerHTML = `<div class="vacio">No se han podido cargar los datos.<br><small>${esc(error.message)}</small></div>`;
  }
  const seccion = SECCION[nombre] ?? nombre;
  document.querySelectorAll(".barra-nav a").forEach((a) => a.classList.toggle("activa", a.dataset.seccion === seccion));
  // Al cambiar de pantalla, arriba; al cambiar un filtro de la misma pantalla, se mantiene la posición
  const mismaPantalla = clave.split("/").slice(0, 3).join("/") === ultimaRuta.split("/").slice(0, 3).join("/");
  window.scrollTo(0, conservarScroll || mismaPantalla ? scroll : 0);
  ultimaRuta = clave;
}

// ---------- Gestos comunes ----------
const aviso = document.getElementById("aviso");
let temporizadorAviso;

function mostrarAviso(html) {
  aviso.innerHTML = html;
  aviso.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => { aviso.hidden = true; }, 6000);
}

document.addEventListener("click", (evento) => {
  // Definición de una estadística (cabeceras de tabla y nombres de estadística en filas)
  const conDefinicion = evento.target.closest("[data-def]");
  if (conDefinicion) {
    mostrarAviso(`<b>${esc(conDefinicion.dataset.nombre)}</b>: ${esc(conDefinicion.dataset.def)}`);
    return;
  }
  // Detalle de un elemento de un gráfico (punto, barra, zona de tiro...)
  const elemento = evento.target.closest("[data-info]");
  if (elemento) {
    mostrarAviso(esc(elemento.dataset.info));
    return;
  }
  if (!evento.target.closest(".aviso")) aviso.hidden = true;

  const chip = evento.target.closest("[data-chip]");
  if (chip) {
    ESTADO[chip.dataset.chip] = chip.dataset.valor;
    mostrar({ conservarScroll: true });
    return;
  }
  const fila = evento.target.closest("[data-ir]");
  if (fila && !evento.target.closest("a")) location.hash = fila.dataset.ir;
});

document.addEventListener("change", (evento) => {
  const select = evento.target.closest("[data-select]");
  if (select) {
    ESTADO[select.dataset.select] = select.value;
    mostrar({ conservarScroll: true });
  }
});

botonVolver.addEventListener("click", () => {
  if (history.length > 1) history.back();
  else location.hash = `#/${SECCION[rutaActual().nombre] ?? "clasificacion"}`;
});

window.addEventListener("hashchange", () => mostrar());

// ---------- Arranque ----------
(async () => {
  try {
    await iniciarMeta();
    document.getElementById("actualizado").textContent = `Datos: ${META.actualizado}`;
  } catch (error) {
    vista.innerHTML = `<div class="vacio">No se han podido cargar los datos. Comprueba la conexión.</div>`;
    return;
  }
  if (!location.hash) location.replace("#/clasificacion");
  mostrar();
})();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}
