// Sección del Atlético: estadística, sistemas, playtypes, P&R, defensa y cuartos (posesiones etiquetadas).
import { estado } from "./estado.js";
import {
  META, barra, cargar, chips, esc, media, nombreJugador, nota, num, ordenDorsal, pct, pestanas, ppp, selector, tabla, titulo,
  vacio, valorStat, claseComparada,
} from "./base.js";
import { chipsJugadores, controlesCarta, elegidosDe, htmlCuartos, htmlEstadistica, periodoCorto } from "./liga.js";
import { burbujas, cartaTiro, mapaCalor, usoEficiencia } from "./graficos.js";

// Jugadores del Atlético que aparecen en una lista de quintetos, ordenados por dorsal
function jugadoresEnQuintetos(quintetos) {
  return [...new Set(quintetos.flat())].sort((a, b) => ordenDorsal(META.jugadores[a]?.[0]) - ordenDorsal(META.jugadores[b]?.[0]));
}

const DEF_POSESIONES = "Finales de posesión etiquetados: tiro de campo, pérdida o falta con tiros libres.";
const DEF_PPP = "Puntos por posesión.";

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
  let html = nota(`${pr.n} posesiones de P&R · ${num(pr.ppp, 2)} PPP${ataque ? "" : " permitido"}. El color compara con ese PPP medio${ataque ? "" : " (verde = el rival anota menos)"}.`);
  html += titulo(ataque ? "Manejadores" : "Defensores del manejador") + tablaPR(pr.manejadores, ataque ? "Manejador" : "Defensor", pr.ppp, fase);
  html += titulo(ataque ? "Bloqueadores" : "Defensores del bloqueador") + tablaPR(pr.bloqueadores, ataque ? "Bloqueador" : "Defensor", pr.ppp, fase);
  html += titulo("Parejas") + tablaPR(pr.parejas, "Pareja", pr.ppp, fase);
  html += titulo("Por tipo de defensa del P&R") + tablaPR(pr.defensa_pr, "Defensa", pr.ppp, fase);
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
    ir: `#/jugador/${f.id}`,
  }))) + nota("Play by play de la federación (todos los partidos). Entre paréntesis, la media del jugador en el partido completo.");
}

