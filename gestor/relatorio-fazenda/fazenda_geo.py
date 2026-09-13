"""GDAL do pacote para o relatorio da fazenda: imagem remota, vetor e geometria.

O gerador que chegou pronto usava rasterio, geopandas e shapely. Os dois
primeiros trazem cada um a sua copia do GDAL -- e o programa ja leva uma, a da
Consulta de Cota. Este modulo faz o mesmo trabalho falando direto com essa DLL,
pelo mesmo carregador das curvas de nivel: uma biblioteca so no processo.

Tres detalhes que so aparecem fora do QGIS, e que custaram teste para achar:

- Carregado por DLL, o curl de dentro do GDAL nao acha os certificados raiz e
  toda imagem do Sentinel falha com "unable to get local issuer certificate".
  O `certifi`, que ja vem com o requests, resolve.
- O INCRA serve GML com `srsName="EPSG:4326"` e coordenada em lat,lon. O OGR,
  por padrao, le a primeira como X e a parcela vai parar no Atlantico Sul;
  `CONSIDER_EPSG_AS_URN=YES` e o que a poe no lugar.
- Area sai sempre de geometria em UTM. Conferido contra o campo `area` do CAR
  em 30 imoveis: diferenca mediana de 0,000 %, a pior de 0,07 %.
"""

from __future__ import annotations

import ctypes as C
import json
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
if not getattr(sys, "frozen", False):
    # rodando do fonte, o carregador do GDAL mora na pasta da Consulta de Cota
    sys.path.insert(0, str(AQUI.parent / "consulta-cota"))

import curvas  # noqa: E402

GDAL_OF_VECTOR = 0x04
OAMS_TRADITIONAL_GIS_ORDER = 0
GDT_BYTE = 1
GCI_RED = 3

# Leitura de COG remoto sem listar diretorio e sem assinar requisicao no S3
# publico; o resto encurta viagens de rede, que e onde o tempo vai.
CONFIG_REDE = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "AWS_NO_SIGN_REQUEST": "YES",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_INGESTED_BYTES_AT_OPEN": "32768",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "67108864",
    "GDAL_HTTP_TIMEOUT": "60",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "GML_DOWNLOAD_SCHEMA": "NO",
}


