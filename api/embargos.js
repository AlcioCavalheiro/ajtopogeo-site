// api/embargos.js — Proxy de consulta aos Termos de Embargo do IBAMA (SISCOM) via
// o serviço ArcGIS REST público da Plataforma PAMGIA (pamgia.ibama.gov.br), para
// o Gestor. O servidor não libera CORS para o navegador, então a consulta roda
// aqui (Vercel). Os nomes de campo do IBAMA não são fixos entre atualizações da
// base; por isso devolvemos as propriedades tal como vieram, e quem lê (o
// relatório) trata de forma defensiva.
//
// Uso: /api/embargos?bbox=minLon,minLat,maxLon,maxLat

const BASE = 'https://pamgia.ibama.gov.br/server/rest/services/app_dadosabertos/adm_embargo_ibama_a/MapServer/0/query';

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }

  try {
    const q = req.query || {};
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

    const params = new URLSearchParams({
      f: 'geojson',
      geometry: `${minLon},${minLat},${maxLon},${maxLat}`,
      geometryType: 'esriGeometryEnvelope',
      inSR: '4326',
      outSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: '*',
      returnGeometry: 'true',
    });
    const url = `${BASE}?${params.toString()}`;

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 25000);
    let features = [];
    let erro = null;
    try {
      const resp = await fetch(url, {
        signal: ctrl.signal,
        headers: { 'User-Agent': 'GestorAJTopoGeo/1.0 (consulta embargos IBAMA)' },
      });
      const text = await resp.text();
      let data;
      try { data = JSON.parse(text); } catch (e) {
        throw new Error('Resposta inválida do servidor do IBAMA.');
      }
      if (data.error) throw new Error(data.error.message || 'Erro no servidor do IBAMA.');
      features = data.features || [];
    } catch (e) {
      erro = e.name === 'AbortError' ? 'Tempo esgotado ao consultar o IBAMA (SISCOM).' : String(e.message || e);
    } finally {
      clearTimeout(timer);
    }

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    return res.json({
      type: 'FeatureCollection',
      total: features.length,
      erro: erro || undefined,
      features,
    });
  } catch (e) {
    res.statusCode = 500;
    return res.json({ erro: 'Falha interna: ' + String(e.message || e) });
  }
};
