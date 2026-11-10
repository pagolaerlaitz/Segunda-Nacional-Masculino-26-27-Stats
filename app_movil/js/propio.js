// Sección del Atlético, con los mismos apartados que en la app de Streamlit:
// Quintetos, Estadística, Ataque, Defensa, Cuartos y Análisis Individual.
import { estado } from "./estado.js";
import {
  META, barra, cargar, chips, esc, foto, media, nombreJugador, nota, num, ordenDorsal, pct, pestanas, ppp, selector,
  signo, subpestanas, tabla, titulo, vacio, valorStat, claseComparada,
} from "./base.js";
import {
  chipsJugadores, controlesCarta, elegidosDe, fichaJugador, htmlCuartos, htmlEstadistica, htmlQuintetos, periodoCorto,
} from "./liga.js";
import { burbujas, cartaTiro, mapaCalor, usoEficiencia } from "./graficos.js";

const APARTADOS = [["quintetos", "🔄 Quintetos"], ["estadistica", "📈 Estadística"], ["ataque", "⚔️ Ataque"],
  ["defensa", "🛡️ Defensa"], ["cuartos", "⏱️ Cuartos"], ["individual", "👤 Análisis Individual"]];
const ATAQUE = [["sistemas", "🧩 Sistemas"], ["playtypes", "🎯 Playtypes"], ["pr", "🤝 P&R"], ["tipo_defensa", "🧱 Tipo de defensa"],
  ["finalizador", "👤 Por finalizador"], ["tiro", "🏀 Carta de tiro"], ["uso", "📊 Uso vs Eficiencia"]];
const DEFENSA = [["quinteto", "🔄 Playtypes por quinteto"], ["tiro", "🎯 Carta de tiro rival"], ["pr", "🤝 P&R defensivo"],
  ["uno", "🧍 Isolation y Post Up"], ["tipo", "🧱 Tipo de defensa"]];

// Jugadores del Atlético que aparecen en una lista de quintetos, ordenados por dorsal
function jugadoresEnQuintetos(quintetos) {
  return [...new Set(quintetos.flat())].sort((a, b) => ordenDorsal(META.jugadores[a]?.[0]) - ordenDorsal(META.jugadores[b]?.[0]));
}

const DEF_POSESIONES = "Finales de posesión etiquetados: tiro de campo, pérdida o falta con tiros libres.";
const DEF_PPP = "Puntos por posesión.";
const SIN_ATAQUE = `<div class="vacio">Todavía no hay posesiones de ataque etiquetadas. Se rellenan con etiquetador.py.</div>`;
const SIN_DEFENSA = `<div class="vacio">Todavía no hay posesiones de defensa etiquetadas. Se rellenan con etiquetador.py.</div>`;

function tablaResumen(filas, cabecera, pppRef, mayorEsMejor = true) {
  if (!filas?.length) return `<div class="vacio">Sin posesiones etiquetadas.</div>`;
  return tabla([cabecera, { t: "Pos.", def: DEF_POSESIONES }, { t: "Frec.", def: "Porcentaje de las posesiones de la tabla." },
    { t: "PPP", def: mayorEsMejor ? DEF_PPP : "Puntos por posesión del rival (más bajo es mejor)." }],
  filas.map((f) => [esc(f.g), f.n, barra(f.f), ppp(f.ppp, pppRef, mayorEsMejor)]));
}

// Resumen por playtype de unas posesiones [playtype, puntos, quinteto]
function resumenPosesiones(posesiones, playtypes) {
  const grupos = {};
  for (const [pt, puntos] of posesiones) {
    grupos[pt] ??= { n: 0, pts: 0 };
    grupos[pt].n += 1;
    grupos[pt].pts += puntos;
  }
  return Object.entries(grupos).map(([pt, g]) => ({ g: playtypes[pt], n: g.n, f: (g.n / posesiones.length) * 100, pts: g.pts, ppp: g.pts / g.n }))
    .sort((a, b) => b.n - a.n || b.ppp - a.ppp);
}

