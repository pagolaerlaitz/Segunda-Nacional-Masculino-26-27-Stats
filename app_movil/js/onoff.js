// Impacto On/Off de una combinación de jugadores (como calcular_stats_quinteto de app.py), calculado en el móvil
// a partir del play by play mínimo de cada equipo: [quinteto en pista, lado (1 propio, 0 rival, -1 nadie), jugada, segundos].
import { esc, nombreJugador, num, tabla, titulo, vacio } from "./base.js";
import { barrasH } from "./graficos.js";

const CONTADORES = ["fgm", "t3m", "fga", "t2a", "t3a", "tlm", "tla", "dreb", "oreb", "ast", "tov"];

function vacios() {
  const propio = Object.fromEntries(CONTADORES.map((c) => [c, 0]));
  const rival = Object.fromEntries(CONTADORES.map((c) => [c, 0]));
  return { propio, rival, seg: 0 };
}

function sumar(a, lado, jugada, seg) {
  a.seg += seg;
  if (lado === -1 || !jugada) return;
  const s = lado === 1 ? a.propio : a.rival;
  switch (jugada) {
    case 93: case 100: s.fgm++; s.fga++; s.t2a++; break;
    case 94: s.fgm++; s.t3m++; s.fga++; s.t3a++; break;
    case 97: s.fga++; s.t2a++; break;
    case 98: s.fga++; s.t3a++; break;
    case 92: s.tlm++; s.tla++; break;
    case 96: s.tla++; break;
    case 104: s.dreb++; break;
    case 101: s.oreb++; break;
    case 107: s.ast++; break;
    case 106: s.tov++; break;
    default: break;
  }
}

function metricas(a) {
  const p = a.propio, r = a.rival;
  const puntos = (p.fgm - p.t3m) * 2 + p.t3m * 3 + p.tlm;
  const puntosRival = (r.fgm - r.t3m) * 2 + r.t3m * 3 + r.tlm;
  const posesiones = ((p.fga + 0.44 * p.tla + p.tov - p.oreb) + (r.fga + 0.44 * r.tla + r.tov - r.oreb)) / 2;
  if (posesiones <= 0) return null;
  const div = (x) => (x > 0 ? x : 1);
  const reb = p.dreb + p.oreb, rebRival = r.dreb + r.oreb;
  const ortg = (puntos / posesiones) * 100, drtg = (puntosRival / posesiones) * 100;
  return {
    "Offensive Rating": ortg, "Defensive Rating": drtg, "Net Rating": ortg - drtg,
    "eFG%": ((p.fgm + 0.5 * p.t3m) / div(p.fga)) * 100,
    "TS%": (puntos / div(2 * (p.fga + 0.44 * p.tla))) * 100,
    "FTr": p.tla / div(p.fga), "2PA%": (p.t2a / div(p.fga)) * 100, "3PA%": (p.t3a / div(p.fga)) * 100,
    "DREB%": (p.dreb / div(p.dreb + r.oreb)) * 100, "OREB%": (p.oreb / div(p.oreb + r.dreb)) * 100,
    "REB%": (reb / div(reb + rebRival)) * 100, "TOV%": (p.tov / posesiones) * 100,
    "AST / TO ratio": p.ast / div(p.tov), "AST%": (p.ast / div(p.fgm)) * 100,
  };
}

export function calcularOnOff(enPista, ids) {
  if (!enPista) return null;
  const contiene = enPista.quintetos.map((q) => ids.every((id) => q.includes(id)));
  const on = vacios(), off = vacios(), media = vacios();
  const companeros = {};
  for (const [q, lado, jugada, seg] of enPista.ev) {
    sumar(contiene[q] ? on : off, lado, jugada, seg);
    sumar(media, lado, jugada, seg);
    if (contiene[q] && seg && ids.length < 5) {
      for (const j of enPista.quintetos[q]) if (!ids.includes(j)) companeros[j] = (companeros[j] ?? 0) + seg;
    }
  }
  const mMedia = metricas(media);
  if (!mMedia) return null;
  return {
    on: metricas(on), off: metricas(off), media: mMedia,
    porcentaje: media.seg ? (on.seg / media.seg) * 100 : 0,
    companeros: Object.entries(companeros).map(([j, s]) => [Number(j), on.seg ? (s / on.seg) * 100 : 0]).sort((a, b) => b[1] - a[1]),
  };
}

