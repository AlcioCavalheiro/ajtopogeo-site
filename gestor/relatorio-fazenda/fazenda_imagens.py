"""Sentinel-2 e Copernicus DEM recortados no perimetro do imovel.

Porte do `imagens_area.py` que chegou pronto, trocando rasterio e pystac-client
pelo GDAL do pacote (`fazenda_geo`) e por uma chamada HTTP ao catalogo STAC.

Conferido contra o dado real:

- O NDVI e calculado direto do numero digital, e isso esta certo. O catalogo
  do Earth Search declara `offset: -0.1` nas bandas, o que sugere a correcao de
  +1000 da baseline 04.00 do Sentinel-2 -- mas os pixels mostram que ela ja foi
  aplicada: o minimo da cena 21KYT de 04/09/2026 e 111 no B08 e 174 no B04, e
  com o +1000 gravado nenhum pixel valido ficaria abaixo de ~1000. Aplicar o
  offset do metadado derrubaria o NDVI (0,157 viraria 0,279 na base do Sao Jorge).
- O EPSG do hemisferio norte estava errado no original: para o fuso 18N dava
  31964, que nao existe -- o programa quebraria em Roraima, no Amapa e no norte
  do Para e do Amazonas. O certo e 31954 + fuso.
"""

from __future__ import annotations

import csv
import math
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
from matplotlib.path import Path as Caminho
from PIL import Image
from pyproj import Transformer

import fazenda_fontes as fontes
import fazenda_geo as geo

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLECAO = "sentinel-2-l2a"
DEM_BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"

# Classes SCL descartadas: sombra de nuvem, nuvem media e alta, cirrus, neve
SCL_RUIM = (3, 8, 9, 10, 11)

# Leituras simultaneas de COG. O gargalo e a rede, nao a CPU; mais que isto
# o S3 comeca a devolver 503 e o GDAL passa a esperar para tentar de novo.
PARALELO = 4


class Cancelado(Exception):
    pass


def _seguro(fn, *args):
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - quem chama decide o que fazer com a falta
        return None


# ------------------------------------------------------------ KML / KMZ


def _sem_ns(tag):
    return tag.split("}")[-1].lower()


def _coordenadas(txt):
    pares = []
    for tok in txt.replace("\n", " ").replace("\t", " ").split():
        p = tok.split(",")
        if len(p) >= 2:
            try:
                pares.append((float(p[0]), float(p[1])))
            except ValueError:
                pass
    return pares


def _fechar(anel):
    return anel if anel[0] == anel[-1] else anel + [anel[0]]


def ler_kml(caminho):
    """Poligonos do KML/KMZ em lon/lat: lista de (anel externo, [aneis internos]).

    O original lia so o anel externo. Um perimetro com area excluida -- uma
    servidao, uma parcela vendida -- entraria com a area cheia; aqui o buraco e
    descontado da area e da mascara.
    """
    caminho = str(caminho)
    if caminho.lower().endswith(".kmz"):
        with zipfile.ZipFile(caminho) as z:
            nomes = [n for n in z.namelist() if n.lower().endswith(".kml")]
            if not nomes:
                raise ValueError("O KMZ nao contem nenhum arquivo .kml.")
            dados = z.read(nomes[0])
    else:
        dados = Path(caminho).read_bytes()

    raiz = ET.fromstring(dados)
    poligonos = []
    for elem in raiz.iter():
        if _sem_ns(elem.tag) != "polygon":
            continue
        externo, internos = None, []
        for sub in elem:
            tipo = _sem_ns(sub.tag)
            if tipo not in ("outerboundaryis", "innerboundaryis"):
                continue
            for c in sub.iter():
                if _sem_ns(c.tag) == "coordinates" and c.text:
                    pts = _coordenadas(c.text)
                    if len(pts) >= 3:
                        if tipo == "outerboundaryis":
                            externo = _fechar(pts)
                        else:
                            internos.append(_fechar(pts))
        if externo:
            poligonos.append((externo, internos))

    if not poligonos:
        for elem in raiz.iter():
            if _sem_ns(elem.tag) in ("linearring", "linestring"):
                for c in elem.iter():
                    if _sem_ns(c.tag) == "coordinates" and c.text:
                        pts = _coordenadas(c.text)
                        if len(pts) >= 3:
                            poligonos.append((_fechar(pts), []))
    if not poligonos:
        raise ValueError("Nenhum poligono encontrado no KML/KMZ.")
    return poligonos