function tablaSecundarios(sec, pppRef, clave) {
  if (!sec) return `<div class="vacio">Sin secondary playtypes en esta selección.</div>`;
  const filas = [];
  for (const f of sec.filas) {
    filas.push({ celdas: [esc(f.g), `<b>${f.n}</b>`, pct(f.f), "", f.top.map(([g, n]) => `${esc(g)} ×${n}`).join(" · "), ppp(f.ppp, pppRef)], clase: "padre" });
    for (const h of f.hijos) filas.push({ celdas: [`↳ ${esc(h.g)}`, h.n, "", barra(h.f), "", ppp(h.ppp, pppRef)], clase: "hija" });
  }
  let html = tabla(["Secondary → principal", { t: "Pos.", def: DEF_POSESIONES },
    { t: "% total", def: "Porcentaje de las posesiones en las que aparece ese secondary playtype." },
    { t: "% dentro", def: "De las posesiones con ese secondary, qué % acaba en cada playtype principal." },
    { t: "Protagonistas", def: "Jugadores que más lo generan (handler en P&R Handler, roller en P&R Roller y secondary player en Isolation y Post Up)." },
    { t: "PPP", def: DEF_PPP }], filas);
  html += nota(`${sec.con} de ${sec.total} posesiones (${num((sec.con / sec.total) * 100, 0)}%) tienen secondary playtype.`);
  const generadores = Object.keys(sec.genera);
  if (generadores.length) {
    const elegido = estado(`${clave}_gen`, generadores[0], generadores);
    html += `<div class="nota"><b>Ver quién genera…</b></div>${selector(`${clave}_gen`, generadores.map((g) => [g, g]), elegido)}`;
    html += tablaResumen(sec.genera[elegido], "Genera → principal", pppRef);
  }
  return html;
}

function tablaPR(filas, cabecera, pppRef, fase) {
  const mayor = fase === "ataque";
  const [rolM, rolB] = mayor ? ["manejador", "bloqueador"] : ["manejador rival", "bloqueador rival"];
  return tabla([cabecera, { t: "P&R", def: "Posesiones de P&R." }, { t: "Frec.", def: "Porcentaje del total de P&R." },
    { t: "PPP", def: DEF_PPP }, { t: "Man. %", def: `% de esos P&R que finaliza el ${rolM} (P&R Handler).` },
    { t: "Man. PPP", def: `PPP cuando finaliza el ${rolM}.` }, { t: "Bloq. %", def: `% de esos P&R que finaliza el ${rolB} (P&R Roller).` },
    { t: "Bloq. PPP", def: `PPP cuando finaliza el ${rolB}.` }],
  filas.map((f) => [esc(f.g), f.n, barra(f.f), ppp(f.ppp, pppRef, mayor),
    `${num(f.acaba[0][0], 0)}%`, ppp(f.acaba[0][1], pppRef, mayor), `${num(f.acaba[1][0], 0)}%`, ppp(f.acaba[1][1], pppRef, mayor)]));
}