def pasta_do_programa() -> Path:
    """Onde ficam o config.json e a pasta `bases`.

    Empacotado, `__file__` aponta para a pasta temporaria em que o executavel se
    descompacta; o que vale e a pasta do proprio .exe. O gerador original usava
    `__file__` direto e, instalado, procuraria as bases num lugar que some ao
    fechar o programa.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return AQUI


def carregar_config(base_dir=None) -> dict:
    base_dir = Path(base_dir) if base_dir else pasta_do_programa()
    cfg = json.loads((base_dir / "config.json").read_text(encoding="utf-8"))
    for chave in ("gdalBin", "gdalData", "projData"):
        if cfg.get(chave):
            cfg[chave] = str((base_dir / cfg[chave]).resolve())
    return cfg


# ------------------------------------------------------------ biblioteca

_lib = None
_trava = threading.Lock()


def biblioteca(cfg=None):
    """A DLL do GDAL com os prototipos que o relatorio usa alem dos das curvas.

    Com trava. Sem ela, a serie de NDVI -- que dispara as leituras em varias
    threads -- fazia a primeira chamada ao GDAL de seis threads ao mesmo tempo:
    seis cargas da DLL, seis GDALAllRegister e seis declaracoes de prototipo em
    corrida. O processo morria com "access violation" e heap corrompido
    (0xc0000374), sem traceback nenhum.
    """
    global _lib
    if _lib is not None:
        return _lib
    with _trava:
        if _lib is None:
            _lib = _carregar(cfg)
    return _lib


def _carregar(cfg):
    lib = curvas.abrir_biblioteca(cfg or carregar_config())
    p = C.c_void_p

    def d(nome, restype, *argtypes):
        fn = getattr(lib, nome)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    d("GDALGetRasterCount", C.c_int, p)
    d("GDALSetRasterColorInterpretation", C.c_int, p, C.c_int)
    d("GDALOpenEx", p, C.c_char_p, C.c_uint, C.POINTER(C.c_char_p),
      C.POINTER(C.c_char_p), C.POINTER(C.c_char_p))
    d("GDALDatasetGetLayerCount", C.c_int, p)
    d("GDALDatasetGetLayer", p, p, C.c_int)
    d("VSIFileFromMemBuffer", p, C.c_char_p, p, C.c_uint64, C.c_int)
    d("VSIFCloseL", C.c_int, p)
    d("VSIUnlink", C.c_int, C.c_char_p)
    d("VSIFree", None, p)
    d("OGR_L_GetSpatialRef", p, p)
    d("OGR_L_SetSpatialFilter", None, p, p)
    d("OGR_F_GetFieldCount", C.c_int, p)
    d("OGR_F_GetFieldDefnRef", p, p, C.c_int)
    d("OGR_F_IsFieldSetAndNotNull", C.c_int, p, C.c_int)
    d("OGR_F_GetFieldAsString", C.c_char_p, p, C.c_int)
    d("OGR_Fld_GetNameRef", C.c_char_p, p)
    d("OGR_G_CreateFromWkt", C.c_int, C.POINTER(C.c_char_p), p, C.POINTER(p))
    d("OGR_G_Clone", p, p)
    d("OGR_G_GetSpatialReference", p, p)
    d("OGR_G_AssignSpatialReference", None, p, p)
    d("OGR_G_TransformTo", C.c_int, p, p)
    d("OGR_G_IsValid", C.c_int, p)
    d("OGR_G_MakeValid", p, p)
    d("OGR_G_Intersection", p, p, p)
    d("OGR_G_Area", C.c_double, p)
    d("OSRImportFromEPSG", C.c_int, p, C.c_int)
    d("OSRExportToWkt", C.c_int, p, C.POINTER(p))

    opcoes = dict(CONFIG_REDE)
    try:
        import certifi
        opcoes["CURL_CA_BUNDLE"] = certifi.where()
    except ImportError:          # sem certifi o curl ainda pode ter o do sistema
        pass
    for chave, valor in opcoes.items():
        lib.CPLSetConfigOption(chave.encode(), str(valor).encode("utf-8"))
    return lib


def _erro(mensagem):
    return curvas._erro(biblioteca(), mensagem)


def _srs(epsg: int):
    lib = biblioteca()
    srs = lib.OSRNewSpatialReference(None)
    if lib.OSRImportFromEPSG(srs, int(epsg)) != 0:
        lib.OSRDestroySpatialReference(srs)
        raise _erro(f"Sistema EPSG:{epsg} desconhecido")
    # x = leste/longitude, sempre. Sem isto o GDAL 3 segue a ordem da norma, que
    # para o EPSG:4326 e latitude primeiro.
    lib.OSRSetAxisMappingStrategy(srs, OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def wkt_do_epsg(epsg: int) -> str:
    lib = biblioteca()
    srs = _srs(epsg)
    saida = C.c_void_p()
    try:
        lib.OSRExportToWkt(srs, C.byref(saida))
        return C.string_at(saida.value).decode("utf-8")
    finally:
        if saida.value:
            lib.VSIFree(saida)
        lib.OSRDestroySpatialReference(srs)


# ------------------------------------------------------------ raster


@dataclass(frozen=True)
class Grade:
    """Grade de pixels em UTM, com o canto superior esquerdo em (x0, y0)."""

    x0: float
    y0: float
    res: float
    nx: int
    ny: int
    epsg: int

    @classmethod
    def envolvendo(cls, xmin, ymin, xmax, ymax, res, epsg, folga_px=6):
        """Grade alinhada em multiplos da resolucao, com folga em volta.

        Alinhar ao multiplo e o que faz o pixel de 10 m coincidir com o do
        Sentinel, que tambem e multiplo de 10 m no UTM: a leitura nao
        reinterpola o que ja estava no lugar.
        """
        f = folga_px * res
        x0 = np.floor((xmin - f) / res) * res
        y1 = np.floor((ymin - f) / res) * res
        x1 = np.ceil((xmax + f) / res) * res
        y0 = np.ceil((ymax + f) / res) * res
        return cls(float(x0), float(y0), float(res), int(round((x1 - x0) / res)),
                   int(round((y0 - y1) / res)), int(epsg))

    @property
    def forma(self):
        return (self.ny, self.nx)

    @property
    def extent(self):
        """(esquerda, direita, baixo, cima) -- a ordem do imshow."""
        return (self.x0, self.x0 + self.nx * self.res,
                self.y0 - self.ny * self.res, self.y0)

    @property
    def area_pixel_ha(self):
        return self.res * self.res / 10000.0

    def geotransform(self):
        return (self.x0, self.res, 0.0, self.y0, 0.0, -self.res)

    def centros(self):
        """Coordenadas dos centros de pixel: (x de cada coluna, y de cada linha)."""
        xs = self.x0 + (np.arange(self.nx) + 0.5) * self.res
        ys = self.y0 - (np.arange(self.ny) + 0.5) * self.res
        return xs, ys


def recortar(origem: str, grade: Grade, metodo="bilinear") -> np.ndarray:
    """Le do raster so a janela da grade, ja reprojetada. Local ou URL.

    Devolve float32 com forma (bandas, linhas, colunas) e NaN onde nao ha dado.
    Com URL, so os blocos do COG que cobrem a janela descem pela rede. Pode ser
    chamada de varias threads ao mesmo tempo: o ctypes solta o GIL durante a
    chamada e cada leitura abre o seu proprio dataset.
    """
    lib = biblioteca()
    nome = "/vsicurl/" + origem if origem.startswith(("http://", "https://")) else origem
    src = lib.GDALOpen(nome.encode("utf-8"), 0)
    if not src:
        raise _erro(f"Nao consegui abrir {origem}")
    try:
        # float() antes do repr: com numpy 2, repr de np.float64 sai como
        # "np.float64(744240.0)" e o GDAL recusa o argumento
        esq, dir_, baixo, cima = (float(v) for v in grade.extent)
        args = ["-of", "MEM", "-t_srs", f"EPSG:{grade.epsg}",
                "-te", repr(esq), repr(baixo), repr(dir_), repr(cima),
                "-ts", str(grade.nx), str(grade.ny), "-r", metodo,
                "-ot", "Float32", "-dstnodata", "nan"]
        opcoes = lib.GDALWarpAppOptionsNew(curvas._lista(args), None)
        if not opcoes:
            raise _erro("Opcoes de recorte invalidas")
        try:
            saida = lib.GDALWarp(b"", None, 1, (C.c_void_p * 1)(src), opcoes, None)
        finally:
            lib.GDALWarpAppOptionsFree(opcoes)
    finally:
        lib.GDALClose(src)
    if not saida:
        raise _erro(f"Nao consegui recortar {origem}")
    try:
        n = lib.GDALGetRasterCount(saida)
        dados = np.empty((n, grade.ny, grade.nx), dtype=np.float32)
        for i in range(n):
            ok = lib.GDALRasterIO(lib.GDALGetRasterBand(saida, i + 1), curvas.GF_Read, 0, 0,
                                  grade.nx, grade.ny, dados[i].ctypes.data_as(C.c_void_p),
                                  grade.nx, grade.ny, curvas.GDT_Float32, 0, 0)
            if ok != curvas.CE_None:
                raise _erro(f"Nao consegui ler {origem}")
    finally:
        lib.GDALClose(saida)
    return dados


def gravar_tif(caminho, dados, grade: Grade, nodata=None, rgb=False):
    """GeoTIFF comprimido. Aceita uint8 (imagem) ou float32 (indice, cota)."""
    lib = biblioteca()
    dados = np.asarray(dados)
    if dados.ndim == 2:
        dados = dados[np.newaxis]
    if dados.dtype == np.uint8:
        tipo, preditor = GDT_BYTE, "2"
    else:
        dados, tipo, preditor = dados.astype(np.float32), curvas.GDT_Float32, "3"
    driver = lib.GDALGetDriverByName(b"GTiff")
    ds = lib.GDALCreate(driver, str(caminho).encode("utf-8"), grade.nx, grade.ny,
                        dados.shape[0], tipo,
                        curvas._lista(["COMPRESS=DEFLATE", "TILED=YES", "PREDICTOR=" + preditor]))
    if not ds:
        raise _erro(f"Nao consegui criar {caminho}")
    try:
        lib.GDALSetGeoTransform(ds, (C.c_double * 6)(*grade.geotransform()))
        lib.GDALSetProjection(ds, wkt_do_epsg(grade.epsg).encode("utf-8"))
        for i in range(dados.shape[0]):
            banda = lib.GDALGetRasterBand(ds, i + 1)
            if nodata is not None:
                lib.GDALSetRasterNoDataValue(banda, float(nodata))
            if rgb and dados.shape[0] == 3:
                lib.GDALSetRasterColorInterpretation(banda, GCI_RED + i)
            bloco = np.ascontiguousarray(dados[i])
            ok = lib.GDALRasterIO(banda, curvas.GF_Write, 0, 0, grade.nx, grade.ny,
                                  bloco.ctypes.data_as(C.c_void_p), grade.nx, grade.ny,
                                  tipo, 0, 0)
            if ok != curvas.CE_None:
                raise _erro(f"Nao consegui gravar {caminho}")
    finally:
        lib.GDALClose(ds)


# ------------------------------------------------------------ vetor


class Vetor:
    """Dataset vetorial do OGR, aberto de arquivo ou dos bytes de uma resposta WFS.

    Resposta de servico vai para o `/vsimem/`, o disco em memoria do GDAL: nada
    de arquivo temporario para apagar, e o OGR escolhe o driver pela extensao.
    """

    def __init__(self, origem, extensao=".geojson", opcoes=()):
        lib = biblioteca()
        self.ds = None
        self._memoria = None
        self._buffer = None
        if isinstance(origem, (bytes, bytearray)):
            self._memoria = f"/vsimem/fazenda_{id(self)}{extensao}"
            self._buffer = C.create_string_buffer(bytes(origem), len(origem))
            arquivo = lib.VSIFileFromMemBuffer(self._memoria.encode(),
                                               C.cast(self._buffer, C.c_void_p), len(origem), 0)
            if not arquivo:
                raise _erro("Nao consegui preparar a resposta do servico para leitura")
            lib.VSIFCloseL(arquivo)
            nome = self._memoria
        else:
            nome = str(origem)
        lista = curvas._lista(list(opcoes)) if opcoes else None
        self.ds = lib.GDALOpenEx(nome.encode("utf-8"), GDAL_OF_VECTOR, None, lista, None)
        if not self.ds:
            erro = _erro("Nao consegui ler " + ("a resposta do servico" if self._memoria else nome))
            self.fechar()
            raise erro

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()

    def fechar(self):
        lib = biblioteca()
        if self.ds:
            lib.GDALClose(self.ds)
            self.ds = None
        if self._memoria:
            lib.VSIUnlink(self._memoria.encode())
            self._memoria = None
        self._buffer = None


def _geometria_wkt(wkt: str, srs):
    lib = biblioteca()
    texto = C.c_char_p(wkt.encode("ascii"))
    geom = C.c_void_p()
    if lib.OGR_G_CreateFromWkt(C.byref(texto), srs, C.byref(geom)) != 0 or not geom.value:
        raise _erro("Geometria invalida")
    return geom.value


def _atributos(feicao) -> dict:
    lib = biblioteca()
    saida = {}
    for i in range(lib.OGR_F_GetFieldCount(feicao)):
        nome = lib.OGR_Fld_GetNameRef(lib.OGR_F_GetFieldDefnRef(feicao, i)).decode("utf-8", "replace")
        if lib.OGR_F_IsFieldSetAndNotNull(feicao, i):
            saida[nome] = (lib.OGR_F_GetFieldAsString(feicao, i) or b"").decode("utf-8", "replace")
    return saida


def sobreposicao(vetor: Vetor, alvo_wkt_utm: str, epsg: int, bbox_wgs=None, epsg_padrao=4674,
                 minimo_m2=100.0):
    """Area comum de cada feicao com o perimetro, em hectare e em percentual.

    `alvo_wkt_utm` e o perimetro ja em UTM. Feicao sem sistema declarado e
    tratada como SIRGAS 2000 geografico, que e como o CAR e o SIGEF distribuem.
    `bbox_wgs` (lon/lat) filtra no driver antes de ler: com o shapefile do
    estado inteiro, e o que separa segundos de minutos.

    `minimo_m2` descarta a lasca de divisa: dois imoveis vizinhos desenhados por
    levantamentos diferentes nunca coincidem no vertice, e a intersecao sai com
    poucos metros quadrados. No Sao Jorge, os tres vizinhos apareciam como
    "sobrepostos" com 0,00 % -- ruido que no relatorio parece conflito.
    """
    lib = biblioteca()
    utm = _srs(epsg)
    alvo = _geometria_wkt(alvo_wkt_utm, utm)
    if not lib.OGR_G_IsValid(alvo):
        valido = lib.OGR_G_MakeValid(alvo)
        if valido:
            lib.OGR_G_DestroyGeometry(alvo)
            alvo = valido
    area_alvo = lib.OGR_G_Area(alvo)
    saida = []
    try:
        for n in range(lib.GDALDatasetGetLayerCount(vetor.ds)):
            camada = lib.GDALDatasetGetLayer(vetor.ds, n)
            srs_camada = lib.OGR_L_GetSpatialRef(camada)
            proprio = None
            if not srs_camada:
                proprio = srs_camada = _srs(epsg_padrao)
            if bbox_wgs:
                l, b, r, t = bbox_wgs
                wgs = _srs(4326)
                filtro = _geometria_wkt(f"POLYGON(({l} {b},{r} {b},{r} {t},{l} {t},{l} {b}))", wgs)
                if lib.OGR_G_TransformTo(filtro, srs_camada) == 0:
                    lib.OGR_L_SetSpatialFilter(camada, filtro)    # o OGR guarda uma copia
                lib.OGR_G_DestroyGeometry(filtro)
                lib.OSRDestroySpatialReference(wgs)
            lib.OGR_L_ResetReading(camada)
            while True:
                feicao = lib.OGR_L_GetNextFeature(camada)
                if not feicao:
                    break
                try:
                    ref = lib.OGR_F_GetGeometryRef(feicao)
                    if not ref:
                        continue
                    geom = lib.OGR_G_Clone(ref)
                    if not lib.OGR_G_GetSpatialReference(geom):
                        lib.OGR_G_AssignSpatialReference(geom, srs_camada)
                    if lib.OGR_G_TransformTo(geom, utm) != 0:
                        lib.OGR_G_DestroyGeometry(geom)
                        continue
                    if not lib.OGR_G_IsValid(geom):
                        valido = lib.OGR_G_MakeValid(geom)
                        if valido:
                            lib.OGR_G_DestroyGeometry(geom)
                            geom = valido
                    comum = 0.0
                    inter = lib.OGR_G_Intersection(geom, alvo)
                    if inter:
                        comum = lib.OGR_G_Area(inter)
                        lib.OGR_G_DestroyGeometry(inter)
                    if comum >= minimo_m2:
                        area = lib.OGR_G_Area(geom)
                        saida.append(dict(
                            atributos=_atributos(feicao),
                            area_feicao_ha=area / 10000.0,
                            area_comum_ha=comum / 10000.0,
                            pct_do_perimetro=100.0 * comum / area_alvo if area_alvo else 0.0,
                            pct_da_feicao=100.0 * comum / area if area else 0.0,
                        ))
                    lib.OGR_G_DestroyGeometry(geom)
                finally:
                    lib.OGR_F_Destroy(feicao)
            if bbox_wgs:
                lib.OGR_L_SetSpatialFilter(camada, None)
            if proprio:
                lib.OSRDestroySpatialReference(proprio)
    finally:
        lib.OGR_G_DestroyGeometry(alvo)
        lib.OSRDestroySpatialReference(utm)
    saida.sort(key=lambda r: -r["area_comum_ha"])
    return saida
