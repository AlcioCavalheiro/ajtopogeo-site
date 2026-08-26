// Servico local (roda so nesta maquina) que expoe cota de terreno e curvas de
// nivel a partir dos DSM.tif gerados pelo DJI Terra, usando o GDAL instalado
// junto com o QGIS. O Gestor (site) nao tem acesso a isso na nuvem -- por
// isso o front-end chama http://127.0.0.1:<porta> em vez de /api/...
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFile, execFileSync } = require('child_process');

const CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));

const GDAL_LOCATION_INFO = path.join(CONFIG.gdalBin, 'gdallocationinfo.exe');
const GDAL_CONTOUR = path.join(CONFIG.gdalBin, 'gdal_contour.exe');
const GDAL_TRANSLATE = path.join(CONFIG.gdalBin, 'gdal_translate.exe');
const GDAL_INFO = path.join(CONFIG.gdalBin, 'gdalinfo.exe');

// o dsm.tif do DJI Terra sai em ~6cm/pixel: gerar curva de nivel direto nessa
// resolucao produz GeoJSON de 200+MB (trava o navegador). Reamostra pra uma
// grade de 1m antes de traçar o contorno -- ja e mais fino que o necessario
// pra curva de nivel e reduz o resultado pra dezenas de MB.
const RESOLUCAO_GRADE_CONTORNO_M = 1;

function verificarAmbiente() {
  const hostname = os.hostname();
  const hostnameOk = CONFIG.hostnamesPermitidos.includes(hostname);
  const gdalOk = fs.existsSync(GDAL_LOCATION_INFO) && fs.existsSync(GDAL_CONTOUR) && fs.existsSync(GDAL_TRANSLATE);
  const pastaRaizOk = fs.existsSync(CONFIG.djiTerraRoot) && fs.statSync(CONFIG.djiTerraRoot).isDirectory();

  const problemas = [];
  if (!hostnameOk) problemas.push(`maquina "${hostname}" nao esta na lista de maquinas autorizadas (config.json > hostnamesPermitidos)`);
  if (!gdalOk) problemas.push(`GDAL nao encontrado em "${CONFIG.gdalBin}" (esperado gdallocationinfo.exe e gdal_contour.exe)`);
  if (!pastaRaizOk) problemas.push(`pasta de projetos do DJI Terra nao encontrada: "${CONFIG.djiTerraRoot}"`);

  return { ok: problemas.length === 0, hostname, hostnameOk, gdalOk, pastaRaizOk, problemas };
}

function listarPastasComDsm() {
  if (!fs.existsSync(CONFIG.djiTerraRoot)) return [];
  return fs.readdirSync(CONFIG.djiTerraRoot, { withFileTypes: true })
    .filter((ent) => ent.isDirectory())
    .map((ent) => {
      const dsmPath = path.join(CONFIG.djiTerraRoot, ent.name, 'map', 'dsm.tif');
      if (!fs.existsSync(dsmPath)) return null;
      const tamanhoMB = Math.round(fs.statSync(dsmPath).size / (1024 * 1024));
      return { nome: ent.name, dsmPath, tamanhoMB };
    })
    .filter(Boolean);
}