function htmlPR(pr, fase) {
  if (!pr) return `<div class="vacio">Sin posesiones de P&R etiquetadas.</div>`;
  const ataque = fase === "ataque";
  let html = nota(`${pr.n} posesiones de P&R · ${num(pr.ppp, 2)} PPP${ataque ? "" : " permitido"}. Frecuencia: % del total de P&R. El color compara con el PPP medio en P&R${ataque ? "" : " (verde = el rival anota menos)"}.`);
  html += titulo(ataque ? "Manejadores" : "Defensores del manejador") + tablaPR(pr.manejadores, ataque ? "Manejador" : "Defensor del manejador", pr.ppp, fase);
  html += titulo(ataque ? "Bloqueadores" : "Defensores del bloqueador") + tablaPR(pr.bloqueadores, ataque ? "Bloqueador" : "Defensor del bloqueador", pr.ppp, fase);
  html += titulo(ataque ? "Parejas manejador - bloqueador" : "Parejas de defensores") + tablaPR(pr.parejas, "Pareja", pr.ppp, fase);
  html += titulo("Uso por tipo de defensa del P&R") + tablaPR(pr.defensa_pr, "Defensa del P&R", pr.ppp, fase);

  // Analizador individual
  const ids = Object.keys(pr.analizador ?? {});
  if (ids.length) {
    html += titulo("🔍 Analizador individual");
    const elegido = estado(`pr_jugador_${fase}`, ids[0], ids);
    html += selector(`pr_jugador_${fase}`, ids.map((j) => [j, nombreJugador(Number(j))]), elegido);
    const a = pr.analizador[elegido];
    html += nota(`${esc(nombreJugador(Number(elegido)))} participa en ${a.n} P&R (${num(a.f, 0)}% del total) · ${num(a.ppp, 2)} PPP${ataque ? "" : " permitido"}. En estas tablas la frecuencia es sobre sus P&R.`);
    html += `<div class="nota"><b>Rol en el P&R</b></div>` + tablaPR(a.rol, "Rol", pr.ppp, fase);
    html += `<div class="nota"><b>Parejas</b></div>` + tablaPR(a.parejas, "Pareja", pr.ppp, fase);
    html += `<div class="nota"><b>Ante cada tipo de defensa del P&R</b></div>` + tablaPR(a.defensa_pr, "Defensa del P&R", pr.ppp, fase);
  }
  return html;
}

// Tabla de un cuarto con la frecuencia y el PPP de todo el partido entre paréntesis
function tablaCuarto(filas, totales, cabecera) {
  if (!filas?.length) return `<div class="vacio">Sin posesiones etiquetadas en este periodo.</div>`;
  const total = Object.fromEntries((totales ?? []).map((f) => [f.g, f]));
  return tabla([cabecera, { t: "Pos.", def: DEF_POSESIONES },
    { t: "Frec.", def: "% de las posesiones etiquetadas del periodo (entre paréntesis, en todo el partido)." },
    { t: "PPP", def: "PPP en el periodo (entre paréntesis, en todo el partido)." }],
  filas.map((f) => {
    const t = total[f.g];
    return [esc(f.g), f.n, `${barra(f.f)}${media(t ? pct(t.f) : "0%")}`, `${ppp(f.ppp, t?.ppp)}${media(t ? num(t.ppp, 2) : "-")}`];
  }));
}

function tablaUso(filas) {
  const columnas = [["%USG", true], ["PPP", false], ["TS%", true], ["Puntos p100", false]];
  const conUso = (filas ?? []).filter((f) => (f.v["%USG"]?.[0] ?? 0) > 0).sort((a, b) => b.v["%USG"][0] - a.v["%USG"][0]);
  if (!conUso.length) return `<div class="vacio">Sin jugadores con uso en este periodo.</div>`;
  return tabla(["Jugador", ...columnas.map(([c]) => ({ t: c, def: META.def_jugador?.[c] ?? c }))], conUso.map((f) => ({
    celdas: [esc(nombreJugador(f.id)), ...columnas.map(([c, esPct]) => {
      const [v, ref] = f.v[c] ?? [];
      if (vacio(v)) return "-";
      const margen = c === "PPP" ? 0.05 : Math.max(Math.abs(ref ?? 0) * 0.05, 0.01);
      return `<span class="${claseComparada(v, ref, true, margen)}">${valorStat(v, c, esPct)}</span>${media(vacio(ref) ? "-" : valorStat(ref, c, esPct))}`;
    })],
    ir: `#/propio/individual/${f.id}`,
  }))) + nota("Play by play de la federación (todos los partidos). Entre paréntesis, la media del jugador en el partido completo.");
}

const cabeceraPosesiones = (d, texto = "posesiones etiquetadas", sufijo = "PPP") =>
  `<div class="cifras tarjeta"><div><div class="valor">${d.n}</div><div class="etiqueta">${texto}</div></div>
    <div><div class="valor">${num(d.ppp, 2)}</div><div class="etiqueta">${sufijo}</div></div></div>`;

