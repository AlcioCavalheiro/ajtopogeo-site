"""Curvas de nivel a partir do modelo digital.

Fala direto com a biblioteca do GDAL que ja vem na pasta `ferramentas` --
a mesma `gdal311.dll` por tras do gdaldem.exe e do gdallocationinfo.exe.
Ela exporta `GDALContourGenerateEx`, entao a geracao de curva nao precisa de
nenhum executavel novo no instalador: so este arquivo.

Tres cuidados estao embutidos, porque sao o que separa curva de prancha de
curva de espaguete:

1. **Reamostragem.** Contornar pixel bruto de fotogrametria (3 a 5 cm) devolve
   linha serrilhada com milhares de vertices por hectare. Antes de contornar,
   o raster e reamostrado por media para um pixel de trabalho compativel com a
   equidistancia pedida.

2. **Suavizacao.** Media movel que ignora nodata, para o ruido residual do MDT
   nao virar dente de serra na curva.

3. **Comprimento minimo.** Poca de ruido vira circulo fechado de 2 m que nao
   representa relevo nenhum. Abaixo do limite, a curva e descartada.

E a curva sai do **DTM**. Sobre o DSM ela contorna copa de arvore e telhado.
"""

from __future__ import annotations

import ctypes as C
import os
from pathlib import Path

import numpy as np

from cota import carregar_config, preparar_ambiente

# --- constantes do GDAL/OGR -------------------------------------------------

GA_ReadOnly = 0
GF_Read, GF_Write = 0, 1
GDT_Float32 = 6
OFTInteger, OFTReal, OFTString = 0, 2, 4
WKB_LINESTRING_25D = -2147483646  # 0x80000002 lido como int com sinal
CE_None = 0

EXTENSOES = {
    ".dxf": "DXF",
    ".shp": "ESRI Shapefile",
    ".gpkg": "GPKG",
    ".geojson": "GeoJSON",
    ".json": "GeoJSON",
}

CAMADA_SIMPLES = "CN_SIMPLES"
CAMADA_MESTRA = "CN_MESTRA"

_lib = None


# --- carga da biblioteca ----------------------------------------------------


def _localizar(pasta: Path) -> Path:
    """Acha a biblioteca do GDAL sem fixar o numero da versao.

    O nome carrega a versao (`gdal311.dll`), entao procurar pelo nome exato
    quebraria no dia em que o pacote for atualizado.
    """
    for padrao in ("gdal*.dll", "libgdal.so*", "libgdal*.dylib"):
        achados = sorted(pasta.glob(padrao))
        if achados:
            return achados[0]
    raise FileNotFoundError(
        "Nao encontrei a biblioteca do GDAL em " + str(pasta) + ".\n"
        "Confira o caminho gdalBin em config.json."
    )