# ------------------------------------------------------------ geometria


def epsg_sirgas_utm(lon, lat):
    """SIRGAS 2000 / UTM: 17S..25S = 31977..31985, 17N..22N = 31971..31976."""
    fuso = int((lon + 180) // 6) + 1
    epsg = (31960 if lat < 0 else 31954) + fuso
    if not 31971 <= epsg <= 31985:
        raise ValueError(f"O perimetro (lon {lon:.3f}, lat {lat:.3f}) esta fora dos fusos "
                         "UTM do Brasil.")
    return epsg


def _shoelace(xy):
    x, y = xy[:, 0], xy[:, 1]
    return abs(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1])) / 2.0


def _comprimento(xy):
    return float(np.hypot(*np.diff(xy, axis=0).T).sum())


def mascara(grade: geo.Grade, poligonos_utm):
    """Pixels cujo centro cai dentro do perimetro (e fora dos buracos)."""
    m = np.zeros(grade.forma, dtype=bool)
    xs, ys = grade.centros()
    for externo, internos in poligonos_utm:
        ix = np.flatnonzero((xs >= externo[:, 0].min()) & (xs <= externo[:, 0].max()))
        iy = np.flatnonzero((ys >= externo[:, 1].min()) & (ys <= externo[:, 1].max()))
        if not ix.size or not iy.size:
            continue
        gx, gy = np.meshgrid(xs[ix], ys[iy])
        pontos = np.column_stack([gx.ravel(), gy.ravel()])
        dentro = Caminho(externo).contains_points(pontos)
        for buraco in internos:
            dentro &= ~Caminho(buraco).contains_points(pontos)
        m[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1] |= dentro.reshape(gy.shape)
    return m


def aneis_para_desenho(poligonos_utm):
    """(xs, ys) de cada anel, para o matplotlib."""
    saida = []
    for externo, internos in poligonos_utm:
        for anel in [externo, *internos]:
            saida.append((anel[:, 0], anel[:, 1]))
    return saida


def preparar(kml, log):
    """Le o perimetro e monta tudo o que as leituras precisam: UTM, grade, mascara."""
    # O GDAL e carregado aqui, numa thread so, antes de qualquer leitura em
    # paralelo. A trava em geo.biblioteca ja protege; carregar cedo tambem faz
    # uma instalacao quebrada falhar no primeiro passo, com mensagem clara.
    geo.biblioteca()
    log("Lendo o perimetro...")
    poligonos = ler_kml(kml)
    lons = [p[0] for ext, _ in poligonos for p in ext]
    lats = [p[1] for ext, _ in poligonos for p in ext]
    bbox = (min(lons), min(lats), max(lons), max(lats))
    centro = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    epsg = epsg_sirgas_utm(*centro)
    t = Transformer.from_crs(4326, epsg, always_xy=True)

    def utm(anel):
        x, y = t.transform([p[0] for p in anel], [p[1] for p in anel])
        return np.column_stack([x, y])

    poligonos_utm = [(utm(e), [utm(i) for i in ints]) for e, ints in poligonos]
    ha = sum(_shoelace(e) - sum(_shoelace(i) for i in ints) for e, ints in poligonos_utm) / 10000.0
    perimetro = sum(_comprimento(e) + sum(_comprimento(i) for i in ints) for e, ints in poligonos_utm)
    todos = np.vstack([e for e, _ in poligonos_utm])
    grade = geo.Grade.envolvendo(*todos.min(axis=0), *todos.max(axis=0), 10, epsg)
    dentro = mascara(grade, poligonos_utm)

    def anel_wkt(xy):
        return "(" + ",".join(f"{x:.3f} {y:.3f}" for x, y in xy) + ")"

    wkt = "MULTIPOLYGON(" + ",".join(
        "(" + ",".join(anel_wkt(a) for a in [e, *ints]) + ")" for e, ints in poligonos_utm) + ")"

    log(f"  {len(poligonos)} poligono(s) | {ha:,.2f} ha | EPSG:{epsg} (SIRGAS 2000 / UTM)")
    log(f"  grade {grade.nx} x {grade.ny} px a 10 m | {int(dentro.sum()):,} pixels dentro")
    l, b, r, tp = bbox
    return dict(
        kml=str(kml), poligonos=poligonos, poligonos_utm=poligonos_utm, bbox=bbox, centro=centro,
        epsg=epsg, ha=ha, perimetro_m=perimetro, grade=grade, dentro=dentro, wkt_utm=wkt,
        busca={"type": "Polygon", "coordinates": [[[l, b], [r, b], [r, tp], [l, tp], [l, b]]]},
    )


