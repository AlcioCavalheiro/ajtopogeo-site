#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderiza o PDF de andamento da rotina de cobrança.

Entrada: um dossiê JSON (gerado a cada semana com a narrativa já redigida).
Saída:   PDF com a tabela de todas as OS abertas (com andamento) e cards de
         destaque para as OS que precisam de atenção.

Uso:
    py rotinas/relatorio_pdf.py dossie.json saida.pdf

O layout segue a identidade do gestor/gerar_relatorio_os.py (azul #0d4fa0).
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

AZUL = colors.HexColor("#0d4fa0")
CINZA_BORDA = colors.HexColor("#CCCCCC")
CINZA_TXT = colors.HexColor("#444444")
VERMELHO = colors.HexColor("#A32D2D")
VERMELHO_BG = colors.HexColor("#FCEBEB")
AMBAR = colors.HexColor("#854F0B")
AMBAR_BG = colors.HexColor("#FAEEDA")
VERDE = colors.HexColor("#27500A")
CINZA_BG = colors.HexColor("#F1EFE8")


def brl(v):
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rt(texto):
    """Escapa para o mini-XML do reportlab e converte quebras de linha.

    Estrito: use em tudo que vem do banco (nome de cliente, obs, status).
    Um '&' ou '<' num nome de cliente quebraria o parser do reportlab.
    """
    return escape(str(texto or "")).replace("\n", "<br/>")


# Tags de formatação liberadas nos campos escritos por nós (narrativa do
# relatório). O texto é escapado primeiro e só estas voltam a valer.
_TAGS_OK = ("b", "i", "u")


def rt_rico(texto):
    """Como rt(), mas devolve <b>, <i> e <u> que nós mesmos escrevemos."""
    saida = rt(texto)
    for tag in _TAGS_OK:
        saida = saida.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        saida = saida.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    return saida


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
                                   fontName="Helvetica-Bold", textColor=AZUL,
                                   alignment=2)
    s["corpo"] = ParagraphStyle("corpo", parent=base["Normal"], fontSize=9,
                                textColor=CINZA_TXT, leading=13)
    s["msg"] = ParagraphStyle("msg", parent=base["Normal"], fontSize=9.5,
                              textColor=colors.HexColor("#1a1a18"), leading=15,
                              leftIndent=8, rightIndent=8,
                              spaceBefore=5, spaceAfter=5)
    s["alerta"] = ParagraphStyle("alerta", parent=base["Normal"], fontSize=8.5,
                                 textColor=VERMELHO, leading=12,
                                 leftIndent=6, rightIndent=6, borderPadding=(4, 6, 4, 6))
    s["dica"] = ParagraphStyle("dica", parent=base["Normal"], fontSize=8.5,
                               textColor=AMBAR, leading=12,
                               leftIndent=6, rightIndent=6, borderPadding=(4, 6, 4, 6))
    s["decisao"] = ParagraphStyle("decisao", parent=base["Normal"], fontSize=9,
                                  fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#333333"), leading=13)
    s["th"] = ParagraphStyle("th", parent=base["Normal"], fontSize=7.5,
                             fontName="Helvetica-Bold", textColor=colors.white)
    s["td"] = ParagraphStyle("td", parent=base["Normal"], fontSize=8,
                             textColor=CINZA_TXT, leading=11)
    # A tabela completa tem 8 colunas e 60+ linhas: precisa de corpo menor.
    s["td_mini"] = ParagraphStyle("td_mini", parent=base["Normal"], fontSize=6.6,
                                  textColor=CINZA_TXT, leading=8.4)
    s["metric_v"] = ParagraphStyle("metric_v", parent=base["Normal"], fontSize=16,
                                   fontName="Helvetica-Bold", textColor=AZUL,
                                   alignment=TA_CENTER)
    s["metric_l"] = ParagraphStyle("metric_l", parent=base["Normal"], fontSize=7.5,
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
        (brl(resumo.get("recebido", 0)), "JÁ RECEBIDO"),
        (brl(resumo.get("em_aberto", 0)), "EM ABERTO A COBRAR"),
    ]
    t = Table(
        [[Paragraph(rt(v), st["metric_v"]) for v, _ in itens],
         [Paragraph(rt(l), st["metric_l"]) for _, l in itens]],
        colWidths=[largura / 4.0] * 4,
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


def tabela_os(lista_os, largura, st):
    cabecalho = ["OS", "Serviço / Imóvel", "Valor", "Dias", "Status"]
    linhas = [[Paragraph(rt(c), st["th"]) for c in cabecalho]]
    for o in lista_os:
        linhas.append([
            Paragraph(rt(o.get("numero")), st["td"]),
            Paragraph(rt(o.get("desc")), st["td"]),
            Paragraph(rt(brl(o.get("valor", 0))), st["td"]),
            Paragraph(rt(o.get("dias")), st["td"]),
            Paragraph(rt(o.get("status")), st["td"]),
        ])
    larguras = [largura * p for p in (0.15, 0.40, 0.15, 0.08, 0.22)]
    t = Table(linhas, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F5")]),
        ("GRID", (0, 0), (-1, -1), 0.4, CINZA_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def tabela_completa(linhas_os, largura, st):
    """Todas as OS em aberto, com contratado / recebido / em aberto / andamento."""
    cab = ["#", "OS", "Cliente", "Contratado", "Recebido", "Em aberto", "Dias", "Status", "Andamento"]
    linhas = [[Paragraph(rt(c), st["th"]) for c in cab]]
    estilo_extra = []
    for i, o in enumerate(linhas_os, 1):
        quitada = bool(o.get("quitada"))
        aberto = brl(o.get("em_aberto", 0)) + (" ✓" if quitada else "")
        linhas.append([
            Paragraph(rt(i), st["td_mini"]),
            Paragraph(rt(o.get("numero")), st["td_mini"]),
            Paragraph(rt((o.get("cliente") or "")[:30]), st["td_mini"]),
            Paragraph(rt(brl(o.get("contratado", 0))), st["td_mini"]),
            Paragraph(rt(brl(o.get("recebido", 0))), st["td_mini"]),
            Paragraph(f"<b>{rt(aberto)}</b>", st["td_mini"]),
            Paragraph(rt(o.get("dias")), st["td_mini"]),
            Paragraph(rt(o.get("status")), st["td_mini"]),
            Paragraph(rt((o.get("andamento") or "—")[:180]), st["td_mini"]),
        ])
        if quitada:
            estilo_extra.append(("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#8A8A85")))

    larguras = [largura * p for p in
                (0.025, 0.09, 0.155, 0.085, 0.08, 0.09, 0.04, 0.125, 0.31)]
    t = Table(linhas, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F5")]),
        ("GRID", (0, 0), (-1, -1), 0.3, CINZA_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ] + estilo_extra))
    return t


def tabela_soltos(recs, largura, st):
    """Recebimentos sem os_id — não abatidos de nenhuma OS."""
    cab = ["Descrição", "Valor", "Data"]
    linhas = [[Paragraph(rt(c), st["th"]) for c in cab]]
    for r in recs:
        linhas.append([
            Paragraph(rt(r.get("descricao") or "—"), st["td"]),
            Paragraph(rt(brl(r.get("valor", 0))), st["td"]),
            Paragraph(rt(r.get("data") or "—"), st["td"]),
        ])
    t = Table(linhas, colWidths=[largura * 0.6, largura * 0.2, largura * 0.2], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AMBAR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AMBAR_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, CINZA_BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def caixa_andamento(texto, largura, st):
    """O andamento atual da OS, destacado — estado dos fatos, não texto para enviar."""
    p = Paragraph(rt(texto), st["msg"])
    t = Table([[p]], colWidths=[largura])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBFBF9")),
        ("BOX", (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, AZUL),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def caixa_aviso(texto, largura, st, tipo="alerta"):
    estilo = st["alerta"] if tipo == "alerta" else st["dica"]
    fundo = VERMELHO_BG if tipo == "alerta" else AMBAR_BG
    prefixo = "<b>NÃO CONFIRMADO — </b>" if tipo == "alerta" else "<b>DICA — </b>"
    t = Table([[Paragraph(prefixo + rt_rico(texto), estilo)]], colWidths=[largura])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fundo),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def linha_decisao(largura, st):
    # Helvetica do reportlab é Latin-1: nada de U+2610, sairia quadrado preto.
    marcas = ("[   ]  Feito     "
              "[   ]  Em andamento     "
              "[   ]  Bloqueado     "
              "[   ]  Não é caso")
    t = Table([[Paragraph(rt(marcas), st["decisao"])]], colWidths=[largura])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF3FA")),
        ("BOX", (0, 0), (-1, -1), 0.5, AZUL),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def card_cobranca(i, c, largura, st):
    partes = []
    cabecalho = Table(
        [[Paragraph(f"<b>{i}. {rt(c.get('titulo'))}</b>", st["card_tit"]),
          Paragraph(rt(brl(c.get("valor", 0))), st["card_val"])]],
        colWidths=[largura * 0.68, largura * 0.32],
    )
    cabecalho.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    partes.append(cabecalho)

    if c.get("contato"):
        partes.append(Paragraph(f"<b>Contato:</b> {rt(c['contato'])}", st["corpo"]))
    partes.append(Spacer(1, 4))

    if c.get("os"):
        partes.append(tabela_os(c["os"], largura, st))
        partes.append(Spacer(1, 5))

    if c.get("contexto"):
        partes.append(Paragraph(rt_rico(c["contexto"]), st["corpo"]))
        partes.append(Spacer(1, 4))

    if c.get("andamento"):
        partes.append(caixa_andamento(c["andamento"], largura, st))

    if c.get("alerta"):
        partes.append(Spacer(1, 4))
        partes.append(caixa_aviso(c["alerta"], largura, st, "alerta"))

    if c.get("dica"):
        partes.append(Spacer(1, 4))
        partes.append(caixa_aviso(c["dica"], largura, st, "dica"))

    partes.append(Spacer(1, 14))
    return partes


def card_interna(letra, p, largura, st):
    partes = []
    cab = Table(
        [[Paragraph(f"<b>{letra}. {rt(p.get('titulo'))}</b>", st["card_tit"]),
          Paragraph(rt(brl(p.get("valor", 0))), st["card_val"])]],
        colWidths=[largura * 0.68, largura * 0.32],
    )
    cab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    partes.append(cab)
    if p.get("os"):
        partes.append(tabela_os(p["os"], largura, st))
        partes.append(Spacer(1, 4))
    if p.get("texto"):
        partes.append(Paragraph(rt_rico(p["texto"]), st["corpo"]))
    partes.append(Spacer(1, 5))

    acao = Table([[Paragraph("<b>Ação:</b> " + rt_rico(p.get("acao", "")), st["corpo"])]],
                 colWidths=[largura])
    acao.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    partes.append(acao)
    partes.append(Spacer(1, 6))
    partes.append(linha_decisao(largura, st))
    partes.append(Spacer(1, 14))
    return partes


def gerar(dossie, saida):
    doc = SimpleDocTemplate(
        str(saida), pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title="Cobranca de OS paradas — AJ TopoGeo", author="AJ TopoGeo",
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
    story.append(Paragraph("Cobrança de OS paradas — relatório de decisão", st["sub"]))
    story.append(Paragraph(f"Gerado em {data_br}", st["sub"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=AZUL, spaceAfter=10))

    story.append(bloco_metricas(dossie.get("resumo", {}), largura, st))
    story.append(Spacer(1, 6))

    if dossie.get("nota_topo"):
        story.append(Paragraph(rt_rico(dossie["nota_topo"]), st["corpo"]))
    story.append(Spacer(1, 10))

    cobrancas = dossie.get("cobrancas", [])
    if cobrancas:
        story.append(faixa_secao(
            f"OS EM DESTAQUE  ({len(cobrancas)})", AZUL, largura, st))
        story.append(Spacer(1, 8))
        for i, c in enumerate(cobrancas, 1):
            story.append(KeepTogether(card_cobranca(i, c, largura, st)))

    internas = dossie.get("internas", [])
    if internas:
        story.append(faixa_secao(
            f"PENDÊNCIAS INTERNAS  ({len(internas)})  —  não são cobrança",
            colors.HexColor("#5A5A55"), largura, st))
        story.append(Spacer(1, 8))
        for letra, p in zip("ABCDEFGHIJ", internas):
            story.append(KeepTogether(card_interna(letra, p, largura, st)))

    soltos = dossie.get("recebimentos_sem_os", [])
    if soltos:
        story.append(PageBreak())
        total_soltos = sum(float(r.get("valor") or 0) for r in soltos)
        story.append(faixa_secao(
            f"RECEBIMENTOS SEM OS VINCULADA  ({len(soltos)}  ·  {brl(total_soltos)})",
            AMBAR, largura, st))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Estes recebimentos <b>não foram descontados de nenhuma OS</b> porque não "
            "têm vínculo no banco — estão ligados só por texto livre. Se algum "
            "corresponder a uma OS da lista, o valor em aberto dela está "
            "<b>superestimado</b>. Concilie antes de cobrar.", st["corpo"]))
        story.append(Spacer(1, 6))
        story.append(tabela_soltos(soltos, largura, st))
        story.append(Spacer(1, 12))

    todas = dossie.get("todas_os", [])
    if todas:
        if not soltos:
            story.append(PageBreak())
        story.append(faixa_secao(
            f"TODAS AS OS EM ABERTO  ({len(todas)})", AZUL, largura, st))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Ordenadas por prioridade de cobrança (valor em aberto, tempo parado e "
            "proximidade de conclusão). A coluna Andamento traz o último registro da "
            "OS no Gestor ou, na falta dele, o motivo provável inferido do status. "
            "Linhas em cinza com ✓ estão quitadas — a pendência delas é técnica, "
            "não financeira.", st["corpo"]))
        story.append(Spacer(1, 6))
        story.append(tabela_completa(todas, largura, st))
        story.append(Spacer(1, 12))

    obs = dossie.get("observacoes", [])
    if obs:
        story.append(PageBreak())
        story.append(faixa_secao("OBSERVAÇÕES DA RODADA", AZUL, largura, st))
        story.append(Spacer(1, 8))
        for o in obs:
            story.append(Paragraph(f"<b>{rt(o.get('titulo'))}</b>", st["card_tit"]))
            story.append(Paragraph(rt_rico(o.get("texto")), st["corpo"]))
            story.append(Spacer(1, 8))

    prox = dossie.get("proxima_semana", [])
    if prox:
        story.append(Spacer(1, 6))
        story.append(faixa_secao("CONFERIR NA PRÓXIMA RODADA",
                                 colors.HexColor("#5A5A55"), largura, st))
        story.append(Spacer(1, 8))
        for n, item in enumerate(prox, 1):
            story.append(Paragraph(f"{n}. {rt(item)}", st["corpo"]))
            story.append(Spacer(1, 3))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZA_BORDA, spaceBefore=6))
    story.append(Paragraph(
        f"AJ TopoGeo  |  gerado em {data_br}  |  "
        f"relatório de andamento — nenhum contato com cliente foi feito a partir daqui",
        st["rodape"]))

    doc.build(story)
    return saida


def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: py rotinas/relatorio_pdf.py <dossie.json> <saida.pdf>")
    origem, destino = Path(sys.argv[1]), Path(sys.argv[2])
    if not origem.exists():
        sys.exit(f"Dossiê não encontrado: {origem}")
    dossie = json.loads(origem.read_text(encoding="utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    gerar(dossie, destino)
    print(f"PDF gerado: {destino}")


if __name__ == "__main__":
    main()