def abrir_biblioteca(pastas: dict | None = None):
    """Carrega a DLL do GDAL e declara os prototipos usados aqui.

    Declarar argtypes/restype nao e preciosismo: em 64 bits, ponteiro devolvido
    sem restype declarado e truncado para int de 32 bits e o programa quebra na
    primeira chamada seguinte, com erro que nao aponta para a causa.
    """
    global _lib
    if _lib is not None:
        return _lib

    pastas = pastas or carregar_config()
    preparar_ambiente(pastas)

    binario = Path(pastas["gdalBin"])
    caminho = _localizar(binario)

    # As DLLs dependentes (proj, geos, tiff...) estao na mesma pasta.
    if hasattr(os, "add_dll_directory") and binario.is_dir():
        try:
            os.add_dll_directory(str(binario))
        except OSError:
            pass

    lib = C.CDLL(str(caminho))
    p = C.c_void_p

    def d(nome, restype, *argtypes):
        fn = getattr(lib, nome)
        fn.restype = restype
        fn.argtypes = list(argtypes)

    d("GDALAllRegister", None)
    d("GDALOpen", p, C.c_char_p, C.c_int)
    d("GDALClose", None, p)
    d("GDALGetDriverByName", p, C.c_char_p)
    d("GDALCreate", p, p, C.c_char_p, C.c_int, C.c_int, C.c_int, C.c_int, C.POINTER(C.c_char_p))
    d("GDALGetRasterBand", p, p, C.c_int)
    d("GDALGetRasterXSize", C.c_int, p)
    d("GDALGetRasterYSize", C.c_int, p)
    d("GDALGetGeoTransform", C.c_int, p, C.POINTER(C.c_double))
    d("GDALSetGeoTransform", C.c_int, p, C.POINTER(C.c_double))
    d("GDALGetProjectionRef", C.c_char_p, p)
    d("GDALSetProjection", C.c_int, p, C.c_char_p)
    d("GDALGetRasterNoDataValue", C.c_double, p, C.POINTER(C.c_int))
    d("GDALComputeRasterMinMax", C.c_int, p, C.c_int, C.POINTER(C.c_double))
    d("GDALSetRasterNoDataValue", C.c_int, p, C.c_double)
    d("GDALRasterIO", C.c_int, p, C.c_int, C.c_int, C.c_int, C.c_int, C.c_int,
      p, C.c_int, C.c_int, C.c_int, C.c_int, C.c_int)
    d("GDALContourGenerateEx", C.c_int, p, p, C.POINTER(C.c_char_p), p, p)
    d("GDALDatasetCreateLayer", p, p, C.c_char_p, p, C.c_int, C.POINTER(C.c_char_p))
    d("GDALWarp", p, C.c_char_p, p, C.c_int, C.POINTER(C.c_void_p), p, C.POINTER(C.c_int))
    d("GDALWarpAppOptionsNew", p, C.POINTER(C.c_char_p), p)
    d("GDALWarpAppOptionsFree", None, p)
    d("OSRNewSpatialReference", p, C.c_char_p)
    d("OSRDestroySpatialReference", None, p)
    d("OSRSetAxisMappingStrategy", None, p, C.c_int)
    d("OSRIsGeographic", C.c_int, p)
    d("OGR_Fld_Create", p, C.c_char_p, C.c_int)
    d("OGR_Fld_Destroy", None, p)
    d("OGR_Fld_SetWidth", None, p, C.c_int)
    d("OGR_L_CreateField", C.c_int, p, p, C.c_int)
    d("OGR_L_GetLayerDefn", p, p)
    d("OGR_L_GetFeatureCount", C.c_longlong, p, C.c_int)
    d("OGR_L_ResetReading", None, p)
    d("OGR_L_GetNextFeature", p, p)
    d("OGR_L_CreateFeature", C.c_int, p, p)
    d("OGR_F_Create", p, p)
    d("OGR_F_Destroy", None, p)
    d("OGR_F_GetFieldAsDouble", C.c_double, p, C.c_int)
    d("OGR_F_GetGeometryRef", p, p)
    d("OGR_F_SetGeometry", C.c_int, p, p)
    d("OGR_F_SetFieldDouble", None, p, C.c_int, C.c_double)
    d("OGR_F_SetFieldInteger", None, p, C.c_int, C.c_int)
    d("OGR_F_SetFieldString", None, p, C.c_int, C.c_char_p)
    d("OGR_FD_GetFieldIndex", C.c_int, p, C.c_char_p)
    d("OGR_G_Length", C.c_double, p)
    d("CPLGetLastErrorMsg", C.c_char_p)
    d("CPLErrorReset", None)
    d("CPLSetConfigOption", None, C.c_char_p, C.c_char_p)

    lib.GDALAllRegister()
    for chave, variavel in (("gdalData", "GDAL_DATA"), ("projData", "PROJ_LIB")):
        valor = pastas.get(chave)
        if valor and Path(valor).is_dir():
            lib.CPLSetConfigOption(variavel.encode(), str(valor).encode())

    _lib = lib
    return lib