# ------------------------------------------------------------ catalogo


def buscar_cenas(ctx, dt_ini, dt_fim, nuvem_max, log, cancelar=lambda: False):
    """Cenas Sentinel-2 L2A do periodo sobre o imovel, com nuvem da cena abaixo do limite."""
    log("Consultando o catalogo Sentinel-2...")
    corpo = {"collections": [COLECAO], "intersects": ctx["busca"],
             "datetime": f"{dt_ini}T00:00:00Z/{dt_fim}T23:59:59Z",
             "query": {"eo:cloud_cover": {"lt": float(nuvem_max)}}, "limit": 100}
    url, metodo, itens = STAC_URL + "/search", "POST", []
    while url and len(itens) < 2000:
        if cancelar():
            raise Cancelado()
        if metodo == "POST":
            r = requests.post(url, json=corpo, timeout=90, headers={"User-Agent": fontes.AGENTE})
        else:
            r = requests.get(url, timeout=90, headers={"User-Agent": fontes.AGENTE})
        r.raise_for_status()
        j = r.json()
        for f in j.get("features") or []:
            itens.append(dict(
                id=f["id"], data=f["properties"]["datetime"][:10],
                nuvem=float(f["properties"].get("eo:cloud_cover", 100.0)),
                assets={k: v["href"] for k, v in (f.get("assets") or {}).items() if "href" in v}))
        proximo = next((l for l in j.get("links") or [] if l.get("rel") == "next"), None)
        if not proximo:
            break
        url, metodo = proximo["href"], proximo.get("method", "GET").upper()
        if metodo == "POST":
            corpo = {**corpo, **proximo["body"]} if proximo.get("merge") else proximo.get("body", corpo)
    if not itens:
        raise RuntimeError(f"Nenhuma cena Sentinel-2 entre {dt_ini} e {dt_fim} com menos de "
                           f"{nuvem_max:.0f} % de nuvem. Amplie o periodo ou o limite de nuvem.")
    log(f"  {len(itens)} cena(s) no periodo.")
    return itens


def nuvem_na_area(item, ctx):
    """Percentual do perimetro coberto por nuvem, sombra ou sem dado (banda SCL)."""
    scl = geo.recortar(item["assets"]["scl"], ctx["grade"], "near")[0]
    v = scl[ctx["dentro"]]
    if v.size == 0:
        return 100.0
    return 100.0 * float((np.isnan(v) | np.isin(v, SCL_RUIM)).sum()) / v.size