// cache em memoria (por caminho+mtime) pra nao rodar gdalinfo de novo a toda
// chamada de /pastas -- gdalinfo -json so le o cabecalho do tif, e rapido
// (~0.2s), mas nao precisa repetir se o arquivo nao mudou.
const _cacheExtensao = new Map();
function obterExtensao(dsmPath) {
  const mtime = fs.statSync(dsmPath).mtimeMs;
  const cacheKey = dsmPath;
  const cacheado = _cacheExtensao.get(cacheKey);
  if (cacheado && cacheado.mtime === mtime) return cacheado.dados;

  const saida = execFileSync(GDAL_INFO, ['-json', dsmPath], { timeout: 15000, maxBuffer: 16 * 1024 * 1024 }).toString('utf8');
  const info = JSON.parse(saida);
  const wkt = info.coordinateSystem && info.coordinateSystem.wkt || '';
  const matches = [...wkt.matchAll(/ID\["EPSG",(\d+)\]/g)];
  const epsg = matches.length ? Number(matches[matches.length - 1][1]) : null;
  const cantos = info.cornerCoordinates;
  const xs = [cantos.upperLeft[0], cantos.upperRight[0], cantos.lowerLeft[0], cantos.lowerRight[0]];
  const ys = [cantos.upperLeft[1], cantos.upperRight[1], cantos.lowerLeft[1], cantos.lowerRight[1]];
  const dados = { epsg, minE: Math.min(...xs), maxE: Math.max(...xs), minN: Math.min(...ys), maxN: Math.max(...ys) };
  _cacheExtensao.set(cacheKey, { mtime, dados });
  return dados;
}

function resolverDsm(pasta) {
  const encontrada = listarPastasComDsm().find((p) => p.nome === pasta);
  return encontrada || null;
}

function enviarJson(res, status, corpo) {
  const texto = JSON.stringify(corpo);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(texto) });
  res.end(texto);
}

function aplicarCors(req, res) {
  const origem = req.headers.origin;
  if (origem && CONFIG.origensPermitidas.includes(origem)) {
    res.setHeader('Access-Control-Allow-Origin', origem);
    res.setHeader('Vary', 'Origin');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  }
}

