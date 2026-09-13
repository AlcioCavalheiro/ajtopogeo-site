"""Relatorio tecnico da fazenda em PDF: mapas, graficos e o documento.

Porte do `relatorio_fazenda.py` que chegou pronto. A diagramacao do PDF e a
dele; o que mudou esta nas fontes de dado (ver `fazenda_fontes`) e em quatro
pontos daqui:

- Mapas e graficos pela API de `Figure` do matplotlib, sem `pyplot`. O pyplot
  guarda estado global e nao e seguro fora da thread principal -- e aqui tudo
  roda na thread de trabalho da janela.
- O capitulo de valor mostra as tabelas pelo que elas sao: VTN por aptidao, da
  Receita, e precos do mercado regional do INCRA com minimo, mediano e maximo.
  Linha que o proprio INCRA publicou incoerente sai marcada, nao corrigida.
- Municipio e modulo fiscal podem sair do CAR, e o documento diz de onde veio
  cada numero.
- O texto do documento tem acento. A Helvetica padrao do PDF usa a codificacao
  WinAnsi, que cobre todos os caracteres do portugues; o que ela nao cobre
  (>=, por exemplo) nao aparece aqui.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

import fazenda_fontes as fontes
import fazenda_geo as geo
import fazenda_imagens as imagens

# Azuis da AJ TopoGeo, os mesmos do site (--brand, --brand-d, --azul) e do
# globo do logo. Ficam fora disso as escalas que carregam significado --
# NDVI, declividade, altitude -- e o contorno vermelho do perimetro.
AZUL = "#155a9e"          # titulos de capitulo
AZUL_MARCA = "#1a6fc4"    # subtitulos e destaques
AZUL_ESCURO = "#0d1b2a"   # titulos de mapa e grafico
AZUL_CLARO = "#e6f1fb"    # cabecalho de tabela
AZUL_FUNDO = "#f5f9fd"    # linha alternada de tabela
AZUL_LINHA = "#c9dcef"    # grade de tabela e filete do rodape
STATUS_CAR = {"AT": "ativo", "PE": "pendente", "SU": "suspenso", "CA": "cancelado"}
NATUREZA_SIGEF = {"particular": "particular", "publico": "pública"}


def num(v, casas=2):
    """Numero no formato brasileiro: 1.234,56."""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "@").replace(".", ",").replace("@", ".")


def _nome_de_arquivo(nome):
    return re.sub(r'[<>:"/\\|?*\s]+', "_", nome.strip()) or "Fazenda"


# ================================================================== mapas


def _figura(largura, altura, dpi=150):
    fig = Figure(figsize=(largura, altura), dpi=dpi)
    FigureCanvasAgg(fig)
    return fig


def _moldura(ax, extent, aneis, titulo):
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    for xs, ys in aneis:
        ax.plot(xs, ys, color="#ffffff", lw=2.6, solid_capstyle="round")
        ax.plot(xs, ys, color="#d32f2f", lw=1.4, solid_capstyle="round")
    ax.set_title(titulo, fontsize=11, weight="bold", color=AZUL_ESCURO, pad=8)
    ax.tick_params(labelsize=7)
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.grid(alpha=0.18, ls=":", lw=0.6)

    # barra de escala
    larg = extent[1] - extent[0]
    passo = 10 ** math.floor(math.log10(larg / 4))
    for m in (5, 2, 1):
        if passo * m <= larg / 3:
            passo *= m
            break
    x0 = extent[0] + larg * 0.05
    y0 = extent[2] + (extent[3] - extent[2]) * 0.05
    alt = (extent[3] - extent[2]) * 0.012
    ax.add_patch(Rectangle((x0, y0), passo, alt, fc="black", ec="black", zorder=6))
    ax.add_patch(Rectangle((x0 + passo, y0), passo, alt, fc="white", ec="black", zorder=6))
    rotulo = f"{passo * 2:.0f} m" if passo * 2 < 1000 else f"{num(passo * 2 / 1000, 1)} km"
    ax.text(x0 + passo, y0 + alt * 1.8, rotulo, fontsize=7, ha="center", zorder=6)

    # norte
    xn = extent[1] - larg * 0.06
    yn = extent[3] - (extent[3] - extent[2]) * 0.16
    dy = (extent[3] - extent[2]) * 0.06
    ax.annotate("", xy=(xn, yn + dy), xytext=(xn, yn - dy * 0.2), zorder=7,
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.6, mutation_scale=14))
    ax.text(xn, yn + dy * 1.15, "N", ha="center", va="bottom", fontsize=10, weight="bold",
            zorder=7, bbox=dict(fc="white", ec="none", alpha=0.75, pad=1.2))


def _salvar(fig, caminho):
    fig.tight_layout()
    fig.savefig(caminho, bbox_inches="tight")


def mapa_rgb(rgb, grade, aneis, caminho, titulo):
    fig = _figura(7.2, 6.4)
    ax = fig.add_subplot()
    ax.imshow(np.transpose(rgb, (1, 2, 0)), extent=grade.extent, interpolation="bilinear")
    _moldura(ax, grade.extent, aneis, titulo)
    _salvar(fig, caminho)


def mapa_ndvi(ndvi, grade, aneis, caminho, titulo):
    fig = _figura(7.2, 6.4)
    ax = fig.add_subplot()
    im = ax.imshow(np.ma.masked_invalid(ndvi), extent=grade.extent, cmap="RdYlGn",
                   vmin=0.0, vmax=0.9, interpolation="nearest")
    _moldura(ax, grade.extent, aneis, titulo)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("NDVI", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    _salvar(fig, caminho)


def mapa_hipso(dem, grade, aneis, caminho, titulo):
    fig = _figura(7.2, 6.4)
    ax = fig.add_subplot()
    m = np.ma.masked_invalid(dem)
    im = ax.imshow(m, extent=grade.extent, cmap="terrain", interpolation="bilinear")
    if m.count() > 10:
        amplitude = float(m.max() - m.min())
        # equidistancia que da de 5 a 25 curvas, qualquer que seja o desnivel
        passo = next((p for p in (1, 2, 5, 10, 20, 25, 50, 100, 200) if amplitude / p <= 25), 500)
        niveis = np.arange(math.floor(m.min() / passo) * passo, m.max() + passo, passo)
        if len(niveis) > 1:
            xs, ys = grade.centros()
            cs = ax.contour(xs, ys, np.nan_to_num(dem, nan=float(m.mean())), levels=niveis,
                            colors="#00000055", linewidths=0.5)
            ax.clabel(cs, inline=True, fontsize=5.5, fmt="%.0f")
    _moldura(ax, grade.extent, aneis, titulo)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Altitude (m)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    _salvar(fig, caminho)


def mapa_declividade(decl, grade, aneis, caminho, titulo):
    limites = [0, 3, 8, 20, 45, 75, 1000]
    cmap = ListedColormap(fontes.CORES_DECL)
    fig = _figura(7.2, 6.4)
    ax = fig.add_subplot()
    ax.imshow(np.ma.masked_invalid(decl), extent=grade.extent, cmap=cmap,
              norm=BoundaryNorm(limites, cmap.N), interpolation="nearest")
    _moldura(ax, grade.extent, aneis, titulo)
    legenda = [Patch(fc=fontes.CORES_DECL[i], ec="#00000044",
                     label=f"{c[2]} ({c[0]}–{c[1]} %)" if c[1] < 1e8 else f"{c[2]} (> {c[0]} %)")
               for i, c in enumerate(fontes.CLASSES_DECL)]
    ax.legend(handles=legenda, loc="upper left", fontsize=6.8, framealpha=0.92,
              bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
    _salvar(fig, caminho)


def grafico_chuva(ch, caminho, titulo):
    fig = _figura(9.6, 4.4, dpi=140)
    ax = fig.add_subplot()
    rot = [f"{fontes.MESES_PT[m - 1]}/{a % 100:02d}" for a, m, _ in ch["recente"]]
    vals = [v for _, _, v in ch["recente"]]
    norm = [ch["normal"][m] for _, m, _ in ch["recente"]]
    x = np.arange(len(vals))
    ax.bar(x, vals, color=[AZUL_MARCA if v >= n else "#e07b39" for v, n in zip(vals, norm)],
           width=0.68, label="últimos 12 meses")
    ax.plot(x, norm, "-o", color=AZUL_ESCURO, lw=1.6, ms=4, label=f"normal {ch['periodo_normal']}")
    ax.set_xticks(x)
    ax.set_xticklabels(rot, fontsize=8, rotation=45, ha="right")
    ax.set_ylabel("Precipitação (mm)")
    ax.set_title(titulo, fontsize=11, weight="bold", color=AZUL_ESCURO)
    ax.grid(axis="y", alpha=0.25, ls=":")
    ax.legend(fontsize=8)
    fig.text(0.01, 0.01, f"Fonte: {ch['fonte']}", fontsize=7, color="#666666")
    fig.tight_layout()
    fig.savefig(caminho)


# ================================================================== PDF


def _identificacao_car(a):
    partes = [f"<b>{escape(a.get('cod_imovel', '-'))}</b>"]
    status = a.get("status_imovel")
    if status:
        partes.append(f"situação: {escape(status)} ({STATUS_CAR.get(status, '?')})")
    if a.get("condicao"):
        partes.append(escape(a["condicao"]))
    if a.get("municipio"):
        partes.append(escape(a["municipio"]))
    return "<br/>".join(partes)


def _identificacao_sigef(a):
    partes = [f"<b>{escape(a.get('parcela_codigo', '-'))}</b>"]
    if a.get("natureza"):
        partes.append(f"parcela {NATUREZA_SIGEF.get(a['natureza'], escape(a['natureza']))}")
    if a.get("data_aprovacao"):
        partes.append(f"certificada em {_data_br(a['data_aprovacao'])}")
    if a.get("registro_data"):
        partes.append(f"registro em {_data_br(a['registro_data'])}")
    return "<br/>".join(partes)


def _data_br(texto):
    m = re.match(r"(\d{4})[-/](\d{2})[-/](\d{2})", str(texto))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else escape(str(texto))


def montar_pdf(caminho, dados, log):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=13, spaceBefore=10, spaceAfter=6,
                        textColor=colors.HexColor(AZUL))
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=10.5, spaceBefore=8, spaceAfter=4,
                        textColor=colors.HexColor(AZUL_MARCA))
    P = ParagraphStyle("P", parent=ss["BodyText"], fontSize=9, leading=13, alignment=TA_JUSTIFY)
    PC = ParagraphStyle("PC", parent=P, alignment=TA_CENTER)
    NOTA = ParagraphStyle("NOTA", parent=P, fontSize=7.8, leading=10.5,
                          textColor=colors.HexColor("#555555"))
    CEL = ParagraphStyle("CEL", parent=ss["BodyText"], fontSize=8, leading=10.5)

    def par(texto, estilo=P):
        return Paragraph(texto, estilo)

    def tabela(linhas, larguras=None, cabecalho=True, alinhar_direita=()):
        linhas = [[Paragraph(escape(c), CEL) if isinstance(c, str) and len(c) > 34 else c
                   for c in lin] for lin in linhas]
        t = Table(linhas, colWidths=larguras, hAlign="LEFT")
        est = [("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
               ("FONTSIZE", (0, 0), (-1, -1), 8),
               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
               ("TOPPADDING", (0, 0), (-1, -1), 3),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
               ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(AZUL_LINHA))]
        for col in alinhar_direita:
            est.append(("ALIGN", (col, 1 if cabecalho else 0), (col, -1), "RIGHT"))
        if cabecalho:
            est += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL_CLARO)),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        for i in range(1 if cabecalho else 0, len(linhas)):
            if i % 2 == 0:
                est.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(AZUL_FUNDO)))
        t.setStyle(TableStyle(est))
        return t

    def figura(cam, larg_mm=165):
        from PIL import Image as PImg
        with PImg.open(cam) as im:
            w, h = im.size
        return Image(str(cam), width=larg_mm * mm, height=larg_mm * mm * h / w)

    def rodape(canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 7)
        canv.setFillColor(colors.HexColor("#777777"))
        canv.drawString(18 * mm, 12 * mm, dados["rodape"])
        canv.drawRightString(A4[0] - 18 * mm, 12 * mm, f"pág. {doc.page}")
        canv.setStrokeColor(colors.HexColor(AZUL_LINHA))
        canv.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
        canv.restoreState()

    doc = SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=20 * mm,
                            title=f"Relatório técnico – {dados['nome']}", author=dados["empresa"])
    ha = dados["ha"]
    s = []

    # ---------------- capa
    s.append(Spacer(1, 18 * mm))
    s.append(par("RELATÓRIO TÉCNICO DE CARACTERIZAÇÃO DE IMÓVEL RURAL",
                 ParagraphStyle("cap", parent=PC, fontSize=16, leading=21,
                                textColor=colors.HexColor(AZUL))))
    s.append(Spacer(1, 6 * mm))
    s.append(par(escape(dados["nome"]), ParagraphStyle("cap2", parent=PC, fontSize=20, leading=25)))
    s.append(Spacer(1, 3 * mm))
    s.append(par(escape(f"{dados['municipio']} – {dados['uf']}"), PC))
    s.append(Spacer(1, 8 * mm))
    if dados.get("img_rgb"):
        s.append(figura(dados["img_rgb"], 112))
    s.append(Spacer(1, 8 * mm))
    s.append(tabela([
        ["Área do perímetro informado", f"{num(ha, 4)} ha"],
        ["Perímetro", f"{num(dados['perimetro_m'], 2)} m"],
        ["Sistema de referência", dados["srs"]],
        ["Data de emissão", dados["data"]],
        ["Responsável técnico", dados["responsavel"] or "–"],
    ], [72 * mm, 88 * mm], cabecalho=False))
    s.append(PageBreak())

    # ---------------- 1. cadastral
    s.append(par("1. IDENTIFICAÇÃO E SITUAÇÃO CADASTRAL", H1))
    s.append(par(
        "Os limites analisados são os do arquivo KML fornecido. As consultas abaixo verificam a "
        "existência de registros oficiais que se sobrepõem a esse polígono. Sobreposição parcial "
        "não significa erro: pode indicar limite desatualizado, desmembramento não averbado ou "
        "divergência entre o levantamento e o cadastro."))
    s.append(Spacer(1, 3 * mm))
    lin = [["Item", "Situação"], ["Área do KML", f"{num(ha, 4)} ha"],
           ["Município", dados["municipio_fonte"]]]
    mod = dados.get("modulo")
    if mod:
        lin.append(["Módulo fiscal do município", f"{num(mod['mf'], 0)} ha – {mod['fonte']}"])
        lin.append(["Módulos fiscais do imóvel", f"{num(mod['n'], 2)} – {mod['classe']}"])
    else:
        lin.append(["Módulo fiscal", "não identificado"])
    lin.append(["Reserva Legal de referência",
                f"{num(dados['rl_pct'], 0)} % = {num(ha * dados['rl_pct'] / 100, 4)} ha"])
    s.append(tabela(lin, [58 * mm, 116 * mm]))
    s.append(Spacer(1, 4 * mm))

    for chave, titulo, ident in (("car", "1.1 Cadastro Ambiental Rural (CAR)", _identificacao_car),
                                 ("sigef", "1.2 Georreferenciamento certificado (SIGEF/INCRA)",
                                  _identificacao_sigef)):
        s.append(par(titulo, H2))
        cad = dados[chave]
        res = cad["resultados"]
        if res is None:
            s.append(par(f"<b>Não foi possível consultar.</b> {escape(cad['aviso'])}"))
        elif not res:
            s.append(par(
                f"Consulta realizada ({escape(cad['origem'])}) e <b>nenhum registro sobreposto "
                "foi localizado</b>. Para o CAR, isso sugere imóvel sem cadastro; para o SIGEF, "
                "imóvel sem certificação. Confirme sempre na consulta oficial antes de qualquer ato."))
        else:
            s.append(par(f"Base consultada: {escape(cad['origem'])}. "
                         f"{len(res)} registro(s) sobreposto(s) ao perímetro."))
            s.append(Spacer(1, 2 * mm))
            corpo = [["#", "Identificação", "Área cad. (ha)", "Comum (ha)", "% do perím.", "% da feição"]]
            for i, r in enumerate(res[:8], 1):
                corpo.append([str(i), Paragraph(ident(r["atributos"]), NOTA),
                              num(r["area_feicao_ha"], 2), num(r["area_comum_ha"], 2),
                              num(r["pct_do_perimetro"], 1), num(r["pct_da_feicao"], 1)])
            s.append(tabela(corpo, [8 * mm, 74 * mm, 24 * mm, 22 * mm, 22 * mm, 22 * mm],
                            alinhar_direita=(2, 3, 4, 5)))
            principal = res[0]
            dif = ha - principal["area_feicao_ha"]
            if abs(dif) > max(0.5, ha * 0.01):
                s.append(Spacer(1, 2 * mm))
                s.append(par(
                    f"<b>Divergência de área:</b> o perímetro informado tem {num(ha, 4)} ha e o "
                    f"registro principal declara {num(principal['area_feicao_ha'], 4)} ha – "
                    f"diferença de {num(dif, 4)} ha "
                    f"({num(100 * dif / principal['area_feicao_ha'], 2)} %). Recomenda-se a "
                    "conferência dos limites e, se confirmada, a retificação do cadastro."))
            if cad.get("aviso"):
                s.append(Spacer(1, 2 * mm))
                s.append(par(escape(cad["aviso"]), NOTA))
        s.append(Spacer(1, 3 * mm))
    s.append(PageBreak())

    # ---------------- 2. imagem
    s.append(par("2. IMAGEM DE SATÉLITE", H1))
    s.append(par(dados["texto_imagem"]))
    s.append(Spacer(1, 3 * mm))
    if dados.get("img_rgb"):
        s.append(figura(dados["img_rgb"]))
    s.append(PageBreak())

    # ---------------- 3. vegetacao
    s.append(par("3. ÍNDICES DE VEGETAÇÃO", H1))
    s.append(par(
        "O NDVI (índice de vegetação por diferença normalizada) mede o vigor da cobertura "
        "vegetal a partir da razão entre as bandas do infravermelho próximo e do vermelho. "
        "Varia de -1 a 1: solo exposto e palhada ficam abaixo de 0,20; pastagem em uso, entre "
        "0,30 e 0,55; lavoura em pleno desenvolvimento, acima de 0,65. Os pixels de nuvem e de "
        "sombra foram removidos antes do cálculo."))
    s.append(Spacer(1, 3 * mm))
    if dados.get("img_ndvi"):
        s.append(figura(dados["img_ndvi"]))
    st = dados.get("stats_ndvi")
    if st:
        s.append(Spacer(1, 3 * mm))
        s.append(tabela([
            ["NDVI médio", "Mediana", "P10", "P90", "Desvio", "Área < 0,20"],
            [num(st["medio"], 3), num(st["mediana"], 3), num(st["p10"], 3), num(st["p90"], 3),
             num(st["desvio"], 3), f"{num(st['pct_baixo'], 1)} %"],
        ], [29 * mm] * 6))
        s.append(Spacer(1, 2 * mm))
        s.append(par("A distância entre P10 e P90 mede a desigualdade interna da área. Faixa larga "
                     "indica manejo heterogêneo, falha de estande ou variação de solo dentro do "
                     "mesmo talhão.", NOTA))
    if dados.get("img_serie"):
        s.append(Spacer(1, 4 * mm))
        s.append(par("3.1 Evolução temporal", H2))
        s.append(figura(dados["img_serie"]))
        s.append(par(dados["texto_serie"], NOTA))
    s.append(PageBreak())

    # ---------------- 4. relevo
    s.append(par("4. RELEVO E DECLIVIDADE", H1))
    s.append(par(dados["texto_relevo"]))
    s.append(Spacer(1, 3 * mm))
    if dados.get("img_hipso"):
        s.append(figura(dados["img_hipso"]))
    if dados.get("img_decl"):
        s.append(Spacer(1, 3 * mm))
        s.append(figura(dados["img_decl"]))
    if dados.get("tab_decl"):
        s.append(Spacer(1, 3 * mm))
        corpo = [["Classe de relevo", "Faixa", "Área (ha)", "% da área"]]
        for r in dados["tab_decl"]:
            corpo.append([r["classe"], r["faixa"], num(r["ha"], 2), num(r["pct"], 1)])
        s.append(tabela(corpo, [52 * mm, 32 * mm, 38 * mm, 38 * mm], alinhar_direita=(2, 3)))
    rr = dados.get("restricoes")
    if rr:
        s.append(Spacer(1, 4 * mm))
        s.append(par("4.1 Restrições por declividade – Lei 12.651/2012", H2))
        s.append(tabela([
            ["Enquadramento", "Critério", "Área (ha)", "% da área"],
            ["APP de encosta (art. 4º, V)", "> 45° (100 %)", num(rr["app_ha"], 2),
             num(rr["app_pct"], 1)],
            ["Área de uso restrito (art. 11)", "25° a 45° (46,6 % a 100 %)",
             num(rr["restrito_ha"], 2), num(rr["restrito_pct"], 1)],
        ], [52 * mm, 46 * mm, 31 * mm, 31 * mm], alinhar_direita=(2, 3)))
        s.append(Spacer(1, 2 * mm))
        s.append(par("Indicativo apenas. O enquadramento legal exige levantamento altimétrico de "
                     "campo; um modelo de 30 metros suaviza encostas curtas e pode subestimar "
                     "tanto a APP quanto a área de uso restrito.", NOTA))
    s.append(PageBreak())

    # ---------------- 5. chuva
    s.append(par("5. REGIME DE CHUVAS", H1))
    ch = dados.get("chuva")
    if ch:
        sinal = "acima" if ch["desvio_pct"] >= 0 else "abaixo"
        s.append(par(
            f"A normal do local, calculada sobre o período {ch['periodo_normal']}, é de "
            f"{num(ch['total_normal'], 0)} mm por ano. Nos últimos doze meses choveu "
            f"{num(ch['total_recente'], 0)} mm, {num(abs(ch['desvio_pct']), 1)} % {sinal} da "
            f"normal. O mês mais chuvoso é {fontes.MESES_PT[ch['mes_chuvoso'] - 1]} "
            f"({num(ch['normal'][ch['mes_chuvoso']], 0)} mm) e o mais seco é "
            f"{fontes.MESES_PT[ch['mes_seco'] - 1]} ({num(ch['normal'][ch['mes_seco']], 0)} mm)."))
        s.append(Spacer(1, 3 * mm))
        if dados.get("img_chuva"):
            s.append(figura(dados["img_chuva"]))
        s.append(Spacer(1, 2 * mm))
        s.append(par(f"Fonte: {ch['fonte']}. A grade tem cerca de 50 km de lado; portanto, o dado "
                     "descreve a região, e não o pluviômetro da sede. Serve para caracterizar o "
                     "regime e comparar anos, não para apurar sinistro.", NOTA))
    else:
        s.append(par("Dados de precipitação não obtidos nesta execução."))
    s.append(PageBreak())

    # ---------------- 6. valor
    s.append(par("6. REFERÊNCIAS DE VALOR POR HECTARE", H1))
    s.append(par(
        "<b>Este capítulo não é uma avaliação de imóvel.</b> Um laudo de avaliação de imóvel "
        "rural exige vistoria, pesquisa de mercado com amostra de elementos comparáveis, "
        "tratamento estatístico e Anotação de Responsabilidade Técnica, conforme a NBR 14653-3. "
        "O que segue são valores públicos de referência, úteis para ordem de grandeza e para "
        "conferência de declaração fiscal."))
    s.append(Spacer(1, 3 * mm))
    vr = dados["valores"]
    vtn = vr.get("vtn")
    if vtn and vtn["linhas"]:
        s.append(par(f"6.1 Valor da Terra Nua – referência fiscal (Receita Federal, exercício "
                     f"{vtn['exercicio']})", H2))
        corpo = [["Aptidão agrícola", "VTN por ha", f"Total para {num(ha, 2)} ha"]]
        for v in vtn["linhas"]:
            if v["valor"] is None:
                corpo.append([v["aptidao"], "sem informação", "–"])
            else:
                corpo.append([v["aptidao"], "R$ " + num(v["valor"], 2), "R$ " + num(v["valor"] * ha, 2)])
        s.append(tabela(corpo, [72 * mm, 44 * mm, 52 * mm], alinhar_direita=(1, 2)))
        s.append(Spacer(1, 2 * mm))
        s.append(par(
            f"Valores {escape(vtn['fonte'])} à Receita Federal. O VTN é a régua que a Receita usa "
            "para conferir o valor declarado na DITR; costuma ficar bem abaixo do preço de "
            "negociação e não deve ser usado como valor de venda. \"Sem informação\" reproduz a "
            "tabela oficial, que não traz valor para aquela aptidão no município.", NOTA))
        s.append(Spacer(1, 4 * mm))

    merc = vr.get("mercado")
    if merc and merc["linhas"]:
        s.append(par(f"6.2 Mercado regional de terras – MRT-{int(merc['mrt']):02d} "
                     f"{escape(merc['mercado'] or '')} (INCRA, RAMT {merc['ano']})", H2))
        corpo = [["Nível", "Tipologia de uso", "VTN mínimo", "VTN mediano", "VTN máximo"]]
        marcados = []
        for v in merc["linhas"]:
            uso = v["uso"] + (" *" if v["inconsistencia"] else "")
            if v["inconsistencia"]:
                marcados.append(f"{v['uso']}: {v['inconsistencia']}")
            corpo.append([v["nivel"], uso, num(v["vtn_min"], 0), num(v["vtn_mediano"], 0),
                          num(v["vtn_max"], 0)])
        s.append(tabela(corpo, [18 * mm, 80 * mm, 24 * mm, 24 * mm, 24 * mm], alinhar_direita=(2, 3, 4)))
        s.append(Spacer(1, 2 * mm))
        s.append(par("Valores em R$ por hectare, preço à vista, sem benfeitorias (Valor da Terra "
                     "Nua). Mínimo e máximo são o campo de arbítrio do INCRA: 85 % e 115 % do "
                     "mediano.", NOTA))
        if marcados:
            s.append(par("* Linha publicada pelo INCRA com incoerência interna, reproduzida sem "
                         "correção: " + escape("; ".join(marcados)) + ".", NOTA))
        primeiro = [v for v in merc["linhas"] if v["nivel"].lower().startswith("primeiro")
                    and not v["inconsistencia"] and v["vtn_min"] and v["vtn_max"]]
        if primeiro:
            lo = min(v["vtn_min"] for v in primeiro)
            hi = max(v["vtn_max"] for v in primeiro)
            s.append(Spacer(1, 2 * mm))
            s.append(par(
                f"<b>Faixa indicativa para o imóvel</b> (primeiro nível categórico, terra nua): "
                f"R$ {num(lo * ha, 2)} a R$ {num(hi * ha, 2)}. O preço de mercado é regional: "
                "descreve um agrupamento de municípios, e não este imóvel. Aptidão agrícola, "
                "acesso, hidrografia, benfeitorias e situação registral movem o valor para dentro "
                "ou para fora dessa faixa."))
    if not (vtn and vtn["linhas"]) and not (merc and merc["linhas"]):
        s.append(par("Nenhuma tabela de referência foi localizada para este município."))
    for aviso in vr["avisos"]:
        s.append(Spacer(1, 2 * mm))
        s.append(par(escape(aviso), NOTA))
    s.append(PageBreak())

    # ---------------- 7. ressalvas
    s.append(par("7. RESSALVAS TÉCNICAS E FONTES", H1))
    for t in dados["ressalvas"]:
        s.append(par("– " + t))
        s.append(Spacer(1, 1.5 * mm))
    s.append(Spacer(1, 4 * mm))
    s.append(par("Fontes utilizadas", H2))
    corpo = [["Dado", "Fonte", "Referência temporal"]]
    for f in dados["fontes"]:
        corpo.append([f[0], Paragraph(escape(f[1]), NOTA), Paragraph(escape(f[2]), NOTA)])
    s.append(tabela(corpo, [34 * mm, 90 * mm, 44 * mm]))
    s.append(Spacer(1, 10 * mm))
    s.append(par("_" * 46, PC))
    s.append(par(escape(dados["responsavel"] or ""), PC))
    s.append(par(escape(dados["empresa"] or ""), PC))

    doc.build(s, onFirstPage=rodape, onLaterPages=rodape)
    log(f"  PDF montado: {Path(caminho).name}")


# ================================================================== pipeline


def gerar_relatorio(kml, pasta, nome, municipio, uf, responsavel, empresa, rl_pct, dias,
                    nuvem_max, com_serie, log, cancelar):
    raiz = geo.pasta_do_programa()
    uf = uf.strip().upper()
    ctx = imagens.preparar(kml, log)
    lon_c, lat_c = ctx["centro"]
    base = _nome_de_arquivo(nome)
    saida = Path(pasta) / f"{base}_relatorio_{date.today()}"
    figuras = saida / "figuras"
    figuras.mkdir(parents=True, exist_ok=True)
    aneis = imagens.aneis_para_desenho(ctx["poligonos_utm"])
    ha = ctx["ha"]

    dados = dict(nome=nome, uf=uf, ha=ha, perimetro_m=ctx["perimetro_m"],
                 srs=f"SIRGAS 2000 / UTM (EPSG:{ctx['epsg']})",
                 data=date.today().strftime("%d/%m/%Y"), responsavel=responsavel,
                 empresa=empresa, rl_pct=rl_pct)

    # ---- cadastro, municipio e modulo fiscal
    log("Consultas cadastrais...")
    dados["car"] = fontes.consultar_cadastro("car", raiz, ctx["wkt_utm"], ctx["bbox"], ctx["epsg"], uf, log)
    dados["sigef"] = fontes.consultar_cadastro("sigef", raiz, ctx["wkt_utm"], ctx["bbox"], ctx["epsg"], uf, log)
    pelo_car = fontes.municipio_pelo_car(dados["car"])
    informado = municipio.strip()
    if informado:
        dados["municipio_fonte"] = f"{informado} (informado)"
    elif pelo_car and pelo_car["municipio"]:
        informado = pelo_car["municipio"]
        dados["municipio_fonte"] = f"{informado} (identificado pelo CAR)"
        log(f"  municipio identificado pelo CAR: {informado}")
    else:
        dados["municipio_fonte"] = "não identificado"
    dados["municipio"] = informado or "município não identificado"

    mesmo = pelo_car and fontes.normalizar(pelo_car["municipio"]) == fontes.normalizar(informado)
    mf, mf_fonte = None, None
    if mesmo and pelo_car["modulo_fiscal"]:
        mf = pelo_car["modulo_fiscal"]
        mf_fonte = f"declarado no CAR ({pelo_car['amostra']} imóveis do município conferidos)"
    elif informado:
        mf, arquivo = fontes.modulo_fiscal_tabela(raiz, informado, uf, pelo_car["cod_ibge"] if mesmo else None)
        if mf:
            mf_fonte = f"tabela de índices básicos do INCRA ({arquivo})"
    n_mod, classe = fontes.classificar_por_modulos(ha, mf)
    dados["modulo"] = dict(mf=mf, fonte=mf_fonte, n=n_mod, classe=classe) if mf else None
    dados["rodape"] = f"{nome} – {dados['municipio']}/{uf} – {empresa}"
    if cancelar():
        raise imagens.Cancelado()

    # ---- imagem e NDVI
    log("Imagem de satelite...")
    hoje = date.today()
    itens = imagens.buscar_cenas(ctx, str(hoje - timedelta(days=dias)), str(hoje), nuvem_max, log, cancelar)
    melhor, pct = imagens.escolher_cena(itens, ctx, log, cancelar)
    data_cena = melhor["data"]
    log(f"  cena de {data_cena} ({pct:.1f} % de nuvem sobre o imovel); baixando as bandas...")
    cena = imagens.ler_cena(melhor, ctx["grade"], ctx["dentro"])
    data_br = _data_br(data_cena)
    dados["img_rgb"] = figuras / "01_satelite.png"
    mapa_rgb(cena["rgb"], ctx["grade"], aneis, dados["img_rgb"], f"Composição colorida Sentinel-2 – {data_br}")
    dados["img_ndvi"] = figuras / "02_ndvi.png"
    mapa_ndvi(cena["ndvi"], ctx["grade"], aneis, dados["img_ndvi"], f"NDVI – {data_br}")
    dados["stats_ndvi"] = imagens.stats_ndvi(cena["ndvi"], ctx["dentro"])
    dados["texto_imagem"] = (
        f"Imagem do satélite Sentinel-2 (Copernicus/ESA) de {data_br}, com resolução de 10 metros, "
        f"processada em nível L2A (reflectância de superfície). Entre as cenas disponíveis nos "
        f"últimos {dias} dias, esta é a mais recente praticamente sem nuvens <b>sobre o polígono "
        f"do imóvel</b> ({num(pct, 1)} %) – critério mais restritivo que o percentual de nuvem "
        f"da cena inteira, que cobre 110 × 110 km.")
    if cancelar():
        raise imagens.Cancelado()

    # ---- serie temporal
    if com_serie:
        log("Serie temporal de NDVI...")
        try:
            linhas = imagens.serie_ndvi(itens, ctx, log, cancelar, min_validos=80.0)
            if len(linhas) >= 4:
                dados["img_serie"] = figuras / "03_serie_ndvi.png"
                imagens.grafico_serie(linhas, dados["img_serie"], nome, ha)
                pico = max(linhas, key=lambda r: r["medio"])
                vale = min(linhas, key=lambda r: r["medio"])
                dados["texto_serie"] = (
                    f"{len(linhas)} datas com pelo menos 80 % do imóvel livre de nuvem. Pico de "
                    f"{num(pico['medio'], 3)} em {_data_br(pico['data'])}; vale de "
                    f"{num(vale['medio'], 3)} em {_data_br(vale['data'])}. Compare datas do mesmo "
                    "estádio fenológico: NDVI é vigor, não produtividade.")
            else:
                log(f"  so {len(linhas)} data(s) valida(s); serie fora do relatorio.")
        except imagens.Cancelado:
            raise
        except Exception as e:  # noqa: BLE001 - a serie e complemento; o relatorio sai sem ela
            log(f"  serie nao gerada: {e}")

    # ---- relevo
    log("Relevo...")
    grade30, dem, dentro30, achados = imagens.mde_glo30(ctx, log)
    if achados and np.isfinite(dem[dentro30]).any():
        dem_m = np.where(dentro30, dem, np.nan)
        decl = fontes.declividade_horn(np.nan_to_num(dem, nan=float(np.nanmean(dem))), 30.0)
        decl = np.where(dentro30, decl, np.nan)
        dados["img_hipso"] = figuras / "04_hipsometria.png"
        mapa_hipso(dem_m, grade30, aneis, dados["img_hipso"], "Hipsometria – Copernicus DEM GLO-30")
        dados["img_decl"] = figuras / "05_declividade.png"
        mapa_declividade(decl, grade30, aneis, dados["img_decl"], "Classes de declividade")
        dados["tab_decl"], mediana = fontes.tabela_declividade(decl, dentro30, grade30.area_pixel_ha)
        dados["restricoes"] = fontes.restricoes_legais(decl, dentro30, grade30.area_pixel_ha)
        dv = dem_m[np.isfinite(dem_m)]
        dominante = max(dados["tab_decl"], key=lambda r: r["pct"])
        dados["texto_relevo"] = (
            f"Altimetria derivada do Copernicus DEM GLO-30, com resolução de 30 metros. A área varia "
            f"de {num(dv.min(), 1)} m a {num(dv.max(), 1)} m de altitude, amplitude de "
            f"{num(dv.max() - dv.min(), 1)} m. A declividade mediana é de {num(mediana, 1)} % e a "
            f"classe dominante é <b>{dominante['classe'].lower()}</b>, com "
            f"{num(dominante['pct'], 1)} % da área. O GLO-30 é um modelo digital de superfície: "
            "inclui o dossel vegetal e as edificações; portanto, superestima a cota em áreas "
            "florestadas e não substitui o levantamento altimétrico.")
    else:
        dados["texto_relevo"] = "Modelo digital de elevação não obtido nesta execução."
        dados["tab_decl"] = dados["restricoes"] = None

    # ---- chuva
    try:
        dados["chuva"] = fontes.chuva_nasa_power(lat_c, lon_c, log=log)
        dados["img_chuva"] = figuras / "06_chuva.png"
        grafico_chuva(dados["chuva"], dados["img_chuva"], "Precipitação mensal – últimos 12 meses e normal")
    except Exception as e:  # noqa: BLE001
        log(f"  chuva nao obtida: {e}")
        dados["chuva"] = None

    # ---- valores
    log("Referencias de valor...")
    dados["valores"] = fontes.valores_referencia(raiz, informado, uf, log)

    # ---- ressalvas e fontes
    dados["ressalvas"] = [
        "Este relatório é um estudo de caracterização por sensoriamento remoto. Não substitui "
        "levantamento topográfico, memorial descritivo, laudo de avaliação nem perícia.",
        "Os limites analisados são os do arquivo digital fornecido pelo contratante. Não houve "
        "conferência de campo dos marcos e das divisas.",
        "As consultas cadastrais refletem a base disponível na data de emissão. Os cadastros são "
        "alterados diariamente; confirme na consulta oficial antes de qualquer ato jurídico.",
        "O modelo digital de elevação é de superfície (MDS) e tem resolução de 30 metros. As áreas "
        "de APP e de uso restrito indicadas por declividade são estimativas preliminares.",
        "Os índices de vegetação medem vigor, não produtividade. A comparação entre datas só é "
        "válida dentro do mesmo estádio fenológico.",
        "As referências de valor são dados públicos de ordem de grandeza. A avaliação de imóvel "
        "rural segue a NBR 14653-3 e exige vistoria, pesquisa de mercado e ART.",
    ]
    vtn, merc = dados["valores"].get("vtn"), dados["valores"].get("mercado")
    ch = dados["chuva"]
    dados["fontes"] = [
        ["Imagem e NDVI", "Copernicus Sentinel-2 L2A (ESA), catálogo STAC AWS Earth Search",
         f"cena de {data_br}"],
        ["Altimetria", "Copernicus DEM GLO-30 (ESA / Airbus), AWS Open Data", "coleção 2021"],
        ["Precipitação", ch["fonte"] if ch else "–", ch["periodo_normal"] if ch else "–"],
        ["CAR", "SICAR – Sistema Nacional de Cadastro Ambiental Rural",
         dados["car"]["origem"] or "não consultado"],
        ["Georreferenciamento", "SIGEF / Acervo Fundiário – INCRA",
         dados["sigef"]["origem"] or "não consultado"],
        ["Valor fiscal", "Receita Federal – Valores de Terra Nua (SIPT)",
         f"exercício {vtn['exercicio']}" if vtn else "não disponível"],
        ["Mercado de terras", "INCRA – Relatório de Análise de Mercados de Terras (RAMT)",
         f"RAMT {merc['ano']}" if merc else "não disponível"],
        ["Módulo fiscal", (dados["modulo"] or {}).get("fonte") or "não identificado", "–"],
    ]

    pdf = saida / f"{base}_relatorio.pdf"
    log("Montando o PDF...")
    montar_pdf(pdf, dados, log)
    log("")
    log(f"CONCLUIDO -> {pdf}")
    return pdf