def escolher_cena(itens, ctx, log, cancelar, recentes=12, menos_nuvem=8):
    """A imagem mais recente sem nuvem SOBRE O IMOVEL.

    A nuvem que o catalogo informa e a da cena inteira, 110 x 110 km: cena com
    40 % de nuvem pode estar limpa sobre a fazenda, e cena com 2 % pode ter a
    nuvem exatamente em cima dela. Entao as cenas sao medidas pela SCL dentro do
    perimetro, da mais recente para tras, e fica a primeira praticamente limpa
    (< 1 %). Num relatorio de caracterizacao, a imagem da semana passada
    descreve melhor o imovel que a de marco -- e o texto do PDF promete isso.

    Se nenhuma das recentes estiver limpa (auge das chuvas), mede as de menor
    nuvem de cena entre as restantes; sem nenhuma limpa, fica a de menos nuvem
    sobre o imovel.
    """
    log("Medindo a nuvem dentro do perimetro (banda SCL)...")
    validos = [i for i in itens if "scl" in i["assets"]]
    por_data = sorted(validos, key=lambda i: i["data"], reverse=True)
    fases = [por_data[:recentes]]
    fases.append(sorted(por_data[recentes:], key=lambda i: i["nuvem"])[:menos_nuvem])
    medidos = []
    for candidatos in fases:
        for k in range(0, len(candidatos), PARALELO):
            if cancelar():
                raise Cancelado()
            lote = candidatos[k:k + PARALELO]
            with ThreadPoolExecutor(len(lote)) as ex:
                pcts = list(ex.map(lambda it: _seguro(nuvem_na_area, it, ctx), lote))
            for it, pct in zip(lote, pcts):
                if pct is None:
                    log(f"  {it['data']}: nao consegui ler a SCL")
                    continue
                log(f"  {it['data']}   nuvem na cena {it['nuvem']:5.1f} %   no imovel {pct:5.1f} %")
                medidos.append((it, pct))
            limpos = [(it, p) for it, p in medidos if p < 1.0]
            if limpos:
                return max(limpos, key=lambda x: x[0]["data"])
    if not medidos:
        return (por_data[0] if por_data else itens[0]), float("nan")
    return min(medidos, key=lambda x: x[1])


# ------------------------------------------------------------ bandas e indices


def indice_ndvi(nir, red):
    with np.errstate(divide="ignore", invalid="ignore"):
        soma = nir + red
        return np.where(soma > 0, (nir - red) / soma, np.nan).astype(np.float32)


def ler_cena(item, grade, dentro):
    """RGB, NDVI mascarado por nuvem e SCL, lidos em paralelo."""
    a = item["assets"]
    tarefas = {"nir": (a["nir"], "bilinear"), "red": (a["red"], "bilinear"), "scl": (a["scl"], "near")}
    if "visual" in a:
        tarefas["visual"] = (a["visual"], "bilinear")
    else:
        tarefas["green"] = (a["green"], "bilinear")
        tarefas["blue"] = (a["blue"], "bilinear")
    with ThreadPoolExecutor(PARALELO) as ex:
        futuros = {k: ex.submit(geo.recortar, url, grade, metodo) for k, (url, metodo) in tarefas.items()}
        bandas = {k: f.result() for k, f in futuros.items()}

    if "visual" in bandas:
        rgb = np.nan_to_num(bandas["visual"], nan=0.0).clip(0, 255).astype(np.uint8)
    else:
        canais = []
        for k in ("red", "green", "blue"):
            c = bandas[k][0]
            vals = c[dentro & np.isfinite(c)]
            p2, p98 = np.percentile(vals, [2, 98]) if vals.size else (0.0, 3000.0)
            canais.append(np.clip((np.nan_to_num(c) - p2) / max(p98 - p2, 1) * 255, 0, 255))
        rgb = np.stack(canais).astype(np.uint8)

    scl = bandas["scl"][0]
    bom = np.isfinite(scl) & ~np.isin(scl, SCL_RUIM)
    ndvi = indice_ndvi(bandas["nir"][0], bandas["red"][0])
    ndvi = np.where(dentro & bom, ndvi, np.nan).astype(np.float32)
    return dict(rgb=rgb, ndvi=ndvi, scl=scl)


def stats_ndvi(ndvi, dentro):
    v = ndvi[dentro]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return None
    return dict(n=int(v.size), medio=float(v.mean()), mediana=float(np.median(v)),
                p10=float(np.percentile(v, 10)), p90=float(np.percentile(v, 90)),
                desvio=float(v.std()), min=float(v.min()), max=float(v.max()),
                pct_baixo=float(100.0 * (v < 0.20).sum() / v.size))


RAMPA = [(-1.0, (120, 90, 70)), (0.0, (185, 155, 115)), (0.15, (225, 215, 130)),
         (0.30, (195, 210, 105)), (0.45, (140, 195, 90)), (0.60, (70, 160, 65)),
         (0.75, (30, 110, 50)), (1.0, (8, 60, 30))]


