#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderiza o PDF da rotina semanal de Analytics + Search Console.

Entrada: o dossiê JSON gerado por rotinas/coletar_analytics_gsc.py, já
enriquecido com as chaves "analise" (destaques e oportunidades) e "decisoes"
(o que foi alterado no site nesta rodada) — essas duas quem preenche é a
análise, não o coletor.

Uso:
    py rotinas/analise_analytics_pdf.py dossie.json saida.pdf

Mesma paleta de rotinas/relatorio_geral_pdf.py (azul #0d4fa0).
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
VERDE = colors.HexColor("#1B7A3D")
VERMELHO = colors.HexColor("#A32D2D")
AMBAR = colors.HexColor("#854F0B")


def rt(texto):
    return escape(str(texto or "")).replace("\n", "<br/>")


def pct(v):
    return f"{v:.1f}%"


def variacao(atual, anterior):
    if not anterior:
        return None
    return (atual - anterior) / anterior * 100


def cor_variacao_hex(v, menor_melhor=False):
    if v is None:
        return "#444444"
    if menor_melhor:
        v = -v
    if v > 0:
        return "#1B7A3D"
    if v < 0:
        return "#A32D2D"
    return "#444444"


def fmt_delta(atual, anterior, casas=0, sufixo="", menor_melhor=False):
    # menor_melhor: para posição média, cair é bom (verde).
    v = variacao(atual, anterior)
    seta = "" if v is None else ("▲" if v > 0 else ("▼" if v < 0 else "•"))
    delta_txt = "" if v is None else f' <font color="{cor_variacao_hex(v, menor_melhor)}">{seta} {abs(v):.0f}%</font>'
    base = f"{atual:,.{casas}f}{sufixo}".replace(",", "_").replace(".", ",").replace("_", ".")
    return base + delta_txt


def estilos():
    base = getSampleStyleSheet()
    s = {}
    s["titulo"] = ParagraphStyle("titulo", parent=base["Normal"], fontSize=22, leading=27,
                                 fontName="Helvetica-Bold", textColor=AZUL, spaceAfter=4)
    s["sub"] = ParagraphStyle("sub", parent=base["Normal"], fontSize=11,
                              textColor=colors.HexColor("#555555"), spaceAfter=2)
    s["secao"] = ParagraphStyle("secao", parent=base["Normal"], fontSize=12,
                                fontName="Helvetica-Bold", textColor=colors.white,
                                leftIndent=6, spaceBefore=2, spaceAfter=2)
    s["corpo"] = ParagraphStyle("corpo", parent=base["Normal"], fontSize=9,
                                textColor=CINZA_TXT, leading=13)
    s["bullet"] = ParagraphStyle("bullet", parent=base["Normal"], fontSize=9.3,
                                 textColor=colors.HexColor("#1a1a18"), leading=13,
                                 leftIndent=10, spaceAfter=4)
    s["th"] = ParagraphStyle("th", parent=base["Normal"], fontSize=7.5,
                             fontName="Helvetica-Bold", textColor=colors.white)
    s["td"] = ParagraphStyle("td", parent=base["Normal"], fontSize=8,
                             textColor=CINZA_TXT, leading=11)
    s["metric_v"] = ParagraphStyle("metric_v", parent=base["Normal"], fontSize=14,
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


def bloco_metricas(itens, largura, st):
    # v já vem formatado (fmt_delta produz markup <font> confiável) — não escapar de novo.
    t = Table(
        [[Paragraph(v, st["metric_v"]) for v, _ in itens],
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


def tabela(cabecalho, linhas, larguras_pct, largura, st):
    dados = [[Paragraph(rt(c), st["th"]) for c in cabecalho]]
    dados.extend(linhas)
    t = Table(dados, colWidths=[largura * p for p in larguras_pct], repeatRows=1)
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
        title="Analytics + Search Console semanal — AJ TopoGeo", author="AJ TopoGeo",
    )
    largura = doc.width
    st = estilos()
    story = []

    gerado = dossie.get("gerado_em", datetime.now().strftime("%Y-%m-%d"))
    try:
        gerado_br = datetime.strptime(gerado, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        gerado_br = gerado
    p_atual = dossie.get("periodo_atual", ["", ""])
    p_anterior = dossie.get("periodo_anterior", ["", ""])

    story.append(Paragraph("AJ TopoGeo", st["titulo"]))
    story.append(Paragraph("Radar semanal — Google Analytics + Search Console", st["sub"]))
    story.append(Paragraph(f"Semana de {p_atual[0]} a {p_atual[1]}  ·  "
                            f"comparado com {p_anterior[0]} a {p_anterior[1]}  ·  "
                            f"gerado em {gerado_br}", st["sub"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=AZUL, spaceAfter=10))

    # --- Métricas gerais ---
    ga4_t = dossie.get("ga4", {}).get("totais", {})
    a, b = ga4_t.get("atual", {}), ga4_t.get("anterior", {})
    gsc_t = dossie.get("gsc", {}).get("totais", {})
    ga, gb = gsc_t.get("atual", {}), gsc_t.get("anterior", {})

    story.append(faixa_secao("VISÃO GERAL DA SEMANA", AZUL, largura, st))
    story.append(Spacer(1, 8))
    story.append(bloco_metricas([
        (fmt_delta(a.get("sessions", 0), b.get("sessions", 0)), "SESSÕES (GA4)"),
        (fmt_delta(a.get("totalUsers", 0), b.get("totalUsers", 0)), "USUÁRIOS"),
        (fmt_delta(ga.get("clicks", 0), gb.get("clicks", 0)), "CLIQUES (BUSCA)"),
        (fmt_delta(ga.get("impressions", 0), gb.get("impressions", 0)), "IMPRESSÕES (BUSCA)"),
        (fmt_delta(ga.get("position", 0) or 0, gb.get("position", 0) or 0, casas=1,
                   menor_melhor=True), "POSIÇÃO MÉDIA"),
    ], largura, st))
    story.append(Spacer(1, 4))
    story.append(Paragraph("▲/▼ comparado à semana anterior. Posição: menor é melhor "
                            "(1ª posição = topo da busca).", st["corpo"]))
    story.append(Spacer(1, 12))

    # --- Eventos de conversão ---
    eventos = dossie.get("ga4", {}).get("eventos_conversao", {})
    ea, eb = eventos.get("atual", {}), eventos.get("anterior", {})
    if ea or eb:
        story.append(faixa_secao("CONTATOS GERADOS PELO SITE (cliques em WhatsApp/e-mail/formulário)",
                                 AZUL_STATUS, largura, st))
        story.append(Spacer(1, 8))
        nomes = sorted(set(ea) | set(eb))
        itens = [(fmt_delta(ea.get(n, 0), eb.get(n, 0)), n.replace("cta_click_", "clique ").replace("lead_formulario", "formulário")) for n in nomes]
        if itens:
            story.append(bloco_metricas(itens[:5], largura, st))
        story.append(Spacer(1, 12))

    # --- Destaques da análise ---
    analise = dossie.get("analise", {})
    destaques = analise.get("destaques", [])
    if destaques:
        story.append(faixa_secao("DESTAQUES DA SEMANA", AZUL, largura, st))
        story.append(Spacer(1, 8))
        for d in destaques:
            story.append(Paragraph("• " + rt(d), st["bullet"]))
        story.append(Spacer(1, 8))

    # --- Páginas mais vistas (GA4) ---
    paginas = dossie.get("ga4", {}).get("paginas_mais_vistas", {})
    pa, pb = paginas.get("atual", {}), paginas.get("anterior", {})
    if pa:
        story.append(PageBreak())
        story.append(faixa_secao("PÁGINAS MAIS VISITADAS", AZUL, largura, st))
        story.append(Spacer(1, 8))
        top = sorted(pa.items(), key=lambda kv: kv[1].get("screenPageViews", 0), reverse=True)[:12]
        linhas = []
        for caminho, dados in top:
            anterior = pb.get(caminho, {}).get("screenPageViews", 0)
            linhas.append([
                Paragraph(rt(caminho), st["td"]),
                Paragraph(fmt_delta(dados.get("screenPageViews", 0), anterior), st["td"]),
            ])
        story.append(tabela(["Página", "Visualizações"], linhas, [0.72, 0.28], largura, st))
        story.append(Spacer(1, 12))

    # --- Consultas de busca (GSC) ---
    consultas = dossie.get("gsc", {}).get("consultas", {})
    ca, cb = consultas.get("atual", {}), consultas.get("anterior", {})
    if ca:
        story.append(faixa_secao("PRINCIPAIS BUSCAS NO GOOGLE", AZUL, largura, st))
        story.append(Spacer(1, 8))
        top = sorted(ca.items(), key=lambda kv: kv[1].get("clicks", 0), reverse=True)[:15]
        linhas = []
        for consulta, dados in top:
            ant = cb.get(consulta, {})
            linhas.append([
                Paragraph(rt(consulta), st["td"]),
                Paragraph(fmt_delta(dados.get("clicks", 0), ant.get("clicks", 0)), st["td"]),
                Paragraph(f"{dados.get('impressions', 0):,.0f}".replace(",", "."), st["td"]),
                Paragraph(f"{dados.get('position', 0):.1f}", st["td"]),
            ])
        story.append(tabela(["Consulta", "Cliques", "Impressões", "Posição"], linhas,
                            [0.46, 0.18, 0.18, 0.18], largura, st))
        story.append(Spacer(1, 12))

    # --- Oportunidades identificadas ---
    oportunidades = analise.get("oportunidades", [])
    if oportunidades:
        story.append(PageBreak())
        story.append(faixa_secao(f"OPORTUNIDADES IDENTIFICADAS  ({len(oportunidades)})", AMBAR, largura, st))
        story.append(Spacer(1, 8))
        for o in oportunidades:
            partes = [Paragraph(f"<b>{rt(o.get('titulo', ''))}</b>", st["corpo"])]
            if o.get("detalhe"):
                partes.append(Paragraph(rt(o["detalhe"]), st["corpo"]))
            partes.append(Spacer(1, 6))
            story.append(KeepTogether(partes))

    # --- Saúde técnica do site ---
    saude = dossie.get("saude_site", {})
    problemas = saude.get("problemas", [])
    story.append(faixa_secao(
        f"SAÚDE TÉCNICA DO SITE  ({saude.get('total_urls', 0)} páginas checadas, "
        f"{len(problemas)} problema(s))",
        VERMELHO if problemas else VERDE, largura, st))
    story.append(Spacer(1, 8))
    if problemas:
        linhas = [[Paragraph(rt(p["url"]), st["td"]), Paragraph(rt(p["tipo"]), st["td"]),
                   Paragraph(rt(p["detalhe"]), st["td"])] for p in problemas]
        story.append(tabela(["URL", "Tipo", "Detalhe"], linhas, [0.4, 0.22, 0.38], largura, st))
    else:
        story.append(Paragraph("Nenhum problema encontrado: todas as páginas do sitemap "
                               "responderam 200 com canonical correto.", st["corpo"]))
    story.append(Spacer(1, 12))

    # --- O que foi feito ---
    decisoes = dossie.get("decisoes", [])
    story.append(faixa_secao(f"O QUE FOI ALTERADO NESTA RODADA  ({len(decisoes)})",
                             AZUL_STATUS, largura, st))
    story.append(Spacer(1, 8))
    if decisoes:
        for d in decisoes:
            texto = f"<b>{rt(d.get('titulo', ''))}</b>"
            if d.get("arquivo"):
                texto += f" — {rt(d['arquivo'])}"
            story.append(Paragraph("• " + texto, st["bullet"]))
            if d.get("descricao"):
                story.append(Paragraph(rt(d["descricao"]), st["corpo"]))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("Nada precisou de alteração nesta semana.", st["corpo"]))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZA_BORDA, spaceBefore=6))
    story.append(Paragraph(
        f"AJ TopoGeo  |  gerado em {gerado_br}  |  radar semanal de Analytics + Search Console",
        st["rodape"]))

    doc.build(story)
    return saida


def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: py rotinas/analise_analytics_pdf.py <dossie.json> <saida.pdf>")
    origem, destino = Path(sys.argv[1]), Path(sys.argv[2])
    if not origem.exists():
        sys.exit(f"Dossiê não encontrado: {origem}")
    dossie = json.loads(origem.read_text(encoding="utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    gerar(dossie, destino)
    print(f"PDF gerado: {destino}")


if __name__ == "__main__":
    main()
