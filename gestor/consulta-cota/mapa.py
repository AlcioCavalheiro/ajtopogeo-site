"""Mapa de declividade em PDF, com as curvas de nivel por cima.

O PDF e escrito a mao. Nao e teimosia: a regra do pacote e nao acrescentar
dependencia, e uma biblioteca de PDF custaria megabytes para desenhar um raster,
umas linhas e uma legenda. A parte do formato usada aqui -- imagem em
FlateDecode, caminhos vetoriais e texto em Helvetica -- cabe em poucas dezenas de
linhas com o `zlib` que ja vem no Python.

O raster entra como imagem colorida por classe; as curvas entram por cima como
vetor, entao continuam nitidas em qualquer ampliacao.
"""

from __future__ import annotations

import ctypes as C
import datetime
import zlib
from pathlib import Path

import numpy as np

import curvas

# Cores das classes de capacidade de uso, na ordem de cota.FAIXAS_DECLIVE:
# verde no que se mecaniza, vermelho no que nao se terraceia.
CORES = [
    (0.63, 0.83, 0.51),   # plano
    (0.85, 0.92, 0.55),   # suave ondulado
    (0.99, 0.91, 0.53),   # ondulado
    (0.97, 0.73, 0.42),   # forte ondulado
    (0.90, 0.50, 0.36),   # montanhoso
    (0.76, 0.29, 0.29),   # escarpado
]
CINZA_VAZIO = (0.94, 0.94, 0.94)

A3_PAISAGEM = (1190.55, 841.89)   # pontos PostScript
MARGEM = 34.0
LARGURA_LEGENDA = 250.0


# --------------------------------------------------------------- PDF cru