def ndvi_png(ndvi, mascara_, caminho):
    pos = np.array([p[0] for p in RAMPA])
    v = np.clip(np.nan_to_num(ndvi, nan=-1.0), -1, 1)
    canais = [np.interp(v, pos, np.array([p[1][i] for p in RAMPA], dtype=float)).astype(np.uint8)
              for i in range(3)]
    alfa = np.where(mascara_ & np.isfinite(ndvi), 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack(canais + [alfa]), mode="RGBA").save(caminho)


# ------------------------------------------------------------ relevo


def mde_glo30(ctx, log):
    """Copernicus DEM GLO-30 recortado numa grade de 30 m, com a mascara dela.

    Devolve (grade, dem, dentro, tiles). O GLO-30 e modelo de SUPERFICIE: inclui
    dossel e edificacao.
    """
    log("Baixando o modelo de elevacao Copernicus GLO-30...")
    todos = np.vstack([e for e, _ in ctx["poligonos_utm"]])
    grade = geo.Grade.envolvendo(*todos.min(axis=0), *todos.max(axis=0), 30, ctx["epsg"], folga_px=4)
    l, b, r, t = ctx["bbox"]
    urls = []
    for la in range(math.floor(b - 0.01), math.floor(t + 0.01) + 1):
        for lo in range(math.floor(l - 0.01), math.floor(r + 0.01) + 1):
            ns = f"N{la:02d}" if la >= 0 else f"S{abs(la):02d}"
            ew = f"E{lo:03d}" if lo >= 0 else f"W{abs(lo):03d}"
            nome = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
            urls.append(f"{DEM_BASE}/{nome}/{nome}.tif")
    with ThreadPoolExecutor(min(PARALELO, len(urls))) as ex:
        pedacos = list(ex.map(lambda u: _seguro(geo.recortar, u, grade, "bilinear"), urls))
    dem = np.full(grade.forma, np.nan, dtype=np.float32)
    achados = 0
    for p in pedacos:
        if p is None:
            continue
        ok = np.isfinite(p[0]) & (p[0] != 0)
        dem[ok] = p[0][ok]
        achados += 1
    log(f"  {achados} de {len(urls)} folha(s) do modelo encontradas.")
    return grade, dem, mascara(grade, ctx["poligonos_utm"]), achados


# ------------------------------------------------------------ serie temporal


def ndvi_da_data(itens_da_data, grade, dentro, min_validos=0.0):
    """NDVI de uma data, juntando as cenas dela e descartando nuvem pela SCL.

    A SCL desce primeiro. Se a nuvem ja deixa o imovel abaixo da cobertura
    minima, as bandas do NDVI nem sao lidas: no periodo chuvoso e boa parte das
    datas, e cada banda poupada sao segundos de rede. As duas bandas que
    restam descem em paralelo. No Sao Jorge, a versao que lia as tres em fila
    levava cerca de 10 s por data.

    Devolve (ndvi, cobertura % pela SCL).
    """
    n_area = int(dentro.sum()) or 1
    bons = np.zeros(grade.forma, dtype=bool)
    uteis = []
    for it in itens_da_data:
        scl = geo.recortar(it["assets"]["scl"], grade, "near")[0]
        bom = dentro & ~bons & np.isfinite(scl) & ~np.isin(scl, SCL_RUIM)
        if bom.any():
            uteis.append((it, bom))
            bons |= bom
        if bons.sum() == n_area:
            break
    cobertura = 100.0 * float(bons.sum()) / n_area
    acumulado = np.full(grade.forma, np.nan, dtype=np.float32)
    if not uteis or cobertura < min_validos:
        return acumulado, cobertura
    for it, bom in uteis:
        with ThreadPoolExecutor(2) as ex:
            nir, red = ex.map(lambda k: geo.recortar(it["assets"][k], grade, "bilinear")[0], ("nir", "red"))
        nd = indice_ndvi(nir, red)
        usar = bom & np.isfinite(nd)
        acumulado[usar] = nd[usar]
    return np.where(dentro, acumulado, np.nan).astype(np.float32), cobertura


PARALELO_SERIE = 6