// ====================================================================== QUINTETOS: MEJORES Y PEORES COMBINACIONES
function* combinaciones(lista, k, desde = 0, actual = []) {
  if (actual.length === k) { yield actual; return; }
  for (let i = desde; i < lista.length; i++) yield* combinaciones(lista, k, i + 1, [...actual, lista[i]]);
}

const PUNTOS_JUGADA = { 93: 2, 100: 2, 94: 3, 92: 1 };

// Como ranking_combinaciones de la app: para cada combinación de `tamano` jugadores, ratings con ella en pista y sin ella
function rankingCombinaciones(enPista, tamano, minimo) {
  // Vector por quinteto: FGA, FTA, TOV, OREB, PTS propios y los mismos del rival
  const porQuinteto = enPista.quintetos.map(() => new Array(10).fill(0));
  for (const [q, lado, jugada] of enPista.ev) {
    if (lado === -1 || !jugada) continue;
    const v = porQuinteto[q], o = lado === 1 ? 0 : 5;
    if ([93, 100, 97, 94, 98].includes(jugada)) v[o] += 1;
    if (jugada === 92 || jugada === 96) v[o + 1] += 1;
    if (jugada === 106) v[o + 2] += 1;
    if (jugada === 101) v[o + 3] += 1;
    v[o + 4] += PUNTOS_JUGADA[jugada] ?? 0;
  }
  const total = new Array(10).fill(0);
  const acumulado = new Map();
  enPista.quintetos.forEach((ids, q) => {
    porQuinteto[q].forEach((x, i) => { total[i] += x; });
    for (const combo of combinaciones([...ids].sort((a, b) => a - b), tamano)) {
      const clave = combo.join(",");
      const v = acumulado.get(clave) ?? new Array(10).fill(0);
      porQuinteto[q].forEach((x, i) => { v[i] += x; });
      acumulado.set(clave, v);
    }
  });
  const ratings = (v) => {
    const pos = ((v[0] + 0.44 * v[1] + v[2] - v[3]) + (v[5] + 0.44 * v[6] + v[7] - v[8])) / 2;
    return pos > 0 ? [pos, (v[4] / pos) * 100, (v[9] / pos) * 100] : null;
  };
  const filas = [];
  for (const [clave, vOn] of acumulado) {
    const on = ratings(vOn), off = ratings(total.map((x, i) => x - vOn[i]));
    if (!on || !off || on[0] < minimo || off[0] < minimo) continue;
    filas.push({ combo: clave.split(",").map(Number), pos: on[0],
      ORtg: [on[1], off[1]], DRtg: [on[2], off[2]], NetRtg: [on[1] - on[2], off[1] - off[2]] });
  }
  return filas;
}

