# App móvil (Vercel)

Web estática instalable en el móvil (PWA). No necesita Node ni compilar nada: Vercel publica esta carpeta tal cual.

## Actualizar los datos (tras cada jornada o después de etiquetar)

1. En la carpeta del proyecto: `py exportar_movil.py`
2. Sube a GitHub la carpeta `app_movil` (sobre todo `data/` y, si hay jugadores nuevos, `img/`).
3. Vercel vuelve a publicar solo en unos segundos. En el móvil, los datos nuevos aparecen al abrir la app con conexión.

## Publicar por primera vez

1. Sube la carpeta `app_movil` al repositorio de GitHub (puede ser el mismo de la app de Streamlit).
2. Entra en vercel.com con tu cuenta de GitHub → **Add New… → Project** → importa el repositorio.
3. En **Root Directory** elige `app_movil`. **Framework Preset**: `Other`. Deja vacíos el comando de build y el de salida.
4. **Deploy**. Te dará una dirección del tipo `https://nombre.vercel.app`.

## Instalar en el móvil

- **Android (Chrome)**: abre la dirección → menú ⋮ → **Instalar aplicación** / **Añadir a pantalla de inicio**.
- **iPhone (Safari)**: abre la dirección → botón Compartir → **Añadir a pantalla de inicio**.

## Probar en el ordenador

`py -m http.server 8600 --directory app_movil` y abre http://localhost:8600

## Estructura

- `index.html`, `styles.css`, `js/`: la interfaz.
- `data/`: los datos (los genera `exportar_movil.py`; no se editan a mano).
- `img/`: escudos y fotos (los copia `exportar_movil.py` desde `assets/`).
- `sw.js`: permite abrir la app sin conexión con los últimos datos descargados.