def serie_ndvi(itens, ctx, log, cancelar, min_validos=80.0, nuvem_area_max=100.0,
               ao_aceitar=None):
    """Estatistica de NDVI por data valida. `ao_aceitar(data, ndvi)` grava raster, se quiser."""
    grade, dentro = ctx["grade"], ctx["dentro"]
    n_area = int(dentro.sum())
    por_data = defaultdict(list)
    for it in itens:
        if all(k in it["assets"] for k in ("scl", "nir", "red")):
            por_data[it["data"]].append(it)
    datas = sorted(por_data)
    log(f"  {len(datas)} data(s) distinta(s) para processar ({PARALELO_SERIE} em paralelo)...")
    resultados, feitos = [], 0

    def tarefa(data):
        if cancelar():
            return data, None, 0.0, "cancelado"
        try:
            nd, cob = ndvi_da_data(por_data[data], grade, dentro, min_validos)
        except Exception as e:  # noqa: BLE001
            return data, None, 0.0, type(e).__name__
        return data, nd, cob, None

    with ThreadPoolExecutor(PARALELO_SERIE) as ex:
        for data, nd, cob_scl, falha in ex.map(tarefa, datas):
            feitos += 1
            if cancelar():
                raise Cancelado()
            if falha:
                log(f"  [{feitos:3d}/{len(datas)}] {data}  FALHA ({falha})")
                continue
            s = stats_ndvi(nd, dentro)
            cobertura = 100.0 * s["n"] / n_area if s and n_area else cob_scl
            nuvem = 100.0 - cobertura
            aceito = bool(s) and cobertura >= min_validos and nuvem <= nuvem_area_max
            log(f"  [{feitos:3d}/{len(datas)}] {data}  {'ok ' if aceito else '-- '}"
                f"nuvem no imovel {nuvem:5.1f} %  " + (f"NDVI {s['medio']:.3f}" if s else "sem pixel valido"))
            if not aceito:
                continue
            if ao_aceitar:
                ao_aceitar(data, nd)
            resultados.append(dict(data=data, cobertura=cobertura, nuvem=nuvem,
                                   cenas=len(por_data[data]), **s))
    resultados.sort(key=lambda r: r["data"])
    return resultados


def grafico_serie(linhas, caminho, titulo, ha):
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    xs = [datetime.strptime(r["data"], "%Y-%m-%d") for r in linhas]
    med = [r["medio"] for r in linhas]
    p10 = [r["p10"] for r in linhas]
    p90 = [r["p90"] for r in linhas]

    fig = Figure(figsize=(12.5, 5.6), dpi=110)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    ax.fill_between(xs, p10, p90, alpha=0.18, color="#1a6fc4",
                    label="faixa P10–P90 (variabilidade interna)")
    ax.plot(xs, med, "-o", color="#155a9e", lw=1.8, ms=4.5, label="NDVI médio da área")
    ax.axhspan(-1, 0.20, color="#c8a165", alpha=0.13)
    ax.text(xs[0], 0.10, "solo exposto / palhada", fontsize=8, color="#7a5c2e", va="center")
    ax.set_ylim(min(-0.05, min(p10) - 0.05), max(1.0, max(p90) + 0.05))
    ax.set_ylabel("NDVI")
    ax.set_title(f"{titulo}  -  {ha:,.1f} ha".replace(",", "@").replace(".", ",").replace("@", "."),
                 fontsize=12, weight="bold")
    ax.grid(alpha=0.25, ls=":")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: (lambda d: f"{fontes.MESES_PT[d.month - 1]}/{d.year % 100:02d}")(mdates.num2date(x))))
    fig.autofmt_xdate(rotation=45)
    ax.legend(loc="best", fontsize=9, framealpha=0.92)
    fig.text(0.01, 0.01, "Fonte: Copernicus Sentinel-2 (ESA)  |  AJ TopoGeo", fontsize=7.5, color="#666666")
    fig.tight_layout()
    fig.savefig(caminho)
    return True


# ------------------------------------------------------------ modos da aba de imagens