# Acima disso nao e relevo, e buraco entrando como terreno. Um voo de fazenda
# tem dezenas de metros de desnivel; 2000 niveis dariam 1 km de desnivel a cada
# metro de equidistancia.
LIMITE_NIVEIS = 2000

# Quanto do progresso cabe ao contorno propriamente dito. Medido num modelo de
# 1918x1818: o GDAL contorna em 1,3 s e a gravacao das 18 mil feicoes leva 36 s
# -- 97% do tempo. Reportar so o contorno deixaria a barra em 100% durante quase
# toda a espera, que e como uma janela parecer travada.
FATIA_CONTORNO = 0.05


def _conferir_desnivel(lib, banda, equidistancia, nodata_conhecido):
    """Barra o contorno quando o desnivel do modelo nao e relevo, e sim buraco.

    Sem esta conferencia o caso classico -- MDT do Pix4D ou do Terra sem o
    nodata gravado, com o buraco em -9999 ou -10000 -- nao devolve erro: devolve
    dez mil niveis, e o GDAL fica mais de dez minutos gerando curvas ate a cota
    -10000. Numa janela isso e um congelamento que se le como travamento.

    A conta e barata (min/max aproximado, por amostragem) e acontece antes de
    qualquer trabalho pesado.
    """
    faixa = (C.c_double * 2)()
    try:
        lib.CPLErrorReset()
        lib.GDALComputeRasterMinMax(banda, 1, faixa)
    except Exception:  # noqa: BLE001 - sem a estatistica, segue como antes
        return None
    menor, maior = faixa[0], faixa[1]
    if not (menor < maior):
        return None

    niveis = (maior - menor) / equidistancia
    if niveis <= LIMITE_NIVEIS:
        return (menor, maior)

    texto = ("O modelo vai de %.0f a %.0f m, ou seja %.0f m de desnivel, o que daria "
             "%.0f curvas de %g m." % (menor, maior, maior - menor, niveis, equidistancia))
    if nodata_conhecido is None and menor < -500:
        texto += ("\n\nIsso nao e relevo: o modelo nao declara valor de vazio, e o buraco "
                  "do raster entrou como terreno. Informe o vazio no campo 'Vazio do "
                  "modelo' -- em MDT do Pix4D e do DJI Terra costuma ser -9999 ou "
                  "-10000 -- e gere de novo.")
    else:
        texto += "\n\nAumente a equidistancia ou recorte o modelo na area de interesse."
    raise ValueError(texto)


def _erro(lib, mensagem: str) -> RuntimeError:
    detalhe = (lib.CPLGetLastErrorMsg() or b"").decode("utf-8", "replace").strip()
    lib.CPLErrorReset()
    return RuntimeError(mensagem + (": " + detalhe if detalhe else "."))


def _lista(itens) -> C.Array:
    """Monta o char** terminado em NULL que o GDAL espera."""
    arr = (C.c_char_p * (len(itens) + 1))()
    for i, texto in enumerate(itens):
        arr[i] = texto.encode("utf-8")
    arr[len(itens)] = None
    return arr


# --- leitura do raster ------------------------------------------------------


def _geo(lib, ds):
    gt = (C.c_double * 6)()
    if lib.GDALGetGeoTransform(ds, gt) != CE_None:
        raise _erro(lib, "O raster nao tem georreferencia")
    return list(gt)


def _em_graus(lib, ds, gt) -> bool:
    """Diz se o raster esta em grau de latitude/longitude, e nao em metro.

    Importa porque tudo aqui e metrico: equidistancia, pixel de trabalho,
    suavizacao e comprimento minimo. Num raster em grau, pedir pixel de 0,5
    reamostraria o voo inteiro para um punhado de pixels, e o erro que o GDAL
    devolve ("too many levels") nao aponta para a causa.

    A pergunta certa e ao sistema de coordenadas; a amplitude das coordenadas
    so entra quando o raster nao declara sistema nenhum.
    """
    wkt = lib.GDALGetProjectionRef(ds)
    if wkt:
        srs = lib.OSRNewSpatialReference(wkt)
        if srs:
            try:
                return bool(lib.OSRIsGeographic(srs))
            finally:
                lib.OSRDestroySpatialReference(srs)
    x, y = gt[0], gt[3]
    return abs(x) <= 180 and abs(y) <= 90 and abs(gt[1]) < 0.01