class PDF:
    """O minimo de PDF para um mapa: imagem, caminhos e texto."""

    def __init__(self, largura, altura):
        self.largura, self.altura = largura, altura
        self.objetos = [None]          # o indice 0 nao existe em PDF
        self.conteudo = []

    def novo(self, corpo: bytes) -> int:
        self.objetos.append(corpo)
        return len(self.objetos) - 1

    def fluxo(self, dados: bytes, extra: str = "") -> int:
        comprimido = zlib.compress(dados, 6)
        cabecalho = (f"<< /Length {len(comprimido)} /Filter /FlateDecode {extra} >>"
                     ).encode("latin-1")
        return self.novo(cabecalho + b"\nstream\n" + comprimido + b"\nendstream")

    # --- desenho -------------------------------------------------------

    def escreve(self, texto):
        self.conteudo.append(texto)

    def cor(self, rgb, traco=False):
        op = "RG" if traco else "rg"
        self.escreve(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} {op}")

    def retangulo(self, x, y, w, h, preenche=None, traco=None, espessura=0.6):
        if preenche:
            self.cor(preenche)
        if traco:
            self.cor(traco, True)
            self.escreve(f"{espessura} w")
        self.escreve(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re "
                     + ("B" if preenche and traco else "f" if preenche else "S"))

    def texto(self, x, y, s, tamanho=9, negrito=False, rgb=(0, 0, 0)):
        self.cor(rgb)
        fonte = "/F2" if negrito else "/F1"
        seguro = (s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))
        self.escreve(f"BT {fonte} {tamanho} Tf {x:.2f} {y:.2f} Td ({seguro}) Tj ET")

    def linhas(self, polilinhas, rgb, espessura):
        """Desenha varias polilinhas ja em coordenadas de pagina."""
        self.cor(rgb, True)
        self.escreve(f"{espessura} w 1 J 1 j")
        for pontos in polilinhas:
            if len(pontos) < 2:
                continue
            self.escreve(f"{pontos[0][0]:.2f} {pontos[0][1]:.2f} m")
            for x, y in pontos[1:]:
                self.escreve(f"{x:.2f} {y:.2f} l")
            self.escreve("S")

    def imagem(self, nome, x, y, w, h):
        self.escreve(f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /{nome} Do Q")

    def recortar(self, x, y, w, h):
        self.escreve(f"q {x:.2f} {y:.2f} {w:.2f} {h:.2f} re W n")

    def solta(self):
        self.escreve("Q")

    # --- fechamento ----------------------------------------------------

    def gravar(self, caminho, imagens: dict):
        fontes = {
            "F1": self.novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
            "F2": self.novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"),
        }
        conteudo = self.fluxo("\n".join(self.conteudo).encode("latin-1"))
        recursos = ("<< /Font << " + " ".join(f"/{k} {v} 0 R" for k, v in fontes.items())
                    + " >> /XObject << "
                    + " ".join(f"/{k} {v} 0 R" for k, v in imagens.items()) + " >> >>")
        pagina = self.novo(b"")        # reservado: precisa do numero do pai
        pais = self.novo(b"")
        self.objetos[pagina] = (
            f"<< /Type /Page /Parent {pais} 0 R /MediaBox [0 0 {self.largura:.2f} "
            f"{self.altura:.2f}] /Resources {recursos} /Contents {conteudo} 0 R >>"
        ).encode("latin-1")
        self.objetos[pais] = (
            f"<< /Type /Pages /Kids [{pagina} 0 R] /Count 1 >>").encode("latin-1")
        raiz = self.novo(f"<< /Type /Catalog /Pages {pais} 0 R >>".encode("latin-1"))

        saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posicoes = [0]
        for i, corpo in enumerate(self.objetos[1:], 1):
            posicoes.append(len(saida))
            saida += f"{i} 0 obj\n".encode("latin-1") + corpo + b"\nendobj\n"
        inicio_tabela = len(saida)
        saida += f"xref\n0 {len(self.objetos)}\n".encode("latin-1")
        saida += b"0000000000 65535 f \n"
        for pos in posicoes[1:]:
            saida += f"{pos:010d} 00000 n \n".encode("latin-1")
        saida += (f"trailer\n<< /Size {len(self.objetos)} /Root {raiz} 0 R >>\n"
                  f"startxref\n{inicio_tabela}\n%%EOF\n").encode("latin-1")
        Path(caminho).write_bytes(bytes(saida))


# --------------------------------------------------------------- dados


def _ler_raster(lib, caminho, largura_alvo=1600):
    """Le o raster reamostrado para o tamanho de impressao.

    Reamostrar antes de desenhar e o que impede um raster de 30 mil colunas de
    virar uma imagem de 2 GB dentro do PDF. Para a classe de declividade, media
    e melhor que vizinho: nao cria degrau onde o terreno nao tem.
    """
    ds = lib.GDALOpen(str(caminho).encode("utf-8"), 0)
    if not ds:
        raise RuntimeError("Nao consegui abrir " + str(caminho))
    try:
        nx, ny = lib.GDALGetRasterXSize(ds), lib.GDALGetRasterYSize(ds)
        gt = curvas._geo(lib, ds)
        nodata = curvas._nodata(lib, lib.GDALGetRasterBand(ds, 1))
        if nx > largura_alvo:
            fator = largura_alvo / nx
            alvo = lib.GDALWarpAppOptionsNew(
                curvas._lista(["-of", "MEM", "-r", "average", "-ts",
                               str(int(nx * fator)), str(max(1, int(ny * fator)))]), None)
            try:
                fontes = (C.c_void_p * 1)(ds)
                menor = lib.GDALWarp(b"", None, 1, fontes, alvo, None)
            finally:
                lib.GDALWarpAppOptionsFree(alvo)
            if menor:
                lib.GDALClose(ds)
                ds = menor
                nx, ny = lib.GDALGetRasterXSize(ds), lib.GDALGetRasterYSize(ds)
                gt = curvas._geo(lib, ds)
        a = curvas._ler(lib, ds, lib.GDALGetRasterBand(ds, 1), nx, ny)
        return a.copy(), gt, nodata
    finally:
        lib.GDALClose(ds)


_ogr_declarado = False


def _declarar_ogr(lib):
    """Funcoes de leitura vetorial que o curvas.py nao precisou declarar.

    Mesma regra de la: restype e argtypes sempre, nos dois. Ponteiro devolvido
    sem restype vira int de 32 bits em 64 bits e quebra na chamada seguinte.
    """
    global _ogr_declarado
    if _ogr_declarado:
        return
    p = C.c_void_p
    for nome, restype, *argtypes in (
            ("GDALOpenEx", p, C.c_char_p, C.c_uint, C.POINTER(C.c_char_p),
             C.POINTER(C.c_char_p), C.POINTER(C.c_char_p)),
            ("GDALDatasetGetLayer", p, p, C.c_int),
            ("OGR_G_GetX", C.c_double, p, C.c_int),
            ("OGR_G_GetY", C.c_double, p, C.c_int),
            ("OGR_G_GetGeometryCount", C.c_int, p),
            ("OGR_G_GetGeometryRef", p, p, C.c_int)):
        fn = getattr(lib, nome)
        fn.restype = restype
        fn.argtypes = list(argtypes)
    _ogr_declarado = True


def _ler_linhas(lib, caminho):
    """Le as curvas geradas, de qualquer um dos formatos que o programa grava."""
    _declarar_ogr(lib)

    ds = lib.GDALOpenEx(str(caminho).encode("utf-8"), 4, None, None, None)  # 4 = vetor
    if not ds:
        raise RuntimeError("Nao consegui abrir as curvas em " + str(caminho))
    saida = []
    try:
        camada = lib.GDALDatasetGetLayer(ds, 0)
        if not camada:
            return saida
        lib.OGR_L_ResetReading(camada)
        while True:
            feicao = lib.OGR_L_GetNextFeature(camada)
            if not feicao:
                break
            try:
                g = lib.OGR_F_GetGeometryRef(feicao)
                if not g:
                    continue
                partes = [g]
                if lib.OGR_G_GetPointCount(g) == 0:
                    partes = [lib.OGR_G_GetGeometryRef(g, i)
                              for i in range(lib.OGR_G_GetGeometryCount(g))]
                for parte in partes:
                    if not parte:
                        continue
                    n = lib.OGR_G_GetPointCount(parte)
                    if n >= 2:
                        saida.append([(lib.OGR_G_GetX(parte, i), lib.OGR_G_GetY(parte, i))
                                      for i in range(n)])
            finally:
                lib.OGR_F_Destroy(feicao)
    finally:
        lib.GDALClose(ds)
    return saida


def _colorir(a, nodata, faixas):
    """Pinta cada pixel pela classe de declividade a que pertence."""
    ny, nx = a.shape
    rgb = np.empty((ny, nx, 3), dtype=np.uint8)
    for c in range(3):
        rgb[:, :, c] = int(CINZA_VAZIO[c] * 255)
    valido = np.isfinite(a)
    if nodata is not None:
        valido &= ~np.isclose(a, nodata)
    # gdaldem devolve declividade negativa em nenhum caso; valor absurdo e vazio
    valido &= (a >= 0) & (a <= 1000)
    for faixa, cor in zip(faixas, CORES):
        fim = faixa["fim"] if faixa["fim"] is not None else 1e9
        dentro = valido & (a >= faixa["inicio"]) & (a < fim)
        for c in range(3):
            rgb[:, :, c] = np.where(dentro, int(cor[c] * 255), rgb[:, :, c])
    return rgb


def _escala_redonda(metros_por_ponto, largura_pontos):
    """Escolhe um comprimento redondo para a barra de escala."""
    alvo = largura_pontos * 0.22 * metros_por_ponto
    for passo in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000):
        if passo >= alvo:
            return passo
    return 10000