def processar_data_unica(kml, pasta, dt_ini, dt_fim, nuvem_max, quer_ndvi, quer_mde, log, cancelar):
    """Melhor imagem do periodo: RGB, NDVI (GeoTIFF + PNG), MDE e declividade."""
    ctx = preparar(kml, log)
    grade, dentro, epsg = ctx["grade"], ctx["dentro"], ctx["epsg"]
    itens = buscar_cenas(ctx, dt_ini, dt_fim, nuvem_max, log, cancelar)
    melhor, pct = escolher_cena(itens, ctx, log, cancelar)
    data = melhor["data"]
    log(f"Selecionada: {data} ({pct:.1f} % de nuvem sobre o imovel)")

    destino = Path(pasta) / f"{Path(kml).stem}_{data}"
    destino.mkdir(parents=True, exist_ok=True)
    resumo = ["RELATORIO DE AQUISICAO DE IMAGENS - AJ TopoGeo", "=" * 52,
              f"Perimetro ............ {Path(kml).name}",
              f"Area ................. {ctx['ha']:,.4f} ha",
              f"Sistema de referencia  SIRGAS 2000 / UTM (EPSG:{epsg})", "",
              f"Cena Sentinel-2 ...... {melhor['id']}",
              f"Data de imageamento .. {data}",
              f"Nuvem na cena ........ {melhor['nuvem']:.1f} %",
              f"Nuvem sobre a area ... {pct:.1f} %",
              "Resolucao optica ..... 10 m (B02/B03/B04/B08)", ""]

    if cancelar():
        raise Cancelado()
    log("Baixando a imagem e as bandas do NDVI...")
    cena = ler_cena(melhor, grade, dentro)
    rgb = np.where(dentro[np.newaxis], cena["rgb"], 0).astype(np.uint8)
    geo.gravar_tif(destino / f"RGB_{data}.tif", rgb, grade, nodata=0, rgb=True)
    log("  RGB gravado.")

    if quer_ndvi:
        ndvi = cena["ndvi"]
        geo.gravar_tif(destino / f"NDVI_{data}.tif", np.where(np.isnan(ndvi), -9999.0, ndvi),
                       grade, nodata=-9999.0)
        ndvi_png(ndvi, dentro, destino / f"NDVI_{data}.png")
        s = stats_ndvi(ndvi, dentro)
        if s:
            resumo += ["NDVI",
                       f"  medio .............. {s['medio']:.3f}",
                       f"  mediana ............ {s['mediana']:.3f}",
                       f"  minimo / maximo .... {s['min']:.3f} / {s['max']:.3f}",
                       f"  desvio padrao ...... {s['desvio']:.3f}",
                       f"  area < 0,20 ........ {s['pct_baixo']:.1f} %", ""]
        log("  NDVI gravado (GeoTIFF + PNG).")

    if quer_mde and not cancelar():
        grade30, dem, _, achados = mde_glo30(ctx, log)
        if achados:
            geo.gravar_tif(destino / "MDE_GLO30.tif", np.where(np.isnan(dem), -9999.0, dem),
                           grade30, nodata=-9999.0)
            decl = fontes.declividade_horn(np.nan_to_num(dem, nan=float(np.nanmean(dem))), 30.0)
            decl = np.where(np.isnan(dem), -9999.0, decl)
            geo.gravar_tif(destino / "DECLIVIDADE_pct.tif", decl, grade30, nodata=-9999.0)
            dv = dem[np.isfinite(dem)]
            resumo += ["ALTIMETRIA (Copernicus GLO-30, 30 m)",
                       f"  cota minima ........ {dv.min():.1f} m",
                       f"  cota maxima ........ {dv.max():.1f} m",
                       f"  amplitude .......... {dv.max() - dv.min():.1f} m", "",
                       "  OBS: GLO-30 e MODELO DIGITAL DE SUPERFICIE (MDS).",
                       "  Inclui dossel e edificacoes. Uso apenas para estudo",
                       "  preliminar - nao substitui levantamento topografico.", ""]
            log("  MDE e declividade gravados.")
        else:
            log("  ATENCAO: nenhuma folha do modelo de elevacao encontrada.")

    resumo += ["Fontes: Copernicus Sentinel-2 (ESA) via AWS Earth Search;",
               "        Copernicus DEM GLO-30 (ESA/Airbus), AWS Open Data."]
    (destino / "resumo.txt").write_text("\n".join(resumo), encoding="utf-8")
    log("")
    log(f"CONCLUIDO -> {destino}")
    return destino