function htmlTopCombinaciones(enPista) {
  let html = titulo("🏆 Mejores y peores combinaciones");
  html += nota("Diferencial = rating del equipo con la combinación en pista menos sin ella. Pos. = posesiones con la combinación en pista. Play by play de la federación.");
  const tamano = estado("top_tamano", "5", ["1", "2", "3", "4", "5"]);
  const minimo = estado("top_minimo", "20", ["5", "10", "20", "30", "50", "100"]);
  html += `<div class="nota"><b>Jugadores en la combinación</b></div>` + chips("top_tamano", ["1", "2", "3", "4", "5"].map((n) => [n, n]), tamano);
  html += `<div class="nota"><b>Mínimo de posesiones (en pista y fuera)</b></div>` + chips("top_minimo", ["5", "10", "20", "30", "50", "100"].map((n) => [n, n]), minimo);
  const filas = rankingCombinaciones(enPista, Number(tamano), Number(minimo));
  if (!filas.length) return html + `<div class="vacio">No hay combinaciones con suficientes posesiones. Baja el mínimo de posesiones.</div>`;
  if (filas.length < 6) html += nota(`Solo ${filas.length} combinaciones llegan al mínimo de posesiones: las listas no repiten combinaciones.`);
  const corto = (id) => {
    const j = META.jugadores[id];
    return j ? `${j[0]} ${j[1].split(" ").at(-1)}` : String(id);
  };
  const metricas = [["ORtg", "Diferencial Offensive Rating", true], ["DRtg", "Diferencial Defensive Rating", false], ["NetRtg", "Diferencial Net Rating", true]];
  for (const [clave, nombre, mayor] of metricas) {
    const dif = (f) => f[clave][0] - f[clave][1];
    const ordenadas = filas.slice().sort((a, b) => (mayor ? dif(b) - dif(a) : dif(a) - dif(b)));
    const mejores = ordenadas.slice(0, 3);
    const peores = ordenadas.slice(mejores.length).slice(-3).reverse();
    html += titulo(nombre);
    for (const [lista, datos] of [["🟢 Mejores", mejores], ["🔴 Peores", peores]]) {
      html += `<div class="nota"><b>${lista}</b></div>`;
      html += datos.length ? tabla(["Jugadores", "Pos.", "On", "Off", "Dif."], datos.map((f) => {
        const d = dif(f);
        const bueno = mayor ? d > 0 : d < 0;
        return [`<span style="white-space:normal;font-size:0.75rem">${esc(f.combo.map(corto).join(", "))}</span>`, num(f.pos, 0),
          num(f[clave][0]), num(f[clave][1]), `<span class="${bueno ? "verde" : "rojo"}">${signo(d)}</span>`];
      })) : nota("No hay más combinaciones con el mínimo de posesiones.");
    }
  }
  return html;
}

