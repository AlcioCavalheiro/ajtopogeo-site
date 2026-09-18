// api/restricoes.js — Proxy de consulta a Terras Indígenas (FUNAI) e Unidades de
// Conservação federais (ICMBio) via GeoServer público, para o Gestor. Nenhum dos
// dois servidores libera CORS, então a consulta roda aqui (Vercel) e devolve o
// GeoJSON liberado para o navegador. Mesmo padrão do api/car.js e api/incra.js.
//
// Uso: /api/restricoes?fonte=funai_ti|icmbio_uc&bbox=minLon,minLat,maxLon,maxLat[&max=1000]

const FONTES = {
  funai_ti: {
    nome: 'Terras Indígenas (FUNAI)',
    url: 'https://geoserver.funai.gov.br/geoserver/ows',
    typename: 'Funai:tis_poligonais',
  },
  icmbio_uc: {
    nome: 'Unidades de Conservação federais (ICMBio)',
    url: 'https://geoservicos.inde.gov.br/geoserver/ICMBio/ows',
    typename: 'ICMBio:limiteucsfederais_a',
  },
};

const MAX_FEATURES_CAP = 2000;

async function wfsFetch(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 25000);
  try {
    const resp = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'User-Agent': 'GestorAJTopoGeo/1.0 (consulta restricoes fundiarias/ambientais)' },
    });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch (e) {
      const m = text.match(/<ows:ExceptionText>([\s\S]*?)<\/ows:ExceptionText>/) || text.match(/<ServiceException[^>]*>([\s\S]*?)<\/ServiceException>/);
      throw new Error(m ? m[1].trim() : 'Resposta inválida do servidor.');
    }
    return data;
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
    const fonte = String(q.fonte || '');
    const cfg = FONTES[fonte];
    if (!cfg) {
      res.statusCode = 400;
      return res.json({ erro: 'fonte inválida.', fontes: Object.keys(FONTES) });
    }

    const bbox = String(q.bbox || '').split(',').map(Number);
    if (bbox.length !== 4 || bbox.some(isNaN)) {
      res.statusCode = 400;
      return res.json({ erro: 'Informe bbox=minLon,minLat,maxLon,maxLat (EPSG:4326).' });
    }
    let [minLon, minLat, maxLon, maxLat] = bbox;
    if (minLon > maxLon) [minLon, maxLon] = [maxLon, minLon];
    if (minLat > maxLat) [minLat, maxLat] = [maxLat, minLat];
    if ((maxLon - minLon) > 2.0 || (maxLat - minLat) > 2.0) {
      res.statusCode = 400;
      return res.json({ erro: 'Área muito grande. Aproxime o zoom (máx. ~2° de lado) e consulte novamente.' });
    }

    let max = parseInt(q.max, 10);
    if (isNaN(max) || max <= 0) max = 500;
    if (max > MAX_FEATURES_CAP) max = MAX_FEATURES_CAP;

    const bboxStr = `${minLon},${minLat},${maxLon},${maxLat},EPSG:4326`;
    const url = `${cfg.url}?service=WFS&version=1.1.0&request=GetFeature`
      + `&typename=${encodeURIComponent(cfg.typename)}&outputFormat=json&srsname=EPSG:4326`
      + `&maxFeatures=${max}&bbox=${encodeURIComponent(bboxStr)}`;

    let features = [];
    let erro = null;
    try {
      const data = await wfsFetch(url);
      features = data.features || [];
    } catch (e) {
      erro = e.name === 'AbortError' ? `Tempo esgotado ao consultar ${cfg.nome}.` : String(e.message || e);
    }

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    return res.json({
      type: 'FeatureCollection',
      fonte, fonte_nome: cfg.nome,
      total: features.length,
      erro: erro || undefined,
      features,
    });
  } catch (e) {
    res.statusCode = 500;
    return res.json({ erro: 'Falha interna: ' + String(e.message || e) });
  }
};
