/* Relatório da Fazenda — gerado no navegador (Gestor AJ TopoGeo).
 *
 * Porte do gerador que rodava no programa do computador (Python + GDAL). Aqui
 * tudo roda no navegador de quem usa o Gestor:
 *
 *   perímetro ............... KML/KMZ (DOMParser, JSZip), DXF (dxf-parser) ou
 *                            shapefile .zip (shpjs); DXF sem coordenadas em
 *                            graus é tratado como SIRGAS 2000/UTM na zona
 *                            informada na aba
 *   prioridade do perímetro . se o SIGEF ou o CAR sobreposto ao perímetro
 *                            enviado for MAIOR que ele, o relatório troca para
 *                            o oficial (SIGEF > CAR > enviado) e reconsulta
 *                            tudo sobre essa geometria — ver RF.gerar
 *   CAR e SIGEF ............ proxies /api/car e /api/incra (os servidores do
 *                            governo não liberam CORS)
 *   Sentinel-2 ............. catálogo STAC + GeoTIFF remoto (geotiff.js), só os
 *                            blocos que cobrem o imóvel descem
 *   relevo ................. Copernicus GLO-30 pelo espelho do OpenTopography
 *                            (o bucket original da AWS não libera CORS)
 *   chuva .................. NASA POWER
 *   valor da terra ......... /gestor/dados/*.csv (VTN 2026 da Receita, RAMT MS
 *                            2024 do INCRA, módulo fiscal)
 *   PDF .................... jsPDF + autoTable, nas cores da AJ
 *
 * O que foi conferido contra o dado real no programa do computador continua
 * valendo aqui (ver gestor/relatorio-fazenda/README.md): NDVI direto do número
 * digital (o offset da baseline 04.00 já vem removido), CAR com bbox lon,lat e
 * município/módulo fiscal tirados do próprio CAR, lasca de divisa abaixo de
 * 100 m² descartada, cena mais recente sem nuvem SOBRE O IMÓVEL.
 */