// ====================================================================== ATAQUE
async function htmlAtaque(sub, at, equipo) {
  let html = subpestanas(ATAQUE, sub, "#/propio/ataque");
  if (sub === "uso") {
    html += nota("Igual que en Liga: calculado con el play by play de la federación (no depende del etiquetado). Las líneas marcan la media de los jugadores del equipo.");
    return html + usoEficiencia(equipo.individuales.filter((f) => !vacio(f.v["%USG"]?.[0]) && !vacio(f.v.PPP?.[0]))
      .map((f) => ({ id: f.id, usg: f.v["%USG"][0], ppp: f.v.PPP[0] })));
  }
  if (!at) return html + SIN_ATAQUE;
  html += cabeceraPosesiones(at);

  if (sub === "playtypes") {
    const modo = estado("pt_modo", "principal", ["principal", "secundario"]);
    html += titulo("Playtypes: frecuencia y eficiencia");
    html += chips("pt_modo", [["principal", "Solo principal"], ["secundario", "Principal + secundario"]], modo);
    const filas = modo === "principal" ? at.playtypes : at.playtypes_con_secundario;
    html += tablaResumen(filas, "Playtype", at.ppp);
    if (modo === "secundario") html += nota("Una posesión cuenta en su playtype principal y en el secundario, así que las frecuencias suman más del 100%: indican en qué % de posesiones aparece cada playtype.");
    html += burbujas(filas, at.ppp) + nota("Toca una burbuja para ver sus datos. La línea marca el PPP medio del equipo.");
    html += titulo("Secondary playtypes") + tablaSecundarios(at.secundarios, at.ppp, "playtypes");
  } else if (sub === "pr") {
    html += htmlPR(at.pr, "ataque");
  } else if (sub === "tipo_defensa") {
    html += titulo("Frecuencia y eficiencia contra cada tipo de defensa");
    html += nota("Frecuencia: % de nuestras posesiones etiquetadas contra cada defensa del rival. El color del PPP compara con el PPP medio del equipo.");
    html += tablaResumen(at.tipo_defensa, "Tipo de defensa", at.ppp) + burbujas(at.tipo_defensa, at.ppp);
  } else if (sub === "finalizador") {
    const dim = estado("fin_dim", "Playtype", ["Playtype", "Sistema"]);
    const mapa = at.finalizador_mapa[dim];
    html += chips("fin_dim", [["Playtype", "Playtype"], ["Sistema", "Sistema"]], dim);
    html += titulo(`PPP por ${dim.toLowerCase()} y jugador que finaliza`);
    html += nota(`Cada casilla: PPP de ese jugador en ese ${dim.toLowerCase()} (posesiones entre paréntesis). Verde por encima de la media del equipo (${num(at.ppp, 2)}), rojo por debajo.`);
    html += mapaCalor(mapa, at.ppp);
    const categoria = estado(`fin_cat_${dim}`, mapa.columnas[0], mapa.columnas);
    const j = mapa.columnas.indexOf(categoria);
    const filas = mapa.filas.map((g, i) => ({ g, n: mapa.n[i][j], ppp: mapa.ppp[i][j] })).filter((f) => !vacio(f.n)).sort((a, b) => b.n - a.n);
    const total = filas.reduce((s, f) => s + f.n, 0);
    const pppCat = filas.reduce((s, f) => s + f.ppp * f.n, 0) / total;
    filas.forEach((f) => { f.f = (f.n / total) * 100; });
    html += titulo(`Detalle de un ${dim.toLowerCase()}`) + selector(`fin_cat_${dim}`, mapa.columnas.map((c) => [c, c]), categoria);
    html += nota(`${total} posesiones de ${esc(categoria)} · ${num(pppCat, 2)} PPP. Frecuencia: % de esas posesiones que finaliza cada jugador. El color compara con el PPP de ese ${dim.toLowerCase()}.`);
    html += tablaResumen(filas, "Finaliza", pppCat);
  } else if (sub === "tiro") {
    const cancha = await cargar("cancha.json");
    const tiradores = [...new Set(at.tiros.map((t) => t[5]).filter((x) => x !== null))]
      .sort((a, b) => at.tiros.filter((t) => t[5] === b).length - at.tiros.filter((t) => t[5] === a).length);
    const elegido = estado("at_tirador", "todos", ["todos", ...tiradores.map(String)]);
    html += selector("at_tirador", [["todos", "Todo el equipo"], ...tiradores.map((x) => [String(x), nombreJugador(x)])], elegido);
    const { html: controles, opciones } = controlesCarta("at_carta");
    const seleccion = elegido === "todos" ? at.tiros : at.tiros.filter((t) => t[5] === Number(elegido));
    html += controles + nota(`${elegido === "todos" ? "Todo el equipo" : esc(nombreJugador(Number(elegido)))}: ${seleccion.length} tiros de campo con localización.`);
    html += cartaTiro(cancha, seleccion, null, opciones);
  } else {
    // Sistemas
    html += titulo("Frecuencia y eficiencia por sistema");
    html += nota("Frecuencia: % de las posesiones etiquetadas en las que se juega ese sistema.");
    html += tablaResumen(at.sistemas, "Sistema", at.ppp);
    const sistemas = at.sistemas.map((f) => f.g);
    const sistema = estado("pr_sistema", sistemas[0], sistemas);
    const d = at.sistema_detalle[sistema];
    html += titulo("¿Cómo se finaliza cada sistema?") + selector("pr_sistema", sistemas.map((s) => [s, s]), sistema);
    html += nota(`${d.n} posesiones ${sistema === "Sin sistema" ? "sin sistema" : `con ${esc(sistema)}`} · ${num(d.ppp, 2)} PPP. Frecuencia es el % de esas posesiones y el color compara con el PPP del sistema.`);
    html += `<div class="nota"><b>Con qué playtype</b></div>` + tablaResumen(d.playtypes, "Playtype final", d.ppp);
    html += `<div class="nota"><b>Quién lo finaliza</b></div>` + tablaResumen(d.finaliza, "Finaliza", d.ppp);
    html += `<div class="nota"><b>Quién lo finaliza y con qué playtype</b></div>` + tablaResumen(d.jugador_playtype, "Jugador · Playtype", d.ppp);
    html += `<div class="nota"><b>Secondary playtypes: qué playtype principal generan</b></div>` + tablaSecundarios(d.secundarios, d.ppp, "sistema");
  }
  return html;
}