def processar_serie(kml, pasta, dt_ini, dt_fim, nuvem_max, nuvem_area_max, min_validos,
                    salvar_rasters, log, cancelar):
    """Curva de vigor do periodo: CSV, grafico e, se pedido, raster por data."""
    ctx = preparar(kml, log)
    itens = buscar_cenas(ctx, dt_ini, dt_fim, nuvem_max, log, cancelar)
    destino = Path(pasta) / f"{Path(kml).stem}_serie_{dt_ini}_a_{dt_fim}"
    destino.mkdir(parents=True, exist_ok=True)
    pasta_ras = destino / "rasters"

    def gravar(data, nd):
        pasta_ras.mkdir(exist_ok=True)
        geo.gravar_tif(pasta_ras / f"NDVI_{data}.tif", np.where(np.isnan(nd), -9999.0, nd),
                       ctx["grade"], nodata=-9999.0)
        ndvi_png(nd, ctx["dentro"], pasta_ras / f"NDVI_{data}.png")

    resultados = serie_ndvi(itens, ctx, log, cancelar, min_validos, nuvem_area_max,
                            ao_aceitar=gravar if salvar_rasters else None)
    if not resultados:
        raise RuntimeError("Nenhuma data passou nos filtros. Afrouxe a nuvem sobre a area.")

    cols = ["data", "cenas", "nuvem", "cobertura", "medio", "mediana", "p10", "p90",
            "desvio", "min", "max", "pct_baixo", "n"]
    cab = ["Data", "Cenas", "Nuvem_area_%", "Cobertura_valida_%", "NDVI_medio", "NDVI_mediana",
           "NDVI_P10", "NDVI_P90", "Desvio_padrao", "NDVI_min", "NDVI_max",
           "Area_NDVI_menor_0.20_%", "Pixels_validos"]
    with open(destino / "serie_ndvi.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cab)
        for r in resultados:
            # decimal com virgula para abrir direto no Excel brasileiro
            w.writerow([f"{r[c]:.4f}".replace(".", ",") if isinstance(r[c], float) else r[c] for c in cols])
    log("")
    log(f"CSV com {len(resultados)} data(s) valida(s) gravado.")
    grafico_serie(resultados, destino / "serie_ndvi.png", Path(kml).stem, ctx["ha"])
    log("Grafico de evolucao gravado.")

    medias = [r["medio"] for r in resultados]
    pico = max(resultados, key=lambda r: r["medio"])
    vale = min(resultados, key=lambda r: r["medio"])
    resumo = ["SERIE TEMPORAL DE NDVI - AJ TopoGeo", "=" * 52,
              f"Perimetro ............ {Path(kml).name}",
              f"Area ................. {ctx['ha']:,.4f} ha",
              f"Sistema de referencia  SIRGAS 2000 / UTM (EPSG:{ctx['epsg']})",
              f"Periodo .............. {dt_ini} a {dt_fim}",
              f"Datas validas ........ {len(resultados)}", "",
              f"NDVI medio do periodo  {sum(medias) / len(medias):.3f}",
              f"Pico ................. {pico['medio']:.3f} em {pico['data']}",
              f"Vale ................. {vale['medio']:.3f} em {vale['data']}", "",
              "Filtros aplicados:",
              f"  nuvem maxima na cena ....... {nuvem_max:.0f} %",
              f"  nuvem maxima sobre a area .. {nuvem_area_max:.0f} %",
              f"  cobertura valida minima .... {min_validos:.0f} %", "",
              "OBS: NDVI e indice de vigor, nao de produtividade. Compare datas",
              "do mesmo estadio fenologico. Pixels de nuvem e sombra foram",
              "removidos pela banda SCL antes do calculo das estatisticas.", "",
              "Fonte: Copernicus Sentinel-2 (ESA) via AWS Earth Search."]
    (destino / "resumo.txt").write_text("\n".join(resumo), encoding="utf-8")
    log("")
    log(f"CONCLUIDO -> {destino}")
    return destino