(function () {
  'use strict';

  const RF = (window.RelFaz = window.RelFaz || {});

  // ------------------------------------------------------------ configuração

  const LIBS = {
    GeoTIFF: 'https://cdn.jsdelivr.net/npm/geotiff@2.1.3/dist-browser/geotiff.js',
    polygonClipping: 'https://cdn.jsdelivr.net/npm/polygon-clipping@0.15.7/dist/polygon-clipping.umd.min.js',
    d3array: 'https://cdn.jsdelivr.net/npm/d3-array@3.2.4/dist/d3-array.min.js',
    d3contour: 'https://cdn.jsdelivr.net/npm/d3-contour@4.0.2/dist/d3-contour.min.js',
    jspdf: 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
    autotable: 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js',
    proj4: 'https://cdn.jsdelivr.net/npm/proj4@2.9.2/dist/proj4.js',
    JSZip: 'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js',
    // mesmas versões já usadas no CAD do Gestor (gestor/index.html), para o
    // relatório aceitar perímetro em DXF e em shapefile (.zip).
    dxfparser: 'https://cdn.jsdelivr.net/npm/dxf-parser@1.1.2/dist/dxf-parser.js',
    shpjs: 'https://cdn.jsdelivr.net/npm/shpjs@4.0.4/dist/shp.js',
  };
  const STAC = 'https://earth-search.aws.element84.com/v1/search';
  const POWER = 'https://power.larc.nasa.gov/api/temporal/daily/point';
  const SCL_RUIM = new Set([3, 8, 9, 10, 11]); // sombra, nuvem média e alta, cirrus, neve
  const LEITURAS = 6; // o navegador abre até 6 conexões por servidor
  const WGS = '+proj=longlat +datum=WGS84 +no_defs';

  const COR = {
    azul: [21, 90, 158], // #155a9e — títulos de capítulo
    marca: [26, 111, 196], // #1a6fc4 — subtítulos e destaques
    escuro: [13, 27, 42], // #0d1b2a — títulos de mapa e gráfico
    claro: [230, 241, 251], // #e6f1fb — cabeçalho de tabela
    fundo: [245, 249, 253], // #f5f9fd — linha alternada
    linha: [201, 220, 239], // #c9dcef — grade e filete
    texto: [34, 34, 34],
    nota: [85, 85, 85],
  };

  RF.apiBase = function () {
    if (window.RELFAZ_API_BASE) return window.RELFAZ_API_BASE;
    const local = /^(localhost|127\.|192\.168\.)/.test(location.hostname) || location.protocol === 'file:';
    return local ? 'https://ajtopogeo.com.br/api' : '/api';
  };
  RF.dadosBase = function () {
    if (window.RELFAZ_DADOS_BASE) return window.RELFAZ_DADOS_BASE;
    return location.protocol === 'file:' ? 'dados/' : '/gestor/dados/';
  };

  class Cancelado extends Error {}
  RF.Cancelado = Cancelado;

  // ------------------------------------------------------------ utilidades

  function carregarScript(url) {
    return new Promise((ok, falha) => {
      const s = document.createElement('script');
      s.src = url;
      s.onload = ok;
      s.onerror = () => falha(new Error('Não consegui carregar ' + url));
      document.head.appendChild(s);
    });
  }

  async function garantirBibliotecas(extensaoArquivo) {
    const faltando = [];
    if (!window.GeoTIFF) faltando.push(carregarScript(LIBS.GeoTIFF));
    if (!window.polygonClipping) faltando.push(carregarScript(LIBS.polygonClipping));
    if (!window.proj4) faltando.push(carregarScript(LIBS.proj4));
    if (!window.JSZip) faltando.push(carregarScript(LIBS.JSZip));
    if (extensaoArquivo === 'dxf' && !window.DxfParser) faltando.push(carregarScript(LIBS.dxfparser));
    if (extensaoArquivo === 'zip' && typeof window.shp !== 'function') faltando.push(carregarScript(LIBS.shpjs));
    if (!(window.jspdf && window.jspdf.jsPDF)) {
      faltando.push(carregarScript(LIBS.jspdf).then(() => carregarScript(LIBS.autotable)));
    }
    if (!(window.d3 && window.d3.contours)) {
      faltando.push((window.d3 && window.d3.range ? Promise.resolve() : carregarScript(LIBS.d3array)).then(() => carregarScript(LIBS.d3contour)));
    }
    await Promise.all(faltando);
    const doc = window.jspdf && window.jspdf.jsPDF;
    if (doc && typeof doc.prototype.autoTable !== 'function') await carregarScript(LIBS.autotable);
  }

  function normalizar(s) {
    return String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
  }

  function num(v, casas) {
    if (v == null || !isFinite(v)) return '–';
    const c = casas == null ? 2 : casas;
    return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: c, maximumFractionDigits: c });
  }

  function dataBr(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso);
  }

  function isoHoje(deslocDias) {
    const d = new Date();
    d.setDate(d.getDate() - (deslocDias || 0));
    return d.toISOString().slice(0, 10);
  }

  function comPrazo(promessa, ms, rotulo) {
    let timer;
    const prazo = new Promise((_, falha) => {
      timer = setTimeout(() => falha(new Error('Tempo esgotado: ' + rotulo)), ms);
    });
    return Promise.race([promessa, prazo]).finally(() => clearTimeout(timer));
  }

  async function buscarJson(url, opcoes, ms) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms || 90000);
    try {
      const r = await fetch(url, Object.assign({ signal: ctrl.signal }, opcoes || {}));
      const texto = await r.text();
      let j;
      try {
        j = JSON.parse(texto);
      } catch (e) {
        throw new Error('Resposta inválida de ' + url.split('?')[0]);
      }
      if (!r.ok) throw new Error((j && (j.erro || j.message)) || 'HTTP ' + r.status);
      return j;
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('Tempo esgotado ao consultar ' + url.split('?')[0]);
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  // Executa `fn` sobre `itens` com no máximo `n` em andamento; devolve na ordem.
  async function emParalelo(itens, n, fn) {
    const saida = new Array(itens.length);
    let proximo = 0;
    async function trabalhador() {
      while (proximo < itens.length) {
        const i = proximo++;
        saida[i] = await fn(itens[i], i);
      }
    }
    await Promise.all(Array.from({ length: Math.min(n, itens.length) }, trabalhador));
    return saida;
  }

  function percentil(ordenado, p) {
    if (!ordenado.length) return NaN;
    const pos = (ordenado.length - 1) * p;
    const lo = Math.floor(pos);
    const hi = Math.ceil(pos);
    return ordenado[lo] + (ordenado[hi] - ordenado[lo]) * (pos - lo);
  }

  // ------------------------------------------------------------ perímetro

  function coordenadas(el) {
    const c = el.getElementsByTagNameNS('*', 'coordinates')[0] || el.getElementsByTagName('coordinates')[0];
    if (!c) return null;
    const pts = [];
    for (const tok of c.textContent.trim().split(/\s+/)) {
      const p = tok.split(',');
      const lon = parseFloat(p[0]);
      const lat = parseFloat(p[1]);
      if (isFinite(lon) && isFinite(lat)) pts.push([lon, lat]);
    }
    if (pts.length < 3) return null;
    const a = pts[0];
    const b = pts[pts.length - 1];
    if (a[0] !== b[0] || a[1] !== b[1]) pts.push([a[0], a[1]]);
    return pts;
  }

  // Polígonos em lon/lat: [[anelExterno, [aneisInternos]], ...]. O buraco de
  // um perímetro (servidão, parcela vendida) é descontado da área e da máscara.
  RF.lerKmlTexto = function (texto) {
    const xml = new DOMParser().parseFromString(texto, 'application/xml');
    if (xml.getElementsByTagName('parsererror').length) throw new Error('O arquivo KML está malformado.');
    const poligonos = [];
    for (const p of xml.getElementsByTagNameNS('*', 'Polygon')) {
      const ext = p.getElementsByTagNameNS('*', 'outerBoundaryIs')[0];
      const anel = ext && coordenadas(ext);
      if (!anel) continue;
      const internos = [];
      for (const i of p.getElementsByTagNameNS('*', 'innerBoundaryIs')) {
        const a = coordenadas(i);
        if (a) internos.push(a);
      }
      poligonos.push([anel, internos]);
    }
    if (!poligonos.length) {
      for (const tag of ['LinearRing', 'LineString']) {
        for (const el of xml.getElementsByTagNameNS('*', tag)) {
          const a = coordenadas(el);
          if (a) poligonos.push([a, []]);
        }
      }
    }
    if (!poligonos.length) throw new Error('Nenhum polígono encontrado no KML/KMZ.');
    return poligonos;
  };

  // Um DXF de topografia quase sempre vem em coordenadas projetadas (UTM), não
  // em graus — ao contrário do KML e do shapefile (que o shpjs já reprojeta
  // pelo .prj). Sem essa informação no próprio arquivo, checa se os valores já
  // parecem lon/lat (raro, mas alguns DXF saem assim); senão exige a zona UTM
  // informada na aba (mesmo padrão de seletor de zona/hemisfério do CAD do
  // Gestor, em gestor/index.html).
  function dxfEhGeografico(poligonos) {
    let n = 0;
    for (const [anel] of poligonos) {
      for (const [x, y] of anel) {
        n++;
        if (!isFinite(x) || !isFinite(y) || Math.abs(x) > 180 || Math.abs(y) > 90) return false;
      }
    }
    return n > 0;
  }

  function lerDxfPerimetro(texto, opcoesDxf) {
    if (!window.DxfParser) throw new Error('Biblioteca de leitura de DXF não carregada.');
    const dxf = new DxfParser().parse(texto);
    const poligonos = [];
    for (const en of dxf.entities || []) {
      if (!((en.type === 'LWPOLYLINE' || en.type === 'POLYLINE') && en.vertices && en.vertices.length > 2)) continue;
      const fechada = !!(en.shape || en.closed || (en.flags && (en.flags & 1)));
      if (!fechada) continue;
      const anel = en.vertices.map((v) => [v.x, v.y]);
      const a = anel[0], b = anel[anel.length - 1];
      if (a[0] !== b[0] || a[1] !== b[1]) anel.push([a[0], a[1]]);
      poligonos.push([anel, []]);
    }
    if (!poligonos.length) throw new Error('Nenhuma polilinha fechada encontrada no DXF. No CAD, feche o perímetro (polyline fechada) antes de exportar.');
    if (dxfEhGeografico(poligonos)) return poligonos;
    const zona = (opcoesDxf && opcoesDxf.zona) || 21;
    const sul = !opcoesDxf || opcoesDxf.sul !== false;
    const def = `+proj=utm +zone=${zona}${sul ? ' +south' : ''} +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs`;
    const conv = proj4(def, WGS);
    return poligonos.map(([anel]) => [anel.map((p) => conv.forward(p)), []]);
  }

  async function lerShapefilePerimetro(buffer) {
    if (typeof window.shp !== 'function') throw new Error('Biblioteca de leitura de shapefile não carregada.');
    let gj = await window.shp(buffer);
    if (Array.isArray(gj)) gj = gj[0];
    const poligonos = [];
    for (const f of (gj && gj.features) || []) {
      const g = f.geometry;
      if (!g) continue;
      if (g.type === 'Polygon') poligonos.push([g.coordinates[0], g.coordinates.slice(1)]);
      else if (g.type === 'MultiPolygon') for (const poli of g.coordinates) poligonos.push([poli[0], poli.slice(1)]);
    }
    if (!poligonos.length) throw new Error('Nenhum polígono encontrado no shapefile (esperado Polygon ou MultiPolygon). Envie o .zip com .shp, .shx, .dbf e .prj.');
    return poligonos;
  }

  RF.lerPerimetro = async function (arquivo, opcoesDxf) {
    const nome = (arquivo.name || '').toLowerCase();
    if (nome.endsWith('.kmz')) {
      const zip = await JSZip.loadAsync(await arquivo.arrayBuffer());
      const kml = Object.keys(zip.files).find((n) => n.toLowerCase().endsWith('.kml'));
      if (!kml) throw new Error('O KMZ não contém nenhum arquivo .kml.');
      return RF.lerKmlTexto(await zip.file(kml).async('string'));
    }
    if (nome.endsWith('.kml')) return RF.lerKmlTexto(await arquivo.text());
    if (nome.endsWith('.dxf')) return lerDxfPerimetro(await arquivo.text(), opcoesDxf);
    if (nome.endsWith('.zip')) return lerShapefilePerimetro(await arquivo.arrayBuffer());
    throw new Error('Formato não suportado. Use .kml, .kmz, .dxf ou .zip (shapefile).');
  };

  // ------------------------------------------------------------ geometria

  function sistemaUtm(lon, lat) {
    const fuso = Math.floor((lon + 180) / 6) + 1;
    const sul = lat < 0;
    // SIRGAS 2000 / UTM: 17S..25S = 31977..31985; 17N..22N = 31971..31976
    const epsg = (sul ? 31960 : 31954) + fuso;
    if (epsg < 31971 || epsg > 31985) throw new Error('O perímetro está fora dos fusos UTM do Brasil.');
    return {
      epsg,
      fuso,
      sul,
      def: `+proj=utm +zone=${fuso}${sul ? ' +south' : ''} +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs`,
      epsgWgs: (sul ? 32700 : 32600) + fuso,
    };
  }

  function defDoEpsg(epsg) {
    if (epsg === 4326 || epsg === 4674) return WGS;
    if (epsg > 32600 && epsg <= 32660) return `+proj=utm +zone=${epsg - 32600} +datum=WGS84 +units=m +no_defs`;
    if (epsg > 32700 && epsg <= 32760) return `+proj=utm +zone=${epsg - 32700} +south +datum=WGS84 +units=m +no_defs`;
    if (epsg >= 31965 && epsg <= 31976) return `+proj=utm +zone=${epsg - 31954} +ellps=GRS80 +units=m +no_defs`;
    if (epsg >= 31977 && epsg <= 31985) return `+proj=utm +zone=${epsg - 31960} +south +ellps=GRS80 +units=m +no_defs`;
    throw new Error('Sistema de coordenadas do raster não suportado: EPSG ' + epsg);
  }

  function areaAnel(a) {
    let s = 0;
    for (let i = 0; i < a.length - 1; i++) s += a[i][0] * a[i + 1][1] - a[i + 1][0] * a[i][1];
    return Math.abs(s) / 2;
  }

  function comprimentoAnel(a) {
    let s = 0;
    for (let i = 0; i < a.length - 1; i++) s += Math.hypot(a[i + 1][0] - a[i][0], a[i + 1][1] - a[i][1]);
    return s;
  }

  // área de MultiPolygon no formato [[anel, buraco...], ...]
  function areaMulti(mp) {
    let s = 0;
    for (const poli of mp || []) {
      if (!poli.length) continue;
      s += areaAnel(poli[0]);
      for (let k = 1; k < poli.length; k++) s -= areaAnel(poli[k]);
    }
    return s;
  }

  class Grade {
    constructor(x0, y0, res, nx, ny) {
      Object.assign(this, { x0, y0, res, nx, ny });
    }
    static envolvendo(xmin, ymin, xmax, ymax, res, folgaPx) {
      const f = (folgaPx == null ? 6 : folgaPx) * res;
      const x0 = Math.floor((xmin - f) / res) * res;
      const y1 = Math.floor((ymin - f) / res) * res;
      const x1 = Math.ceil((xmax + f) / res) * res;
      const y0 = Math.ceil((ymax + f) / res) * res;
      return new Grade(x0, y0, res, Math.round((x1 - x0) / res), Math.round((y0 - y1) / res));
    }
    get extent() {
      return [this.x0, this.x0 + this.nx * this.res, this.y0 - this.ny * this.res, this.y0];
    }
    get areaPixelHa() {
      return (this.res * this.res) / 10000;
    }
  }

  // Pixels cujo centro cai dentro do perímetro, por varredura de linha: cada
  // linha cruza as arestas de todos os anéis do polígono, e a regra par-ímpar
  // já tira os buracos.
  function mascara(grade, poligonosUtm) {
    const { nx, ny, x0, y0, res } = grade;
    const m = new Uint8Array(nx * ny);
    for (const [ext, internos] of poligonosUtm) {
      const aneis = [ext, ...internos];
      let ymin = Infinity;
      let ymax = -Infinity;
      for (const p of ext) {
        if (p[1] < ymin) ymin = p[1];
        if (p[1] > ymax) ymax = p[1];
      }
      const r0 = Math.max(0, Math.floor((y0 - ymax) / res));
      const r1 = Math.min(ny - 1, Math.ceil((y0 - ymin) / res));
      for (let r = r0; r <= r1; r++) {
        const yc = y0 - (r + 0.5) * res;
        const xs = [];
        for (const a of aneis) {
          for (let i = 0; i < a.length - 1; i++) {
            const [ax, ay] = a[i];
            const [bx, by] = a[i + 1];
            if (ay > yc !== by > yc) xs.push(ax + ((yc - ay) * (bx - ax)) / (by - ay));
          }
        }
        xs.sort((p, q) => p - q);
        for (let k = 0; k + 1 < xs.length; k += 2) {
          const c0 = Math.max(0, Math.ceil((xs[k] - x0) / res - 0.5));
          const c1 = Math.min(nx - 1, Math.ceil((xs[k + 1] - x0) / res - 0.5) - 1);
          for (let c = c0; c <= c1; c++) m[r * nx + c] = 1;
        }
      }
    }
    return m;
  }

  RF.preparar = async function (arquivo, log, opcoesDxf) {
    log('Lendo o perímetro...');
    const poligonos = await RF.lerPerimetro(arquivo, opcoesDxf);
    return RF.construirCtx(poligonos, log);
  };

  // Monta o contexto geométrico (grade, máscara, área) a partir de polígonos já
  // lidos em lon/lat — usado tanto para o arquivo enviado quanto para trocar o
  // perímetro pelo do CAR/SIGEF quando ele é maior (ver RF.gerar).
  RF.construirCtx = async function (poligonos, log) {
    let l = Infinity, b = Infinity, r = -Infinity, t = -Infinity;
    for (const [ext] of poligonos) {
      for (const [x, y] of ext) {
        if (x < l) l = x;
        if (x > r) r = x;
        if (y < b) b = y;
        if (y > t) t = y;
      }
    }
    const centro = [(l + r) / 2, (b + t) / 2];
    const sis = sistemaUtm(centro[0], centro[1]);
    const conv = proj4(WGS, sis.def);
    const utm = (anel) => anel.map((p) => conv.forward(p));
    const poligonosUtm = poligonos.map(([e, ints]) => [utm(e), ints.map(utm)]);
    let ha = 0;
    let perimetro = 0;
    let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
    for (const [e, ints] of poligonosUtm) {
      ha += areaAnel(e) - ints.reduce((s, i) => s + areaAnel(i), 0);
      perimetro += comprimentoAnel(e) + ints.reduce((s, i) => s + comprimentoAnel(i), 0);
      for (const [x, y] of e) {
        if (x < xmin) xmin = x;
        if (x > xmax) xmax = x;
        if (y < ymin) ymin = y;
        if (y > ymax) ymax = y;
      }
    }
    ha /= 10000;
    const grade = Grade.envolvendo(xmin, ymin, xmax, ymax, 10);
    const dentro = mascara(grade, poligonosUtm);
    let nDentro = 0;
    for (let i = 0; i < dentro.length; i++) nDentro += dentro[i];
    log(`  ${poligonos.length} polígono(s) | ${num(ha, 2)} ha | EPSG:${sis.epsg} (SIRGAS 2000 / UTM ${sis.fuso}${sis.sul ? 'S' : 'N'})`);
    log(`  grade ${grade.nx} x ${grade.ny} px a 10 m | ${nDentro.toLocaleString('pt-BR')} pixels dentro`);
    return {
      poligonos, poligonosUtm, bbox: [l, b, r, t], centro, sis, ha, perimetro,
      limitesUtm: [xmin, ymin, xmax, ymax], grade, dentro, nDentro,
      multiUtm: poligonosUtm.map(([e, ints]) => [e, ...ints]),
    };
  };

  // ------------------------------------------------------------ cadastro

  function geometriaUtm(g, conv) {
    if (!g) return null;
    const anel = (a) => a.map((p) => conv.forward([p[0], p[1]]));
    if (g.type === 'Polygon') return [g.coordinates.map(anel)];
    if (g.type === 'MultiPolygon') return g.coordinates.map((poli) => poli.map(anel));
    return null;
  }

  // Geometria GeoJSON (lon/lat) de uma feição do CAR/SIGEF -> formato interno de
  // polígonos [[anelExterno, [aneisInternos]], ...], o mesmo que RF.lerKmlTexto
  // devolve. Usado para trocar o perímetro analisado pelo do CAR/SIGEF.
  function geojsonParaPoligonos(g) {
    if (!g) return [];
    if (g.type === 'Polygon') return [[g.coordinates[0], g.coordinates.slice(1)]];
    if (g.type === 'MultiPolygon') return g.coordinates.map((poli) => [poli[0], poli.slice(1)]);
    return [];
  }

  // Área comum de cada feição com o perímetro. Abaixo de 100 m² é lasca de
  // divisa — dois levantamentos nunca coincidem no vértice — e não conflito.
  function sobreposicao(features, ctx) {
    const conv = proj4(WGS, ctx.sis.def);
    const areaAlvo = areaMulti(ctx.multiUtm);
    const saida = [];
    for (const f of features || []) {
      const mp = geometriaUtm(f.geometry, conv);
      if (!mp) continue;
      let inter;
      try {
        inter = polygonClipping.intersection(ctx.multiUtm, mp);
      } catch (e) {
        continue; // geometria inválida na origem
      }
      const comum = areaMulti(inter);
      if (comum < 100) continue;
      const area = areaMulti(mp);
      saida.push({
        atributos: f.properties || {},
        geometria: f.geometry,
        area_feicao_ha: area / 10000,
        area_comum_ha: comum / 10000,
        pct_do_perimetro: areaAlvo ? (100 * comum) / areaAlvo : 0,
        pct_da_feicao: area ? (100 * comum) / area : 0,
      });
    }
    saida.sort((a, b) => b.area_comum_ha - a.area_comum_ha);
    return saida;
  }

  function bboxParam(ctx, folga) {
    const [l, b, r, t] = ctx.bbox;
    const f = folga || 0;
    return [l - f, b - f, r + f, t + f].map((v) => v.toFixed(6)).join(',');
  }

  async function consultarCar(ctx, uf, log) {
    log('  CAR:');
    const hoje = dataBr(isoHoje(0));
    try {
      const j = await buscarJson(`${RF.apiBase()}/car?bbox=${bboxParam(ctx)}&uf=${uf}&max=2000`, null, 60000);
      const feats = j.features || [];
      if (!feats.length && j.erros && j.erros.length) throw new Error(j.erros.join('; '));
      log(`    ${feats.length} imóvel(is) do CAR na janela`);
      return { resultados: sobreposicao(feats, ctx), features: feats, origem: `WFS do SICAR, consulta ao vivo em ${hoje}`, aviso: null };
    } catch (e) {
      log('    falhou: ' + e.message);
      return { resultados: null, features: [], origem: null, aviso: 'Não foi possível consultar o CAR: ' + e.message };
    }
  }

  async function consultarSigef(ctx, uf, log) {
    log('  SIGEF/INCRA:');
    const hoje = dataBr(isoHoje(0));
    const resultados = [];
    const features = [];
    let respondeu = false;
    const erros = [];
    for (const [tema, natureza] of [['certificada_sigef_particular', 'particular'], ['certificada_sigef_publico', 'pública']]) {
      try {
        const j = await buscarJson(`${RF.apiBase()}/incra?tema=${tema}&bbox=${bboxParam(ctx)}&uf=${uf}&max=2000`, null, 60000);
        const feats = j.features || [];
        if (!feats.length && j.erros && j.erros.length) throw new Error(j.erros.join('; '));
        respondeu = true;
        log(`    ${tema}: ${feats.length} parcela(s) na janela`);
        for (const f of feats) features.push(Object.assign({}, f, { properties: Object.assign({}, f.properties, { natureza }) }));
        for (const r of sobreposicao(feats, ctx)) {
          r.atributos = Object.assign({}, r.atributos, { natureza });
          resultados.push(r);
        }
      } catch (e) {
        erros.push(e.message);
        log(`    ${tema}: falhou (${e.message})`);
      }
    }
    if (!respondeu) {
      return { resultados: null, features: [], origem: null, aviso: 'Não foi possível consultar o SIGEF: o acervo fundiário do INCRA não respondeu (' + erros.join('; ') + ').' };
    }
    resultados.sort((a, b) => b.area_comum_ha - a.area_comum_ha);
    return { resultados, features, origem: `WFS do Acervo Fundiário do INCRA, consulta ao vivo em ${hoje}`, aviso: null };
  }

  // Município do imóvel de maior área comum e o módulo fiscal dele: cada imóvel
  // do CAR traz `area` e `m_fiscal`, e a razão é o módulo do município.
  function municipioPeloCar(car) {
    const razoes = {};
    const nomes = {};
    for (const f of car.features || []) {
      const p = f.properties || {};
      const cod = String(p.cod_municipio_ibge || '');
      if (!cod) continue;
      nomes[cod] = p.municipio;
      const area = parseFloat(p.area);
      const mf = parseFloat(p.m_fiscal);
      if (area >= 20 && mf > 0) (razoes[cod] = razoes[cod] || []).push(area / mf);
    }
    let cod = car.resultados && car.resultados.length ? String(car.resultados[0].atributos.cod_municipio_ibge || '') : '';
    if (!cod) {
      const cods = Object.keys(razoes).sort((a, b) => razoes[b].length - razoes[a].length);
      cod = cods[0] || '';
    }
    if (!cod) return null;
    const amostra = (razoes[cod] || []).slice().sort((a, b) => a - b);
    return {
      codIbge: cod,
      municipio: nomes[cod] || (car.resultados && car.resultados[0] && car.resultados[0].atributos.municipio),
      moduloFiscal: amostra.length ? Math.round(percentil(amostra, 0.5)) : null,
      amostra: amostra.length,
    };
  }

  // -------------------------------------------------- fundiário, ambiental e riscos

  // Terra Indígena e Unidade de Conservação federal têm "entorno" que importa
  // mesmo sem sobreposição (art. 4º, III do SNUC; diretrizes de licenciamento
  // perto de TI). Por isso a consulta busca numa janela maior que o imóvel, e o
  // relatório declara sempre o mesmo raio que consultou — nunca um raio no texto
  // e outro na tabela.
  const RAIO_ENTORNO_KM = 10;
  const RAIO_ENTORNO_GRAUS = RAIO_ENTORNO_KM / 111;

  function pick(atributos, candidatos) {
    for (const c of candidatos) {
      const v = atributos[c];
      if (v != null && String(v).trim() !== '') return String(v).trim();
    }
    return null;
  }

  function contarPontos(mp) {
    let n = 0;
    for (const poli of mp || []) for (const anel of poli) n += anel.length;
    return n;
  }

  // Menor distância (m) entre dois MultiPolygon em UTM, pela distância de cada
  // vértice de um aos segmentos do outro. Suficiente na escala de km do entorno;
  // evita o custo de um algoritmo exato de menor distância entre polígonos.
  function distanciaMinima(mpA, mpB) {
    function distPontoSegmento(px, py, ax, ay, bx, by) {
      const dx = bx - ax, dy = by - ay;
      const len2 = dx * dx + dy * dy;
      let t = len2 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0;
      t = Math.max(0, Math.min(1, t));
      return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
    }
    function segmentos(mp) {
      const segs = [];
      for (const poli of mp || []) for (const anel of poli) for (let i = 0; i < anel.length - 1; i++) segs.push([anel[i], anel[i + 1]]);
      return segs;
    }
    const segsA = segmentos(mpA), segsB = segmentos(mpB);
    if (!segsA.length || !segsB.length) return Infinity;
    let min = Infinity;
    for (const [a0, a1] of segsA) {
      for (const [b0, b1] of segsB) {
        const d = Math.min(
          distPontoSegmento(a0[0], a0[1], b0[0], b0[1], b1[0], b1[1]),
          distPontoSegmento(a1[0], a1[1], b0[0], b0[1], b1[0], b1[1]),
          distPontoSegmento(b0[0], b0[1], a0[0], a0[1], a1[0], a1[1]),
          distPontoSegmento(b1[0], b1[1], a0[0], a0[1], a1[0], a1[1]));
        if (d < min) min = d;
        if (min === 0) return 0;
      }
    }
    return min;
  }

  // Feições não sobrepostas, mas dentro do raio de entorno. Geometria grande
  // demais (TI e UC podem ter milhares de vértices) é descartada da lista em vez
  // de arriscar travar o navegador ou devolver uma distância errada.
  function entornoNaoSobreposto(features, ctx, sobrepostos) {
    const conv = proj4(WGS, ctx.sis.def);
    const jaContadas = new Set(sobrepostos.map((r) => JSON.stringify(r.atributos)));
    const custoImovel = contarPontos(ctx.multiUtm);
    const saida = [];
    for (const f of features || []) {
      if (jaContadas.has(JSON.stringify(f.properties || {}))) continue;
      const mp = geometriaUtm(f.geometry, conv);
      if (!mp) continue;
      if (custoImovel * contarPontos(mp) > 3000000) continue;
      const d = distanciaMinima(ctx.multiUtm, mp);
      if (d <= RAIO_ENTORNO_KM * 1000) saida.push({ atributos: f.properties || {}, distanciaKm: d / 1000 });
    }
    saida.sort((a, b) => a.distanciaKm - b.distanciaKm);
    return saida.slice(0, 5);
  }

  // Consulta genérica com sobreposição exata + entorno, usada para TI, UC,
  // assentamento e quilombola — mesmo padrão de tratamento de erro do CAR/SIGEF:
  // falhou uma fonte, o relatório diz isso e segue, nunca finge que é "conforme".
  async function consultarComEntorno(url, nome, ctx, log) {
    log('  ' + nome + ':');
    try {
      const j = await buscarJson(url, null, 60000);
      const feats = j.features || [];
      const erroBase = j.erro || (j.erros && j.erros.length ? j.erros.join('; ') : null);
      if (!feats.length && erroBase) throw new Error(erroBase);
      const resultados = sobreposicao(feats, ctx);
      const entorno = entornoNaoSobreposto(feats, ctx, resultados);
      log(`    ${feats.length} feição(ões) na janela | ${resultados.length} sobreposta(s) | ${entorno.length} no entorno de ${RAIO_ENTORNO_KM} km`);
      return { resultados, entorno, raioKm: RAIO_ENTORNO_KM, origem: `${nome}, consulta ao vivo em ${dataBr(isoHoje(0))}`, aviso: erroBase || null };
    } catch (e) {
      log('    falhou: ' + e.message);
      return { resultados: null, entorno: [], raioKm: RAIO_ENTORNO_KM, origem: null, aviso: 'Não foi possível consultar ' + nome + ': ' + e.message };
    }
  }

  function urlRestricao(ctx, fonte) {
    return `${RF.apiBase()}/restricoes?fonte=${fonte}&bbox=${bboxParam(ctx, RAIO_ENTORNO_GRAUS)}&max=500`;
  }
  function urlFundiario(ctx, uf, tema) {
    return `${RF.apiBase()}/incra?tema=${tema}&bbox=${bboxParam(ctx, RAIO_ENTORNO_GRAUS)}&uf=${uf}&max=500`;
  }

  // Embargo do IBAMA: a base pública já mudou nome de campo entre atualizações,
  // então a identificação tenta várias chaves plausíveis em vez de supor um
  // esquema fixo — na dúvida, mostra o que existe em vez de imprimir "–" errado.
  async function consultarEmbargos(ctx, log) {
    log('  Embargos ambientais (IBAMA/SISCOM):');
    try {
      const j = await buscarJson(`${RF.apiBase()}/embargos?bbox=${bboxParam(ctx)}`, null, 60000);
      const feats = j.features || [];
      if (!feats.length && j.erro) throw new Error(j.erro);
      const resultados = sobreposicao(feats, ctx);
      log(`    ${feats.length} termo(s) na janela | ${resultados.length} sobreposto(s)`);
      return { resultados, origem: `SISCOM/IBAMA (PAMGIA), consulta ao vivo em ${dataBr(isoHoje(0))}`, aviso: j.erro || null };
    } catch (e) {
      log('    falhou: ' + e.message);
      return { resultados: null, origem: null, aviso: 'Não foi possível consultar o IBAMA: ' + e.message };
    }
  }

  // Pareamento SIGEF x CAR pela sobreposição geométrica (IoU = interseção / união)
  // — a mesma ideia usada por serviços de dossiê fundiário para não contar a
  // mesma terra duas vezes. IoU ≥ 0,95: mesma terra (a mesma área tem os dois
  // registros). IoU ≥ 0,70: pareados, mas as áreas não coincidem o bastante para
  // afirmar que é a mesma terra. Abaixo disso: sobreposição parcial, apenas
  // informativa. Nunca infere titularidade — só compara geometria.
  function parearSigefCar(ctx, carFeatures, sigefFeatures) {
    const conv = proj4(WGS, ctx.sis.def);
    const cars = (carFeatures || []).map((f) => ({ atributos: f.properties || {}, mp: geometriaUtm(f.geometry, conv) })).filter((x) => x.mp);
    const sigefs = (sigefFeatures || []).map((f) => ({ atributos: f.properties || {}, mp: geometriaUtm(f.geometry, conv) })).filter((x) => x.mp);
    const pares = [];
    for (const s of sigefs) {
      const areaS = areaMulti(s.mp);
      if (areaS < 100) continue;
      let melhor = null;
      for (const c of cars) {
        let inter;
        try { inter = polygonClipping.intersection(s.mp, c.mp); } catch (e) { continue; }
        const comum = areaMulti(inter);
        if (comum < 100) continue;
        const areaC = areaMulti(c.mp);
        let areaU;
        try { areaU = areaMulti(polygonClipping.union(s.mp, c.mp)); } catch (e) { areaU = areaS + areaC - comum; }
        const iou = areaU ? comum / areaU : 0;
        if (!melhor || iou > melhor.iou) melhor = { atributos: c.atributos, iou, areaCarHa: areaC / 10000 };
      }
      if (melhor) {
        const classe = melhor.iou >= 0.95 ? 'mesma_terra' : melhor.iou >= 0.70 ? 'pareado' : 'sobreposicao_parcial';
        pares.push({ sigef: s.atributos, car: melhor.atributos, iouPct: melhor.iou * 100, areaSigefHa: areaS / 10000, areaCarHa: melhor.areaCarHa, classe });
      }
    }
    pares.sort((a, b) => b.iouPct - a.iouPct);
    return pares;
  }

  // -------------------------------------------------- Reserva Legal (Lei 12.651)

  // Amazônia Legal (Lei Complementar 124/2007): só nesses estados o percentual
  // muda por bioma (floresta 80 %, cerrado 35 %, campos gerais 20 %) — em todo o
  // resto do país é 20 % fixo (art. 12, IV). O Maranhão entra na lista por ter
  // parte do território na Amazônia Legal, mesmo sem estar 100 % nela.
  const UF_AMAZONIA_LEGAL = new Set(['AC', 'AP', 'AM', 'MA', 'MT', 'PA', 'RO', 'RR', 'TO']);

  function calcularRL(uf, ha, modulo) {
    const naAmazonia = UF_AMAZONIA_LEGAL.has(uf);
    const r = { amazoniaLegal: naAmazonia, pctMin: null, minHa: null, baseLegal: '', nota: '' };
    if (!naAmazonia) {
      r.pctMin = 20;
      r.minHa = (ha * 20) / 100;
      r.baseLegal = 'Lei 12.651/2012, art. 12, IV — fora da Amazônia Legal, Reserva Legal mínima de 20 % em qualquer bioma.';
    } else {
      r.baseLegal = 'Lei 12.651/2012, art. 12, I — dentro da Amazônia Legal, o mínimo varia por bioma (floresta 80 %, cerrado 35 %, campos gerais 20 %).';
      r.nota = 'O bioma/fitofisionomia predominante do imóvel não foi classificado nesta execução (exigiria a camada de vegetação do IBGE cruzada com o perímetro). Sem essa classificação, o relatório não aplica um percentual — aplicar 80 % por padrão, como faz o concorrente, erra sempre que o imóvel não é de floresta.';
    }
    if (modulo && modulo.n != null && modulo.n <= 4) {
      r.art67 = `O imóvel tem ${num(modulo.n, 2)} módulos fiscais (≤ 4) — pode se enquadrar no art. 67 da Lei 12.651/2012: a Reserva Legal fica limitada à área de vegetação nativa existente em 22/07/2008, mediante inscrição no CAR. Este relatório não mede a vegetação de 2008 (exige série histórica de imagens ou declaração no CAR); a aplicação do artigo depende dessa comprovação.`;
    }
    return r;
  }

  // -------------------------------------------------- logística

  const CAPITAIS_UF = {
    AC: ['Rio Branco', -9.9750, -67.8243], AL: ['Maceió', -9.6498, -35.7089], AP: ['Macapá', 0.0349, -51.0694],
    AM: ['Manaus', -3.1190, -60.0217], BA: ['Salvador', -12.9777, -38.5016], CE: ['Fortaleza', -3.7172, -38.5433],
    DF: ['Brasília', -15.7939, -47.8828], ES: ['Vitória', -20.3155, -40.3128], GO: ['Goiânia', -16.6869, -49.2648],
    MA: ['São Luís', -2.5307, -44.3068], MT: ['Cuiabá', -15.6014, -56.0979], MS: ['Campo Grande', -20.4697, -54.6201],
    MG: ['Belo Horizonte', -19.9167, -43.9345], PA: ['Belém', -1.4558, -48.4902], PB: ['João Pessoa', -7.1195, -34.8450],
    PR: ['Curitiba', -25.4284, -49.2733], PE: ['Recife', -8.0476, -34.8770], PI: ['Teresina', -5.0892, -42.8019],
    RJ: ['Rio de Janeiro', -22.9068, -43.1729], RN: ['Natal', -5.7945, -35.2110], RS: ['Porto Alegre', -30.0346, -51.2177],
    RO: ['Porto Velho', -8.7619, -63.9039], RR: ['Boa Vista', 2.8235, -60.6758], SC: ['Florianópolis', -27.5954, -48.5480],
    SP: ['São Paulo', -23.5505, -46.6333], SE: ['Aracaju', -10.9472, -37.0731], TO: ['Palmas', -10.1689, -48.3317],
  };

  function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const rad = (d) => (d * Math.PI) / 180;
    const dLat = rad(lat2 - lat1), dLon = rad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function logisticaCapital(lonC, latC, uf) {
    const cap = CAPITAIS_UF[uf];
    if (!cap) return null;
    const [nome, lat, lon] = cap;
    return { capital: nome, km: haversineKm(latC, lonC, lat, lon) };
  }

  // ------------------------------------------------------------ rasters remotos

  // Lê do GeoTIFF remoto só a janela que cobre a grade e reamostra nela.
  // Devolve um Float32Array por banda (linhas x colunas), NaN onde não há dado.
  async function recortar(url, grade, sis, metodo) {
    const tiff = await comPrazo(GeoTIFF.fromUrl(url), 120000, 'abrir ' + url.split('/').pop());
    const img = await tiff.getImage();
    const k = img.geoKeys || {};
    const epsg = k.ProjectedCSTypeGeoKey || k.GeographicTypeGeoKey || 4326;
    const [ox, oy] = img.getOrigin();
    const [rx, ry] = img.getResolution();
    const W = img.getWidth();
    const H = img.getHeight();
    const nodataBruto = img.getGDALNoData();
    const nodata = nodataBruto == null ? null : Number(nodataBruto);
    const { nx, ny, x0, y0, res } = grade;
    const n = nx * ny;
    const px = new Float64Array(n);
    const py = new Float64Array(n);
    const mesmo = epsg === sis.epsgWgs || epsg === sis.epsg;
    const conv = mesmo ? null : proj4(sis.def, defDoEpsg(epsg));
    let cmin = Infinity, cmax = -Infinity, rmin = Infinity, rmax = -Infinity;
    for (let r = 0, i = 0; r < ny; r++) {
      const y = y0 - (r + 0.5) * res;
      for (let c = 0; c < nx; c++, i++) {
        let x = x0 + (c + 0.5) * res;
        let yy = y;
        if (conv) [x, yy] = conv.forward([x, y]);
        const fc = (x - ox) / rx;
        const fr = (yy - oy) / ry;
        px[i] = fc;
        py[i] = fr;
        if (fc < cmin) cmin = fc;
        if (fc > cmax) cmax = fc;
        if (fr < rmin) rmin = fr;
        if (fr > rmax) rmax = fr;
      }
    }
    const wc0 = Math.max(0, Math.floor(cmin) - 2);
    const wr0 = Math.max(0, Math.floor(rmin) - 2);
    const wc1 = Math.min(W, Math.ceil(cmax) + 2);
    const wr1 = Math.min(H, Math.ceil(rmax) + 2);
    const nb = img.getSamplesPerPixel();
    const saida = Array.from({ length: nb }, () => new Float32Array(n).fill(NaN));
    if (wc0 >= wc1 || wr0 >= wr1) return saida; // o raster não cobre a grade
    const ww = wc1 - wc0;
    const wh = wr1 - wr0;
    const ras = await comPrazo(img.readRasters({ window: [wc0, wr0, wc1, wr1] }), 240000, 'ler ' + url.split('/').pop());
    const valido = (v) => v != null && isFinite(v) && (nodata == null || v !== nodata);
    for (let bnd = 0; bnd < nb; bnd++) {
      const src = ras[bnd];
      const dst = saida[bnd];
      for (let i = 0; i < n; i++) {
        if (metodo === 'near') {
          const c = Math.floor(px[i]) - wc0;
          const r = Math.floor(py[i]) - wr0;
          if (c < 0 || r < 0 || c >= ww || r >= wh) continue;
          const v = src[r * ww + c];
          if (valido(v)) dst[i] = v;
        } else {
          const fx = px[i] - 0.5 - wc0;
          const fy = py[i] - 0.5 - wr0;
          const c = Math.floor(fx);
          const r = Math.floor(fy);
          if (c < 0 || r < 0 || c + 1 >= ww || r + 1 >= wh) {
            const cn = Math.floor(px[i]) - wc0;
            const rn = Math.floor(py[i]) - wr0;
            if (cn >= 0 && rn >= 0 && cn < ww && rn < wh) {
              const v = src[rn * ww + cn];
              if (valido(v)) dst[i] = v;
            }
            continue;
          }
          const dx = fx - c;
          const dy = fy - r;
          const a = src[r * ww + c];
          const b2 = src[r * ww + c + 1];
          const c2 = src[(r + 1) * ww + c];
          const d = src[(r + 1) * ww + c + 1];
          if (valido(a) && valido(b2) && valido(c2) && valido(d)) {
            dst[i] = a * (1 - dx) * (1 - dy) + b2 * dx * (1 - dy) + c2 * (1 - dx) * dy + d * dx * dy;
          } else {
            const v = src[Math.round(fy) * ww + Math.round(fx)];
            if (valido(v)) dst[i] = v;
          }
        }
      }
    }
    return saida;
  }

  // ------------------------------------------------------------ Sentinel-2

  async function buscarCenas(ctx, dtIni, dtFim, nuvemMax, log, cancelar) {
    log('Consultando o catálogo Sentinel-2...');
    const [l, b, r, t] = ctx.bbox;
    let corpo = {
      collections: ['sentinel-2-l2a'],
      intersects: { type: 'Polygon', coordinates: [[[l, b], [r, b], [r, t], [l, t], [l, b]]] },
      datetime: `${dtIni}T00:00:00Z/${dtFim}T23:59:59Z`,
      query: { 'eo:cloud_cover': { lt: Number(nuvemMax) } },
      limit: 100,
    };
    let url = STAC;
    let metodo = 'POST';
    const itens = [];
    while (url && itens.length < 2000) {
      if (cancelar()) throw new Cancelado();
      const j = await buscarJson(url, metodo === 'POST'
        ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) }
        : {}, 90000);
      for (const f of j.features || []) {
        const assets = {};
        for (const [kk, v] of Object.entries(f.assets || {})) if (v && v.href) assets[kk] = v.href;
        itens.push({ id: f.id, data: f.properties.datetime.slice(0, 10), nuvem: Number(f.properties['eo:cloud_cover'] ?? 100), assets });
      }
      const prox = (j.links || []).find((x) => x.rel === 'next');
      if (!prox) break;
      url = prox.href;
      metodo = (prox.method || 'GET').toUpperCase();
      if (metodo === 'POST') corpo = prox.merge ? Object.assign({}, corpo, prox.body) : prox.body || corpo;
    }
    if (!itens.length) {
      throw new Error(`Nenhuma cena Sentinel-2 entre ${dataBr(dtIni)} e ${dataBr(dtFim)} com menos de ${nuvemMax}% de nuvem. Amplie o período ou o limite de nuvem.`);
    }
    log(`  ${itens.length} cena(s) no período.`);
    return itens;
  }

  async function nuvemNoImovel(item, ctx) {
    const [scl] = await recortar(item.assets.scl, ctx.grade, ctx.sis, 'near');
    let ruim = 0;
    for (let i = 0; i < scl.length; i++) {
      if (!ctx.dentro[i]) continue;
      if (isNaN(scl[i]) || SCL_RUIM.has(scl[i])) ruim++;
    }
    return ctx.nDentro ? (100 * ruim) / ctx.nDentro : 100;
  }

  // A imagem mais recente sem nuvem SOBRE O IMÓVEL: a nuvem do catálogo é a da
  // cena inteira (110 x 110 km) e não diz nada sobre a fazenda.
  async function escolherCena(itens, ctx, log, cancelar) {
    log('Medindo a nuvem dentro do perímetro (banda SCL)...');
    const validos = itens.filter((i) => i.assets.scl);
    const porData = validos.slice().sort((a, b) => (a.data < b.data ? 1 : -1));
    const fases = [porData.slice(0, 12), porData.slice(12).sort((a, b) => a.nuvem - b.nuvem).slice(0, 8)];
    const medidos = [];
    for (const candidatos of fases) {
      for (let k = 0; k < candidatos.length; k += LEITURAS) {
        if (cancelar()) throw new Cancelado();
        const lote = candidatos.slice(k, k + LEITURAS);
        const pcts = await Promise.all(lote.map((it) => nuvemNoImovel(it, ctx).catch(() => null)));
        lote.forEach((it, i) => {
          if (pcts[i] == null) {
            log(`  ${dataBr(it.data)}: não consegui ler a SCL`);
            return;
          }
          log(`  ${dataBr(it.data)}   nuvem na cena ${num(it.nuvem, 1)} %   no imóvel ${num(pcts[i], 1)} %`);
          medidos.push([it, pcts[i]]);
        });
        const limpos = medidos.filter((m) => m[1] < 1);
        if (limpos.length) return limpos.sort((a, b) => (a[0].data < b[0].data ? 1 : -1))[0];
      }
    }
    if (!medidos.length) return [porData[0] || itens[0], NaN];
    return medidos.sort((a, b) => a[1] - b[1])[0];
  }

  function indiceNdvi(nir, red, i) {
    const s = nir[i] + red[i];
    return s > 0 ? (nir[i] - red[i]) / s : NaN;
  }

  async function lerCena(item, ctx) {
    const a = item.assets;
    const pedidos = [recortar(a.nir, ctx.grade, ctx.sis, 'bilinear'), recortar(a.red, ctx.grade, ctx.sis, 'bilinear'), recortar(a.scl, ctx.grade, ctx.sis, 'near')];
    pedidos.push(a.visual ? recortar(a.visual, ctx.grade, ctx.sis, 'bilinear') : Promise.all([recortar(a.red, ctx.grade, ctx.sis, 'bilinear'), recortar(a.green, ctx.grade, ctx.sis, 'bilinear'), recortar(a.blue, ctx.grade, ctx.sis, 'bilinear')]));
    const [[nir], [red], [scl], visual] = await Promise.all(pedidos);
    const n = ctx.grade.nx * ctx.grade.ny;
    let rgb;
    if (a.visual) {
      rgb = visual;
    } else {
      // sem a composição pronta: estica cada banda entre os percentis 2 e 98
      rgb = visual.map(([banda]) => {
        const vals = [];
        for (let i = 0; i < n; i++) if (ctx.dentro[i] && isFinite(banda[i])) vals.push(banda[i]);
        vals.sort((p, q) => p - q);
        const p2 = percentil(vals, 0.02) || 0;
        const p98 = percentil(vals, 0.98) || 3000;
        const out = new Float32Array(n);
        for (let i = 0; i < n; i++) out[i] = Math.max(0, Math.min(255, ((banda[i] - p2) / Math.max(p98 - p2, 1)) * 255));
        return out;
      });
    }
    const ndvi = new Float32Array(n).fill(NaN);
    for (let i = 0; i < n; i++) {
      if (!ctx.dentro[i]) continue;
      if (isNaN(scl[i]) || SCL_RUIM.has(scl[i])) continue;
      ndvi[i] = indiceNdvi(nir, red, i);
    }
    return { rgb, ndvi };
  }

  function estatisticas(ndvi, dentro) {
    const v = [];
    for (let i = 0; i < ndvi.length; i++) if (dentro[i] && isFinite(ndvi[i])) v.push(ndvi[i]);
    if (!v.length) return null;
    v.sort((a, b) => a - b);
    let soma = 0;
    let soma2 = 0;
    let baixo = 0;
    for (const x of v) {
      soma += x;
      soma2 += x * x;
      if (x < 0.2) baixo++;
    }
    const medio = soma / v.length;
    return {
      n: v.length, medio, mediana: percentil(v, 0.5), p10: percentil(v, 0.1), p90: percentil(v, 0.9),
      desvio: Math.sqrt(Math.max(0, soma2 / v.length - medio * medio)), min: v[0], max: v[v.length - 1],
      pctBaixo: (100 * baixo) / v.length,
    };
  }

  // Série: a SCL desce primeiro e só as datas que passam na cobertura mínima
  // baixam as bandas do NDVI — no período chuvoso é boa parte delas.
  async function serieNdvi(itens, ctx, log, cancelar, minValidos) {
    const porData = {};
    for (const it of itens) {
      if (it.assets.scl && it.assets.nir && it.assets.red) (porData[it.data] = porData[it.data] || []).push(it);
    }
    const datas = Object.keys(porData).sort();
    log(`  ${datas.length} data(s) para processar (${LEITURAS} em paralelo; alguns minutos)...`);
    let feitos = 0;
    const linhas = await emParalelo(datas, LEITURAS, async (data) => {
      if (cancelar()) throw new Cancelado();
      const n = ctx.grade.nx * ctx.grade.ny;
      const bons = new Uint8Array(n);
      const uteis = [];
      let cobertos = 0;
      try {
        for (const it of porData[data]) {
          const [scl] = await recortar(it.assets.scl, ctx.grade, ctx.sis, 'near');
          const bom = new Uint8Array(n);
          let algum = false;
          for (let i = 0; i < n; i++) {
            if (ctx.dentro[i] && !bons[i] && isFinite(scl[i]) && !SCL_RUIM.has(scl[i])) {
              bom[i] = 1;
              bons[i] = 1;
              cobertos++;
              algum = true;
            }
          }
          if (algum) uteis.push([it, bom]);
          if (cobertos >= ctx.nDentro) break;
        }
        const cobertura = ctx.nDentro ? (100 * cobertos) / ctx.nDentro : 0;
        let st = null;
        if (uteis.length && cobertura >= minValidos) {
          const ndvi = new Float32Array(n).fill(NaN);
          for (const [it, bom] of uteis) {
            const [[nir], [red]] = await Promise.all([recortar(it.assets.nir, ctx.grade, ctx.sis, 'bilinear'), recortar(it.assets.red, ctx.grade, ctx.sis, 'bilinear')]);
            for (let i = 0; i < n; i++) if (bom[i]) ndvi[i] = indiceNdvi(nir, red, i);
          }
          st = estatisticas(ndvi, ctx.dentro);
        }
        feitos++;
        const cob = st ? (100 * st.n) / ctx.nDentro : cobertura;
        const aceito = !!st && cob >= minValidos;
        log(`  [${String(feitos).padStart(3)}/${datas.length}] ${dataBr(data)}  ${aceito ? 'ok ' : '-- '}nuvem no imóvel ${num(100 - cob, 1)} %` + (st ? `  NDVI ${num(st.medio, 3)}` : ''));
        return aceito ? Object.assign({ data }, st) : null;
      } catch (e) {
        if (e instanceof Cancelado) throw e;
        feitos++;
        log(`  [${String(feitos).padStart(3)}/${datas.length}] ${dataBr(data)}  FALHA (${e.message})`);
        return null;
      }
    });
    return linhas.filter(Boolean);
  }

  // ------------------------------------------------------------ relevo

  async function modeloElevacao(ctx, log) {
    log('Baixando o modelo de elevação Copernicus GLO-30...');
    const [xmin, ymin, xmax, ymax] = ctx.limitesUtm;
    const grade = Grade.envolvendo(xmin, ymin, xmax, ymax, 30, 4);
    const [l, b, r, t] = ctx.bbox;
    const urls = [];
    for (let la = Math.floor(b - 0.01); la <= Math.floor(t + 0.01); la++) {
      for (let lo = Math.floor(l - 0.01); lo <= Math.floor(r + 0.01); lo++) {
        const ns = la >= 0 ? 'N' + String(la).padStart(2, '0') : 'S' + String(-la).padStart(2, '0');
        const ew = lo >= 0 ? 'E' + String(lo).padStart(3, '0') : 'W' + String(-lo).padStart(3, '0');
        urls.push(`https://opentopography.s3.sdsc.edu/raster/COP30/COP30_hh/Copernicus_DSM_10_${ns}_00_${ew}_00_DEM.tif`);
      }
    }
    const pedacos = await Promise.all(urls.map((u) => recortar(u, grade, ctx.sis, 'bilinear').catch(() => null)));
    const n = grade.nx * grade.ny;
    const dem = new Float32Array(n).fill(NaN);
    let achados = 0;
    for (const p of pedacos) {
      if (!p) continue;
      achados++;
      for (let i = 0; i < n; i++) if (isFinite(p[0][i]) && p[0][i] > -1000) dem[i] = p[0][i];
    }
    log(`  ${achados} de ${urls.length} folha(s) do modelo encontradas.`);
    return { grade, dem, dentro: mascara(grade, ctx.poligonosUtm), achados };
  }

  const CLASSES_DECL = [
    [0, 3, 'Plano'], [3, 8, 'Suave ondulado'], [8, 20, 'Ondulado'],
    [20, 45, 'Forte ondulado'], [45, 75, 'Montanhoso'], [75, 1e9, 'Escarpado'],
  ];
  const CORES_DECL = ['#2e7d32', '#9ccc65', '#fff176', '#ffb74d', '#e57373', '#8e24aa'];

  // Declividade em % pelo método de Horn (janela 3x3), com borda repetida.
  function declividadeHorn(dem, nx, ny, px) {
    let soma = 0, cont = 0;
    for (const v of dem) if (isFinite(v)) { soma += v; cont++; }
    const media = cont ? soma / cont : 0;
    const z = (r, c) => {
      const v = dem[Math.min(ny - 1, Math.max(0, r)) * nx + Math.min(nx - 1, Math.max(0, c))];
      return isFinite(v) ? v : media;
    };
    const out = new Float32Array(nx * ny);
    for (let r = 0; r < ny; r++) {
      for (let c = 0; c < nx; c++) {
        const a = z(r - 1, c - 1), b = z(r - 1, c), cc = z(r - 1, c + 1);
        const d = z(r, c - 1), f = z(r, c + 1);
        const g = z(r + 1, c - 1), h = z(r + 1, c), i = z(r + 1, c + 1);
        const dzdx = (cc + 2 * f + i - (a + 2 * d + g)) / (8 * px);
        const dzdy = (g + 2 * h + i - (a + 2 * b + cc)) / (8 * px);
        out[r * nx + c] = 100 * Math.hypot(dzdx, dzdy);
      }
    }
    return out;
  }

  function tabelaDeclividade(decl, dentro, areaPx) {
    const v = [];
    for (let i = 0; i < decl.length; i++) if (dentro[i] && isFinite(decl[i])) v.push(decl[i]);
    if (!v.length) return { linhas: [], mediana: 0, restricoes: null };
    const linhas = CLASSES_DECL.map(([lo, hi, nome]) => {
      let n = 0;
      for (const x of v) if (x >= lo && x < hi) n++;
      return { classe: nome, faixa: hi < 1e8 ? `${lo} a ${hi} %` : '> 75 %', ha: n * areaPx, pct: (100 * n) / v.length };
    });
    const lim25 = 100 * Math.tan((25 * Math.PI) / 180);
    let app = 0, restrito = 0;
    for (const x of v) {
      if (x >= 100) app++;
      else if (x >= lim25) restrito++;
    }
    v.sort((a, b) => a - b);
    return {
      linhas, mediana: percentil(v, 0.5),
      restricoes: { appHa: app * areaPx, appPct: (100 * app) / v.length, restritoHa: restrito * areaPx, restritoPct: (100 * restrito) / v.length },
    };
  }

  // ------------------------------------------------------------ chuva

  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

  async function chuvaNasaPower(lat, lon, log) {
    const hoje = new Date();
    const fim = new Date(hoje.getFullYear(), hoje.getMonth(), 0); // último dia do mês anterior
    const inicio = new Date(fim.getFullYear() - 20, 0, 1);
    const fmt = (d) => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
    log(`  Precipitação NASA POWER (${inicio.getFullYear()}-${fim.getFullYear()})...`);
    const j = await buscarJson(`${POWER}?parameters=PRECTOTCORR&community=AG&latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&start=${fmt(inicio)}&end=${fmt(fim)}&format=JSON`, null, 120000);
    const serie = j.properties.parameter.PRECTOTCORR;
    const porMes = {};
    for (const [k, v] of Object.entries(serie)) {
      if (v == null || v < -900) continue;
      const chave = k.slice(0, 6);
      porMes[chave] = (porMes[chave] || 0) + v;
    }
    const ult12 = [];
    for (let i = 11; i >= 0; i--) {
      const d = new Date(fim.getFullYear(), fim.getMonth() - i, 1);
      ult12.push([d.getFullYear(), d.getMonth() + 1]);
    }
    const noUlt = new Set(ult12.map(([a, m]) => `${a}${String(m).padStart(2, '0')}`));
    const clim = Array.from({ length: 12 }, () => []);
    const anos = new Set();
    for (const [k, v] of Object.entries(porMes)) {
      if (noUlt.has(k)) continue;
      clim[Number(k.slice(4, 6)) - 1].push(v);
      anos.add(Number(k.slice(0, 4)));
    }
    const normal = clim.map((vs) => (vs.length ? vs.reduce((s, x) => s + x, 0) / vs.length : NaN));
    const recente = ult12.map(([a, m]) => [a, m, porMes[`${a}${String(m).padStart(2, '0')}`] ?? NaN]);
    const totalNormal = normal.reduce((s, x) => s + (isFinite(x) ? x : 0), 0);
    const totalRecente = recente.reduce((s, x) => s + (isFinite(x[2]) ? x[2] : 0), 0);
    const listaAnos = [...anos].sort();
    let seco = 0, chuvoso = 0;
    normal.forEach((v, i) => {
      if (v < normal[seco]) seco = i;
      if (v > normal[chuvoso]) chuvoso = i;
    });
    return {
      normal, recente, totalNormal, totalRecente,
      desvioPct: totalNormal ? (100 * (totalRecente - totalNormal)) / totalNormal : NaN,
      periodoNormal: listaAnos.length ? `${listaAnos[0]}-${listaAnos[listaAnos.length - 1]}` : '-',
      mesSeco: seco, mesChuvoso: chuvoso,
      fonte: 'NASA POWER / MERRA-2 (grade de ~0,5° × 0,625°)',
    };
  }

  // ------------------------------------------------------------ valor da terra

  const cacheCsv = {};
  async function lerCsv(nome) {
    if (!cacheCsv[nome]) {
      cacheCsv[nome] = fetch(RF.dadosBase() + nome).then((r) => {
        if (!r.ok) throw new Error('Tabela ' + nome + ' indisponível (HTTP ' + r.status + ')');
        return r.text();
      }).then((texto) => {
        const linhas = texto.replace(/^﻿/, '').split(/\r?\n/).filter((l) => l.trim());
        const cab = linhas[0].split(';');
        return linhas.slice(1).map((l) => {
          const v = l.split(';');
          const o = {};
          cab.forEach((c, i) => (o[c] = v[i] == null ? '' : v[i]));
          return o;
        });
      });
    }
    return cacheCsv[nome];
  }

  function numero(v) {
    const x = parseFloat(String(v).replace(',', '.'));
    return isFinite(x) ? x : null;
  }

  const VTN_COLUNAS = [
    ['lavoura_aptidao_boa', 'Lavoura – aptidão boa'],
    ['lavoura_aptidao_regular', 'Lavoura – aptidão regular'],
    ['lavoura_aptidao_restrita', 'Lavoura – aptidão restrita'],
    ['pastagem_plantada', 'Pastagem plantada'],
    ['silvicultura_ou_pastagem_natural', 'Silvicultura ou pastagem natural'],
    ['preservacao_fauna_flora', 'Preservação da fauna e da flora'],
  ];
  const FONTE_VTN = { 1: 'informados pelo município', 2: 'informados por órgão estadual' };

  async function valoresReferencia(municipio, uf, log) {
    const saida = { vtn: null, mercado: null, avisos: [] };
    if (!municipio) {
      saida.avisos.push('Município não identificado: sem ele não há como buscar VTN nem preço de mercado.');
      return saida;
    }
    const alvo = normalizar(municipio);
    try {
      const vtn = await lerCsv('vtn_2026.csv');
      const lin = vtn.find((l) => normalizar(l.uf) === normalizar(uf) && normalizar(l.municipio) === alvo);
      if (lin) {
        saida.vtn = { exercicio: 2026, fonte: FONTE_VTN[lin.fonte] || '', linhas: VTN_COLUNAS.map(([c, rotulo]) => ({ aptidao: rotulo, valor: numero(lin[c]) })) };
        log(`  VTN 2026: ${municipio}/${uf} encontrado.`);
      } else {
        saida.avisos.push(`${municipio}/${uf} não consta na tabela de VTN 2026 da Receita Federal.`);
      }
    } catch (e) {
      saida.avisos.push('Tabela de VTN indisponível: ' + e.message);
    }
    try {
      const mapa = await lerCsv('mercado_municipios_ms_2024.csv');
      const m = mapa.find((l) => normalizar(l.uf) === normalizar(uf) && normalizar(l.municipio) === alvo);
      if (m) {
        const precos = await lerCsv('mercado_ms_2024.csv');
        const linhas = precos.filter((p) => normalizar(p.uf) === normalizar(uf) && String(p.mrt) === String(m.mrt)).map((p) => ({
          nivel: p.nivel, uso: p.uso, vtnMin: numero(p.vtn_min), vtnMediano: numero(p.vtn_mediano), vtnMax: numero(p.vtn_max),
          inconsistencia: (p.inconsistencia_na_fonte || '').trim(),
        }));
        saida.mercado = { mrt: m.mrt, mercado: m.mercado, ano: 2024, linhas };
        log(`  Mercado: MRT-${String(m.mrt).padStart(2, '0')} ${m.mercado}, ${linhas.length} tipologia(s).`);
      } else {
        saida.avisos.push(`Não há tabela de mercado de terras do INCRA carregada para ${municipio}/${uf} (hoje só Mato Grosso do Sul, RAMT 2024).`);
      }
    } catch (e) {
      saida.avisos.push('Tabela de mercado indisponível: ' + e.message);
    }
    return saida;
  }

  async function moduloFiscalTabela(municipio, uf, codIbge) {
    try {
      const t = await lerCsv('modulo_fiscal_2013.csv');
      const l = t.find((x) => (codIbge && x.cod_ibge === String(codIbge)) || (normalizar(x.municipio) === normalizar(municipio) && normalizar(x.uf) === normalizar(uf)));
      return l ? numero(l.modulo_fiscal_ha) : null;
    } catch (e) {
      return null;
    }
  }

  function classificarPorModulos(ha, mf) {
    if (!mf) return [null, null];
    const n = ha / mf;
    if (n <= 4) return [n, 'pequena propriedade (até 4 módulos fiscais)'];
    if (n <= 15) return [n, 'média propriedade (de 4 a 15 módulos fiscais)'];
    return [n, 'grande propriedade (acima de 15 módulos fiscais)'];
  }

  // ------------------------------------------------------------ desenho

  function rgbCss(c, alfa) {
    return alfa == null ? `rgb(${c[0]},${c[1]},${c[2]})` : `rgba(${c[0]},${c[1]},${c[2]},${alfa})`;
  }

  function hexRgb(h) {
    return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  }

  function rampa(paradas) {
    const pos = paradas.map((p) => p[0]);
    const cor = paradas.map((p) => (typeof p[1] === 'string' ? hexRgb(p[1]) : p[1]));
    return (t) => {
      if (!isFinite(t)) return null;
      t = Math.max(pos[0], Math.min(pos[pos.length - 1], t));
      let k = 0;
      while (k < pos.length - 2 && t > pos[k + 1]) k++;
      const f = (t - pos[k]) / (pos[k + 1] - pos[k] || 1);
      return [0, 1, 2].map((j) => Math.round(cor[k][j] + (cor[k + 1][j] - cor[k][j]) * f));
    };
  }

  const RDYLGN = rampa(['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'].map((c, i) => [i / 10, c]));
  const TERRAIN = rampa([[0, [51, 51, 153]], [0.15, [0, 153, 255]], [0.25, [0, 204, 102]], [0.5, [255, 255, 153]], [0.75, [128, 92, 84]], [1, [255, 255, 255]]]);

  function passoBonito(amplitude, alvo) {
    const bruto = amplitude / alvo;
    const p = Math.pow(10, Math.floor(Math.log10(bruto)));
    const f = bruto / p;
    return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
  }

  // Figura de mapa no estilo do relatório: raster, perímetro, eixos em UTM,
  // escala gráfica, norte, e barra de cores ou legenda à direita.
  function figuraMapa(o) {
    const { grade, titulo } = o;
    const L = 1500;
    const direita = o.legenda ? 390 : o.barra ? 190 : 50;
    const esq = 140, topo = 90, base = 90;
    const [e0, e1, n0, n1] = grade.extent;
    const larguraUtil = L - esq - direita;
    const escala = larguraUtil / (e1 - e0);
    const alturaPlot = (n1 - n0) * escala;
    const A = Math.round(topo + alturaPlot + base);
    const cv = document.createElement('canvas');
    cv.width = L;
    cv.height = A;
    const g = cv.getContext('2d');
    g.fillStyle = '#fff';
    g.fillRect(0, 0, L, A);
    const X = (e) => esq + (e - e0) * escala;
    const Y = (n) => topo + (n1 - n) * escala;

    // raster
    const img = document.createElement('canvas');
    img.width = grade.nx;
    img.height = grade.ny;
    const ig = img.getContext('2d');
    const dados = ig.createImageData(grade.nx, grade.ny);
    for (let i = 0; i < grade.nx * grade.ny; i++) {
      const c = o.pixel(i);
      if (!c) continue;
      dados.data[i * 4] = c[0];
      dados.data[i * 4 + 1] = c[1];
      dados.data[i * 4 + 2] = c[2];
      dados.data[i * 4 + 3] = 255;
    }
    ig.putImageData(dados, 0, 0);
    g.imageSmoothingEnabled = !!o.suavizar;
    g.drawImage(img, esq, topo, larguraUtil, alturaPlot);

    // curvas (hipsometria)
    if (o.curvas) o.curvas(g, X, Y);

    // grade de coordenadas e rótulos
    g.strokeStyle = 'rgba(0,0,0,0.18)';
    g.setLineDash([4, 6]);
    g.lineWidth = 1;
    g.fillStyle = '#333';
    g.font = '20px Arial';
    const pe = passoBonito(e1 - e0, 5);
    g.textAlign = 'center';
    for (let e = Math.ceil(e0 / pe) * pe; e <= e1; e += pe) {
      g.beginPath();
      g.moveTo(X(e), topo);
      g.lineTo(X(e), topo + alturaPlot);
      g.stroke();
      g.fillText(String(Math.round(e)), X(e), topo + alturaPlot + 30);
    }
    const pn = passoBonito(n1 - n0, 5);
    g.textAlign = 'right';
    for (let n = Math.ceil(n0 / pn) * pn; n <= n1; n += pn) {
      g.beginPath();
      g.moveTo(esq, Y(n));
      g.lineTo(esq + larguraUtil, Y(n));
      g.stroke();
      g.fillText(String(Math.round(n)), esq - 10, Y(n) + 7);
    }
    g.setLineDash([]);
    g.strokeStyle = '#222';
    g.lineWidth = 1.5;
    g.strokeRect(esq, topo, larguraUtil, alturaPlot);

    // perímetro: branco por baixo, vermelho por cima
    for (const [largura, cor] of [[7, '#ffffff'], [3.5, '#d32f2f']]) {
      g.strokeStyle = cor;
      g.lineWidth = largura;
      g.lineJoin = 'round';
      for (const [ext, ints] of o.aneis) {
        for (const anel of [ext, ...ints]) {
          g.beginPath();
          anel.forEach((p, k) => (k ? g.lineTo(X(p[0]), Y(p[1])) : g.moveTo(X(p[0]), Y(p[1]))));
          g.stroke();
        }
      }
    }

    // título
    g.fillStyle = rgbCss(COR.escuro);
    g.font = 'bold 30px Arial';
    g.textAlign = 'center';
    g.fillText(titulo, esq + larguraUtil / 2, 55);

    // escala gráfica
    const larg = e1 - e0;
    let passo = Math.pow(10, Math.floor(Math.log10(larg / 4)));
    for (const m of [5, 2, 1]) {
      if (passo * m <= larg / 3) {
        passo *= m;
        break;
      }
    }
    const bx = X(e0 + larg * 0.05);
    const by = Y(n0 + (n1 - n0) * 0.05);
    const bw = passo * escala;
    g.fillStyle = '#000';
    g.fillRect(bx, by - 14, bw, 14);
    g.fillStyle = '#fff';
    g.fillRect(bx + bw, by - 14, bw, 14);
    g.strokeStyle = '#000';
    g.lineWidth = 2;
    g.strokeRect(bx, by - 14, bw * 2, 14);
    g.font = 'bold 20px Arial';
    g.textAlign = 'center';
    const rotulo = passo * 2 < 1000 ? `${Math.round(passo * 2)} m` : `${num((passo * 2) / 1000, 1)} km`;
    g.fillStyle = 'rgba(255,255,255,0.8)';
    const tw = g.measureText(rotulo).width;
    g.fillRect(bx + bw - tw / 2 - 6, by - 44, tw + 12, 26);
    g.fillStyle = '#000';
    g.fillText(rotulo, bx + bw, by - 24);

    // norte
    const nxp = esq + larguraUtil - 55;
    const nyp = topo + 60;
    g.fillStyle = 'rgba(255,255,255,0.8)';
    g.fillRect(nxp - 26, nyp - 42, 52, 110);
    g.fillStyle = '#000';
    g.font = 'bold 30px Arial';
    g.fillText('N', nxp, nyp - 10);
    g.beginPath();
    g.moveTo(nxp, nyp);
    g.lineTo(nxp - 13, nyp + 30);
    g.lineTo(nxp + 13, nyp + 30);
    g.closePath();
    g.fill();
    g.fillRect(nxp - 3, nyp + 28, 6, 32);

    // barra de cores
    if (o.barra) {
      const { rampa: cmap, min, max, rotulo: rot } = o.barra;
      const x = esq + larguraUtil + 35;
      const h = alturaPlot * 0.9;
      const y = topo + (alturaPlot - h) / 2;
      for (let k = 0; k < h; k++) {
        const c = cmap(1 - k / h);
        g.fillStyle = rgbCss(c);
        g.fillRect(x, y + k, 36, 1.5);
      }
      g.strokeStyle = '#333';
      g.lineWidth = 1;
      g.strokeRect(x, y, 36, h);
      g.fillStyle = '#333';
      g.font = '20px Arial';
      g.textAlign = 'left';
      const pb = passoBonito(max - min, 6);
      for (let v = Math.ceil(min / pb) * pb; v <= max + 1e-9; v += pb) {
        const yy = y + h - ((v - min) / (max - min)) * h;
        g.fillRect(x + 36, yy - 1, 8, 2);
        g.fillText(num(v, pb < 1 ? 1 : 0), x + 50, yy + 7);
      }
      g.save();
      g.translate(x + 150, y + h / 2);
      g.rotate(-Math.PI / 2);
      g.textAlign = 'center';
      g.fillText(rot, 0, 0);
      g.restore();
    }

    // legenda de classes
    if (o.legenda) {
      let y = topo + 10;
      const x = esq + larguraUtil + 30;
      g.font = '21px Arial';
      g.textAlign = 'left';
      for (const [cor, texto] of o.legenda) {
        g.fillStyle = cor;
        g.fillRect(x, y, 34, 24);
        g.strokeStyle = 'rgba(0,0,0,0.3)';
        g.strokeRect(x, y, 34, 24);
        g.fillStyle = '#222';
        g.fillText(texto, x + 46, y + 19);
        y += 38;
      }
    }
    return cv;
  }

  function figuraSerie(linhas, titulo, ha) {
    const L = 1700, A = 760;
    const esq = 110, dir = 40, topo = 80, base = 110;
    const cv = document.createElement('canvas');
    cv.width = L;
    cv.height = A;
    const g = cv.getContext('2d');
    g.fillStyle = '#fff';
    g.fillRect(0, 0, L, A);
    const t = linhas.map((l) => new Date(l.data + 'T12:00:00Z').getTime());
    const t0 = t[0], t1 = t[t.length - 1] || t0 + 1;
    const ymin = Math.min(-0.05, Math.min(...linhas.map((l) => l.p10)) - 0.05);
    const ymax = Math.max(1, Math.max(...linhas.map((l) => l.p90)) + 0.05);
    const W = L - esq - dir, H = A - topo - base;
    const X = (x) => esq + ((x - t0) / (t1 - t0 || 1)) * W;
    const Y = (y) => topo + (1 - (y - ymin) / (ymax - ymin)) * H;
    g.fillStyle = 'rgba(200,161,101,0.16)';
    g.fillRect(esq, Y(0.2), W, Y(ymin) - Y(0.2));
    g.fillStyle = '#7a5c2e';
    g.font = '19px Arial';
    g.textAlign = 'left';
    g.fillText('solo exposto / palhada', esq + 10, Y(0.1) + 6);
    // faixa P10–P90
    g.fillStyle = 'rgba(26,111,196,0.18)';
    g.beginPath();
    linhas.forEach((l, i) => (i ? g.lineTo(X(t[i]), Y(l.p90)) : g.moveTo(X(t[i]), Y(l.p90))));
    for (let i = linhas.length - 1; i >= 0; i--) g.lineTo(X(t[i]), Y(linhas[i].p10));
    g.closePath();
    g.fill();
    // grade e eixos
    g.strokeStyle = 'rgba(0,0,0,0.15)';
    g.setLineDash([3, 5]);
    g.fillStyle = '#333';
    g.font = '19px Arial';
    g.textAlign = 'right';
    for (let v = Math.ceil(ymin * 5) / 5; v <= ymax + 1e-9; v += 0.2) {
      g.beginPath();
      g.moveTo(esq, Y(v));
      g.lineTo(esq + W, Y(v));
      g.stroke();
      g.fillText(num(Math.abs(v) < 1e-9 ? 0 : v, 1), esq - 10, Y(v) + 6);
    }
    const inicio = new Date(t0);
    let mes = new Date(Date.UTC(inicio.getUTCFullYear(), inicio.getUTCMonth() + 1, 1));
    while (mes.getTime() <= t1) {
      const x = X(mes.getTime());
      g.beginPath();
      g.moveTo(x, topo);
      g.lineTo(x, topo + H);
      g.stroke();
      g.save();
      g.translate(x, topo + H + 16);
      g.rotate(-Math.PI / 4);
      g.textAlign = 'right';
      g.fillText(`${MESES[mes.getUTCMonth()]}/${String(mes.getUTCFullYear() % 100).padStart(2, '0')}`, 0, 10);
      g.restore();
      mes = new Date(Date.UTC(mes.getUTCFullYear(), mes.getUTCMonth() + 1, 1));
    }
    g.setLineDash([]);
    g.strokeStyle = '#333';
    g.strokeRect(esq, topo, W, H);
    // linha do NDVI médio
    g.strokeStyle = rgbCss(COR.azul);
    g.lineWidth = 3.5;
    g.beginPath();
    linhas.forEach((l, i) => (i ? g.lineTo(X(t[i]), Y(l.medio)) : g.moveTo(X(t[i]), Y(l.medio))));
    g.stroke();
    g.fillStyle = rgbCss(COR.azul);
    linhas.forEach((l, i) => {
      g.beginPath();
      g.arc(X(t[i]), Y(l.medio), 5.5, 0, 2 * Math.PI);
      g.fill();
    });
    g.save();
    g.translate(35, topo + H / 2);
    g.rotate(-Math.PI / 2);
    g.textAlign = 'center';
    g.fillStyle = '#333';
    g.fillText('NDVI', 0, 0);
    g.restore();
    g.fillStyle = rgbCss(COR.escuro);
    g.font = 'bold 28px Arial';
    g.textAlign = 'center';
    g.fillText(`${titulo} – ${num(ha, 1)} ha`, esq + W / 2, 50);
    // legenda
    g.font = '19px Arial';
    g.textAlign = 'left';
    g.fillStyle = 'rgba(255,255,255,0.9)';
    g.fillRect(esq + 12, topo + 12, 390, 70);
    g.fillStyle = 'rgba(26,111,196,0.3)';
    g.fillRect(esq + 24, topo + 22, 36, 18);
    g.fillStyle = '#222';
    g.fillText('faixa P10–P90 (variabilidade interna)', esq + 70, topo + 38);
    g.strokeStyle = rgbCss(COR.azul);
    g.lineWidth = 3.5;
    g.beginPath();
    g.moveTo(esq + 24, topo + 64);
    g.lineTo(esq + 60, topo + 64);
    g.stroke();
    g.fillText('NDVI médio da área', esq + 70, topo + 70);
    g.fillStyle = '#666';
    g.font = '16px Arial';
    g.fillText('Fonte: Copernicus Sentinel-2 (ESA) | AJ TopoGeo', 10, A - 12);
    return cv;
  }

  function figuraChuva(ch) {
    const L = 1600, A = 740;
    const esq = 110, dir = 40, topo = 80, base = 130;
    const cv = document.createElement('canvas');
    cv.width = L;
    cv.height = A;
    const g = cv.getContext('2d');
    g.fillStyle = '#fff';
    g.fillRect(0, 0, L, A);
    const vals = ch.recente.map((r) => (isFinite(r[2]) ? r[2] : 0));
    const norm = ch.recente.map((r) => ch.normal[r[1] - 1]);
    const ymax = Math.max(10, ...vals, ...norm.filter(isFinite)) * 1.1;
    const W = L - esq - dir, H = A - topo - base;
    const passoX = W / 12;
    const Y = (v) => topo + H - (v / ymax) * H;
    g.strokeStyle = 'rgba(0,0,0,0.15)';
    g.setLineDash([3, 5]);
    g.fillStyle = '#333';
    g.font = '19px Arial';
    g.textAlign = 'right';
    const py = passoBonito(ymax, 6);
    for (let v = 0; v <= ymax; v += py) {
      g.beginPath();
      g.moveTo(esq, Y(v));
      g.lineTo(esq + W, Y(v));
      g.stroke();
      g.fillText(String(Math.round(v)), esq - 10, Y(v) + 6);
    }
    g.setLineDash([]);
    ch.recente.forEach((r, i) => {
      const x = esq + i * passoX + passoX * 0.16;
      g.fillStyle = vals[i] >= norm[i] ? rgbCss(COR.marca) : '#e07b39';
      g.fillRect(x, Y(vals[i]), passoX * 0.68, Y(0) - Y(vals[i]));
      g.save();
      g.translate(esq + i * passoX + passoX / 2, topo + H + 16);
      g.rotate(-Math.PI / 4);
      g.textAlign = 'right';
      g.fillStyle = '#333';
      g.fillText(`${MESES[r[1] - 1]}/${String(r[0] % 100).padStart(2, '0')}`, 0, 10);
      g.restore();
    });
    g.strokeStyle = rgbCss(COR.escuro);
    g.lineWidth = 3;
    g.beginPath();
    norm.forEach((v, i) => {
      const x = esq + i * passoX + passoX / 2;
      i ? g.lineTo(x, Y(v)) : g.moveTo(x, Y(v));
    });
    g.stroke();
    g.fillStyle = rgbCss(COR.escuro);
    norm.forEach((v, i) => {
      g.beginPath();
      g.arc(esq + i * passoX + passoX / 2, Y(v), 5, 0, 2 * Math.PI);
      g.fill();
    });
    g.strokeStyle = '#333';
    g.lineWidth = 1.5;
    g.strokeRect(esq, topo, W, H);
    g.save();
    g.translate(35, topo + H / 2);
    g.rotate(-Math.PI / 2);
    g.textAlign = 'center';
    g.fillStyle = '#333';
    g.font = '19px Arial';
    g.fillText('Precipitação (mm)', 0, 0);
    g.restore();
    g.fillStyle = rgbCss(COR.escuro);
    g.font = 'bold 28px Arial';
    g.textAlign = 'center';
    g.fillText('Precipitação mensal – últimos 12 meses e normal', esq + W / 2, 50);
    g.font = '19px Arial';
    g.textAlign = 'left';
    const lx = esq + W - 330;
    g.fillStyle = 'rgba(255,255,255,0.9)';
    g.fillRect(lx, topo + 10, 320, 66);
    g.fillStyle = rgbCss(COR.marca);
    g.fillRect(lx + 12, topo + 20, 30, 18);
    g.fillStyle = '#222';
    g.fillText('últimos 12 meses', lx + 52, topo + 36);
    g.strokeStyle = rgbCss(COR.escuro);
    g.beginPath();
    g.moveTo(lx + 12, topo + 58);
    g.lineTo(lx + 42, topo + 58);
    g.stroke();
    g.fillText(`normal ${ch.periodoNormal}`, lx + 52, topo + 64);
    g.fillStyle = '#666';
    g.font = '16px Arial';
    g.fillText('Fonte: ' + ch.fonte, 10, A - 12);
    return cv;
  }

  // ------------------------------------------------------------ PDF

  function montarPdf(d) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'mm', format: 'a4' });
    const ML = 18, MR = 18, MT = 16, MB = 22;
    const PW = 210, PH = 297, LU = PW - ML - MR;
    let y = MT;
    const ha = d.ha;

    const novaPagina = () => {
      doc.addPage();
      y = MT;
    };
    const garantir = (h) => {
      if (y + h > PH - MB) novaPagina();
    };
    const cor = (c) => doc.setTextColor(c[0], c[1], c[2]);
    const h1 = (t) => {
      garantir(14);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(13);
      cor(COR.azul);
      doc.text(t, ML, y + 5);
      y += 10;
    };
    const h2 = (t) => {
      garantir(12);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10.5);
      cor(COR.marca);
      doc.text(t, ML, y + 4);
      y += 8;
    };
    const par = (t, opcoes) => {
      const o = Object.assign({ tamanho: 9, cor: COR.texto, negrito: false, entrelinha: 4.6, justificar: true }, opcoes || {});
      doc.setFont('helvetica', o.negrito ? 'bold' : 'normal');
      doc.setFontSize(o.tamanho);
      cor(o.cor);
      const linhas = doc.splitTextToSize(t, LU);
      linhas.forEach((linha, i) => {
        garantir(o.entrelinha);
        const ultima = i === linhas.length - 1;
        if (o.justificar && !ultima) doc.text(linha, ML, y + 3.4, { maxWidth: LU, align: 'justify' });
        else doc.text(linha, ML, y + 3.4);
        y += o.entrelinha;
      });
      y += 1.5;
    };
    const nota = (t) => par(t, { tamanho: 7.8, cor: COR.nota, entrelinha: 3.8 });
    const espaco = (mm) => (y += mm);
    const figura = (cv, largura) => {
      const w = largura || 165;
      const h = (w * cv.height) / cv.width;
      garantir(h + 2);
      doc.addImage(cv.toDataURL('image/jpeg', 0.9), 'JPEG', ML + (LU - w) / 2, y, w, h, undefined, 'FAST');
      y += h + 2;
    };
    const tabela = (cabecalho, corpo, colunas, opcoes) => {
      doc.autoTable(Object.assign({
        startY: y,
        head: cabecalho ? [cabecalho] : undefined,
        body: corpo,
        margin: { left: ML, right: MR, bottom: MB },
        theme: 'grid',
        styles: { font: 'helvetica', fontSize: 8, cellPadding: 1.6, textColor: COR.texto, lineColor: COR.linha, lineWidth: 0.25, valign: 'middle' },
        headStyles: { fillColor: COR.claro, textColor: COR.escuro, fontStyle: 'bold' },
        alternateRowStyles: { fillColor: COR.fundo },
        columnStyles: colunas || {},
      }, opcoes || {}));
      y = doc.lastAutoTable.finalY + 3;
    };

    // ---------------- capa
    if (window.LOGO_B64) {
      try {
        doc.addImage(window.LOGO_B64, 'PNG', PW / 2 - 26, y, 52, 26, undefined, 'FAST');
        y += 30;
      } catch (e) { /* logo é enfeite */ }
    }
    y += 10;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(16);
    cor(COR.azul);
    doc.text(doc.splitTextToSize('RELATÓRIO TÉCNICO DE CARACTERIZAÇÃO DE IMÓVEL RURAL', LU - 20), PW / 2, y, { align: 'center' });
    y += 20;
    doc.setFontSize(20);
    cor(COR.texto);
    doc.text(d.nome, PW / 2, y, { align: 'center' });
    y += 8;
    doc.setFontSize(9);
    doc.text(`${d.municipio} – ${d.uf}`, PW / 2, y, { align: 'center' });
    y += 6;
    if (d.figRgb) figura(d.figRgb, 112);
    espaco(4);
    tabela(null, [
      [d.perimetroFonte === 'enviado' ? 'Área do perímetro informado' : `Área analisada (perímetro do ${d.perimetroFonte === 'sigef' ? 'SIGEF' : 'CAR'})`, `${num(ha, 4)} ha`],
      ['Perímetro', `${num(d.perimetro, 2)} m`],
      ['Sistema de referência', `SIRGAS 2000 / UTM ${d.sis.fuso}${d.sis.sul ? 'S' : 'N'} (EPSG:${d.sis.epsg})`],
      ['Data de emissão', d.data],
      ['Responsável técnico', d.responsavel || '–'],
    ], { 0: { cellWidth: 72 } }, { margin: { left: ML + 7, right: MR + 7 }, alternateRowStyles: {} });

    // ---------------- diagnóstico executivo
    novaPagina();
    h1('DIAGNÓSTICO EXECUTIVO');
    par('Ficha-resumo do imóvel e verificação de conformidade contra as bases públicas cruzadas nesta execução. Os números abaixo são os mesmos usados nos capítulos correspondentes — nenhum valor é digitado duas vezes.');
    if (d.perimetroFonte !== 'enviado') {
      const FONTE_PERIM_NOME2 = { sigef: 'SIGEF/INCRA', car: 'CAR/SICAR' };
      nota(`Perímetro analisado: ${FONTE_PERIM_NOME2[d.perimetroFonte]} (${num(ha, 2)} ha), não o arquivo enviado (${num(d.perimetroEnviadoHa, 2)} ha) — o oficial é maior. Detalhe em 1.`);
    }
    espaco(1);
    tabela(['Área', 'Município', 'UF', 'Módulos fiscais', 'RL mínima (Lei 12.651)'], [[
      `${num(ha, 2)} ha`, d.municipio, d.uf,
      d.modulo ? `${num(d.modulo.n, 2)} – ${d.modulo.classe}` : 'não identificado',
      d.rl.pctMin != null ? `${d.rl.pctMin} % = ${num(d.rl.minHa, 2)} ha` : 'requer classificação de bioma',
    ]]);
    espaco(2);
    h2('Conformidade e riscos');
    const itensDiag = [];
    const diag = (nome, status, texto) => itensDiag.push({ nome, status, texto });
    if (d.car.resultados == null) diag('Cadastro Ambiental Rural (CAR)', 'SEM_DADOS', 'Não foi possível consultar.');
    else if (!d.car.resultados.length) diag('Cadastro Ambiental Rural (CAR)', 'ATENCAO', 'Nenhum registro do CAR sobreposto ao perímetro.');
    else {
      const p = d.car.resultados[0];
      const dif = Math.abs(ha - p.area_feicao_ha);
      diag('Cadastro Ambiental Rural (CAR)', dif > Math.max(0.5, ha * 0.01) ? 'ATENCAO' : 'CONFORME',
        dif > Math.max(0.5, ha * 0.01) ? `Área do CAR diverge ${num(dif, 2)} ha da informada.` : 'Sobreposição encontrada, área compatível.');
    }
    if (d.sigef.resultados == null) diag('Georreferenciamento (SIGEF)', 'SEM_DADOS', 'Não foi possível consultar.');
    else if (!d.sigef.resultados.length) diag('Georreferenciamento (SIGEF)', 'ATENCAO', 'Imóvel sem certificação SIGEF localizada.');
    else diag('Georreferenciamento (SIGEF)', 'CONFORME', `${d.sigef.resultados.length} parcela(s) certificada(s) sobreposta(s).`);
    for (const [chave, nomeItem] of [['ti', 'Terra Indígena'], ['uc', 'Unidade de Conservação federal'], ['assentamento', 'Assentamento'], ['quilombola', 'Território quilombola']]) {
      const r = d.restricoes[chave];
      if (r.resultados == null) diag(nomeItem, 'SEM_DADOS', 'Não foi possível consultar.');
      else if (r.resultados.length) diag(nomeItem, 'CRITICO', `Sobreposição direta com ${r.resultados.length} feição(ões).`);
      else if (r.entorno.length) diag(nomeItem, 'CONFORME', `Sem sobreposição; a mais próxima está a ${num(r.entorno[0].distanciaKm, 1)} km (entorno de ${r.raioKm} km consultado).`);
      else diag(nomeItem, 'CONFORME', `Sem sobreposição nem ocorrência no entorno de ${r.raioKm} km consultado.`);
    }
    if (d.embargos.resultados == null) diag('Embargos ambientais (IBAMA)', 'SEM_DADOS', 'Não foi possível consultar.');
    else if (d.embargos.resultados.length) diag('Embargos ambientais (IBAMA)', 'CRITICO', `${d.embargos.resultados.length} termo(s) de embargo sobrepõe(m) o perímetro.`);
    else diag('Embargos ambientais (IBAMA)', 'CONFORME', 'Nenhum termo de embargo sobreposto.');
    diag('Reserva Legal — mínimo legal', 'SEM_DADOS', d.rl.pctMin != null
      ? `Mínimo calculado: ${num(d.rl.minHa, 2)} ha. Conformidade real depende da RL averbada e da vegetação nativa existente — não medidas nesta execução.`
      : d.rl.nota);
    const CORES_STATUS = { CONFORME: [39, 80, 10], ATENCAO: [156, 97, 9], CRITICO: [163, 45, 45], SEM_DADOS: [102, 102, 102] };
    const ROTULOS_STATUS = { CONFORME: 'CONFORME', ATENCAO: 'ATENÇÃO', CRITICO: 'CRÍTICO', SEM_DADOS: 'SEM DADOS' };
    tabela(['Item', 'Status', 'Leitura'], itensDiag.map((l) => [l.nome, { content: ROTULOS_STATUS[l.status], styles: { textColor: CORES_STATUS[l.status], fontStyle: 'bold' } }, l.texto]),
      { 0: { cellWidth: 50 }, 1: { cellWidth: 22 }, 2: { fontSize: 7.6 } });
    const relevantes = itensDiag.filter((l) => l.status === 'CRITICO' || l.status === 'ATENCAO');
    if (relevantes.length) {
      espaco(1);
      h2('Principais pontos de atenção');
      relevantes.slice(0, 5).forEach((l) => par(`– ${l.nome}: ${l.texto}`));
    }
    if (d.parIou.length) {
      const mesma = d.parIou.filter((p) => p.classe === 'mesma_terra').length;
      nota(`Pareamento SIGEF × CAR (ver 1.3): ${d.parIou.length} parcela(s) do SIGEF cruzada(s) com o CAR, sendo ${mesma} classificada(s) como mesma terra (IoU ≥ 95 %).`);
    }
    nota('Diagnóstico automático a partir das mesmas consultas detalhadas nos capítulos seguintes. "Sem dados" indica falha na consulta ao vivo, não conformidade — gerar de novo tenta a consulta outra vez.');

    // ---------------- 1. cadastral
    novaPagina();
    h1('1. IDENTIFICAÇÃO E SITUAÇÃO CADASTRAL');
    const FONTE_PERIM_NOME = { enviado: 'arquivo enviado', sigef: 'SIGEF/INCRA', car: 'CAR/SICAR' };
    if (d.perimetroFonte === 'enviado') {
      par('Os limites analisados são os do arquivo enviado. As consultas abaixo verificam a existência de registros oficiais que se sobrepõem a esse polígono. Sobreposição parcial não significa erro: pode indicar limite desatualizado, desmembramento não averbado ou divergência entre o levantamento e o cadastro.');
    } else {
      par(`O arquivo enviado tem ${num(d.perimetroEnviadoHa, 4)} ha — menor que o registro do ${FONTE_PERIM_NOME[d.perimetroFonte]} sobreposto a ele. Por isso os limites analisados neste relatório são os do ${FONTE_PERIM_NOME[d.perimetroFonte]} (${num(ha, 4)} ha), não os do arquivo enviado: entre um perímetro enviado incompleto e o registro oficial maior, o relatório usa o oficial. Se o perímetro enviado é o correto (ex.: retificação em andamento, ainda não refletida no cadastro), desconsidere esta troca e confira a área diretamente pelo arquivo original.`);
    }
    const itens = [[d.perimetroFonte === 'enviado' ? 'Área do perímetro enviado' : `Área analisada (${FONTE_PERIM_NOME[d.perimetroFonte]})`, `${num(ha, 4)} ha`], ['Município', d.municipioFonte]];
    if (d.modulo) {
      itens.push(['Módulo fiscal do município', `${num(d.modulo.mf, 0)} ha – ${d.modulo.fonte}`]);
      itens.push(['Módulos fiscais do imóvel', `${num(d.modulo.n, 2)} – ${d.modulo.classe}`]);
    } else {
      itens.push(['Módulo fiscal', 'não identificado']);
    }
    itens.push(['Reserva Legal mínima (Lei 12.651)', d.rl.pctMin != null ? `${d.rl.pctMin} % = ${num(d.rl.minHa, 4)} ha` : 'requer classificação de bioma (ver 1.4)']);
    tabela(['Item', 'Situação'], itens, { 0: { cellWidth: 58 } });
    const STATUS = { AT: 'ativo', PE: 'pendente', SU: 'suspenso', CA: 'cancelado' };
    for (const [chave, titulo] of [['car', '1.1 Cadastro Ambiental Rural (CAR)'], ['sigef', '1.2 Georreferenciamento certificado (SIGEF/INCRA)']]) {
      espaco(2);
      h2(titulo);
      const cad = d[chave];
      if (cad.resultados == null) {
        par(cad.aviso || 'Não foi possível consultar.');
        continue;
      }
      if (!cad.resultados.length) {
        par(`Consulta realizada (${cad.origem}) e nenhum registro sobreposto foi localizado. Para o CAR, isso sugere imóvel sem cadastro; para o SIGEF, imóvel sem certificação. Confirme sempre na consulta oficial antes de qualquer ato.`);
        continue;
      }
      par(`Base consultada: ${cad.origem}. ${cad.resultados.length} registro(s) sobreposto(s) ao perímetro.`);
      const corpo = cad.resultados.slice(0, 8).map((r, i) => {
        const a = r.atributos;
        const ident = chave === 'car'
          ? [a.cod_imovel || '–', a.status_imovel ? `situação: ${a.status_imovel} (${STATUS[a.status_imovel] || '?'})` : '', a.condicao || '', a.municipio || ''].filter(Boolean).join('\n')
          : [a.parcela_codigo || '–', a.natureza ? `parcela ${a.natureza}` : '', a.data_aprovacao ? `certificada em ${dataBr(a.data_aprovacao)}` : '', a.registro_data ? `registro em ${dataBr(a.registro_data)}` : ''].filter(Boolean).join('\n');
        return [String(i + 1), ident, num(r.area_feicao_ha, 2), num(r.area_comum_ha, 2), num(r.pct_do_perimetro, 1), num(r.pct_da_feicao, 1)];
      });
      tabela(['#', 'Identificação', 'Área cad. (ha)', 'Comum (ha)', '% do perím.', '% da feição'], corpo, {
        0: { cellWidth: 8 }, 1: { cellWidth: 70, fontSize: 7.2 },
        2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' }, 5: { halign: 'right' },
      });
      const principal = cad.resultados[0];
      const dif = ha - principal.area_feicao_ha;
      if (Math.abs(dif) > Math.max(0.5, ha * 0.01)) {
        par(`Divergência de área: o perímetro informado tem ${num(ha, 4)} ha e o registro principal declara ${num(principal.area_feicao_ha, 4)} ha – diferença de ${num(dif, 4)} ha (${num((100 * dif) / principal.area_feicao_ha, 2)} %). Recomenda-se a conferência dos limites e, se confirmada, a retificação do cadastro.`);
      }
    }

    espaco(2);
    h2('1.3 Pareamento SIGEF × CAR');
    par('Compara a geometria de cada parcela SIGEF sobreposta ao perímetro com o CAR mais próximo, pela razão entre a área comum e a área conjunta dos dois (IoU). O pareamento só compara geometria — nunca infere quem é o titular a partir dele.');
    if (!d.parIou.length) {
      par('Nenhuma parcela SIGEF sobreposta ao perímetro para parear com o CAR.');
    } else {
      const ROT_CLASSE = { mesma_terra: 'mesma terra (IoU ≥ 95 %)', pareado: 'pareado (IoU ≥ 70 %)', sobreposicao_parcial: 'sobreposição parcial' };
      tabela(['Parcela SIGEF', 'Imóvel CAR', 'Área SIGEF (ha)', 'Área CAR (ha)', 'IoU', 'Classe'],
        d.parIou.slice(0, 8).map((p) => [p.sigef.parcela_codigo || '–', p.car.cod_imovel || '–', num(p.areaSigefHa, 2), num(p.areaCarHa, 2), `${num(p.iouPct, 1)} %`, ROT_CLASSE[p.classe]]),
        { 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' }, 5: { fontSize: 7.4 } });
      nota('IoU (interseção sobre união) mede o quanto as duas geometrias coincidem. Abaixo de 70 % as áreas divergem demais para tratar como a mesma terra — pode ser desmembramento, remembramento ou cadastro desatualizado.');
    }

    espaco(2);
    h2('1.4 Reserva Legal — enquadramento legal');
    par(d.rl.baseLegal);
    if (d.rl.pctMin != null) {
      par(`Mínimo exigido: ${d.rl.pctMin} % da área do imóvel = ${num(d.rl.minHa, 4)} ha.`);
    } else {
      par(d.rl.nota);
    }
    if (d.rl.art67) par(d.rl.art67);
    nota('Este cálculo é o mínimo legal, não uma verificação de conformidade: dizer se a Reserva Legal exigida está cumprida exige medir a vegetação nativa existente (MapBiomas ou classificação equivalente) e conferir a RL averbada na matrícula — nenhuma das duas foi feita nesta execução. O art. 15 (cômputo de APP dentro da RL) e o art. 12, §§ 4º–5º (redução a 50 % com ZEE/UC/TI) são possibilidades que dependem de análise caso a caso e não foram aplicados automaticamente.');

    // ---------------- 2. diagnóstico fundiário e ambiental
    novaPagina();
    h1('2. DIAGNÓSTICO FUNDIÁRIO E AMBIENTAL');
    par('Sobreposição exata do perímetro com Terra Indígena, Unidade de Conservação federal, assentamento e território quilombola; e, quando não há sobreposição, a distância até a ocorrência mais próxima dentro do raio consultado. O mesmo raio declarado no texto é o raio efetivamente consultado.');
    const CAMPOS_ID = {
      ti: ['terrai_nom', 'nome', 'ti_nome', 'terra_indi'],
      uc: ['nome_uc', 'nome', 'nome_uc1', 'nm_uc'],
      assentamento: ['nome_proje', 'nome_pa', 'nome', 'projeto'],
      quilombola: ['nome_comun', 'comunidade', 'nome'],
    };
    const NUM = { ti: '2.1', uc: '2.2', assentamento: '2.3', quilombola: '2.4' };
    const TITULOS = {
      ti: 'Terra Indígena (FUNAI)', uc: 'Unidade de Conservação federal (ICMBio)',
      assentamento: 'Assentamento (INCRA)', quilombola: 'Território quilombola (INCRA/Fundação Palmares)',
    };
    for (const chave of ['ti', 'uc', 'assentamento', 'quilombola']) {
      espaco(2);
      h2(`${NUM[chave]} ${TITULOS[chave]}`);
      const r = d.restricoes[chave];
      if (r.resultados == null) {
        par(r.aviso || 'Não foi possível consultar.');
        continue;
      }
      if (r.resultados.length) {
        par(`Base consultada: ${r.origem}. ${r.resultados.length} feição(ões) sobreposta(s) ao perímetro.`);
        tabela(['#', 'Identificação', 'Área da feição (ha)', 'Área comum (ha)', '% do perímetro'],
          r.resultados.slice(0, 6).map((f, i) => [String(i + 1), pick(f.atributos, CAMPOS_ID[chave]) || `(ver consulta oficial, ${Object.keys(f.atributos).length} campo(s) na fonte)`,
            num(f.area_feicao_ha, 2), num(f.area_comum_ha, 2), `${num(f.pct_do_perimetro, 1)} %`],
          ), { 0: { cellWidth: 8 }, 1: { cellWidth: 68, fontSize: 7.4 }, 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' } });
      } else if (r.entorno.length) {
        par(`Base consultada: ${r.origem}. Nenhuma sobreposição direta. Ocorrência(s) no entorno de ${r.raioKm} km:`);
        tabela(['Identificação', 'Distância (km)'], r.entorno.map((e) => [pick(e.atributos, CAMPOS_ID[chave]) || '(ver consulta oficial)', num(e.distanciaKm, 1)]), { 1: { halign: 'right' } });
      } else {
        par(`Base consultada: ${r.origem}. Sem sobreposição e sem ocorrência no entorno de ${r.raioKm} km consultado.`);
      }
    }
    espaco(2);
    h2('2.5 Embargos ambientais (IBAMA/SISCOM)');
    if (d.embargos.resultados == null) {
      par(d.embargos.aviso || 'Não foi possível consultar.');
    } else if (!d.embargos.resultados.length) {
      par(`Base consultada: ${d.embargos.origem}. Nenhum termo de embargo sobreposto ao perímetro.`);
    } else {
      par(`Base consultada: ${d.embargos.origem}. ${d.embargos.resultados.length} termo(s) de embargo sobreposto(s) ao perímetro.`);
      tabela(['#', 'Identificação', 'Área do termo (ha)', 'Área comum (ha)', '% do perímetro'],
        d.embargos.resultados.slice(0, 6).map((f, i) => [String(i + 1),
          pick(f.atributos, ['nu_ato', 'numero_ato', 'nu_auto_infracao', 'seq_embargo']) || `(ver consulta oficial, ${Object.keys(f.atributos).length} campo(s) na fonte)`,
          num(f.area_feicao_ha, 2), num(f.area_comum_ha, 2), `${num(f.pct_do_perimetro, 1)} %`]),
        { 0: { cellWidth: 8 }, 1: { cellWidth: 60 }, 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' } });
      nota('Um termo de embargo restringe o uso da área; não é, por si só, uma condenação — o auto de infração que originou o embargo pode estar em recurso ou já ter sido baixado. Confirme a situação atual na consulta oficial do IBAMA antes de qualquer decisão.');
    }
    nota('Terra Indígena, Unidade de Conservação e território quilombola consultados na base federal; unidades e áreas de proteção estaduais (ex.: Imasul, no caso de MS) não estão nesta consulta. A distância de entorno não é calculada para feições com geometria muito grande (algumas Terras Indígenas e Unidades de Conservação têm dezenas de milhares de vértices) — quando isso ocorre, a feição some da lista de entorno em vez de mostrar uma distância aproximada. Sobreposição parcial não significa irregularidade — pode indicar zona de amortecimento, limite a atualizar ou sobreposição heterogênea já tratada em processo próprio.');

    // ---------------- 3. imagem
    novaPagina();
    h1('3. IMAGEM DE SATÉLITE');
    par(d.textoImagem);
    if (d.figRgb) figura(d.figRgb);

    // ---------------- 4. vegetação
    novaPagina();
    h1('4. ÍNDICES DE VEGETAÇÃO');
    par('O NDVI (índice de vegetação por diferença normalizada) mede o vigor da cobertura vegetal a partir da razão entre as bandas do infravermelho próximo e do vermelho. Varia de -1 a 1: solo exposto e palhada ficam abaixo de 0,20; pastagem em uso, entre 0,30 e 0,55; lavoura em pleno desenvolvimento, acima de 0,65. Os pixels de nuvem e de sombra foram removidos antes do cálculo.');
    if (d.figNdvi) figura(d.figNdvi);
    if (d.stats) {
      const s = d.stats;
      tabela(['NDVI médio', 'Mediana', 'P10', 'P90', 'Desvio', 'Área < 0,20'],
        [[num(s.medio, 3), num(s.mediana, 3), num(s.p10, 3), num(s.p90, 3), num(s.desvio, 3), `${num(s.pctBaixo, 1)} %`]]);
      nota('A distância entre P10 e P90 mede a desigualdade interna da área. Faixa larga indica manejo heterogêneo, falha de estande ou variação de solo dentro do mesmo talhão.');
    }
    if (d.figSerie) {
      espaco(2);
      h2('4.1 Evolução temporal');
      figura(d.figSerie);
      nota(d.textoSerie);
    }

    // ---------------- 5. relevo
    novaPagina();
    h1('5. RELEVO E DECLIVIDADE');
    par(d.textoRelevo);
    if (d.figHipso) figura(d.figHipso);
    if (d.figDecl) figura(d.figDecl);
    if (d.decl && d.decl.linhas.length) {
      tabela(['Classe de relevo', 'Faixa', 'Área (ha)', '% da área'],
        d.decl.linhas.map((r) => [r.classe, r.faixa, num(r.ha, 2), num(r.pct, 1)]),
        { 2: { halign: 'right' }, 3: { halign: 'right' } });
      const rr = d.decl.restricoes;
      espaco(1);
      h2('5.1 Restrições por declividade – Lei 12.651/2012');
      tabela(['Enquadramento', 'Critério', 'Área (ha)', '% da área'], [
        ['APP de encosta (art. 4º, V)', '> 45° (100 %)', num(rr.appHa, 2), num(rr.appPct, 1)],
        ['Área de uso restrito (art. 11)', '25° a 45° (46,6 % a 100 %)', num(rr.restritoHa, 2), num(rr.restritoPct, 1)],
      ], { 2: { halign: 'right' }, 3: { halign: 'right' } });
      nota('Indicativo apenas. O enquadramento legal exige levantamento altimétrico de campo; um modelo de 30 metros suaviza encostas curtas e pode subestimar tanto a APP quanto a área de uso restrito.');
    }

    // ---------------- 6. chuva
    novaPagina();
    h1('6. REGIME DE CHUVAS');
    const ch = d.chuva;
    if (ch) {
      par(`A normal do local, calculada sobre o período ${ch.periodoNormal}, é de ${num(ch.totalNormal, 0)} mm por ano. Nos últimos doze meses choveu ${num(ch.totalRecente, 0)} mm, ${num(Math.abs(ch.desvioPct), 1)} % ${ch.desvioPct >= 0 ? 'acima' : 'abaixo'} da normal. O mês mais chuvoso é ${MESES[ch.mesChuvoso]} (${num(ch.normal[ch.mesChuvoso], 0)} mm) e o mais seco é ${MESES[ch.mesSeco]} (${num(ch.normal[ch.mesSeco], 0)} mm).`);
      if (d.figChuva) figura(d.figChuva);
      nota(`Fonte: ${ch.fonte}. A grade tem cerca de 50 km de lado; portanto, o dado descreve a região, e não o pluviômetro da sede. Serve para caracterizar o regime e comparar anos, não para apurar sinistro.`);
    } else {
      par('Dados de precipitação não obtidos nesta execução.');
    }

    // ---------------- 7. logística
    novaPagina();
    h1('7. LOGÍSTICA');
    par('Distâncias em linha reta a partir do centro do imóvel. Não é rota rodoviária: o percurso real por estrada costuma ser maior, principalmente em relevo recortado ou sem acesso pavimentado direto.');
    espaco(1);
    if (d.logistica) {
      tabela(['Referência', 'Distância em linha reta'], [[`Capital do estado (${d.logistica.capital})`, `${num(d.logistica.km, 0)} km`]]);
      nota('Distância até armazéns, frigoríficos SIF e aeródromos mais próximos não está disponível nesta versão do relatório: exige uma tabela geocodificada própria (CONAB, MAPA/SIF, ANAC), ainda não incorporada ao Gestor.');
    } else {
      par('Não foi possível calcular a distância até a capital: UF não identificada na tabela de capitais.');
    }

    // ---------------- 8. valor
    novaPagina();
    h1('8. REFERÊNCIAS DE VALOR POR HECTARE');
    par('Este capítulo não é uma avaliação de imóvel. Um laudo de avaliação de imóvel rural exige vistoria, pesquisa de mercado com amostra de elementos comparáveis, tratamento estatístico e Anotação de Responsabilidade Técnica, conforme a NBR 14653-3. O que segue são valores públicos de referência, úteis para ordem de grandeza e para conferência de declaração fiscal.', { negrito: false });
    const vr = d.valores;
    if (vr.vtn) {
      h2(`8.1 Valor da Terra Nua – referência fiscal (Receita Federal, exercício ${vr.vtn.exercicio})`);
      tabela(['Aptidão agrícola', 'VTN por ha', `Total para ${num(ha, 2)} ha`],
        vr.vtn.linhas.map((v) => v.valor == null ? [v.aptidao, 'sem informação', '–'] : [v.aptidao, 'R$ ' + num(v.valor, 2), 'R$ ' + num(v.valor * ha, 2)]),
        { 1: { halign: 'right' }, 2: { halign: 'right' } });
      nota(`Valores ${vr.vtn.fonte} à Receita Federal. O VTN é a régua que a Receita usa para conferir o valor declarado na DITR; costuma ficar bem abaixo do preço de negociação e não deve ser usado como valor de venda. "Sem informação" reproduz a tabela oficial, que não traz valor para aquela aptidão no município.`);
      espaco(2);
    }
    if (vr.mercado && vr.mercado.linhas.length) {
      const m = vr.mercado;
      h2(`8.2 Mercado regional de terras – MRT-${String(m.mrt).padStart(2, '0')} ${m.mercado} (INCRA, RAMT ${m.ano})`);
      const marcados = [];
      tabela(['Nível', 'Tipologia de uso', 'VTN mínimo', 'VTN mediano', 'VTN máximo'],
        m.linhas.map((v) => {
          if (v.inconsistencia) marcados.push(`${v.uso}: ${v.inconsistencia}`);
          return [v.nivel, v.uso + (v.inconsistencia ? ' *' : ''), num(v.vtnMin, 0), num(v.vtnMediano, 0), num(v.vtnMax, 0)];
        }),
        { 0: { cellWidth: 18 }, 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' } });
      nota('Valores em R$ por hectare, preço à vista, sem benfeitorias (Valor da Terra Nua). Mínimo e máximo são o campo de arbítrio do INCRA: 85 % e 115 % do mediano.');
      if (marcados.length) nota('* Linha publicada pelo INCRA com incoerência interna, reproduzida sem correção: ' + marcados.join('; ') + '.');
      const primeiro = m.linhas.filter((v) => /^primeiro/i.test(v.nivel) && !v.inconsistencia && v.vtnMin && v.vtnMax);
      if (primeiro.length) {
        const lo = Math.min(...primeiro.map((v) => v.vtnMin));
        const hi = Math.max(...primeiro.map((v) => v.vtnMax));
        par(`Faixa indicativa para o imóvel (primeiro nível categórico, terra nua): R$ ${num(lo * ha, 2)} a R$ ${num(hi * ha, 2)}. O preço de mercado é regional: descreve um agrupamento de municípios, e não este imóvel. Aptidão agrícola, acesso, hidrografia, benfeitorias e situação registral movem o valor para dentro ou para fora dessa faixa.`);
      }
    }
    if (!vr.vtn && !(vr.mercado && vr.mercado.linhas.length)) par('Nenhuma tabela de referência foi localizada para este município.');
    for (const aviso of vr.avisos) nota(aviso);

    // ---------------- 9. ressalvas
    novaPagina();
    h1('9. RESSALVAS TÉCNICAS E FONTES');
    for (const t of [
      'Este relatório é um estudo de caracterização por sensoriamento remoto e cruzamento de bases públicas. Não substitui levantamento topográfico, memorial descritivo, laudo de avaliação, parecer jurídico nem perícia.',
      d.perimetroFonte === 'enviado'
        ? 'Os limites analisados são os do arquivo digital fornecido pelo contratante. Não houve conferência de campo dos marcos e das divisas.'
        : `Os limites analisados são os do ${d.perimetroFonte === 'sigef' ? 'SIGEF' : 'CAR'} sobreposto ao arquivo enviado, não os do arquivo em si — ver 1. Não houve conferência de campo dos marcos e das divisas em nenhum dos dois.`,
      'As consultas cadastrais e fundiárias refletem a base disponível na data de emissão. Os cadastros são alterados diariamente; confirme na consulta oficial antes de qualquer ato jurídico.',
      'O diagnóstico executivo e o pareamento SIGEF × CAR comparam apenas geometria. Nenhum dado de titularidade (nome de proprietário) foi cruzado entre bases — quando um nome aparece em um cadastro, o relatório não afirma que essa pessoa é a proprietária atual do imóvel.',
      'A Reserva Legal mínima informada (cap. 1.4) é o percentual legal, não uma verificação de conformidade: não foi medida a vegetação nativa existente nem a RL averbada em matrícula.',
      'O modelo digital de elevação é de superfície (MDS) e tem resolução de 30 metros. As áreas de APP e de uso restrito indicadas por declividade são estimativas preliminares.',
      'Os índices de vegetação medem vigor, não produtividade. A comparação entre datas só é válida dentro do mesmo estádio fenológico.',
      'As distâncias de logística são em linha reta, a partir do centro do imóvel, e limitadas à capital do estado nesta versão.',
      'As referências de valor são dados públicos de ordem de grandeza. A avaliação de imóvel rural segue a NBR 14653-3 e exige vistoria, pesquisa de mercado e ART.',
    ].concat(d.perimetroExtensao === 'dxf' ? [
      `O perímetro veio de um DXF. Se as coordenadas do arquivo já estavam em graus (lon/lat), foram usadas como enviadas; caso contrário, foram tratadas como SIRGAS 2000 / UTM fuso ${d.dxfZona}${d.dxfHemisferio} — confira se essa é a zona correta do arquivo original antes de usar os resultados.`,
    ] : []).concat(d.perimetroExtensao === 'zip' ? [
      'O perímetro veio de um shapefile (.zip). A reprojeção para graus depende do .prj enviado junto — sem ele, as coordenadas podem estar erradas sem nenhum aviso do sistema.',
    ] : [])) par('– ' + t);
    espaco(2);
    h2('Fontes utilizadas');
    tabela(['Dado', 'Fonte', 'Referência temporal'], d.fontes, { 0: { cellWidth: 34 }, 2: { cellWidth: 44 } });
    garantir(28);
    y += 14;
    doc.setDrawColor(90, 90, 90);
    doc.setLineWidth(0.3);
    doc.line(PW / 2 - 45, y, PW / 2 + 45, y);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    cor(COR.texto);
    if (d.responsavel) doc.text(d.responsavel, PW / 2, y + 5, { align: 'center' });
    doc.text(d.empresa || '', PW / 2, y + (d.responsavel ? 10 : 5), { align: 'center' });

    // rodapé em todas as páginas
    const total = doc.getNumberOfPages();
    for (let p = 1; p <= total; p++) {
      doc.setPage(p);
      doc.setDrawColor(COR.linha[0], COR.linha[1], COR.linha[2]);
      doc.setLineWidth(0.3);
      doc.line(ML, PH - 15, PW - MR, PH - 15);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(7);
      doc.setTextColor(119, 119, 119);
      doc.text(`${d.nome} – ${d.municipio}/${d.uf} – ${d.empresa || ''}`, ML, PH - 11);
      doc.text(`pág. ${p}`, PW - MR, PH - 11, { align: 'right' });
    }
    return doc;
  }

  // ------------------------------------------------------------ fluxo completo

  /**
   * Gera o relatório. opcoes: {arquivo, nome, municipio, uf, responsavel,
   * empresa, dias, nuvemMax, comSerie, log(texto), cancelado()}.
   * A Reserva Legal mínima é calculada pela Lei 12.651/2012 (ver calcularRL),
   * não é mais um percentual digitado.
   * Devolve {doc, nomeArquivo, dados}.
   */
  RF.gerar = async function (opcoes) {
    const log = opcoes.log || (() => {});
    const cancelar = opcoes.cancelado || (() => false);
    const passo = () => {
      if (cancelar()) throw new Cancelado();
    };
    const uf = String(opcoes.uf || 'MS').toUpperCase();
    const extensao = (opcoes.arquivo.name || '').toLowerCase().split('.').pop();
    await garantirBibliotecas(extensao);
    passo();
    log('Lendo o perímetro...');
    const poligonosEnviados = await RF.lerPerimetro(opcoes.arquivo, { zona: Number(opcoes.dxfZona) || 21, sul: opcoes.dxfHemisferio !== 'N' });
    let ctx = await RF.construirCtx(poligonosEnviados, log);
    const areaEnviadaHa = ctx.ha;
    passo();

    // ---- cadastro, e prioridade do perímetro (SIGEF > CAR > enviado)
    //
    // O arquivo enviado pode estar incompleto (não pega toda a área real). Se o
    // SIGEF ou o CAR sobreposto for MAIOR que o enviado, o oficial é que vira a
    // base de toda a análise (imagem, relevo, RL etc.) — nunca o contrário: um
    // perímetro enviado maior que o oficial é respeitado (pode ser retificação
    // em andamento, ainda não refletida no cadastro). Exige a sobreposição
    // cobrir mais da metade do perímetro enviado, para não trocar pela terra do
    // vizinho por causa de uma lasca de divisa com área grande.
    log('Consultas cadastrais...');
    let [carBusca, sigefBusca] = await Promise.all([consultarCar(ctx, uf, log), consultarSigef(ctx, uf, log)]);
    passo();
    const bomMatch = (r) => r && r.pct_do_perimetro > 50;
    const sigefPrincipal = sigefBusca.resultados && sigefBusca.resultados[0];
    const carPrincipal = carBusca.resultados && carBusca.resultados[0];
    let fontePerimetro = 'enviado';
    if (bomMatch(sigefPrincipal) && sigefPrincipal.area_feicao_ha > areaEnviadaHa + 0.001) fontePerimetro = 'sigef';
    else if (bomMatch(carPrincipal) && carPrincipal.area_feicao_ha > areaEnviadaHa + 0.001) fontePerimetro = 'car';

    let carFinal = carBusca, sigefFinal = sigefBusca;
    if (fontePerimetro !== 'enviado') {
      const escolhida = fontePerimetro === 'sigef' ? sigefPrincipal : carPrincipal;
      const nomeFonte = fontePerimetro === 'sigef' ? 'SIGEF' : 'CAR';
      log(`  Perímetro enviado (${num(areaEnviadaHa, 4)} ha) menor que o ${nomeFonte} sobreposto (${num(escolhida.area_feicao_ha, 4)} ha) — usando o perímetro do ${nomeFonte} para a análise.`);
      ctx = await RF.construirCtx(geojsonParaPoligonos(escolhida.geometria), log);
      passo();
      log('Reconsultando CAR e SIGEF sobre o perímetro oficial...');
      [carFinal, sigefFinal] = await Promise.all([consultarCar(ctx, uf, log), consultarSigef(ctx, uf, log)]);
      passo();
    }
    const [lonC, latC] = ctx.centro;
    const nome = (opcoes.nome || '').trim() || (opcoes.arquivo.name || 'Fazenda').replace(/\.(kml|kmz|dxf|zip)$/i, '').replace(/_/g, ' ');
    const d = {
      nome, uf, ha: ctx.ha, perimetro: ctx.perimetro, sis: ctx.sis,
      data: dataBr(isoHoje(0)), responsavel: (opcoes.responsavel || '').trim(), empresa: (opcoes.empresa || 'AJ TopoGeo').trim(),
      car: carFinal, sigef: sigefFinal, perimetroFonte: fontePerimetro, perimetroEnviadoHa: areaEnviadaHa,
      perimetroExtensao: extensao, dxfZona: Number(opcoes.dxfZona) || 21, dxfHemisferio: opcoes.dxfHemisferio !== 'N' ? 'S' : 'N',
    };

    // ---- município e módulo fiscal
    const peloCar = municipioPeloCar(d.car);
    let municipio = (opcoes.municipio || '').trim();
    if (municipio) d.municipioFonte = `${municipio} (informado)`;
    else if (peloCar && peloCar.municipio) {
      municipio = peloCar.municipio;
      d.municipioFonte = `${municipio} (identificado pelo CAR)`;
      log('  município identificado pelo CAR: ' + municipio);
    } else d.municipioFonte = 'não identificado';
    d.municipio = municipio || 'município não identificado';
    const mesmo = peloCar && normalizar(peloCar.municipio) === normalizar(municipio);
    let mf = null, mfFonte = null;
    if (mesmo && peloCar.moduloFiscal) {
      mf = peloCar.moduloFiscal;
      mfFonte = `declarado no CAR (${peloCar.amostra} imóveis do município conferidos)`;
    } else if (municipio) {
      mf = await moduloFiscalTabela(municipio, uf, mesmo ? peloCar.codIbge : null);
      if (mf) mfFonte = 'tabela de índices básicos do INCRA (2013)';
    }
    const [nMod, classe] = classificarPorModulos(ctx.ha, mf);
    d.modulo = mf ? { mf, fonte: mfFonte, n: nMod, classe } : null;
    d.parIou = parearSigefCar(ctx, d.car.features || [], d.sigef.features || []);
    d.rl = calcularRL(uf, ctx.ha, d.modulo);
    d.logistica = logisticaCapital(lonC, latC, uf);
    passo();

    // ---- diagnóstico fundiário e ambiental (TI, UC, assentamento, quilombola, embargos)
    log('Diagnóstico fundiário e ambiental...');
    const [ti, uc, assent, quilombo, embargos] = await Promise.all([
      consultarComEntorno(urlRestricao(ctx, 'funai_ti'), 'Terras Indígenas (FUNAI)', ctx, log),
      consultarComEntorno(urlRestricao(ctx, 'icmbio_uc'), 'Unidades de Conservação federais (ICMBio)', ctx, log),
      consultarComEntorno(urlFundiario(ctx, uf, 'assentamentos'), 'Assentamentos (INCRA)', ctx, log),
      consultarComEntorno(urlFundiario(ctx, uf, 'quilombolas'), 'Territórios quilombolas (INCRA/Fundação Palmares)', ctx, log),
      consultarEmbargos(ctx, log),
    ]);
    d.restricoes = { ti, uc, assentamento: assent, quilombola: quilombo };
    d.embargos = embargos;
    passo();

    // ---- imagem e NDVI
    log('Imagem de satélite...');
    const dias = Number(opcoes.dias) || 365;
    const itens = await buscarCenas(ctx, isoHoje(dias), isoHoje(0), Number(opcoes.nuvemMax) || 70, log, cancelar);
    const [melhor, pct] = await escolherCena(itens, ctx, log, cancelar);
    log(`  cena de ${dataBr(melhor.data)} (${num(pct, 1)} % de nuvem sobre o imóvel); baixando as bandas...`);
    const cena = await lerCena(melhor, ctx);
    passo();
    const dataCena = dataBr(melhor.data);
    d.stats = estatisticas(cena.ndvi, ctx.dentro);
    d.figRgb = figuraMapa({
      grade: ctx.grade, aneis: ctx.poligonosUtm, titulo: `Composição colorida Sentinel-2 – ${dataCena}`, suavizar: true,
      pixel: (i) => (isFinite(cena.rgb[0][i]) ? [cena.rgb[0][i], cena.rgb[1][i], cena.rgb[2][i]] : [235, 235, 235]),
    });
    d.figNdvi = figuraMapa({
      grade: ctx.grade, aneis: ctx.poligonosUtm, titulo: `NDVI – ${dataCena}`,
      pixel: (i) => (isFinite(cena.ndvi[i]) ? RDYLGN(cena.ndvi[i] / 0.9) : [255, 255, 255]),
      barra: { rampa: RDYLGN, min: 0, max: 0.9, rotulo: 'NDVI' },
    });
    d.textoImagem = `Imagem do satélite Sentinel-2 (Copernicus/ESA) de ${dataCena}, com resolução de 10 metros, processada em nível L2A (reflectância de superfície). Entre as cenas disponíveis nos últimos ${dias} dias, esta é a mais recente praticamente sem nuvens sobre o polígono do imóvel (${num(pct, 1)} %) – critério mais restritivo que o percentual de nuvem da cena inteira, que cobre 110 × 110 km.`;

    // ---- série temporal
    if (opcoes.comSerie) {
      log('Série temporal de NDVI...');
      try {
        const linhas = await serieNdvi(itens, ctx, log, cancelar, 80);
        if (linhas.length >= 4) {
          d.figSerie = figuraSerie(linhas, nome, ctx.ha);
          const pico = linhas.reduce((a, b) => (b.medio > a.medio ? b : a));
          const vale = linhas.reduce((a, b) => (b.medio < a.medio ? b : a));
          d.textoSerie = `${linhas.length} datas com pelo menos 80 % do imóvel livre de nuvem. Pico de ${num(pico.medio, 3)} em ${dataBr(pico.data)}; vale de ${num(vale.medio, 3)} em ${dataBr(vale.data)}. Compare datas do mesmo estádio fenológico: NDVI é vigor, não produtividade.`;
        } else {
          log(`  só ${linhas.length} data(s) válida(s); série fora do relatório.`);
        }
      } catch (e) {
        if (e instanceof Cancelado) throw e;
        log('  série não gerada: ' + e.message);
      }
    }
    passo();

    // ---- relevo
    log('Relevo...');
    const mde = await modeloElevacao(ctx, log);
    let temDem = false;
    for (let i = 0; i < mde.dem.length; i++) if (mde.dentro[i] && isFinite(mde.dem[i])) { temDem = true; break; }
    if (mde.achados && temDem) {
      const g30 = mde.grade;
      const demM = mde.dem.map((v, i) => (mde.dentro[i] ? v : NaN));
      const decl = declividadeHorn(mde.dem, g30.nx, g30.ny, 30).map((v, i) => (mde.dentro[i] ? v : NaN));
      let zmin = Infinity, zmax = -Infinity;
      for (const v of demM) if (isFinite(v)) { if (v < zmin) zmin = v; if (v > zmax) zmax = v; }
      const amplitude = zmax - zmin;
      d.figHipso = figuraMapa({
        grade: g30, aneis: ctx.poligonosUtm, titulo: 'Hipsometria – Copernicus DEM GLO-30', suavizar: true,
        pixel: (i) => (isFinite(demM[i]) ? TERRAIN((demM[i] - zmin) / (amplitude || 1)) : [255, 255, 255]),
        barra: { rampa: TERRAIN, min: zmin, max: zmax, rotulo: 'Altitude (m)' },
        curvas: (g, X, Y) => {
          if (!(window.d3 && d3.contours) || amplitude <= 0) return;
          const passoCurva = [1, 2, 5, 10, 20, 25, 50, 100, 200].find((p) => amplitude / p <= 25) || 500;
          const niveis = [];
          for (let z = Math.ceil(zmin / passoCurva) * passoCurva; z <= zmax; z += passoCurva) niveis.push(z);
          // Curvas traçadas sobre o modelo inteiro (e não sobre o recortado) e
          // recortadas no desenho pelo perímetro. Preencher o lado de fora da
          // máscara com um valor falso fazia o traçador desenhar um degrau em
          // toda a borda: uma linha serrilhada colada ao limite, cheia de rótulos.
          const valores = Array.from(mde.dem, (v) => (isFinite(v) ? v : zmin));
          const contornos = d3.contours().size([g30.nx, g30.ny]).thresholds(niveis)(valores);
          g.save();
          g.beginPath();
          for (const [ext, ints] of ctx.poligonosUtm) {
            for (const anel of [ext, ...ints]) {
              anel.forEach((p, k) => (k ? g.lineTo(X(p[0]), Y(p[1])) : g.moveTo(X(p[0]), Y(p[1]))));
              g.closePath();
            }
          }
          g.clip('evenodd');
          g.strokeStyle = 'rgba(0,0,0,0.38)';
          g.lineWidth = 1.3;
          g.fillStyle = '#222';
          g.font = '15px Arial';
          g.textAlign = 'center';
          const [e0, , , n1] = g30.extent;
          for (const ct of contornos) {
            for (const poli of ct.coordinates) {
              for (const anel of poli) {
                g.beginPath();
                anel.forEach((p, k) => {
                  const px = X(e0 + p[0] * g30.res);
                  const py = Y(n1 - p[1] * g30.res);
                  k ? g.lineTo(px, py) : g.moveTo(px, py);
                });
                g.stroke();
                if (anel.length > 40) {
                  const p = anel[Math.floor(anel.length / 2)];
                  g.fillText(String(ct.value), X(e0 + p[0] * g30.res), Y(n1 - p[1] * g30.res) - 3);
                }
              }
            }
          }
          g.restore();
        },
      });
      const coresDecl = CORES_DECL.map(hexRgb);
      d.figDecl = figuraMapa({
        grade: g30, aneis: ctx.poligonosUtm, titulo: 'Classes de declividade',
        pixel: (i) => {
          const v = decl[i];
          if (!isFinite(v)) return [255, 255, 255];
          const k = CLASSES_DECL.findIndex(([lo, hi]) => v >= lo && v < hi);
          return coresDecl[k < 0 ? 5 : k];
        },
        legenda: CLASSES_DECL.map(([lo, hi, nome2], k) => [CORES_DECL[k], hi < 1e8 ? `${nome2} (${lo}–${hi} %)` : `${nome2} (> ${lo} %)`]),
      });
      d.decl = tabelaDeclividade(decl, mde.dentro, g30.areaPixelHa);
      const dominante = d.decl.linhas.reduce((a, b) => (b.pct > a.pct ? b : a));
      d.textoRelevo = `Altimetria derivada do Copernicus DEM GLO-30, com resolução de 30 metros. A área varia de ${num(zmin, 1)} m a ${num(zmax, 1)} m de altitude, amplitude de ${num(amplitude, 1)} m. A declividade mediana é de ${num(d.decl.mediana, 1)} % e a classe dominante é ${dominante.classe.toLowerCase()}, com ${num(dominante.pct, 1)} % da área. O GLO-30 é um modelo digital de superfície: inclui o dossel vegetal e as edificações; portanto, superestima a cota em áreas florestadas e não substitui o levantamento altimétrico.`;
    } else {
      d.textoRelevo = 'Modelo digital de elevação não obtido nesta execução.';
    }
    passo();

    // ---- chuva
    try {
      d.chuva = await chuvaNasaPower(latC, lonC, log);
      d.figChuva = figuraChuva(d.chuva);
    } catch (e) {
      log('  chuva não obtida: ' + e.message);
      d.chuva = null;
    }

    // ---- valores
    log('Referências de valor...');
    d.valores = await valoresReferencia(municipio, uf, log);

    d.fontes = [
      ['Imagem e NDVI', 'Copernicus Sentinel-2 L2A (ESA), catálogo STAC AWS Earth Search', `cena de ${dataCena}`],
      ['Altimetria', 'Copernicus DEM GLO-30 (ESA / Airbus), via OpenTopography', 'coleção 2021'],
      ['Precipitação', d.chuva ? d.chuva.fonte : '–', d.chuva ? d.chuva.periodoNormal : '–'],
      ['CAR', 'SICAR – Sistema Nacional de Cadastro Ambiental Rural', d.car.origem || 'não consultado'],
      ['Georreferenciamento', 'SIGEF / Acervo Fundiário – INCRA', d.sigef.origem || 'não consultado'],
      ['Terra Indígena', 'FUNAI – Terras Indígenas (poligonais)', d.restricoes.ti.origem || 'não consultado'],
      ['Unidade de Conservação', 'ICMBio – Limites das UC federais (INDE)', d.restricoes.uc.origem || 'não consultado'],
      ['Assentamento e quilombola', 'INCRA – Acervo Fundiário', d.restricoes.assentamento.origem || d.restricoes.quilombola.origem || 'não consultado'],
      ['Embargos ambientais', 'IBAMA – SISCOM (PAMGIA)', d.embargos.origem || 'não consultado'],
      ['Valor fiscal', 'Receita Federal – Valores de Terra Nua (SIPT)', d.valores.vtn ? `exercício ${d.valores.vtn.exercicio}` : 'não disponível'],
      ['Mercado de terras', 'INCRA – Relatório de Análise de Mercados de Terras (RAMT)', d.valores.mercado ? `RAMT ${d.valores.mercado.ano}` : 'não disponível'],
      ['Módulo fiscal', (d.modulo && d.modulo.fonte) || 'não identificado', '–'],
      ['Capital do estado', 'IBGE (coordenadas de referência)', '–'],
    ];

    log('Montando o PDF...');
    const doc = montarPdf(d);
    const nomeArquivo = `${nome.replace(/[<>:"/\\|?*\s]+/g, '_')}_relatorio_${isoHoje(0)}.pdf`;
    log('CONCLUÍDO: ' + nomeArquivo);
    return { doc, nomeArquivo, dados: d };
  };

  // ------------------------------------------------------------ aba do Gestor

  let _relfazCancelar = false;
  let _relfazRodando = false;

  window.geoRelFazHtml = function () {
    const ufs = ['AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'];
    return '<div class="card mb1">'
      + '<div class="st mb1"><i class="ti ti-report-analytics" style="color:var(--brand)"></i>Relatório da Fazenda</div>'
      + '<div class="mu sm mb1">Relatório técnico em PDF a partir do perímetro em KML/KMZ, DXF ou shapefile (.zip): diagnóstico executivo, situação no CAR e no SIGEF (com pareamento por geometria — se o CAR ou o SIGEF sobreposto for maior que o arquivo enviado, o relatório usa o oficial, prioridade SIGEF), Reserva Legal mínima pela Lei 12.651, sobreposição com Terra Indígena, Unidade de Conservação, assentamento, quilombola e embargos do IBAMA, imagem de satélite, NDVI e série temporal, relevo e declividade, regime de chuvas, logística até a capital e referências de valor da terra (VTN 2026 e mercado regional do INCRA). Tudo é consultado na hora, pela internet.</div>'
      + '<div class="fg mb1"><label class="fl">Perímetro (KML, KMZ, DXF ou .zip de shapefile)</label><input class="fc" id="relfaz-arquivo" type="file" accept=".kml,.kmz,.dxf,.zip" onchange="relfazArquivoEscolhido(this)"></div>'
      + '<div class="g2 mb1" id="relfaz-dxf-crs" style="display:none">'
      + '<div class="fg"><label class="fl">Zona UTM do DXF <span class="mu">(só se as coordenadas não forem lon/lat)</span></label><select class="fc" id="relfaz-dxf-zona">' + Array.from({ length: 9 }, (_, i) => 17 + i).map((z) => `<option value="${z}"${z === 21 ? ' selected' : ''}>${z}</option>`).join('') + '</select></div>'
      + '<div class="fg"><label class="fl">Hemisfério</label><select class="fc" id="relfaz-dxf-hemis"><option value="S" selected>Sul</option><option value="N">Norte</option></select></div>'
      + '</div>'
      + '<div class="g2 mb1">'
      + '<div class="fg"><label class="fl">Nome do imóvel</label><input class="fc" id="relfaz-nome" placeholder="ex. Fazenda São Jorge"></div>'
      + '<div class="fg"><label class="fl">Município <span class="mu">(em branco: identifica pelo CAR)</span></label><input class="fc" id="relfaz-municipio"></div>'
      + '</div>'
      + '<div class="g2 mb1">'
      + '<div class="fg"><label class="fl">UF</label><select class="fc" id="relfaz-uf">' + ufs.map((u) => `<option${u === 'MS' ? ' selected' : ''}>${u}</option>`).join('') + '</select></div>'
      + '<div class="fg"><label class="fl">Responsável técnico</label><input class="fc" id="relfaz-responsavel"></div>'
      + '</div>'
      + '<div class="fg mb1"><label class="fl">Empresa</label><input class="fc" id="relfaz-empresa" value="AJ TopoGeo"></div>'
      + '<div class="g2 mb1">'
      + '<div class="fg"><label class="fl">Janela de busca da imagem (dias)</label><input class="fc" id="relfaz-dias" type="number" value="365" min="10" max="1095"></div>'
      + '<div class="fg"><label class="fl">Nuvem máxima na cena (%)</label><input class="fc" id="relfaz-nuvem" type="number" value="70" min="1" max="100"></div>'
      + '</div>'
      + '<label class="sm mb1" style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="relfaz-serie" checked> Incluir série temporal de NDVI do período (baixa uma imagem por data; alguns minutos a mais)</label>'
      + '<div class="fx g8 mb1">'
      + '<button class="btn bsm" id="relfaz-gerar" onclick="relfazGerar()"><i class="ti ti-file-type-pdf"></i> Gerar relatório</button>'
      + '<button class="btn bsm" id="relfaz-parar" onclick="relfazParar()" style="display:none"><i class="ti ti-player-stop"></i> Parar</button>'
      + '</div>'
      + '<div id="relfaz-resultado" class="sm mb1"></div>'
      + '<div id="relfaz-log" style="display:none;background:#0d1b2a;color:#dbe7f5;font-family:Consolas,monospace;font-size:11.5px;line-height:1.45;border-radius:8px;padding:10px 12px;max-height:320px;overflow:auto;white-space:pre-wrap"></div>'
      + '<div class="mu sm" style="margin-top:.6rem">Não é laudo de avaliação: o próprio relatório lista as ressalvas de cada dado. Preço de mercado de terras disponível hoje para Mato Grosso do Sul; VTN para todo o Brasil.</div>'
      + '</div>';
  };

  window.relfazInit = function () {
    try {
      const salvo = JSON.parse(localStorage.getItem('relfaz_prefs') || '{}');
      for (const k of ['responsavel', 'empresa', 'uf']) {
        const el = document.getElementById('relfaz-' + k);
        if (el && salvo[k]) el.value = salvo[k];
      }
    } catch (e) { /* preferências são conveniência */ }
  };

  window.relfazArquivoEscolhido = function (input) {
    const f = input.files && input.files[0];
    const nome = document.getElementById('relfaz-nome');
    if (f && nome && !nome.value.trim()) nome.value = f.name.replace(/\.(kml|kmz|dxf|zip)$/i, '').replace(/_/g, ' ');
    const bloco = document.getElementById('relfaz-dxf-crs');
    if (bloco) bloco.style.display = f && /\.dxf$/i.test(f.name) ? '' : 'none';
  };

  window.relfazParar = function () {
    _relfazCancelar = true;
    const r = document.getElementById('relfaz-resultado');
    if (r) r.innerHTML = '<span class="mu"><i class="ti ti-loader"></i> Parando depois da leitura em andamento…</span>';
  };

  window.relfazGerar = async function () {
    if (_relfazRodando) return;
    const val = (id) => (document.getElementById('relfaz-' + id) || {}).value || '';
    const arquivo = (document.getElementById('relfaz-arquivo').files || [])[0];
    const aviso = (t) => (typeof toast === 'function' ? toast(t, true) : alert(t));
    if (!arquivo) return aviso('Escolha o arquivo KML ou KMZ do perímetro.');
    const logEl = document.getElementById('relfaz-log');
    const res = document.getElementById('relfaz-resultado');
    const btn = document.getElementById('relfaz-gerar');
    const parar = document.getElementById('relfaz-parar');
    try {
      localStorage.setItem('relfaz_prefs', JSON.stringify({ responsavel: val('responsavel'), empresa: val('empresa'), uf: val('uf') }));
    } catch (e) { /* ok */ }
    _relfazRodando = true;
    _relfazCancelar = false;
    btn.disabled = true;
    parar.style.display = '';
    logEl.style.display = 'block';
    logEl.textContent = '';
    res.innerHTML = '<span class="mu"><i class="ti ti-loader"></i> Gerando o relatório — acompanhe abaixo. Com a série temporal leva alguns minutos; pode continuar usando outras abas.</span>';
    const t0 = Date.now();
    const log = (t) => {
      logEl.textContent += t + '\n';
      logEl.scrollTop = logEl.scrollHeight;
    };
    try {
      const r = await RF.gerar({
        arquivo, nome: val('nome'), municipio: val('municipio'), uf: val('uf'), responsavel: val('responsavel'),
        empresa: val('empresa'), dias: val('dias'), nuvemMax: val('nuvem'),
        dxfZona: val('dxf-zona'), dxfHemisferio: val('dxf-hemis'),
        comSerie: document.getElementById('relfaz-serie').checked, log, cancelado: () => _relfazCancelar,
      });
      r.doc.save(r.nomeArquivo);
      const min = ((Date.now() - t0) / 60000).toFixed(1).replace('.', ',');
      res.innerHTML = `<span style="color:#27500A"><i class="ti ti-check"></i> Relatório gerado em ${min} min — <strong>${r.nomeArquivo}</strong> baixado.</span>`;
      if (typeof toast === 'function') toast('Relatório da fazenda gerado!');
    } catch (e) {
      if (e instanceof Cancelado) {
        res.innerHTML = '<span class="mu"><i class="ti ti-player-stop"></i> Parado a pedido.</span>';
      } else {
        res.innerHTML = '<span style="color:#A32D2D"><i class="ti ti-alert-circle"></i> ' + String(e.message || e) + '</span>';
        log('FALHOU: ' + (e.stack || e));
      }
    } finally {
      _relfazRodando = false;
      btn.disabled = false;
      parar.style.display = 'none';
    }
  };
})();