export async function propio(pestana = "estadistica") {
  const [datos, equipo] = await Promise.all([cargar("propio.json"), cargar(`equipos/${META.id_propio}.json`)]);
  const at = datos.ataque;
  const df = datos.defensa;
  let html = pestanas([["estadistica", "📈 Estadística"], ["sistemas", "🧩 Sistemas"], ["playtypes", "🎯 Playtypes"],
    ["finalizador", "👤 Por finalizador"], ["uso", "📊 Uso"], ["tiro", "🏀 Carta de tiro"], ["pr", "🤝 P&R"],
    ["defensa", "🛡️ Defensa"], ["cuartos", "⏱️ Cuartos"]], pestana, "#/propio");
  const sinAtaque = `<div class="vacio">Todavía no hay posesiones de ataque etiquetadas.</div>`;

  if (pestana === "sistemas") {
    if (!at) return { titulo: "Atlético", html: html + sinAtaque };
    html += nota(`${at.n} posesiones etiquetadas · ${num(at.ppp, 2)} PPP. El color compara con el PPP medio del equipo.`);
    html += titulo("Frecuencia y eficiencia por sistema") + tablaResumen(at.sistemas, "Sistema", at.ppp);
    const sistemas = at.sistemas.map((f) => f.g);
    const sistema = estado("pr_sistema", sistemas[0], sistemas);
    const d = at.sistema_detalle[sistema];
    html += titulo("¿Cómo se finaliza cada sistema?") + selector("pr_sistema", sistemas.map((s) => [s, s]), sistema);
    html += nota(`${d.n} posesiones ${sistema === "Sin sistema" ? "sin sistema" : `con ${esc(sistema)}`} · ${num(d.ppp, 2)} PPP. El color compara con el PPP del sistema.`);
    html += `<div class="nota"><b>Con qué playtype</b></div>` + tablaResumen(d.playtypes, "Playtype", d.ppp);
    html += `<div class="nota"><b>Quién lo finaliza</b></div>` + tablaResumen(d.finaliza, "Finaliza", d.ppp);
    html += `<div class="nota"><b>Quién y con qué playtype</b></div>` + tablaResumen(d.jugador_playtype, "Jugador · Playtype", d.ppp);
    html += `<div class="nota"><b>Secondary playtypes</b></div>` + tablaSecundarios(d.secundarios, d.ppp, "sistema");
  } else if (pestana === "playtypes") {
    if (!at) return { titulo: "Atlético", html: html + sinAtaque };
    const modo = estado("pt_modo", "principal", ["principal", "secundario"]);
    html += titulo("Frecuencia y eficiencia");
    html += chips("pt_modo", [["principal", "Solo principal"], ["secundario", "Principal + secundario"]], modo);
    const filasPt = modo === "principal" ? at.playtypes : at.playtypes_con_secundario;
    html += tablaResumen(filasPt, "Playtype", at.ppp);
    if (modo === "secundario") html += nota("Cada posesión cuenta en su playtype principal y en el secundario: las frecuencias suman más del 100%.");
    html += burbujas(filasPt, at.ppp) + nota("Toca una burbuja para ver sus datos. La línea marca el PPP medio del equipo.");
    html += titulo("Secondary playtypes") + tablaSecundarios(at.secundarios, at.ppp, "playtypes");
    html += titulo("Ante cada tipo de defensa") + tablaResumen(at.tipo_defensa, "Defensa rival", at.ppp) + burbujas(at.tipo_defensa, at.ppp);
  } else if (pestana === "finalizador") {
    if (!at) return { titulo: "Atlético", html: html + sinAtaque };
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
    html += nota(`${total} posesiones de ${esc(categoria)} · ${num(pppCat, 2)} PPP. El color compara con ese PPP.`);
    html += tablaResumen(filas, "Finaliza", pppCat);
  } else if (pestana === "uso") {
    html += nota("Calculado con el play by play de la federación (todos los partidos, no depende del etiquetado).");
    html += usoEficiencia(equipo.individuales.filter((f) => !vacio(f.v["%USG"]?.[0]) && !vacio(f.v.PPP?.[0]))
      .map((f) => ({ id: f.id, usg: f.v["%USG"][0], ppp: f.v.PPP[0] })));
  } else if (pestana === "tiro") {
    if (!at) return { titulo: "Atlético", html: html + sinAtaque };
    const cancha = await cargar("cancha.json");
    const tiradores = [...new Set(at.tiros.map((t) => t[5]).filter((j) => j !== null))]
      .sort((a, b) => at.tiros.filter((t) => t[5] === b).length - at.tiros.filter((t) => t[5] === a).length);
    const elegido = estado("at_tirador", "todos", ["todos", ...tiradores.map(String)]);
    html += selector("at_tirador", [["todos", "Todo el equipo"], ...tiradores.map((j) => [String(j), nombreJugador(j)])], elegido);
    const { html: controles, opciones } = controlesCarta("at_carta");
    const seleccion = elegido === "todos" ? at.tiros : at.tiros.filter((t) => t[5] === Number(elegido));
    html += controles + nota(`${elegido === "todos" ? "Todo el equipo" : esc(nombreJugador(Number(elegido)))}: ${seleccion.length} tiros de campo con localización.`);
    html += cartaTiro(cancha, seleccion, null, opciones);
  } else if (pestana === "pr") {
    const fase = estado("pr_fase", "ataque", ["ataque", "defensa"]);
    html += chips("pr_fase", [["ataque", "⚔️ Ataque"], ["defensa", "🛡️ Defensa"]], fase);
    html += htmlPR(fase === "ataque" ? at?.pr : df?.pr, fase);
  } else if (pestana === "defensa") {
    if (!df) return { titulo: "Atlético", html: html + `<div class="vacio">Todavía no hay posesiones de defensa etiquetadas.</div>` };
    html += nota(`${df.n} posesiones del rival etiquetadas · ${num(df.ppp, 2)} PPP permitido. Verde = el rival anota menos que su media.`);
    const plantilla = jugadoresEnQuintetos(df.quintetos);

    // ¿Cómo nos anotan según quién está en pista?
    html += titulo("¿Cómo nos anotan según quién está en pista?");
    const enPistaQ = elegidosDe("def_q");
    html += nota("Elige hasta 5 jugadores (ninguno = todo el equipo).") + chipsJugadores("def_q", plantilla, enPistaQ);
    const conEllos = (indice) => enPistaQ.every((j) => df.quintetos[indice].includes(j));
    const posesiones = df.posesiones.filter(([, , q]) => conEllos(q));
    const filasPt = resumenPosesiones(posesiones, df.playtypes_lista);
    if (enPistaQ.length) {
      const pppSel = posesiones.length ? posesiones.reduce((s, p) => s + p[1], 0) / posesiones.length : NaN;
      html += nota(`Con ellos en pista: <b>${posesiones.length} posesiones</b>, <span class="${claseComparada(pppSel, df.ppp, false, 0.05)}">${num(pppSel, 2)} PPP permitido</span> (equipo: ${num(df.ppp, 2)}).`);
    }
    html += tablaResumen(filasPt, "Playtype rival", df.ppp, false) + burbujas(filasPt, df.ppp, "PPP permitido");

    // ¿Desde dónde nos tiran según quién está en pista?
    html += titulo("¿Desde dónde nos tiran según quién está en pista?");
    const enPistaT = elegidosDe("def_tiro");
    html += chipsJugadores("def_tiro", plantilla, enPistaT);
    const cancha = await cargar("cancha.json");
    const tirosOn = df.tiros.filter((t) => enPistaT.every((j) => df.quintetos[t[5]].includes(j)));
    const tirosOff = enPistaT.length ? df.tiros.filter((t) => !enPistaT.every((j) => df.quintetos[t[5]].includes(j))) : null;
    if (enPistaT.length) html += nota(`${tirosOn.length} tiros del rival con ellos en pista (On) y ${tirosOff.length} sin ellos (Off).`);
    const { html: controles, opciones } = controlesCarta("def_carta");
    html += controles + cartaTiro(cancha, tirosOn, tirosOff, { ...opciones, mayorEsMejor: false });

    html += titulo("Por tipo de defensa") + tablaResumen(df.tipo_defensa, "Tipo de defensa", df.ppp, false);
    for (const [playtype, d] of Object.entries(df.uno_contra_uno)) {
      html += titulo(`${playtype}: defensores`);
      html += d.filas.length ? tabla(["Defensor", { t: "Acc.", def: `Posesiones de ${playtype} del rival en las que fue el dPlayer.` },
        { t: "En pista", def: "Posesiones del rival (etiquetadas) con el jugador en pista." },
        { t: "% defend.", def: `% de esas posesiones en las que le tocó defender un ${playtype}.` },
        { t: "PPP", def: "Puntos por posesión encajados en esas acciones (más bajo es mejor)." }],
      d.filas.map((f) => [esc(f.g), f.n, f.en_pista, barra(f.pct), ppp(f.ppp, d.ppp_equipo, false)]))
        + nota(`PPP del rival en ${playtype} contra todo el equipo: ${num(d.ppp_equipo, 2)}.`)
        : `<div class="vacio">Ninguna posesión de ${playtype} tiene indicado el dPlayer.</div>`;
    }
  } else if (pestana === "cuartos") {
    html += htmlCuartos(equipo, (etiqueta, filasIndiv) => {
      const q = datos.cuartos[etiqueta];
      let extra = "";
      if (at) {
        extra += nota(q ? `${periodoCorto(etiqueta)}: ${q.n} posesiones etiquetadas · ${num(q.ppp, 2)} PPP (en todo el partido: ${num(at.ppp, 2)}).`
          : "Sin posesiones etiquetadas en este periodo.");
        extra += titulo("Sistemas") + tablaCuarto(q?.sistemas, at.sistemas, "Sistema");
        extra += titulo("Playtypes") + tablaCuarto(q?.playtypes, at.playtypes, "Playtype");
      }
      extra += titulo("Jugadores: uso y eficiencia") + tablaUso(filasIndiv);
      const conUso = (filasIndiv ?? []).filter((f) => (f.v["%USG"]?.[0] ?? 0) > 0 && !vacio(f.v.PPP?.[0]));
      if (conUso.length > 1) extra += usoEficiencia(conUso.map((f) => ({ id: f.id, usg: f.v["%USG"][0], ppp: f.v.PPP[0] })));
      return extra;
    });
  } else {
    html += htmlEstadistica(equipo, "el Atlético");
  }
  return { titulo: "Atlético San Sebastián", html };
}
