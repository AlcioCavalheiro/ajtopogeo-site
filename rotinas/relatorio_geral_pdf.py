#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderiza o PDF do relatório geral de OS abertas e orçamentos.

Entrada: o dossiê JSON gerado por rotinas/relatorio_geral.py (--dossie).
Saída:   PDF com uma ficha completa por OS aberta e a tabela dos orçamentos
         com status Enviado (aguardando resposta do cliente).

Uso:
    py rotinas/relatorio_geral_pdf.py dossie.json saida.pdf

O layout segue a identidade do gestor/gerar_relatorio_os.py (azul #0d4fa0),
mesma paleta de rotinas/relatorio_pdf.py.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

AZUL = colors.HexColor("#0d4fa0")
AZUL_STATUS = colors.HexColor("#5478A8")
CINZA_BORDA = colors.HexColor("#CCCCCC")
CINZA_TXT = colors.HexColor("#444444")
CINZA_BG = colors.HexColor("#F7F7F5")
AMBAR = colors.HexColor("#854F0B")


def brl(v):
    return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rt(texto):
    return escape(str(texto or "")).replace("\n", "<br/>")


def estilos():
    base = getSampleStyleSheet()
    s = {}
    s["titulo"] = ParagraphStyle("titulo", parent=base["Normal"], fontSize=22,
                                 fontName="Helvetica-Bold", textColor=AZUL, spaceAfter=4)
    s["sub"] = ParagraphStyle("sub", parent=base["Normal"], fontSize=11,
                              textColor=colors.HexColor("#555555"), spaceAfter=2)
    s["secao"] = ParagraphStyle("secao", parent=base["Normal"], fontSize=12,
                                fontName="Helvetica-Bold", textColor=colors.white,
                                leftIndent=6, spaceBefore=2, spaceAfter=2)
    s["card_tit"] = ParagraphStyle("card_tit", parent=base["Normal"], fontSize=11,
                                   fontName="Helvetica-Bold",
                                   textColor=colors.HexColor("#1a1a18"), spaceAfter=1)
    s["card_val"] = ParagraphStyle("card_val", parent=base["Normal"], fontSize=11,
                                   fontName="Helvetica-Bold", textColor=AZUL, alignment=2)
    s["corpo"] = ParagraphStyle("corpo", parent=base["Normal"], fontSize=9,
                                textColor=CINZA_TXT, leading=13)
    s["hist"] = ParagraphStyle("hist", parent=base["Normal"], fontSize=8.3,
                               textColor=CINZA_TXT, leading=12, leftIndent=4)
    s["th"] = ParagraphStyle("th", parent=base["Normal"], fontSize=7.5,
                             fontName="Helvetica-Bold", textColor=colors.white)
    s["td"] = ParagraphStyle("td", parent=base["Normal"], fontSize=8,
                             textColor=CINZA_TXT, leading=11)
    s["metric_v"] = ParagraphStyle("metric_v", parent=base["Normal"], fontSize=15,
                                   fontName="Helvetica-Bold", textColor=AZUL, alignment=TA_CENTER)
    s["metric_l"] = ParagraphStyle("metric_l", parent=base["Normal"], fontSize=7,
                                   textColor=colors.HexColor("#666666"), alignment=TA_CENTER)
    s["rodape"] = ParagraphStyle("rodape", parent=base["Normal"], fontSize=8,
                                 textColor=colors.HexColor("#888888"), alignment=TA_CENTER)
    return s


def faixa_secao(texto, cor, largura, st):
    t = Table([[Paragraph(rt(texto), st["secao"])]], colWidths=[largura])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def bloco_metricas(resumo, largura, st):
    itens = [
        (str(resumo.get("os_abertas", "—")), "OS EM ABERTO"),
        (brl(resumo.get("contratado", 0)), "CONTRATADO"),
        (brl(resumo.get("em_aberto", 0)), "EM ABERTO A COBRAR"),
        (str(resumo.get("orcamentos_enviados", "—")), "ORÇ. ENVIADOS"),
        (brl(resumo.get("valor_enviados", 0)), "VALOR ENVIADO"),
    ]
    t = Table(
        [[Paragraph(rt(v), st["metric_v"]) for v, _ in itens],
         [Paragraph(rt(l), st["metric_l"]) for _, l in itens]],
        colWidths=[largura / len(itens)] * len(itens),
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F9FC")),
        ("BOX", (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E8EE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    return t


def card_os(f, largura, st):
    partes = []
    cab = Table(
        [[Paragraph(f"<b>{rt(f.get('numero'))} — {rt(f.get('cliente'))}</b>", st["card_tit"]),
          Paragraph(rt(brl(f.get("valor_aberto", 0))) + (" ✓" if f.get("quitada") else ""),
                    st["card_val"])]],
        colWidths=[largura * 0.68, largura * 0.32],
    )
    cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    partes.append(cab)

    linha1 = " · ".join(x for x in (
        f.get("tipo"), f"parada há {f.get('dias_parada')} dias",
    ) if x)
    partes.append(Paragraph(rt(linha1), st["corpo"]))

    detalhe = []
    if f.get("obra"):
        detalhe.append("Obra: " + f["obra"] + (f" ({f['municipio']})" if f.get("municipio") else ""))
    if f.get("responsavel"):
        detalhe.append("Responsável: " + f["responsavel"])
    if f.get("orcamento_numero"):
        detalhe.append("Origem: orçamento " + f["orcamento_numero"])
    if detalhe:
        partes.append(Paragraph(rt(" · ".join(detalhe)), st["corpo"]))

    financeiro = (f"Contratado {brl(f.get('valor_total', 0))} · "
                  f"recebido {brl(f.get('recebido', 0))} · "
                  f"<b>em aberto {brl(f.get('valor_aberto', 0))}</b>")
    partes.append(Paragraph(financeiro, st["corpo"]))

    contato = " · ".join(x for x in (f.get("telefone"), f.get("email")) if x)
    if contato:
        partes.append(Paragraph("Contato: " + rt(contato), st["corpo"]))

    if f.get("historico"):
        partes.append(Spacer(1, 3))
        partes.append(Paragraph("<b>Andamento:</b>", st["corpo"]))
        for h in f["historico"]:
            prefixo = rt(h.get("quando", ""))
            usuario = f" ({rt(h['usuario'])})" if h.get("usuario") else ""
            partes.append(Paragraph(f"{prefixo} — {rt(h.get('txt', ''))}{usuario}", st["hist"]))
    if f.get("obs"):
        partes.append(Spacer(1, 3))
        partes.append(Paragraph("<b>Obs:</b> " + rt(f["obs"]), st["corpo"]))

    partes.append(Spacer(1, 10))
    linha = Table([[""]], colWidths=[largura])
    linha.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, CINZA_BORDA)]))
    partes.append(linha)
    partes.append(Spacer(1, 8))
    return partes