def _nodata(lib, banda):
    tem = C.c_int(0)
    valor = lib.GDALGetRasterNoDataValue(banda, C.byref(tem))
    return valor if tem.value else None


def _ler(lib, ds, banda, nx, ny) -> np.ndarray:
    a = np.empty((ny, nx), dtype=np.float32)
    ok = lib.GDALRasterIO(banda, GF_Read, 0, 0, nx, ny,
                          a.ctypes.data_as(C.c_void_p), nx, ny, GDT_Float32, 0, 0)
    if ok != CE_None:
        raise _erro(lib, "Nao consegui ler o raster")
    return a


# --- reamostragem e suavizacao ---------------------------------------------


def _reamostrar(lib, ds, pixel_origem, pixel_alvo, nodata):
    """Reduz o raster para o pixel de trabalho, por media.

    Media, e nao vizinho mais proximo: a media e o que de fato remove o ruido
    de alta frequencia em vez de apenas jogar pixels fora.
    """
    argumentos = ["-of", "MEM", "-r", "average",
                  "-tr", repr(pixel_alvo), repr(pixel_alvo)]
    if nodata is not None:
        argumentos += ["-srcnodata", repr(nodata), "-dstnodata", repr(nodata)]

    opcoes = lib.GDALWarpAppOptionsNew(_lista(argumentos), None)
    if not opcoes:
        raise _erro(lib, "Nao consegui montar a reamostragem")
    try:
        fontes = (C.c_void_p * 1)(ds)
        saida = lib.GDALWarp(b"", None, 1, fontes, opcoes, None)
    finally:
        lib.GDALWarpAppOptionsFree(opcoes)
    if not saida:
        raise _erro(lib, "Nao consegui reamostrar o modelo")
    return saida


def _media_movel(a: np.ndarray, valido: np.ndarray, raio: int):
    """Media movel quadrada que ignora buraco, por soma acumulada.

    Divide pela contagem de pixels validos de cada janela, e nao pelo tamanho
    da janela: sem isso, a borda de um vazio puxaria a cota para baixo e a
    curva se deformaria justamente onde o modelo ja e fraco.
    """
    def somar(m):
        s = np.cumsum(np.cumsum(np.pad(m, ((1, 0), (1, 0))), axis=0), axis=1)
        ny, nx = m.shape
        i = np.clip(np.arange(ny)[:, None] + np.array([-raio, raio + 1])[None, :], 0, ny)
        j = np.clip(np.arange(nx)[:, None] + np.array([-raio, raio + 1])[None, :], 0, nx)
        i0, i1 = i[:, 0][:, None], i[:, 1][:, None]
        j0, j1 = j[:, 0][None, :], j[:, 1][None, :]
        return s[i1, j1] - s[i0, j1] - s[i1, j0] + s[i0, j0]

    soma = somar(np.where(valido, a, 0.0).astype(np.float64))
    conta = somar(valido.astype(np.float64))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(conta > 0, soma / np.maximum(conta, 1), np.nan), conta > 0