function numeroValido(valor) {
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

function tratarStatus(req, res) {
  const ambiente = verificarAmbiente();
  enviarJson(res, 200, ambiente);
}

function tratarPastas(req, res) {
  const ambiente = verificarAmbiente();
  if (!ambiente.ok) return enviarJson(res, 503, ambiente);
  const pastas = listarPastasComDsm().map((p) => {
    try {
      return { nome: p.nome, tamanhoMB: p.tamanhoMB, extensao: obterExtensao(p.dsmPath) };
    } catch (e) {
      return { nome: p.nome, tamanhoMB: p.tamanhoMB, extensao: null };
    }
  });
  enviarJson(res, 200, pastas);
}

function tratarCota(req, res, query) {
  const ambiente = verificarAmbiente();
  if (!ambiente.ok) return enviarJson(res, 503, ambiente);

  const projeto = resolverDsm(query.get('pasta') || '');
  if (!projeto) return enviarJson(res, 404, { erro: 'pasta de projeto nao encontrada' });

  const e = numeroValido(query.get('e'));
  const n = numeroValido(query.get('n'));
  if (e === null || n === null) return enviarJson(res, 400, { erro: 'coordenadas e/n invalidas' });

  execFile(GDAL_LOCATION_INFO, ['-valonly', '-geoloc', projeto.dsmPath, String(e), String(n)], { timeout: 30000 }, (err, stdout, stderr) => {
    if (err) {
      // coordenada fora da extensao do raster: com -valonly o gdallocationinfo
      // sai com erro e sem nenhuma saida (nao com -9999, que so vale pra pixel
      // sem dado dentro da extensao) -- diferencia de erro real (stdout/stderr
      // com texto) checando se as duas saidas vieram vazias.
      if (!stdout.trim() && !stderr.trim()) {
        return enviarJson(res, 200, { cota: null, foraDaArea: true });
      }
      return enviarJson(res, 500, { erro: 'falha ao consultar o GDAL', detalhe: stderr || stdout || err.message });
    }
    const bruto = stdout.trim();
    if (bruto === '' || bruto === '-9999') return enviarJson(res, 200, { cota: null, foraDaArea: true });
    const cota = numeroValido(bruto);
    if (cota === null) return enviarJson(res, 500, { erro: 'retorno inesperado do GDAL', detalhe: bruto });
    enviarJson(res, 200, { cota: Math.round(cota * 100) / 100, unidade: 'm', foraDaArea: false });
  });
}

function tratarCurvasNivel(req, res, query) {
  const ambiente = verificarAmbiente();
  if (!ambiente.ok) return enviarJson(res, 503, ambiente);

  const projeto = resolverDsm(query.get('pasta') || '');
  if (!projeto) return enviarJson(res, 404, { erro: 'pasta de projeto nao encontrada' });

  const intervalo = numeroValido(query.get('intervalo')) || 1;
  if (intervalo < 0.1 || intervalo > 50) return enviarJson(res, 400, { erro: 'intervalo deve estar entre 0.1 e 50 metros' });

  const sufixo = `${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const vrtPath = path.join(os.tmpdir(), `dsm_reamostrado_${sufixo}.vrt`);
  const geojsonPath = path.join(os.tmpdir(), `curvas_${sufixo}.geojson`);

  const limpar = () => { fs.unlink(vrtPath, () => {}); fs.unlink(geojsonPath, () => {}); };

  execFile(GDAL_TRANSLATE, ['-of', 'VRT', '-tr', String(RESOLUCAO_GRADE_CONTORNO_M), String(RESOLUCAO_GRADE_CONTORNO_M), '-r', 'average', projeto.dsmPath, vrtPath], { timeout: 30000 }, (errT, _stdoutT, stderrT) => {
    if (errT) { limpar(); return enviarJson(res, 500, { erro: 'falha ao reamostrar o DSM', detalhe: stderrT || errT.message }); }

    execFile(GDAL_CONTOUR, ['-a', 'cota', '-i', String(intervalo), '-f', 'GeoJSON', vrtPath, geojsonPath], { timeout: 180000 }, (err, stdout, stderr) => {
      if (err) { limpar(); return enviarJson(res, 500, { erro: 'falha ao gerar curvas de nivel', detalhe: stderr || err.message }); }
      fs.readFile(geojsonPath, 'utf8', (errLeitura, conteudo) => {
        limpar();
        if (errLeitura) return enviarJson(res, 500, { erro: 'falha ao ler o resultado do GDAL', detalhe: errLeitura.message });
        res.writeHead(200, { 'Content-Type': 'application/geo+json; charset=utf-8' });
        res.end(conteudo);
      });
    });
  });
}

const servidor = http.createServer((req, res) => {
  aplicarCors(req, res);
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }

  const url = new URL(req.url, `http://127.0.0.1:${CONFIG.porta}`);
  if (req.method !== 'GET') return enviarJson(res, 405, { erro: 'metodo nao suportado' });

  if (url.pathname === '/status') return tratarStatus(req, res);
  if (url.pathname === '/pastas') return tratarPastas(req, res);
  if (url.pathname === '/cota') return tratarCota(req, res, url.searchParams);
  if (url.pathname === '/curvas-nivel') return tratarCurvasNivel(req, res, url.searchParams);
  enviarJson(res, 404, { erro: 'rota nao encontrada' });
});

const ambienteInicial = verificarAmbiente();
console.log('--- Servico local DSM (cota / curvas de nivel) ---');
console.log(`maquina: ${ambienteInicial.hostname}`);
console.log(`hostname autorizado: ${ambienteInicial.hostnameOk ? 'OK' : 'FALHOU'}`);
console.log(`GDAL instalado: ${ambienteInicial.gdalOk ? 'OK' : 'FALHOU'} (${CONFIG.gdalBin})`);
console.log(`pasta de projetos DJI Terra: ${ambienteInicial.pastaRaizOk ? 'OK' : 'FALHOU'} (${CONFIG.djiTerraRoot})`);

if (!ambienteInicial.ok) {
  console.error('\nBLOQUEADO: este servico nao pode rodar nesta maquina.');
  ambienteInicial.problemas.forEach((p) => console.error(' - ' + p));
  process.exitCode = 1;
} else {
  servidor.listen(CONFIG.porta, '127.0.0.1', () => {
    console.log(`\nOK, escutando em http://127.0.0.1:${CONFIG.porta}`);
  });
}