def tabela_orcamentos(lista, largura, st, mostrar_dias=False):
    cab = ["Número", "Cliente", "Valor", "Obra / Local", "Data"]
    if mostrar_dias:
        cab.append("Dias")
    linhas = [[Paragraph(rt(c), st["th"]) for c in cab]]
    for f in lista:
        local = f.get("obra") or f.get("local_endereco") or "—"
        linha = [
            Paragraph(rt(f.get("numero")), st["td"]),
            Paragraph(rt(f.get("cliente")), st["td"]),
            Paragraph(rt(brl(f.get("valor_total", 0))), st["td"]),
            Paragraph(rt(local), st["td"]),
            Paragraph(rt(f.get("data_emissao") or "—"), st["td"]),
        ]
        if mostrar_dias:
            dias_txt = f"{f.get('dias_desde_envio', 0)} dias"
            if f.get("vencido"):
                dias_txt += ' <font color="#A32D2D"><b>vencido</b></font>'
            linha.append(Paragraph(dias_txt, st["td"]))
        if f.get("os_gerada"):
            linha[1] = Paragraph(rt(f.get("cliente")) + f"<br/><i>OS gerada: {rt(f['os_gerada'])}</i>",
                                 st["td"])
        linhas.append(linha)

    n = len(cab)
    if mostrar_dias:
        larguras = [largura * p for p in (0.13, 0.22, 0.11, 0.26, 0.10, 0.18)]
    else:
        larguras = [largura * p for p in (0.15, 0.32, 0.15, 0.28, 0.10)]
    t = Table(linhas, colWidths=larguras[:n], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, CINZA_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def gerar(dossie, saida):
    doc = SimpleDocTemplate(
        str(saida), pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title="Relatório geral de OS e orçamentos — AJ TopoGeo", author="AJ TopoGeo",
    )
    largura = doc.width
    st = estilos()
    story = []

    data_txt = dossie.get("data") or datetime.now().strftime("%Y-%m-%d")
    try:
        data_br = datetime.strptime(data_txt, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        data_br = data_txt

    story.append(Paragraph("AJ TopoGeo", st["titulo"]))
    story.append(Paragraph("Relatório geral — OS abertas e orçamentos", st["sub"]))
    story.append(Paragraph(f"Gerado em {data_br}", st["sub"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=AZUL, spaceAfter=10))

    story.append(bloco_metricas(dossie.get("resumo", {}), largura, st))
    story.append(Spacer(1, 12))

    os_por_status = dossie.get("os_por_status", {})
    total_os = sum(len(lista) for lista in os_por_status.values())
    story.append(faixa_secao(f"OS EM ABERTO  ({total_os})", AZUL, largura, st))
    story.append(Spacer(1, 8))
    for status, lista in os_por_status.items():
        total_status = sum(f.get("valor_aberto", 0) for f in lista)
        story.append(faixa_secao(
            f"{status.upper()}  ({len(lista)} · {brl(total_status)} em aberto)",
            AZUL_STATUS, largura, st))
        story.append(Spacer(1, 6))
        for f in lista:
            story.append(KeepTogether(card_os(f, largura, st)))
        story.append(Spacer(1, 4))

    enviados = dossie.get("orcamentos_enviados", [])
    if enviados:
        total = sum(f.get("valor_total", 0) for f in enviados)
        story.append(PageBreak())
        story.append(faixa_secao(f"ORÇAMENTOS ENVIADOS  ({len(enviados)} · {brl(total)})",
                                 AMBAR, largura, st))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Aguardando resposta do cliente. \"Vencido\" quer dizer que passou a data de "
            "validade sem retorno — não é recusa.", st["corpo"]))
        story.append(Spacer(1, 6))
        story.append(tabela_orcamentos(enviados, largura, st, mostrar_dias=True))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZA_BORDA, spaceBefore=6))
    story.append(Paragraph(
        f"AJ TopoGeo  |  gerado em {data_br}  |  relatório de acompanhamento — "
        f"nenhum contato com cliente foi feito a partir daqui", st["rodape"]))

    doc.build(story)
    return saida


def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: py rotinas/relatorio_geral_pdf.py <dossie.json> <saida.pdf>")
    origem, destino = Path(sys.argv[1]), Path(sys.argv[2])
    if not origem.exists():
        sys.exit(f"Dossiê não encontrado: {origem}")
    dossie = json.loads(origem.read_text(encoding="utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    gerar(dossie, destino)
    print(f"PDF gerado: {destino}")


if __name__ == "__main__":
    main()