def _suavizar(lib, ds, raio_px: int, nodata):
    """Devolve um raster em memoria com o modelo suavizado."""
    nx, ny = lib.GDALGetRasterXSize(ds), lib.GDALGetRasterYSize(ds)
    # A suavizacao trabalha com o raster inteiro na memoria. Depois da
    # reamostragem isso e barato; no pixel nativo de um voo grande, nao e.
    if nx * ny > 400_000_000 // 4:
        raise MemoryError(
            "O modelo tem " + str(nx) + "x" + str(ny) + " pixels -- grande demais para "
            "suavizar inteiro na memoria. Aumente o pixel de trabalho ou desligue a "
            "suavizacao."
        )
    banda = lib.GDALGetRasterBand(ds, 1)
    a = _ler(lib, ds, banda, nx, ny)

    valido = np.isfinite(a)
    if nodata is not None:
        valido &= ~np.isclose(a, nodata)

    suave, ok = _media_movel(a, valido, raio_px)
    vazio = -9999.0 if nodata is None else nodata
    saida_arr = np.where(ok, suave, vazio).astype(np.float32)

    mem = lib.GDALGetDriverByName(b"MEM")
    novo = lib.GDALCreate(mem, b"", nx, ny, 1, GDT_Float32, None)
    if not novo:
        raise _erro(lib, "Nao consegui criar o raster suavizado")
    gt = (C.c_double * 6)(*_geo(lib, ds))
    lib.GDALSetGeoTransform(novo, gt)
    lib.GDALSetProjection(novo, lib.GDALGetProjectionRef(ds))
    nova_banda = lib.GDALGetRasterBand(novo, 1)
    lib.GDALSetRasterNoDataValue(nova_banda, vazio)
    saida_arr = np.ascontiguousarray(saida_arr)
    if lib.GDALRasterIO(nova_banda, GF_Write, 0, 0, nx, ny,
                        saida_arr.ctypes.data_as(C.c_void_p), nx, ny,
                        GDT_Float32, 0, 0) != CE_None:
        raise _erro(lib, "Nao consegui gravar o raster suavizado")
    return novo, vazio


# --- geracao ----------------------------------------------------------------


def _camada_memoria(lib, wkt):
    # "MEM" primeiro: o driver vetorial "Memory" esta depreciado desde a 3.11 e
    # imprime aviso a cada chamada -- num programa sem console isso nao aparece
    # para ninguem, mas some quando a DLL for atualizada e o nome sair
    driver = lib.GDALGetDriverByName(b"MEM") or lib.GDALGetDriverByName(b"Memory")
    ds = lib.GDALCreate(driver, b"curvas", 0, 0, 0, 0, None)
    if not ds:
        raise _erro(lib, "Nao consegui abrir a camada de trabalho")

    srs = None
    if wkt:
        srs = lib.OSRNewSpatialReference(wkt)
        if srs:
            lib.OSRSetAxisMappingStrategy(srs, 0)  # ordem tradicional E,N

    camada = lib.GDALDatasetCreateLayer(ds, b"curvas", srs, WKB_LINESTRING_25D, None)
    if srs:
        lib.OSRDestroySpatialReference(srs)
    if not camada:
        raise _erro(lib, "Nao consegui criar a camada de trabalho")

    campo = lib.OGR_Fld_Create(b"ELEV", OFTReal)
    lib.OGR_L_CreateField(camada, campo, 1)
    lib.OGR_Fld_Destroy(campo)
    return ds, camada


def _camada_saida(lib, caminho: Path, wkt):
    formato = EXTENSOES.get(caminho.suffix.lower())
    if formato is None:
        raise ValueError(
            "Nao sei gravar " + caminho.suffix + ". Use .dxf, .shp, .gpkg ou .geojson."
        )
    driver = lib.GDALGetDriverByName(formato.encode())
    if not driver:
        raise RuntimeError("O GDAL deste pacote nao tem o driver " + formato + ".")

    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()

    ds = lib.GDALCreate(driver, str(caminho).encode("utf-8"), 0, 0, 0, 0, None)
    if not ds:
        raise _erro(lib, "Nao consegui criar " + str(caminho))

    srs = lib.OSRNewSpatialReference(wkt) if wkt else None
    if srs:
        lib.OSRSetAxisMappingStrategy(srs, 0)
    camada = lib.GDALDatasetCreateLayer(ds, b"curvas", srs, WKB_LINESTRING_25D, None)
    if srs:
        lib.OSRDestroySpatialReference(srs)
    if not camada:
        raise _erro(lib, "Nao consegui criar a camada de saida")

    # "Layer" e o campo que o driver DXF le para decidir o layer do CAD. O DXF
    # tem esquema fixo e recusa o resto -- nem adianta tentar criar.
    campos = [(b"Layer", OFTString)]
    if formato != "DXF":
        campos += [(b"ELEV", OFTReal), (b"MESTRA", OFTInteger)]
    for nome, tipo in campos:
        campo = lib.OGR_Fld_Create(nome, tipo)
        if tipo == OFTString:
            lib.OGR_Fld_SetWidth(campo, 32)
        lib.OGR_L_CreateField(camada, campo, 1)
        lib.OGR_Fld_Destroy(campo)
    return ds, camada, formato


