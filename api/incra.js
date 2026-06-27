// api/incra.js — Proxy de consulta ao Acervo Fundiário do INCRA (WFS) para o Gestor.
//
// O servidor do INCRA (acervofundiario.incra.gov.br) não envia cabeçalhos CORS,
// então o navegador não consegue consultá-lo diretamente. Esta função roda no
// servidor (Vercel), consulta o WFS, converte o GML em GeoJSON e devolve com CORS
// liberado. Também detecta a UF automaticamente a partir do retângulo (bbox).
//
// Uso: /api/incra?bbox=minLon,minLat,maxLon,maxLat&tema=certificada_sigef_particular[&uf=MS][&max=1000]

// GeoJSON simplificado das UFs (IBGE 2020) — embutido no bundle via require.
const UF_GEO = require('./_data/br_uf.json');

// Camadas (temas) disponíveis no acervo fundiário. O sufixo _<uf> é acrescentado.
const TEMAS = {
  certificada_sigef_particular: 'SIGEF Certificado — Particular',
  certificada_sigef_publico:    'SIGEF Certificado — Público',
  imoveiscertificados_privado:  'SNCI 1ª/2ª Norma — Privado',
  imoveiscertificados_publico:  'SNCI 1ª/2ª Norma — Público',
  assentamentos:                'Assentamentos',
  quilombolas:                  'Quilombolas',
  parcelageo:                   'Parcelas (parcelageo)',
};

const INCRA_BASE = 'https://acervofundiario.incra.gov.br/i3geo/ogc.php';
const MAX_FEATURES_CAP = 2000;

// Ponto-em-polígono (ray casting), coords em [lon,lat].
function pointInRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}
function ufOf(lon, lat) {
  for (const ft of UF_GEO.features) {
    for (const poly of ft.geometry.coordinates) {
      if (pointInRing(lon, lat, poly[0])) return ft.properties.uf;
    }
  }
  return null;
}
// UFs que o retângulo toca (testa centro + 4 cantos).
function ufsDoBbox(minLon, minLat, maxLon, maxLat) {
  const pts = [
    [(minLon + maxLon) / 2, (minLat + maxLat) / 2],
    [minLon, minLat], [minLon, maxLat], [maxLon, minLat], [maxLon, maxLat],
  ];
  const set = [];
  for (const [lon, lat] of pts) {
    const uf = ufOf(lon, lat);
    if (uf && !set.includes(uf)) set.push(uf);
  }
  return set;
}

function parseCoords(str) {
  const ring = [];
  const toks = String(str).trim().split(/\s+/);
  for (const t of toks) {
    const p = t.split(',');
    const lon = parseFloat(p[0]), lat = parseFloat(p[1]);
    if (!isNaN(lon) && !isNaN(lat)) ring.push([lon, lat]);
  }
  return ring;
}

// Converte o GML (WFS 1.0.0 do MapServer/i3geo) em features GeoJSON.
function gmlToFeatures(gml, uf, tema) {
  const features = [];
  const blocks = gml.split('<gml:featureMember>').slice(1);
  for (const block of blocks) {
    // Geometria: 1+ polígonos -> Polygon ou MultiPolygon.
    const polys = [];
    const polyRe = /<gml:Polygon[^>]*>([\s\S]*?)<\/gml:Polygon>/g;
    let pm;
    while ((pm = polyRe.exec(block)) !== null) {
      const pc = pm[1];
      const outerM = pc.match(/<gml:outerBoundaryIs>[\s\S]*?<gml:coordinates>([\s\S]*?)<\/gml:coordinates>/);
      if (!outerM) continue;
      const rings = [parseCoords(outerM[1])];
      const innerRe = /<gml:innerBoundaryIs>[\s\S]*?<gml:coordinates>([\s\S]*?)<\/gml:coordinates>/g;
      let im;
      while ((im = innerRe.exec(pc)) !== null) rings.push(parseCoords(im[1]));
      if (rings[0].length >= 3) polys.push(rings);
    }
    if (!polys.length) continue;
    const geometry = polys.length === 1
      ? { type: 'Polygon', coordinates: polys[0] }
      : { type: 'MultiPolygon', coordinates: polys };

    // Atributos: nós-folha <ms:tag>valor</ms:tag> (exceto a geometria).
    const props = { _uf: uf, _tema: tema };
    const attrRe = /<ms:([A-Za-z0-9_]+)>([^<]*)<\/ms:[A-Za-z0-9_]+>/g;
    let am;
    while ((am = attrRe.exec(block)) !== null) {
      const key = am[1];
      if (key === 'msGeometry') continue;
      props[key] = am[2].trim();
    }
    features.push({ type: 'Feature', properties: props, geometry: geometry });
  }
  return features;
}

