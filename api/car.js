// api/car.js — Proxy de consulta ao SICAR (Cadastro Ambiental Rural) via GeoServer
// público (geoserver.car.gov.br) para o Gestor. O GeoServer do SICAR não envia
// cabeçalhos CORS, então esta função roda no servidor (Vercel) e devolve o
// GeoJSON liberado para o navegador. Suporta dois modos:
//   - área visível: /api/car?bbox=minLon,minLat,maxLon,maxLat[&max=1000]
//   - imóvel específico: /api/car?cod=UF-XXXXXXX-XXXXXXXX...

const UF_GEO = require('./_data/br_uf.json');

const CAR_BASE = 'https://geoserver.car.gov.br/geoserver/sicar/wfs';
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

async function wfsFetch(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 25000);
  try {
    const resp = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'User-Agent': 'GestorAJTopoGeo/1.0 (consulta SICAR)' },
    });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch (e) {
      const m = text.match(/<ows:ExceptionText>([\s\S]*?)<\/ows:ExceptionText>/) || text.match(/<ServiceException[^>]*>([\s\S]*?)<\/ServiceException>/);
      throw new Error(m ? m[1].trim() : 'Resposta inválida do GeoServer do SICAR.');
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

async function consultarUfArea(uf, bboxStr, max) {
  const layer = `sicar_imoveis_${uf.toLowerCase()}`;
  const url = `${CAR_BASE}?service=WFS&version=1.1.0&request=GetFeature`
    + `&typename=sicar:${layer}&outputFormat=json&srsname=EPSG:4326`
    + `&maxFeatures=${max}&bbox=${encodeURIComponent(bboxStr + ',EPSG:4326')}`;
  try {
    const data = await wfsFetch(url);
    return { uf, features: data.features || [] };
  } catch (e) {
    return { uf, erro: e.name === 'AbortError' ? 'Tempo esgotado ao consultar o SICAR' : String(e.message || e) };
  }
}

async function consultarPorCodigo(cod) {
  const uf = String(cod).split('-')[0].toUpperCase();
  if (!/^[A-Z]{2}$/.test(uf)) throw new Error('Código do imóvel inválido. Use o formato UF-XXXXXXX-XXXXXXXX...');
  const layer = `sicar_imoveis_${uf.toLowerCase()}`;
  const filter = `cod_imovel='${cod.replace(/'/g, "''")}'`;
  const url = `${CAR_BASE}?service=WFS&version=1.1.0&request=GetFeature`
    + `&typename=sicar:${layer}&outputFormat=json&srsname=EPSG:4326`
    + `&CQL_FILTER=${encodeURIComponent(filter)}`;
  const data = await wfsFetch(url);
  return data.features || [];
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }

  try {
    const q = req.query || {};

    // Modo "imóvel específico": consulta por código do CAR (sem depender de bbox).
    if (q.cod) {
      const cod = String(q.cod).trim();
      const features = await consultarPorCodigo(cod);
      res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
      return res.json({ type: 'FeatureCollection', total: features.length, features });
    }

    // Modo "área visível na tela": consulta por bbox (EPSG:4326).
    const bbox = String(q.bbox || '').split(',').map(Number);
    if (bbox.length !== 4 || bbox.some(isNaN)) {
      res.statusCode = 400;
      return res.json({ erro: 'Informe bbox=minLon,minLat,maxLon,maxLat (EPSG:4326) ou cod=<código do imóvel>.' });
    }
    let [minLon, minLat, maxLon, maxLat] = bbox;
    if (minLon > maxLon) [minLon, maxLon] = [maxLon, minLon];
    if (minLat > maxLat) [minLat, maxLat] = [maxLat, minLat];

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

    const resultados = await Promise.all(ufs.map((uf) => consultarUfArea(uf, bboxStr, max)));
    let features = [];
    const erros = [];
    for (const r of resultados) {
      if (r.features) features = features.concat(r.features);
      if (r.erro) erros.push(`${r.uf}: ${r.erro}`);
    }

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    return res.json({
      type: 'FeatureCollection',
      ufs,
      total: features.length,
      erros: erros.length ? erros : undefined,
      features,
    });
  } catch (e) {
    res.statusCode = 500;
    return res.json({ erro: 'Falha interna: ' + String(e.message || e) });
  }
};