def gerar_curvas(raster, saida, equidistancia=1.0, mestra_a_cada=5,
                 pixel=None, suavizacao=None, comprimento_minimo=None,
                 base=0.0, nodata=None, progresso=None) -> dict:
    """Gera as curvas de nivel do modelo e grava em DXF, SHP, GPKG ou GeoJSON.

    raster             modelo digital de terreno (.tif)
    saida              arquivo de saida; a extensao escolhe o formato
    equidistancia      intervalo entre curvas, em metros
    mestra_a_cada      a cada quantas curvas entra uma mestra (0 desliga)
    pixel              pixel de trabalho em metros; None escolhe sozinho,
                       0 contorna o pixel original do raster
    suavizacao         raio da media movel em metros; None usa um pixel de
                       trabalho, 0 desliga
    comprimento_minimo curvas menores que isso sao descartadas; None usa
                       oito pixels de trabalho, 0 mantem tudo
    base               cota de referencia; as curvas saem em base + n*equidistancia
    nodata             valor de vazio, quando o raster nao declara o proprio
    progresso          funcao opcional recebendo fracao de 0 a 1

    Devolve um resumo com contagem, faixa de cota e o que foi usado de fato.
    As curvas saem em 3D: a cota vai na propria geometria, entao o Civil 3D
    consome o DXF direto como dado de superficie.
    """
    raster, saida = Path(raster), Path(saida)
    if not raster.exists():
        raise FileNotFoundError("Nao encontrei o modelo: " + str(raster))
    if equidistancia <= 0:
        raise ValueError("A equidistancia precisa ser maior que zero.")

    lib = abrir_biblioteca()
    ds = lib.GDALOpen(str(raster).encode("utf-8"), GA_ReadOnly)
    if not ds:
        raise _erro(lib, "O GDAL nao conseguiu abrir " + str(raster))

    abertos = [ds]
    try:
        gt = _geo(lib, ds)
        if _em_graus(lib, ds, gt):
            raise ValueError(
                "Este modelo esta em graus de latitude/longitude, e a curva de nivel "
                "precisa de um modelo em metros -- equidistancia, suavizacao e "
                "comprimento minimo nao significam nada em grau, e o DXF sairia em "
                "grau, inservivel no Civil 3D.\n\n"
                "Reprojete o modelo para UTM (SIRGAS 2000 / UTM 21S, EPSG:31981, na "
                "regiao da empresa) e gere de novo. O MDT que sai do Agisoft costuma "
                "vir assim; o do Pix4D ja vem em UTM."
            )
        pixel_origem = abs(gt[1])
        declarado = _nodata(lib, lib.GDALGetRasterBand(ds, 1))
        nodata_pedido = nodata
        nodata = float(nodata) if nodata is not None else declarado

        # Pixel de trabalho: metade da equidistancia da uma curva com vertice a
        # cada poucos metros, que e o que se consegue desenhar. Nunca aumenta a
        # resolucao do original -- reamostrar para mais fino nao inventa terreno.
        if pixel is None:
            pixel = max(pixel_origem, equidistancia / 2.0)
        pixel = float(pixel or pixel_origem)
        pixel = max(pixel, pixel_origem)

        trabalho = ds
        if pixel > pixel_origem * 1.01:
            trabalho = _reamostrar(lib, ds, pixel_origem, pixel, nodata)
            abertos.append(trabalho)
            nodata = _nodata(lib, lib.GDALGetRasterBand(trabalho, 1)) or nodata

        if suavizacao is None:
            suavizacao = pixel
        raio_px = int(round(float(suavizacao) / pixel)) if suavizacao else 0
        if raio_px >= 1:
            trabalho, nodata = _suavizar(lib, trabalho, raio_px, nodata)
            abertos.append(trabalho)

        wkt = lib.GDALGetProjectionRef(trabalho)
        banda = lib.GDALGetRasterBand(trabalho, 1)
        _conferir_desnivel(lib, banda, equidistancia,
                           declarado if nodata_pedido is None else nodata_pedido)

        mem_ds, mem_camada = _camada_memoria(lib, wkt)
        abertos.append(mem_ds)

        opcoes = ["LEVEL_INTERVAL=" + repr(float(equidistancia)),
                  "LEVEL_BASE=" + repr(float(base)),
                  "ELEV_FIELD=0",
                  "POLYGONIZE=NO"]
        if nodata is not None:
            opcoes.append("NODATA=" + repr(float(nodata)))

        retorno = None
        if progresso is not None:
            tipo = C.CFUNCTYPE(C.c_int, C.c_double, C.c_char_p, C.c_void_p)

            def ponte(fracao, mensagem, dados):
                progresso(float(fracao) * FATIA_CONTORNO)
                return 1

            retorno = tipo(ponte)  # guardado em variavel: sem isso o GC leva

        if lib.GDALContourGenerateEx(banda, mem_camada, _lista(opcoes),
                                     C.cast(retorno, C.c_void_p) if retorno else None,
                                     None) != CE_None:
            raise _erro(lib, "O GDAL nao conseguiu gerar as curvas")

        if comprimento_minimo is None:
            comprimento_minimo = 8 * pixel

        saida_ds, saida_camada, formato = _camada_saida(lib, saida, wkt)
        abertos.append(saida_ds)
        defn = lib.OGR_L_GetLayerDefn(saida_camada)
        i_layer = lib.OGR_FD_GetFieldIndex(defn, b"Layer")
        i_elev = lib.OGR_FD_GetFieldIndex(defn, b"ELEV")
        i_mestra = lib.OGR_FD_GetFieldIndex(defn, b"MESTRA")

        passo_mestra = equidistancia * mestra_a_cada if mestra_a_cada else 0
        contagem = mestras = descartadas = 0
        cota_min = cota_max = None

        total = lib.OGR_L_GetFeatureCount(mem_camada, 1) or 0
        lidas = 0

        lib.OGR_L_ResetReading(mem_camada)
        while True:
            feicao = lib.OGR_L_GetNextFeature(mem_camada)
            if not feicao:
                break
            lidas += 1
            if progresso is not None and total and lidas % 200 == 0:
                progresso(FATIA_CONTORNO + (1 - FATIA_CONTORNO) * lidas / total)
            try:
                geometria = lib.OGR_F_GetGeometryRef(feicao)
                if not geometria:
                    continue
                if comprimento_minimo and lib.OGR_G_Length(geometria) < comprimento_minimo:
                    descartadas += 1
                    continue

                elev = lib.OGR_F_GetFieldAsDouble(feicao, 0)
                e_mestra = False
                if passo_mestra:
                    resto = abs(elev / passo_mestra - round(elev / passo_mestra))
                    e_mestra = resto < 1e-6

                nova = lib.OGR_F_Create(defn)
                try:
                    lib.OGR_F_SetGeometry(nova, geometria)
                    # O DXF tem esquema fixo (Layer, LineType, ...) e recusa campo
                    # novo: la a cota viaja no Z da geometria, e o indice vem -1.
                    if i_layer >= 0:
                        lib.OGR_F_SetFieldString(
                            nova, i_layer,
                            (CAMADA_MESTRA if e_mestra else CAMADA_SIMPLES).encode())
                    if i_elev >= 0:
                        lib.OGR_F_SetFieldDouble(nova, i_elev, elev)
                    if i_mestra >= 0:
                        lib.OGR_F_SetFieldInteger(nova, i_mestra, 1 if e_mestra else 0)
                    if lib.OGR_L_CreateFeature(saida_camada, nova) != CE_None:
                        raise _erro(lib, "Nao consegui gravar uma curva")
                finally:
                    lib.OGR_F_Destroy(nova)

                contagem += 1
                mestras += 1 if e_mestra else 0
                cota_min = elev if cota_min is None else min(cota_min, elev)
                cota_max = elev if cota_max is None else max(cota_max, elev)
            finally:
                lib.OGR_F_Destroy(feicao)

        # O laco reporta de 200 em 200 feicoes, entao a ultima leva quase nunca
        # cai num multiplo e o progresso pararia em 0,99. Quem estiver ouvindo
        # precisa do 1,0 para saber que agora vem a gravacao em disco, que nao
        # tem como ser reportada.
        if progresso is not None:
            progresso(1.0)

        # Vazio nao declarado e a armadilha classica: o -9999 do buraco entra
        # como terreno e a rotina devolve milhares de curvas ate a cota -6000.
        aviso = None
        if declarado is None and nodata_pedido is None and cota_min is not None and (
                cota_min < -500 or (cota_max - cota_min) > 3000):
            aviso = ("O modelo nao declara valor de vazio e as cotas vao de "
                     + ("%.0f" % cota_min) + " a " + ("%.0f" % cota_max) + " m. "
                     "Provavelmente o buraco do raster entrou como terreno -- "
                     "informe o nodata (-9999 costuma ser) e gere de novo.")

        return {
            "arquivo": str(saida),
            "aviso": aviso,
            "nodata": nodata,
            "formato": formato,
            "curvas": contagem,
            "mestras": mestras,
            "descartadas": descartadas,
            "equidistancia": equidistancia,
            "cota_min": cota_min,
            "cota_max": cota_max,
            "pixel_origem": pixel_origem,
            "pixel": pixel,
            "suavizacao": raio_px * pixel,
            "comprimento_minimo": comprimento_minimo,
        }
    finally:
        for aberto in reversed(abertos):
            lib.GDALClose(aberto)  # fechar e o que descarrega o arquivo em disco