// ====================================================================== DEFENSA
async function htmlDefensa(sub, df) {
  let html = subpestanas(DEFENSA, sub, "#/propio/defensa");
  if (!df) return html + SIN_DEFENSA;
  html += cabeceraPosesiones(df, "posesiones del rival", "PPP permitido");
  const plantilla = jugadoresEnQuintetos(df.quintetos);

  if (sub === "tiro") {
    html += titulo("¿Desde dónde nos tiran según quién está en pista?");
    const enPista = elegidosDe("def_tiro");
    html += nota("Jugadores en pista (ninguno = todo el equipo), hasta 5.") + chipsJugadores("def_tiro", plantilla, enPista);
    const cancha = await cargar("cancha.json");
    const conEllos = (t) => enPista.every((j) => df.quintetos[t[5]].includes(j));
    const tirosOn = df.tiros.filter(conEllos);
    const tirosOff = enPista.length ? df.tiros.filter((t) => !conEllos(t)) : null;
    if (enPista.length) html += nota(`${tirosOn.length} tiros del rival con ellos en pista (On) y ${tirosOff.length} sin ellos (Off).`);
    const { html: controles, opciones } = controlesCarta("def_carta");
    html += controles + cartaTiro(cancha, tirosOn, tirosOff, { ...opciones, mayorEsMejor: false });
  } else if (sub === "pr") {
    html += htmlPR(df.pr, "defensa");
  } else if (sub === "uno") {
    html += nota("Para cada jugador que ha sido el defensor directo (dPlayer) al menos una vez: cuántas veces, en qué % de las posesiones del rival con él en pista le ha tocado defender esa acción y los PPP que encaja. El color compara con el PPP del rival en esa acción contra todo el equipo (verde = encaja menos).");
    for (const [playtype, d] of Object.entries(df.uno_contra_uno)) {
      html += titulo(playtype);
      html += d.filas.length ? tabla(["Defensor", { t: "Acciones", def: `Posesiones de ${playtype} del rival en las que fue el dPlayer.` },
        { t: "Pos. en pista", def: "Posesiones del rival (etiquetadas) con el jugador en pista." },
        { t: "% defendidas", def: `Porcentaje de esas posesiones en las que le tocó defender un ${playtype}.` },
        { t: "Puntos", def: "Puntos encajados en esas acciones." },
        { t: "PPP encajados", def: "Puntos por posesión encajados en esas acciones. Cuanto más bajo, mejor." }],
      d.filas.map((f) => [esc(f.g), f.n, f.en_pista, barra(f.pct), f.pts, ppp(f.ppp, d.ppp_equipo, false)]))
        + nota(`${d.n} posesiones de ${playtype} con dPlayer · PPP del rival en ${playtype} contra todo el equipo: ${num(d.ppp_equipo, 2)}.`)
        : `<div class="vacio">Ninguna posesión de ${playtype} del rival tiene indicado el dPlayer.</div>`;
    }
  } else if (sub === "tipo") {
    html += titulo("Eficiencia del rival por tipo de defensa");
    html += tablaResumen(df.tipo_defensa, "Tipo de defensa", df.ppp, false);
  } else {
    // Playtypes por quinteto
    html += titulo("¿Cómo nos anotan según quién está en pista?");
    const enPista = elegidosDe("def_q");
    html += nota("Jugadores en pista (ninguno = todo el equipo), hasta 5.") + chipsJugadores("def_q", plantilla, enPista);
    const posesiones = df.posesiones.filter(([, , q]) => enPista.every((j) => df.quintetos[q].includes(j)));
    const filas = resumenPosesiones(posesiones, df.playtypes_lista);
    if (enPista.length) {
      const pppSel = posesiones.length ? posesiones.reduce((s, p) => s + p[1], 0) / posesiones.length : NaN;
      html += nota(`Con ellos en pista: <b>${posesiones.length} posesiones</b>, <span class="${claseComparada(pppSel, df.ppp, false, 0.05)}">${num(pppSel, 2)} PPP permitido</span> (equipo: ${num(df.ppp, 2)}).`);
    }
    html += tablaResumen(filas, "Playtype del rival", df.ppp, false) + burbujas(filas, df.ppp, "PPP permitido");
  }
  return html;
}