# --------------------------------------------------------------- mapa


def gerar_mapa(declividade, saida, faixas, curvas_arquivo=None, titulo="",
               sistema="", modelo="", progresso=None) -> dict:
    """Monta o mapa de declividade em PDF.

    declividade     raster de declividade em porcentagem (o que a aba gera)
    saida           .pdf de destino
    faixas          o que `cota.areas_por_faixa` devolveu, com hectares e %
    curvas_arquivo  curvas de nivel a desenhar por cima (opcional)
    titulo          nome do trabalho, no cabecalho
    sistema         sistema de coordenadas, para a nota de rodape
    modelo          nome do modelo digital de origem
    """
    def aviso(f):
        if progresso:
            progresso(f)

    lib = curvas.abrir_biblioteca()
    aviso(0.05)
    a, gt, nodata = _ler_raster(lib, declividade)
    aviso(0.45)
    rgb = _colorir(a, nodata, faixas)
    ny, nx = a.shape

    linhas = []
    if curvas_arquivo and Path(curvas_arquivo).exists():
        linhas = _ler_linhas(lib, curvas_arquivo)
    aviso(0.65)

    largura, altura = A3_PAISAGEM
    pdf = PDF(largura, altura)

    # moldura do mapa
    x0 = MARGEM
    y0 = MARGEM + 28
    mapa_w = largura - 2 * MARGEM - LARGURA_LEGENDA - 12
    mapa_h = altura - y0 - MARGEM - 40

    # o raster mantem a proporcao dentro da moldura
    escala = min(mapa_w / nx, mapa_h / ny)
    img_w, img_h = nx * escala, ny * escala
    img_x = x0 + (mapa_w - img_w) / 2
    img_y = y0 + (mapa_h - img_h) / 2

    pdf.retangulo(x0, y0, mapa_w, mapa_h, preenche=(1, 1, 1))
    pdf.recortar(x0, y0, mapa_w, mapa_h)
    pdf.imagem("Im0", img_x, img_y, img_w, img_h)

    if linhas:
        # metros do terreno -> pontos da pagina
        mpp = abs(gt[1]) * nx / img_w
        def para_pagina(p):
            return (img_x + (p[0] - gt[0]) / abs(gt[1]) * (img_w / nx),
                    img_y + img_h - (gt[3] - p[1]) / abs(gt[5]) * (img_h / ny))
        pdf.linhas([[para_pagina(p) for p in linha] for linha in linhas],
                   (0.25, 0.25, 0.25), 0.25)
    else:
        mpp = abs(gt[1]) * nx / img_w
    pdf.solta()
    pdf.retangulo(x0, y0, mapa_w, mapa_h, traco=(0.35, 0.35, 0.35), espessura=0.8)
    aviso(0.8)

    # ---- cabecalho ----
    pdf.texto(x0, altura - MARGEM - 12, "MAPA DE DECLIVIDADE", 17, negrito=True)
    if titulo:
        pdf.texto(x0, altura - MARGEM - 30, titulo, 11, rgb=(0.25, 0.25, 0.25))

    # ---- legenda ----
    lx = largura - MARGEM - LARGURA_LEGENDA
    ly = altura - MARGEM - 62
    pdf.retangulo(lx, y0, LARGURA_LEGENDA, ly - y0 + 40, preenche=(0.985, 0.985, 0.985),
                  traco=(0.7, 0.7, 0.7))
    cy = ly + 20
    pdf.texto(lx + 12, cy, "Classes de declividade", 11, negrito=True)
    cy -= 22
    pdf.texto(lx + 12, cy, "Declividade", 8, rgb=(0.4, 0.4, 0.4))
    pdf.texto(lx + 118, cy, "Hectares", 8, rgb=(0.4, 0.4, 0.4))
    pdf.texto(lx + 190, cy, "% area", 8, rgb=(0.4, 0.4, 0.4))
    cy -= 6

    total = sum(f["hectares"] for f in faixas) or 1
    for faixa, cor in zip(faixas, CORES):
        cy -= 22
        pdf.retangulo(lx + 12, cy - 2, 16, 13, preenche=cor, traco=(0.4, 0.4, 0.4), espessura=0.4)
        rot = (f"{faixa['inicio']} a {faixa['fim']} %" if faixa["fim"]
               else f"acima de {faixa['inicio']} %")
        pdf.texto(lx + 34, cy + 1, rot, 9)
        pdf.texto(lx + 118, cy + 1, f"{faixa['hectares']:,.2f}".replace(",", "."), 9)
        pdf.texto(lx + 190, cy + 1, f"{faixa['porcento']:.1f}", 9)
        cy -= 11
        pdf.texto(lx + 34, cy + 1, faixa["nome"], 8, rgb=(0.45, 0.45, 0.45))

    cy -= 26
    pdf.retangulo(lx + 12, cy + 12, LARGURA_LEGENDA - 24, 0.7, preenche=(0.7, 0.7, 0.7))
    pdf.texto(lx + 12, cy, "Area total", 9, negrito=True)
    pdf.texto(lx + 118, cy, f"{total:,.2f}".replace(",", "."), 9, negrito=True)
    pdf.texto(lx + 190, cy, "100,0", 9, negrito=True)

    terraceavel = sum(f["hectares"] for f in faixas if f["inicio"] < 13)
    cy -= 18
    pdf.texto(lx + 12, cy, f"Ate 13% (terraceavel): {terraceavel:,.2f} ha "
                           f"({100 * terraceavel / total:.0f}%)".replace(",", "."),
              9, rgb=(0.05, 0.42, 0.23))

    if linhas:
        cy -= 24
        pdf.linhas([[(lx + 12, cy + 4), (lx + 28, cy + 4)]], (0.25, 0.25, 0.25), 0.5)
        pdf.texto(lx + 34, cy + 1, f"Curvas de nivel ({len(linhas)} linhas)", 9)

    # ---- barra de escala ----
    passo = _escala_redonda(mpp, mapa_w)
    barra = passo / mpp
    bx, by = x0 + 10, y0 + 12
    for i in range(4):
        pdf.retangulo(bx + i * barra / 4, by, barra / 4, 5,
                      preenche=(0, 0, 0) if i % 2 == 0 else (1, 1, 1),
                      traco=(0, 0, 0), espessura=0.4)
    pdf.texto(bx, by - 11, "0", 7)
    rotulo = f"{passo} m" if passo < 1000 else f"{passo / 1000:g} km"
    pdf.texto(bx + barra - 10, by - 11, rotulo, 7)

    # ---- norte ----
    nx_, ny_ = x0 + mapa_w - 26, y0 + mapa_h - 40
    pdf.cor((0.15, 0.15, 0.15))
    pdf.escreve(f"{nx_:.1f} {ny_:.1f} m {nx_ - 7:.1f} {ny_ - 20:.1f} l "
                f"{nx_:.1f} {ny_ - 14:.1f} l {nx_ + 7:.1f} {ny_ - 20:.1f} l f")
    pdf.texto(nx_ - 4, ny_ + 5, "N", 10, negrito=True)

    # ---- rodape ----
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    pe = [f"Modelo: {modelo}" if modelo else "", f"Sistema: {sistema}" if sistema else "",
          f"Gerado em {hoje} - AJ TopoGeo"]
    pdf.texto(x0, MARGEM + 12, "   |   ".join(p for p in pe if p), 8,
              rgb=(0.45, 0.45, 0.45))
    pdf.texto(x0, MARGEM, "Classes de capacidade de uso do solo. A declividade sai do "
                          "modelo digital de terreno; confira em campo antes do projeto.",
              7.5, rgb=(0.55, 0.55, 0.55))

    dados = rgb.tobytes()
    imagem = pdf.fluxo(dados, f"/Type /XObject /Subtype /Image /Width {nx} /Height {ny} "
                              "/ColorSpace /DeviceRGB /BitsPerComponent 8")
    pdf.gravar(saida, {"Im0": imagem})
    aviso(1.0)

    return dict(arquivo=str(saida), pixels=(nx, ny), curvas=len(linhas),
                hectares=total, escala_barra=passo)
