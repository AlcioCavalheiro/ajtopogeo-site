"""Consultas do relatorio da fazenda: cadastro, chuva, relevo e valor da terra.

Reescrito a partir do `fontes_dados.py` que chegou pronto. O que mudou, e por
que -- tudo conferido contra os servicos reais em 13/09/2026, em volta da
Faz. Sao Jorge:

- CAR ao vivo nao funcionava por quatro motivos em fila: o servidor recusa o
  aperto de mao TLS no nivel de seguranca padrao do OpenSSL 3 (aceita com
  SECLEVEL=1); as camadas se chamam `sicar_imoveis_<uf>` e o codigo procurava
  "imovel"; mesmo casando, pegaria as tres primeiras em ordem alfabetica (AC,
  AL, AM); e o GeoServer quer o bbox em lon,lat. Corrigido, devolveu 50 imoveis.
- SIGEF ao vivo nao funcionava porque o i3geo do INCRA nao serve GeoJSON --
  responde ExceptionReport. Em GML2, com o bbox em lat,lon (a ordem contraria
  a do CAR), devolveu 82 parcelas.
- A tabela de valor punha no PDF qualquer coluna numerica acima de 100: o
  codigo IBGE saia como R$ 5.000.203,00/ha, o exercicio como R$ 2.025,00/ha, e
  "18.500" era lido como 18,5 e sumia. Agora as tabelas tem colunas nomeadas, e
  numero inteiro com ponto de milhar e lido como milhar.
- O modulo fiscal sai do proprio CAR: cada imovel traz `area` e `m_fiscal`, e a
  razao entre os dois e o modulo do municipio (15,0 ha em Campo Grande nos 40
  imoveis conferidos). A tabela do INCRA fica de reserva.

As consultas ao vivo vem antes da base em disco. O original fazia o contrario
porque o WFS nao funcionava; funcionando, o cadastro do dia vale mais que um
arquivo baixado ha meses. A base local continua entrando quando o servico cai,
e o relatorio diz qual das duas foi usada.
"""

from __future__ import annotations

import csv
import math
import re
import ssl
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import numpy as np
import requests
from requests.adapters import HTTPAdapter

import fazenda_geo as geo

WFS_CAR = "https://geoserver.car.gov.br/geoserver/sicar/wfs"
WFS_INCRA = "http://acervofundiario.incra.gov.br/i3geo/ogc.php"
POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
TIMEOUT = 90
AGENTE = "AJTopoGeo-RelatorioFazenda/1.0"

PASTAS_BASE = {
    "car": "bases/CAR",
    "sigef": "bases/SIGEF",
    "vtn": "bases/VTN",
    "mercado": "bases/MERCADO",
    "modulo_fiscal": "bases/MODULO_FISCAL",
}

ONDE_BAIXAR = {
    "car": "consultapublica.car.gov.br › Base de Downloads › AREA_IMOVEL do estado",
    "sigef": "acervofundiario.incra.gov.br › Download › parcelas certificadas SIGEF por UF",
    "vtn": "gov.br/receitafederal › Valores de Terra Nua (VTN) › tabela do exercício",
    "mercado": "gov.br/incra › Relatório de Análise de Mercados de Terras (RAMT) do estado",
    "modulo_fiscal": "gov.br/incra › Tabela de Índices Básicos do SNCR",
}