async function consultarUf(tema, uf, bboxStr, max) {
  const layer = `${tema}_${uf.toLowerCase()}`;
  const url = `${INCRA_BASE}?tema=${layer}&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature`
    + `&TYPENAME=ms:${layer}&SRSNAME=EPSG:4326&BBOX=${encodeURIComponent(bboxStr)}&MAXFEATURES=${max}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 25000);
  try {
    const resp = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'User-Agent': 'GestorAJTopoGeo/1.0 (consulta acervo fundiario)' },
    });
    const text = await resp.text();
    if (text.indexOf('ServiceException') >= 0) {
      const m = text.match(/<ServiceException[^>]*>([\s\S]*?)<\/ServiceException>/);
      return { uf, erro: (m ? m[1].trim() : 'Erro no servidor do INCRA') };
    }
    return { uf, features: gmlToFeatures(text, uf, tema) };
  } catch (e) {
    return { uf, erro: e.name === 'AbortError' ? 'Tempo esgotado ao consultar o INCRA' : String(e.message || e) };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }

  try {
    const q = req.query || {};
    const tema = String(q.tema || 'certificada_sigef_particular');
    if (!TEMAS[tema]) {
      res.statusCode = 400;
      return res.json({ erro: 'Tema inválido.', temas: Object.keys(TEMAS) });
    }
    const bbox = String(q.bbox || '').split(',').map(Number);
    if (bbox.length !== 4 || bbox.some(isNaN)) {
      res.statusCode = 400;
      return res.json({ erro: 'bbox inválido. Use bbox=minLon,minLat,maxLon,maxLat (EPSG:4326).' });
    }
    let [minLon, minLat, maxLon, maxLat] = bbox;
    if (minLon > maxLon) [minLon, maxLon] = [maxLon, minLon];
    if (minLat > maxLat) [minLat, maxLat] = [maxLat, minLat];

    // Proteção: retângulo grande demais sobrecarrega o servidor do INCRA.
    if ((maxLon - minLon) > 1.0 || (maxLat - minLat) > 1.0) {
      res.statusCode = 400;
      return res.json({ erro: 'Área muito grande. Aproxime o zoom (máx. ~1° de lado) e consulte novamente.' });
    }

    let max = parseInt(q.max, 10);
    if (isNaN(max) || max <= 0) max = 1000;
    if (max > MAX_FEATURES_CAP) max = MAX_FEATURES_CAP;

    const bboxStr = `${minLon},${minLat},${maxLon},${maxLat}`;
    let ufs = q.uf ? [String(q.uf).toUpperCase()] : ufsDoBbox(minLon, minLat, maxLon, maxLat);
    if (!ufs.length) {
      res.statusCode = 422;
      return res.json({ erro: 'Não foi possível identificar a UF do retângulo (fora do Brasil?). Informe &uf=XX.' });
    }

    const resultados = await Promise.all(ufs.map((uf) => consultarUf(tema, uf, bboxStr, max)));
    let features = [];
    const erros = [];
    for (const r of resultados) {
      if (r.features) features = features.concat(r.features);
      if (r.erro) erros.push(`${r.uf}: ${r.erro}`);
    }

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    return res.json({
      type: 'FeatureCollection',
      tema, tema_nome: TEMAS[tema], ufs,
      total: features.length,
      erros: erros.length ? erros : undefined,
      features,
    });
  } catch (e) {
    res.statusCode = 500;
    return res.json({ erro: 'Falha interna: ' + String(e.message || e) });
  }
};
