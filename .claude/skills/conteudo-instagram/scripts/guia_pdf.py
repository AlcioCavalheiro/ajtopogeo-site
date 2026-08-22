# -*- coding: utf-8 -*-
"""Guia de publicação em PDF a partir da pauta.json.

    python guia_pdf.py pauta.json

Uma página por peça, com as miniaturas na ordem de upload, a legenda numa
caixa para copiar, as hashtags e as observações de montagem. Fecha com a
página de sigilo e pendências. É o único entregável que o usuário lê inteiro
antes de postar - o resto ele só arrasta para o Instagram.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                PageBreak, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

_F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("SUI", _F + "segoeui.ttf"))
pdfmetrics.registerFont(TTFont("SUI-B", _F + "segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("SUI-K", _F + "seguibl.ttf"))
pdfmetrics.registerFont(TTFont("SUI-SB", _F + "seguisb.ttf"))
pdfmetrics.registerFont(TTFont("SUI-I", _F + "segoeuii.ttf"))
pdfmetrics.registerFontFamily("SUI", normal="SUI", bold="SUI-B",
                              italic="SUI-I", boldItalic="SUI-B")

AZUL = colors.HexColor("#0d1b2a")
AZUL3 = colors.HexColor("#1a3a5c")
ACC = colors.HexColor("#3E8FC4")
CINZA = colors.HexColor("#5b6b7c")
LINHA = colors.HexColor("#d5dde5")

PAG_W, PAG_H = A4
ML = 18 * mm

S = ParagraphStyle("s", fontName="SUI", fontSize=9.5, leading=14.5, textColor=AZUL)
S_PEQ = ParagraphStyle("sp", parent=S, fontSize=8.3, leading=12, textColor=CINZA)
S_LEG = ParagraphStyle("leg", parent=S, fontSize=10, leading=16, leftIndent=6 * mm)
S_TAG = ParagraphStyle("tag", parent=S, fontSize=8.6, leading=13.5,
                       textColor=ACC, fontName="SUI-SB", leftIndent=6 * mm)
S_CEL = ParagraphStyle("cel", fontName="SUI", fontSize=8.6, leading=12.6, textColor=AZUL)
S_CAB = ParagraphStyle("cab", fontName="SUI-B", fontSize=8.6, leading=12.6,
                       textColor=colors.white)
H1 = ParagraphStyle("h1", fontName="SUI-K", fontSize=19, leading=23, textColor=AZUL)
H2 = ParagraphStyle("h2", fontName="SUI-K", fontSize=13, leading=17, textColor=AZUL,
                    spaceBefore=9, spaceAfter=4)

_PAUTA = {}


def _cabecalho(cnv, doc):
    cnv.saveState()
    cnv.setFillColor(AZUL)
    cnv.rect(0, PAG_H - 13 * mm, PAG_W, 13 * mm, stroke=0, fill=1)
    cnv.setFillColor(ACC)
    cnv.rect(0, PAG_H - 13.8 * mm, PAG_W, 0.8 * mm, stroke=0, fill=1)
    cnv.setFont("SUI-B", 8)
    cnv.setFillColor(colors.HexColor("#8fa8bd"))
    cnv.drawString(ML, PAG_H - 8.6 * mm, "AJ TOPOGEO  ·  GUIA DE PUBLICAÇÃO INSTAGRAM")
    cnv.drawRightString(PAG_W - ML, PAG_H - 8.6 * mm, _PAUTA.get("data_br", ""))
    cnv.setFont("SUI", 7.5)
    cnv.setFillColor(CINZA)
    cnv.drawRightString(PAG_W - ML, 10 * mm, f"página {doc.page}")
    cnv.setStrokeColor(LINHA)
    cnv.setLineWidth(0.5)
    cnv.line(ML, 14 * mm, PAG_W - ML, 14 * mm)
    cnv.restoreState()


def rotulo(txt):
    return Paragraph(f'<font face="SUI-B" color="#3E8FC4">{txt.upper()}</font>', S_PEQ)


def tabela(dados, larguras, com_cabecalho=True):
    corpo = [[Paragraph(str(c).replace("\n", "<br/>"),
                        S_CAB if (com_cabecalho and r == 0) else S_CEL)
              for c in linha] for r, linha in enumerate(dados)]
    # repeatRows: quando a tabela quebra de página, o cabeçalho reaparece em vez
    # de deixar linhas órfãs sem título na página seguinte.
    t = Table(corpo, colWidths=larguras, repeatRows=1 if com_cabecalho else 0)
    est = [("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINHA),
           ("TOPPADDING", (0, 0), (-1, -1), 2.6 * mm),
           ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6 * mm),
           ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm)]
    if com_cabecalho:
        est += [("BACKGROUND", (0, 0), (-1, 0), AZUL3),
                ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white)]
    t.setStyle(TableStyle(est))
    return t


def caixa_legenda(texto):
    linhas = [[Paragraph(p, S_LEG)] for p in texto.split("\n\n")]
    t = Table(linhas, colWidths=[PAG_W - 2 * ML])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f6fa")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACC),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm)]))
    return t


def tira(caminhos, legendas, altura, max_w=None):
    if max_w is None:
        max_w = PAG_W - 2 * ML
    imgs = []
    for c in caminhos:
        im = Image(c)
        im.drawHeight = altura
        im.drawWidth = altura * (im.imageWidth / im.imageHeight)
        imgs.append(im)
    gap = 3 * mm
    total = sum(im.drawWidth for im in imgs) + gap * len(imgs)
    if total > max_w:  # contact sheet largo (Reel) não pode estourar a página
        k = max_w / total
        for im in imgs:
            im.drawHeight *= k
            im.drawWidth *= k
        gap *= k
    t = Table([imgs, [Paragraph(l, S_PEQ) for l in legendas]],
              colWidths=[im.drawWidth + gap for im in imgs])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 1), (-1, 1), 2)]))
    return t


def build(caminho_pauta):
    global _PAUTA
    with open(caminho_pauta, encoding="utf-8") as fh:
        pauta = json.load(fh)
    _PAUTA = pauta
    pasta = pauta["pasta_saida"]
    saida = os.path.join(pasta, f"GUIA_PUBLICACAO_{pauta['data']}.pdf")

    doc = BaseDocTemplate(saida, pagesize=A4, leftMargin=ML, rightMargin=ML,
                          topMargin=20 * mm, bottomMargin=18 * mm,
                          title="Guia de publicação Instagram — AJ TopoGeo",
                          author="AJ TopoGeo")
    doc.addPageTemplates([PageTemplate(
        id="p", frames=[Frame(ML, 18 * mm, PAG_W - 2 * ML, PAG_H - 38 * mm)],
        onPage=_cabecalho)])

    E = [rotulo(pauta.get("subtitulo", pauta["servico"])), Spacer(1, 2 * mm),
         Paragraph("O que publicar e como", H1), Spacer(1, 1 * mm),
         Paragraph(pauta.get("resumo", ""), S), Spacer(1, 5 * mm)]

    linhas = [["Peça", "Formato", "Arquivos", "Publicar em"]]
    for p in pauta["pecas"]:
        if p["formato"] == "carrossel":
            fmt = f"Carrossel\n{len(p['cards'])} cards 1080×1350"
            arq = f"{p['id']}_CARD_1_… a _{len(p['cards'])}_…"
        else:
            fmt = "Reel\n1080×1920"
            arq = f"{p['id']}_REEL.mp4\n+ capa {p['id']}_CAPA_REEL.jpg"
        linhas.append([f"{p['id']} — {p.get('eixo','')}\n{p.get('titulo','')}",
                       fmt, arq, p.get("quando", "")])
    E.append(tabela(linhas, [42 * mm, 30 * mm, 68 * mm, 24 * mm]))

    if pauta.get("antes_de_subir"):
        E += [Spacer(1, 5 * mm), Paragraph("Antes de subir qualquer peça", H2),
              tabela([["Verificar", "Detalhe"]] +
                     [[i["item"], i["detalhe"]] for i in pauta["antes_de_subir"]],
                     [40 * mm, 134 * mm])]

    for p in pauta["pecas"]:
        E.append(PageBreak())
        E += [rotulo(f"{p['id']} · {p['formato']} · eixo {p.get('eixo','')}"),
              Spacer(1, 1.5 * mm), Paragraph(p.get("titulo", ""), H1),
              Spacer(1, 3 * mm)]

        if p["formato"] == "carrossel":
            arqs, legs = [], []
            for i, c in enumerate(p["cards"], 1):
                arqs.append(os.path.join(pasta,
                            f"{p['id']}_CARD_{i}_{c.get('slug','card')}.jpg"))
                legs.append(f"{i} {c.get('rotulo_curto', '')}".strip())
            altura = 48 * mm if len(arqs) <= 4 else 42 * mm
            E.append(tira(arqs, legs, altura))
        else:
            capa = os.path.join(pasta, f"{p['id']}_CAPA_REEL.jpg")
            itens, legs = [capa], ["capa (upload separado)"]
            tiraimg = os.path.join(pasta, f"{p['id']}_cenas.jpg")
            if os.path.exists(tiraimg):
                itens.append(tiraimg)
                legs.append("cenas do vídeo montado")
            E.append(tira(itens, legs, 46 * mm))

        E += [Spacer(1, 5 * mm), Paragraph("Legenda", H2),
              caixa_legenda(p["legenda"]), Spacer(1, 4 * mm),
              Paragraph("Hashtags", H2),
              Paragraph(" ".join(p["hashtags"]), S_TAG)]

        if p["formato"] == "reel" and any(c.get("fala") for c in p.get("cenas", [])):
            # Reel narrado: o texto da locução é conteúdo aprovável, não detalhe
            # de produção - quem publica precisa ler o que a voz diz antes de subir.
            cfg = p.get("narracao") or {}
            voz = cfg.get("voz", "pt-BR-AntonioNeural")
            rate = cfg.get("rate", "+7%")
            # KeepTogether: o roteiro é lido de uma vez, comparando cena a cena.
            # Sem isso a tabela quebra e sobra uma linha órfã na página seguinte.
            E += [Spacer(1, 4 * mm),
                  KeepTogether([
                      Paragraph("Roteiro da locução", H2),
                      Paragraph(f"Voz neural {voz}, velocidade {rate}, som "
                                f"ambiente de campo abaixado por baixo da voz. "
                                f"Sem música: se quiser uma batida, suba por "
                                f"cima na edição do Instagram.", S_PEQ),
                      Spacer(1, 2 * mm),
                      tabela([["Cena", "Legenda na tela", "O que a voz diz"]] +
                             [[str(i), c.get("texto", "—") or "—",
                               c.get("fala", "—") or "—"]
                              for i, c in enumerate(p["cenas"], 1)],
                             [12 * mm, 48 * mm, 114 * mm])])]

        if p["formato"] == "reel" and p.get("passos"):
            E += [Spacer(1, 4 * mm), Paragraph("Como subir", H2),
                  tabela([["Passo", "O que fazer"]] +
                         [[str(i), t] for i, t in enumerate(p["passos"], 1)],
                         [14 * mm, 160 * mm])]
        if p.get("montagem"):
            # mantém título e parágrafo juntos: evita a linha órfã numa página
            # quase em branco quando a observação é longa (caso do Reel).
            E += [Spacer(1, 5 * mm),
                  KeepTogether([Paragraph("Observações de montagem", H2),
                                Paragraph(p["montagem"], S)])]

    E.append(PageBreak())
    E += [rotulo("regras da casa"), Spacer(1, 1.5 * mm),
          Paragraph("Sigilo do cliente e pendências", H1), Spacer(1, 3 * mm)]
    if pauta.get("fora"):
        E += [Paragraph("O que ficou de fora, e por quê", H2),
              tabela([["Material", "Motivo"]] +
                     [[i["material"], i["motivo"]] for i in pauta["fora"]],
                     [45 * mm, 129 * mm])]
    if pauta.get("liberado"):
        E += [Spacer(1, 5 * mm),
              KeepTogether([Paragraph("O que foi conferido e está liberado", H2),
                            Paragraph(pauta["liberado"], S)])]
    if pauta.get("pendencias"):
        # mesmo motivo do "Onde está tudo": sem KeepTogether o título "Pendências"
        # fica sozinho no pé da página e a tabela abre na seguinte sem seção.
        E += [Spacer(1, 5 * mm),
              KeepTogether([Paragraph("Pendências", H2),
                            tabela([["Item", "Situação"]] +
                                   [[i["item"], i["situacao"]]
                                    for i in pauta["pendencias"]],
                                   [45 * mm, 129 * mm])])]
    if pauta.get("onde"):
        # KeepTogether: sem isso o título fica sozinho no pé da página de sigilo
        # e a tabela abre na página seguinte, órfã de cabeçalho de seção.
        E += [Spacer(1, 6 * mm),
              KeepTogether([Paragraph("Onde está tudo", H2),
                            tabela([["Pasta", "Conteúdo"]] +
                                   [[i["pasta"], i["conteudo"]]
                                    for i in pauta["onde"]],
                                   [58 * mm, 116 * mm])])]

    doc.build(E)
    print("gerado:", saida)
    return saida


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python guia_pdf.py pauta.json")
    build(sys.argv[1])