def resumo(res: dict) -> str:
    """Uma linha para a barra de situacao da janela."""
    if not res["curvas"]:
        return "Nenhuma curva gerada -- confira a equidistancia e o desnivel da area."
    texto = (str(res["curvas"]) + " curvas de " + ("%g" % res["equidistancia"]) + " m"
             + " (" + str(res["mestras"]) + " mestras)"
             + "   |   cota " + ("%.2f" % res["cota_min"]) + " a "
             + ("%.2f" % res["cota_max"]) + " m"
             + "   |   pixel de trabalho " + ("%.2f" % res["pixel"]) + " m")
    if res["descartadas"]:
        texto += "   |   " + str(res["descartadas"]) + " trechos curtos descartados"
    if res.get("aviso"):
        texto += "\nATENCAO: " + res["aviso"]
    return texto


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Curvas de nivel a partir do MDT.")
    ap.add_argument("raster")
    ap.add_argument("saida")
    ap.add_argument("--equidistancia", type=float, default=1.0)
    ap.add_argument("--mestra", type=int, default=5)
    ap.add_argument("--pixel", type=float, default=None)
    ap.add_argument("--suavizacao", type=float, default=None)
    ap.add_argument("--minimo", type=float, default=None)
    ap.add_argument("--nodata", type=float, default=None)
    a = ap.parse_args()

    print(resumo(gerar_curvas(a.raster, a.saida,
                              equidistancia=a.equidistancia,
                              mestra_a_cada=a.mestra,
                              pixel=a.pixel,
                              suavizacao=a.suavizacao,
                              comprimento_minimo=a.minimo,
                              nodata=a.nodata,
                              progresso=lambda f: None)))
