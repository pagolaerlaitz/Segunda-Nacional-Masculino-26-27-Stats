// Filtros elegidos en cada pantalla (pestaña de categoría, periodo, sistema...). Se mantienen mientras la app
// está abierta; las vistas leen aquí su valor con uno por defecto.
export const ESTADO = {};

export function estado(clave, porDefecto, validos = null) {
  const valor = ESTADO[clave];
  if (valor === undefined || (validos && !validos.includes(valor))) return porDefecto;
  return valor;
}