const BLOQUES = {
  "Eficiencia ofensiva / defensiva": ["Offensive Rating", "Defensive Rating", "Net Rating"],
  "Tiro": ["eFG%", "TS%", "FTr", "2PA%", "3PA%"],
  "Rebote": ["DREB%", "OREB%", "REB%"],
  "Cuidado de balón": ["TOV%", "AST / TO ratio", "AST%"],
};
const MENOR_ES_MEJOR = ["Defensive Rating", "TOV%"];

function formato(v, stat) {
  if (vacio(v)) return "-";
  if (stat === "FTr") return num(v, 3);
  if (stat === "AST / TO ratio") return num(v, 2);
  if (stat.includes("%")) return `${num(v)}%`;
  if (stat === "Net Rating" && v > 0) return `+${num(v)}`;
  return num(v);
}

// Compañeros con los que más comparte pista y tablas On / Off / Diferencial / Media del equipo
export function htmlOnOff(datos, ids, { textoMinutos, conDiferencial = true }) {
  if (!datos) return `<div class="vacio">Sin datos en pista.</div>`;
  if (!datos.on) return `<div class="vacio">${ids.length > 1 ? "Estos jugadores nunca han coincidido en pista juntos." : "No registra minutos en pista."}</div>`;
  let html = `<div class="tarjeta cifra-grande"><div><b class="naranja">⏱ Minutos en pista</b><div class="nota" style="margin:2px 0 0">${textoMinutos}</div></div>
    <span class="valor">${num(datos.porcentaje)}%</span></div>`;
  if (ids.length < 5) {
    html += titulo("🤝 ¿Con quién comparte la pista?");
    html += barrasH(datos.companeros.filter(([, p]) => p > 0).map(([j, p]) => ({ etiqueta: nombreJugador(j), valor: p, info: `${nombreJugador(j)}: ${num(p)}% de esos minutos` })));
  }
  for (const [bloque, stats] of Object.entries(BLOQUES)) {
    html += titulo(bloque);
    html += tabla(["Estadística", "On", "Off", ...(conDiferencial ? ["Dif."] : []), "Media"], stats.map((stat) => {
      const on = datos.on?.[stat], off = datos.off?.[stat];
      const comparable = !vacio(on) && !vacio(off) && on !== off;
      const mejor = comparable && ((on > off) !== MENOR_ES_MEJOR.includes(stat));
      const claseOn = comparable ? (mejor ? "verde" : "rojo") : "";
      const dif = comparable ? on - off : NaN;
      const difTexto = vacio(dif) ? "-" : `${dif > 0 ? "+" : ""}${stat === "FTr" ? num(dif, 3) : stat === "AST / TO ratio" ? num(dif, 2) : num(dif)}${stat.includes("%") ? "%" : ""}`;
      return [esc(stat), `<span class="${claseOn}">${formato(on, stat)}</span>`, `<span class="neutro">${formato(off, stat)}</span>`,
        ...(conDiferencial ? [`<span class="${claseOn}">${difTexto}</span>`] : []), `<span class="media">${formato(datos.media[stat], stat)}</span>`];
    }));
  }
  return html + `<div class="nota">On: con ${ids.length > 1 ? "la combinación" : "el jugador"} en pista. Off: sin ${ids.length > 1 ? "ella" : "él"}. Verde si On es mejor que Off. Media: todo el equipo.</div>`;
}