def normalizar(s) -> str:
    """Sem acento, minusculo, sem espaco duplo -- para casar nome de municipio."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


# ------------------------------------------------------------ rede


class _TLSLegado(HTTPAdapter):
    """O GeoServer do CAR so aceita o aperto de mao com o nivel de seguranca 1."""

    def init_poolmanager(self, *args, **kwargs):
        try:
            import certifi
            contexto = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            contexto = ssl.create_default_context()
        contexto.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = contexto
        return super().init_poolmanager(*args, **kwargs)


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = AGENTE
    s.mount("https://geoserver.car.gov.br", _TLSLegado())
    return s


def _bbox_lonlat(bbox):
    l, b, r, t = bbox
    return f"{l},{b},{r},{t},EPSG:4326"


def _bbox_latlon(bbox):
    l, b, r, t = bbox
    return f"{b},{l},{t},{r},EPSG:4326"


# ------------------------------------------------------------ bases locais


def localizar_base(raiz, chave, uf=None):
    """Arquivo vetorial da base pedida (CAR/SIGEF) em disco, ou None."""
    pasta = Path(raiz) / PASTAS_BASE[chave]
    if not pasta.is_dir():
        return None
    achados = [a for e in ("*.gpkg", "*.shp", "*.geojson", "*.json") for a in pasta.rglob(e)]
    if not achados:
        return None
    if uf:
        # "_MS." ou "_MS_" no nome; "ms" solto casaria com qualquer "gms", "msg"...
        preferidos = [a for a in achados if re.search(rf"(^|[^a-z]){uf.lower()}([^a-z]|$)", a.stem.lower())]
        achados = preferidos or achados
    # GeoPackage costuma ter indice espacial; entre iguais, o maior
    achados.sort(key=lambda a: (a.suffix.lower() != ".gpkg", -a.stat().st_size))
    return achados[0]


def situacao_das_bases(raiz, uf=None) -> list[tuple[str, str]]:
    """Linha por base, para a janela mostrar o que esta carregado."""
    saida = []
    for chave in PASTAS_BASE:
        if chave in ("car", "sigef"):
            arq = localizar_base(raiz, chave, uf)
            saida.append((chave, f"reserva local: {arq.name}" if arq else "ao vivo (sem reserva local)"))
        else:
            arqs = sorted((Path(raiz) / PASTAS_BASE[chave]).rglob("*.csv"))
            saida.append((chave, ", ".join(a.name for a in arqs) if arqs else "AUSENTE"))
    return saida


# ------------------------------------------------------------ cadastro


def car_ao_vivo(uf, bbox, alvo_wkt_utm, epsg, log):
    camada = f"sicar:sicar_imoveis_{uf.lower()}"
    r = sessao().get(WFS_CAR, params=dict(
        service="WFS", version="1.1.0", request="GetFeature", typeName=camada,
        outputFormat="application/json", srsName="EPSG:4326", bbox=_bbox_lonlat(bbox)),
        timeout=TIMEOUT)
    r.raise_for_status()
    if not r.content.lstrip().startswith(b"{"):
        raise RuntimeError("o servico respondeu sem GeoJSON: " + r.text[:160])
    bruto = r.json()
    n = len(bruto.get("features") or [])
    total = bruto.get("totalFeatures")
    log(f"    {camada}: {n} imovel(is) na janela"
        + (f" -- o servico tem {total} e cortou a resposta" if isinstance(total, int) and total > n else ""))
    if not n:
        return [], bruto
    with geo.Vetor(r.content, ".geojson") as v:
        return geo.sobreposicao(v, alvo_wkt_utm, epsg), bruto


def sigef_ao_vivo(uf, bbox, alvo_wkt_utm, epsg, log):
    """Parcelas certificadas, particulares e publicas, do Acervo Fundiario."""
    resultados, respondeu = [], False
    for tipo in ("particular", "publico"):
        tema = f"certificada_sigef_{tipo}_{uf.lower()}"
        try:
            r = requests.get(WFS_INCRA, params=dict(
                service="WFS", version="1.1.0", request="GetFeature", typeName=tema, tema=tema,
                outputFormat="GML2", srsName="EPSG:4326", bbox=_bbox_latlon(bbox)),
                timeout=TIMEOUT, headers={"User-Agent": AGENTE})
            r.raise_for_status()
        except requests.RequestException as e:
            log(f"    {tema}: {type(e).__name__}")
            continue
        cabeca = r.content[:800]
        if b"ExceptionReport" in cabeca or b"FeatureCollection" not in cabeca:
            log(f"    {tema}: o servico nao tem esta camada")
            continue
        respondeu = True
        n = r.content.count(b"featureMember")
        log(f"    {tema}: {n} parcela(s) na janela")
        if not n:
            continue
        with geo.Vetor(r.content, ".gml", opcoes=["CONSIDER_EPSG_AS_URN=YES"]) as v:
            for item in geo.sobreposicao(v, alvo_wkt_utm, epsg):
                item["atributos"]["natureza"] = tipo
                resultados.append(item)
    if not respondeu:
        raise RuntimeError("o Acervo Fundiario nao respondeu")
    resultados.sort(key=lambda x: -x["area_comum_ha"])
    return resultados


def consultar_cadastro(tipo, raiz, alvo_wkt_utm, bbox, epsg, uf, log) -> dict:
    """CAR ou SIGEF: ao vivo, e a base em disco se o servico cair.

    `resultados` lista vazia = consultado e nada sobreposto; None = nao deu.
    """
    rotulo = "CAR" if tipo == "car" else "SIGEF/INCRA"
    hoje = date.today().strftime("%d/%m/%Y")
    log(f"  {rotulo}:")
    try:
        if tipo == "car":
            res, bruto = car_ao_vivo(uf, bbox, alvo_wkt_utm, epsg, log)
            origem = f"WFS do SICAR, consulta ao vivo em {hoje}"
        else:
            res, bruto = sigef_ao_vivo(uf, bbox, alvo_wkt_utm, epsg, log), None
            origem = f"WFS do Acervo Fundiário do INCRA, consulta ao vivo em {hoje}"
        return dict(resultados=res, origem=origem, aviso=None, bruto=bruto)
    except Exception as e:  # noqa: BLE001 - cai para a base local, e diz no log
        log(f"    consulta ao vivo falhou ({type(e).__name__}: {str(e)[:120]})")

    caminho = localizar_base(raiz, tipo, uf)
    if caminho:
        try:
            log(f"    lendo a base local {caminho.name}...")
            with geo.Vetor(caminho) as v:
                res = geo.sobreposicao(v, alvo_wkt_utm, epsg, bbox_wgs=bbox)
            data = datetime.fromtimestamp(caminho.stat().st_mtime).strftime("%d/%m/%Y")
            return dict(resultados=res, origem=f"base local {caminho.name} (arquivo de {data})",
                        aviso="O serviço não respondeu; foi usada a base em disco, que pode "
                              "estar desatualizada.", bruto=None)
        except Exception as e:  # noqa: BLE001
            log(f"    falha na base local: {e}")
    aviso = (f"Não foi possível consultar o {rotulo}: o serviço não respondeu e não há base "
             f"em {PASTAS_BASE[tipo]}/. Onde baixar: {ONDE_BAIXAR[tipo]}.")
    log(f"    {aviso}")
    return dict(resultados=None, origem=None, aviso=aviso, bruto=None)


def municipio_pelo_car(car: dict) -> dict | None:
    """Municipio e modulo fiscal tirados da propria resposta do CAR.

    O municipio e o do imovel de maior area comum com o perimetro. O modulo e a
    mediana de `area / m_fiscal` dos imoveis desse municipio com 20 ha ou mais:
    abaixo disso o arredondamento do `m_fiscal` (duas casas) distorce a razao.
    """
    bruto = car.get("bruto") or {}
    razoes, nomes = defaultdict(list), {}
    for f in bruto.get("features") or []:
        p = f.get("properties") or {}
        cod = str(p.get("cod_municipio_ibge") or "")
        if not cod:
            continue
        nomes[cod] = p.get("municipio")
        try:
            area, mf = float(p.get("area")), float(p.get("m_fiscal"))
        except (TypeError, ValueError):
            continue
        if area >= 20 and mf > 0:
            razoes[cod].append(area / mf)
    cod = None
    if car.get("resultados"):
        cod = str(car["resultados"][0]["atributos"].get("cod_municipio_ibge") or "") or None
    if not cod and razoes:
        cod = max(razoes, key=lambda c: len(razoes[c]))
    if not cod:
        return None
    amostra = razoes.get(cod) or []
    return dict(cod_ibge=cod, municipio=nomes.get(cod),
                modulo_fiscal=float(round(float(np.median(amostra)))) if amostra else None,
                amostra=len(amostra))


# ------------------------------------------------------------ chuva

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun",
            "jul", "ago", "set", "out", "nov", "dez"]


def chuva_nasa_power(lat, lon, anos_normal=20, log=print) -> dict:
    """Precipitacao do NASA POWER: climatologia mensal e ultimos 12 meses.

    Conferido no Sao Jorge: normal de 1.185 mm/ano, ultimos 12 meses 11 % abaixo.
    """
    hoje = date.today()
    fim = date(hoje.year, hoje.month, 1) - date.resolution
    inicio = date(fim.year - anos_normal, 1, 1)
    log(f"  Precipitacao NASA POWER ({inicio.year}-{fim.year})...")
    r = requests.get(POWER, params=dict(
        parameters="PRECTOTCORR", community="AG", latitude=f"{lat:.4f}", longitude=f"{lon:.4f}",
        start=inicio.strftime("%Y%m%d"), end=fim.strftime("%Y%m%d"), format="JSON"),
        timeout=TIMEOUT, headers={"User-Agent": AGENTE})
    r.raise_for_status()
    serie = r.json()["properties"]["parameter"]["PRECTOTCORR"]

    por_mes = defaultdict(float)
    for k, v in serie.items():
        if v is None or v < -900:
            continue
        por_mes[(int(k[:4]), int(k[4:6]))] += float(v)
    if not por_mes:
        raise RuntimeError("NASA POWER nao retornou dados de precipitacao.")

    ult12, cur = [], date(fim.year, fim.month, 1)
    for _ in range(12):
        ult12.append((cur.year, cur.month))
        cur = (cur - date.resolution).replace(day=1)
    ult12.reverse()
    fora = [(a, m) for (a, m) in por_mes if (a, m) not in set(ult12)]

    # a normal exclui os ultimos 12 meses, para nao comparar o ano com ele mesmo
    clim = {m: [por_mes[(a, mm)] for (a, mm) in fora if mm == m] for m in range(1, 13)}
    normal = {m: (sum(v) / len(v) if v else float("nan")) for m, v in clim.items()}
    recente = [(a, m, por_mes.get((a, m), float("nan"))) for a, m in ult12]
    total_normal = sum(v for v in normal.values() if not math.isnan(v))
    total_recente = sum(v for _, _, v in recente if not math.isnan(v))
    anos = sorted({a for a, _ in fora})
    return dict(
        normal=normal, recente=recente, total_normal=total_normal, total_recente=total_recente,
        desvio_pct=100.0 * (total_recente - total_normal) / total_normal if total_normal else float("nan"),
        periodo_normal=f"{anos[0]}-{anos[-1]}" if anos else "-",
        mes_seco=min(normal, key=lambda m: normal[m]),
        mes_chuvoso=max(normal, key=lambda m: normal[m]),
        fonte="NASA POWER / MERRA-2 (grade de ~0,5° × 0,625°)",
    )


# ------------------------------------------------------------ declividade

# Classes de relevo - Manual Tecnico de Pedologia (IBGE) / Embrapa
CLASSES_DECL = [
    (0, 3, "Plano"),
    (3, 8, "Suave ondulado"),
    (8, 20, "Ondulado"),
    (20, 45, "Forte ondulado"),
    (45, 75, "Montanhoso"),
    (75, 1e9, "Escarpado"),
]
CORES_DECL = ["#2e7d32", "#9ccc65", "#fff176", "#ffb74d", "#e57373", "#8e24aa"]


def declividade_horn(dem, px):
    """Declividade em % pelo metodo de Horn (janela 3x3). Conferido em rampas de
    2, 10, 30 e 50 graus: sai exato."""
    z = np.pad(dem, 1, mode="edge")
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * px)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * px)
    return 100.0 * np.hypot(dzdx, dzdy)


def tabela_declividade(decl, dentro, area_px_ha):
    v = decl[dentro & np.isfinite(decl)]
    if v.size == 0:
        return [], 0.0
    linhas = []
    for lo, hi, nome in CLASSES_DECL:
        n = int(((v >= lo) & (v < hi)).sum())
        linhas.append(dict(classe=nome, faixa=f"{lo} a {hi} %" if hi < 1e8 else "> 75 %",
                           ha=n * area_px_ha, pct=100.0 * n / v.size))
    return linhas, float(np.median(v))


def restricoes_legais(decl, dentro, area_px_ha):
    """Lei 12.651/2012: art. 4, V -- APP acima de 45 graus (100 %);
    art. 11 -- uso restrito entre 25 e 45 graus (46,6 % a 100 %)."""
    v = decl[dentro & np.isfinite(decl)]
    if v.size == 0:
        return None
    lim_25 = 100.0 * math.tan(math.radians(25))
    n_app = int((v >= 100.0).sum())
    n_res = int(((v >= lim_25) & (v < 100.0)).sum())
    return dict(app_ha=n_app * area_px_ha, app_pct=100.0 * n_app / v.size,
                restrito_ha=n_res * area_px_ha, restrito_pct=100.0 * n_res / v.size)


# ------------------------------------------------------------ valores

VTN_COLUNAS = [
    ("lavoura_aptidao_boa", "Lavoura – aptidão boa"),
    ("lavoura_aptidao_regular", "Lavoura – aptidão regular"),
    ("lavoura_aptidao_restrita", "Lavoura – aptidão restrita"),
    ("pastagem_plantada", "Pastagem plantada"),
    ("silvicultura_ou_pastagem_natural", "Silvicultura ou pastagem natural"),
    ("preservacao_fauna_flora", "Preservação da fauna e da flora"),
]
FONTE_VTN = {"1": "informados pelo município", "2": "informados por órgão estadual"}

# Coluna com numero que NAO e valor por hectare. Era a falta disto que punha o
# codigo IBGE e o ano na tabela de precos do PDF.
NAO_E_VALOR = re.compile(r"cod|ibge|^ano|exerc|fonte|^id$|^uf$|munic|mrt|nivel|mercado|regi"
                         r"|area|popul|^lat|^lon|inconsist")


def ler_csv(caminho) -> list[dict]:
    """CSV com separador e codificacao que o Brasil costuma usar."""
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            with open(caminho, encoding=codificacao, newline="") as f:
                amostra = f.read(4096)
                f.seek(0)
                try:
                    dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t")
                except csv.Error:
                    dialeto = csv.excel
                    dialeto.delimiter = ";"
                return list(csv.DictReader(f, dialect=dialeto))
        except UnicodeDecodeError:
            continue
    return []


def valor_br(texto):
    """Numero escrito do jeito brasileiro, do americano ou com erro de digitacao.

    "18.500" e dezoito mil e quinhentos, nao 18,5: preco de terra por hectare nao
    tem tres casas decimais. "7.046.16", que aparece na tabela do VTN 2026, e
    7.046,16. "s/informacao" vira None.
    """
    if texto is None:
        return None
    t = str(texto).strip().replace("R$", "").replace(" ", "")
    if not t or re.search(r"informa|^-+$", t, re.I):
        return None
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        return float(t.replace(".", ""))
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        partes = t.split(".")
        t = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return float(t)
    except ValueError:
        return None


def _exercicio(caminho) -> int:
    m = re.search(r"(20\d\d)", Path(caminho).name)
    return int(m.group(1)) if m else 0


def vtn_do_municipio(raiz, municipio, uf):
    """VTN da Receita para o municipio, da tabela de exercicio mais recente."""
    pasta = Path(raiz) / PASTAS_BASE["vtn"]
    alvo, alvo_uf = normalizar(municipio), normalizar(uf)
    for arq in sorted(pasta.rglob("*.csv"), key=_exercicio, reverse=True):
        for lin in ler_csv(arq):
            chaves = {normalizar(k): k for k in lin if k}
            kmun = next((chaves[k] for k in chaves if "munic" in k), None)
            kuf = next((chaves[k] for k in chaves if k in ("uf", "estado", "sigla_uf")), None)
            if not kmun or normalizar(lin[kmun]) != alvo:
                continue
            if kuf and normalizar(lin[kuf]) not in (alvo_uf, ""):
                continue
            linhas = []
            if any(c in lin for c, _ in VTN_COLUNAS):
                for c, rotulo in VTN_COLUNAS:
                    if c in lin:
                        linhas.append(dict(aptidao=rotulo, valor=valor_br(lin[c])))
            else:
                for k, v in lin.items():
                    if not k or k in (kmun, kuf) or NAO_E_VALOR.search(normalizar(k)):
                        continue
                    x = valor_br(v)
                    if x is not None:
                        linhas.append(dict(aptidao=k.strip(), valor=x))
            fonte = (lin.get("fonte") or "").strip()
            return dict(linhas=linhas, exercicio=_exercicio(arq), arquivo=arq.name,
                        fonte=FONTE_VTN.get(fonte, fonte))
    return None


def mercado_do_municipio(raiz, municipio, uf):
    """Precos referenciais do INCRA (RAMT/PPR) para o mercado regional do municipio.

    Duas tabelas: a que diz em qual mercado regional (MRT) cada municipio esta,
    e a de precos por mercado. Sem o municipio na primeira, nao ha preco -- e o
    relatorio diz isso, em vez de cair para uma media do estado que nao descreve
    o imovel.
    """
    pasta = Path(raiz) / PASTAS_BASE["mercado"]
    mapa, precos = {}, []
    for arq in sorted(pasta.rglob("*.csv"), key=_exercicio, reverse=True):
        linhas = ler_csv(arq)
        if not linhas:
            continue
        colunas = {normalizar(k) for k in linhas[0] if k}
        if {"uso", "mrt"} <= colunas:
            precos += [dict(l, _arquivo=arq.name, _ano=_exercicio(arq)) for l in linhas]
        elif {"municipio", "mrt"} <= colunas:
            for l in linhas:
                mapa.setdefault((normalizar(l.get("uf")), normalizar(l.get("municipio"))),
                                (str(l["mrt"]), l.get("mercado"), _exercicio(arq)))
    chave = (normalizar(uf), normalizar(municipio))
    if chave not in mapa:
        return None
    mrt, mercado, ano = mapa[chave]
    escolhidos = [p for p in precos if normalizar(p.get("uf")) == chave[0]
                  and str(p.get("mrt")) == mrt and p["_ano"] == ano]
    return dict(
        mrt=mrt, mercado=mercado, ano=ano,
        arquivo=escolhidos[0]["_arquivo"] if escolhidos else None,
        linhas=[dict(nivel=p.get("nivel", ""), uso=p.get("uso", ""),
                     vtn_min=valor_br(p.get("vtn_min")), vtn_mediano=valor_br(p.get("vtn_mediano")),
                     vtn_max=valor_br(p.get("vtn_max")), vti_mediano=valor_br(p.get("vti_mediano")),
                     inconsistencia=(p.get("inconsistencia_na_fonte") or "").strip())
                for p in escolhidos])


def valores_referencia(raiz, municipio, uf, log) -> dict:
    saida = dict(vtn=None, mercado=None, avisos=[])
    if not municipio:
        saida["avisos"].append("Município não identificado: sem ele não há como buscar VTN nem "
                               "preço de mercado.")
        log("  Valores: municipio nao identificado.")
        return saida
    saida["vtn"] = vtn_do_municipio(raiz, municipio, uf)
    if saida["vtn"]:
        log(f"  VTN {saida['vtn']['exercicio']}: {len(saida['vtn']['linhas'])} aptidao(oes) para {municipio}.")
    else:
        saida["avisos"].append(f"{municipio}/{uf} não consta nas tabelas de VTN carregadas "
                               f"({ONDE_BAIXAR['vtn']}).")
        log(f"  VTN: {municipio}/{uf} nao encontrado.")
    saida["mercado"] = mercado_do_municipio(raiz, municipio, uf)
    if saida["mercado"]:
        m = saida["mercado"]
        log(f"  Mercado: MRT-{int(m['mrt']):02d} {m['mercado']} ({m['ano']}), {len(m['linhas'])} tipologia(s).")
    else:
        saida["avisos"].append(f"Não há tabela de mercado de terras do INCRA carregada para "
                               f"{municipio}/{uf} ({ONDE_BAIXAR['mercado']}).")
        log(f"  Mercado: sem tabela para {municipio}/{uf}.")
    return saida


def modulo_fiscal_tabela(raiz, municipio, uf, cod_ibge=None):
    """Modulo fiscal pela tabela do INCRA: (hectares, arquivo) ou (None, None)."""
    pasta = Path(raiz) / PASTAS_BASE["modulo_fiscal"]
    for arq in sorted(pasta.rglob("*.csv"), key=_exercicio, reverse=True):
        for l in ler_csv(arq):
            if cod_ibge and str(l.get("cod_ibge", "")).strip() == str(cod_ibge):
                return valor_br(l.get("modulo_fiscal_ha")), arq.name
            if (municipio and normalizar(l.get("municipio")) == normalizar(municipio)
                    and normalizar(l.get("uf")) == normalizar(uf)):
                return valor_br(l.get("modulo_fiscal_ha")), arq.name
    return None, None


def classificar_por_modulos(area_ha, mf):
    """Lei 8.629/1993, art. 4."""
    if not mf or mf <= 0:
        return None, None
    n = area_ha / mf
    if n <= 4:
        return n, "pequena propriedade (até 4 módulos fiscais)"
    if n <= 15:
        return n, "média propriedade (de 4 a 15 módulos fiscais)"
    return n, "grande propriedade (acima de 15 módulos fiscais)"