// ====================================================================== CUARTOS
function htmlCuartosPropio(datos, equipo) {
  const at = datos.ataque;
  return htmlCuartos(equipo, (etiqueta, filasIndiv) => {
    const q = datos.cuartos[etiqueta];
    let extra = "";
    if (at) {
      extra += nota(q ? `${periodoCorto(etiqueta)}: ${q.n} posesiones etiquetadas · ${num(q.ppp, 2)} PPP (en todo el partido: ${num(at.ppp, 2)}).`
        : "Sin posesiones etiquetadas en este periodo.");
      extra += titulo("Sistemas: frecuencia y eficiencia") + tablaCuarto(q?.sistemas, at.sistemas, "Sistema");
      extra += titulo("Playtypes: frecuencia y eficiencia") + tablaCuarto(q?.playtypes, at.playtypes, "Playtype");
    }
    extra += titulo("Jugadores: uso y eficiencia") + tablaUso(filasIndiv);
    const conUso = (filasIndiv ?? []).filter((f) => (f.v["%USG"]?.[0] ?? 0) > 0 && !vacio(f.v.PPP?.[0]));
    if (conUso.length > 1) extra += usoEficiencia(conUso.map((f) => ({ id: f.id, usg: f.v["%USG"][0], ppp: f.v.PPP[0] })));
    return extra;
  });
}

// ====================================================================== ANÁLISIS INDIVIDUAL
function htmlPlantillaPropio(equipo) {
  const jugadores = equipo.plantilla.slice().sort((a, b) => ordenDorsal(a.dorsal) - ordenDorsal(b.dorsal));
  return `<div class="lista-jugadores">${jugadores.map((j) =>
    `<a class="jugador" href="#/propio/individual/${j.id}">${foto(j.id)}<span class="dorsal">${esc(j.dorsal ?? "-")}</span><span class="nombre">${esc(j.nombre)}</span></a>`).join("")}</div>`;
}

// ====================================================================== ENTRADA
export async function propio(apartado = "quintetos", sub = null, extra = null) {
  if (!APARTADOS.some(([clave]) => clave === apartado)) apartado = "quintetos";
  // Ficha de un jugador dentro de Análisis Individual: Perfil, Impacto, Carta de tiro, Playtypes y Sistemas
  if (apartado === "individual" && sub) return fichaJugador(Number(sub), extra ?? "perfil", `#/propio/individual/${sub}`);

  const [datos, equipo] = await Promise.all([cargar("propio.json"), cargar(`equipos/${META.id_propio}.json`)]);
  let html = pestanas(APARTADOS, apartado, "#/propio");
  if (apartado === "estadistica") html += htmlEstadistica(equipo, "el Atlético");
  else if (apartado === "ataque") html += await htmlAtaque(ATAQUE.some(([c]) => c === sub) ? sub : "sistemas", datos.ataque, equipo);
  else if (apartado === "defensa") html += await htmlDefensa(DEFENSA.some(([c]) => c === sub) ? sub : "quinteto", datos.defensa);
  else if (apartado === "cuartos") html += htmlCuartosPropio(datos, equipo);
  else if (apartado === "individual") html += htmlPlantillaPropio(equipo);
  else html += htmlQuintetos(equipo, META.id_propio) + (equipo.en_pista ? htmlTopCombinaciones(equipo.en_pista) : "");
  return { titulo: "Atlético San Sebastián", html };
}
