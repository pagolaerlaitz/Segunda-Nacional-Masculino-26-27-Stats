// Service worker: la app se abre al instante y funciona sin conexión.
// - Interfaz (HTML, CSS, JS, iconos): la copia guardada, y en segundo plano se descarga la nueva para la próxima vez.
// - Datos (data/*.json): primero la red, para ver siempre lo último; sin conexión, la última copia guardada.
// - Imágenes (escudos y fotos): primero la caché.
const VERSION = "v1";
const INTERFAZ = `interfaz-${VERSION}`;
const DATOS = "datos";
const IMAGENES = "imagenes";

const ARCHIVOS_INTERFAZ = [
  "./", "index.html", "styles.css", "manifest.webmanifest",
  "js/main.js", "js/estado.js", "js/base.js", "js/graficos.js", "js/onoff.js","js/liga.js", "js/propio.js",
  "icons/icono-192.png", "icons/icono-512.png", "icons/favicon.png", "icons/apple-touch-icon.png",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(INTERFAZ).then((cache) => cache.addAll(ARCHIVOS_INTERFAZ)));
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((claves) => Promise.all(
      claves.filter((c) => c.startsWith("interfaz-") && c !== INTERFAZ).map((c) => caches.delete(c))
    ))
  );
  self.clients.claim();
});

async function redPrimero(peticion) {
  const cache = await caches.open(DATOS);
  try {
    const respuesta = await fetch(peticion);
    if (respuesta.ok) cache.put(peticion, respuesta.clone());
    return respuesta;
  } catch (error) {
    const guardada = await cache.match(peticion);
    if (guardada) return guardada;
    throw error;
  }
}

async function cachePrimero(peticion, nombreCache) {
  const cache = await caches.open(nombreCache);
  const guardada = await cache.match(peticion, { ignoreSearch: true });
  if (guardada) return guardada;
  const respuesta = await fetch(peticion);
  if (respuesta.ok) cache.put(peticion, respuesta.clone());
  return respuesta;
}

self.addEventListener("fetch", (evento) => {
  const url = new URL(evento.request.url);
  if (evento.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.includes("/data/") || url.pathname.endsWith("version.txt")) {
    evento.respondWith(redPrimero(evento.request));
  } else if (url.pathname.includes("/img/")) {
    evento.respondWith(cachePrimero(evento.request, IMAGENES));
  } else {
    evento.respondWith(cacheYActualizar(evento.request));
  }
});

// Interfaz: se sirve la copia guardada (rápido y sin conexión) y se descarga la nueva para la próxima vez
async function cacheYActualizar(peticion) {
  const cache = await caches.open(INTERFAZ);
  const guardada = await cache.match(peticion, { ignoreSearch: true });
  const nueva = fetch(peticion).then((respuesta) => {
    if (respuesta.ok) cache.put(peticion, respuesta.clone());
    return respuesta;
  }).catch(() => guardada);
  return guardada || nueva;
}
