"""Gera o PDF da triagem a partir do markdown, no padrao visual AJ TopoGeo.

Uso:
    python relatorio.py <triagem-XXX.md> [--croqui <croqui.dxf>] [--rev 01]

O .md continua sendo a fonte unica: este script so o compoe em pagina. Editar
o relatorio significa editar o .md e rodar de novo.

Paleta e metricas extraidas do RT-627/2026, que e o padrao dos relatorios
tecnicos da empresa - faixa azul-marinho, filete azul claro, titulo marinho,
secoes em azul medio, tabela com cabecalho marinho e linhas alternadas, caixa
de sintese em vermelho, rodape cinza em duas linhas.

Markdown reconhecido: titulos (#, ##, ###), paragrafos, listas com "-",
tabelas com "|", citacao "> " (vira caixa de sintese), regua "---" e
**negrito** no meio da linha.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from fpdf.fonts import FontFace

MARINHO = (11, 46, 89)
FILETE = (91, 163, 224)
SECAO = (30, 95, 165)
CORPO = (68, 68, 68)
DISCRETO = (122, 122, 122)
LINHA_ALT = (234, 241, 251)
BORDA = (207, 220, 239)
CAIXA_FUNDO = (252, 235, 235)
CAIXA_FILETE = (163, 45, 45)
CAIXA_TEXTO = (90, 20, 20)
SUBTITULO_FAIXA = (188, 213, 242)

EMPRESA = "AJ TopoGeo"
LINHA_EMPRESA = "Topografia • Agrimensura • Georreferenciamento — Sidrolândia/MS"
RODAPE = "AJ TopoGeo  •  CNPJ 46.639.961/0001-41  •  @aj_topogeo  •  (67) 99348-0660"
AVISO = ("Triagem documental preliminar — não substitui levantamento "
         "georreferenciado e certificação no INCRA/SIGEF.")

FONTES = [("Arial", "", r"C:\Windows\Fonts\arial.ttf"),
          ("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf"),
          ("Arial", "I", r"C:\Windows\Fonts\ariali.ttf")]

FAIXA_MM = 21.9   # 62 pt no modelo
FILETE_MM = 1.4   # 4 pt


class Relatorio(FPDF):
    def __init__(self, referencia: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.referencia = referencia
        self.set_auto_page_break(True, margin=20)
        self.set_margins(15, FAIXA_MM + FILETE_MM + 7, 15)
        self.fonte = "helvetica"
        if all(Path(c).exists() for _, _, c in FONTES):
            for fam, estilo, caminho in FONTES:
                self.add_font(fam, estilo, caminho)
            self.fonte = "Arial"

    def _globo(self, cx, cy, r):
        """Marca da empresa: globo em fio branco sobre a faixa."""
        self.set_draw_color(255, 255, 255)
        self.set_line_width(0.35)
        self.circle(cx - r, cy - r, r * 2)
        self.ellipse(cx - r * 0.42, cy - r, r * 0.84, r * 2)
        self.line(cx - r, cy, cx + r, cy)
        for f in (0.5, -0.5):
            dy = r * f
            dx = r * (1 - f * f) ** 0.5
            self.line(cx - dx, cy + dy, cx + dx, cy + dy)
        self.set_line_width(0.2)

    def header(self):
        self.set_fill_color(*MARINHO)
        self.rect(0, 0, self.w, FAIXA_MM, "F")
        self.set_fill_color(*FILETE)
        self.rect(0, FAIXA_MM, self.w, FILETE_MM, "F")

        self._globo(21.5, FAIXA_MM / 2, 6.3)

        self.set_xy(30, 4)
        self.set_text_color(255, 255, 255)
        self.set_font(self.fonte, "B", 15)
        self.cell(0, 7, EMPRESA, new_x="LMARGIN", new_y="NEXT")
        self.set_x(30)
        self.set_font(self.fonte, "", 7.5)
        self.set_text_color(*SUBTITULO_FAIXA)
        self.cell(0, 4, LINHA_EMPRESA)

        self.set_xy(-95, 5.5)
        self.set_font(self.fonte, "", 7.5)
        self.set_text_color(255, 255, 255)
        self.cell(80, 4, "Triagem Documental", align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_xy(-95, 9.8)
        self.cell(80, 4, self.referencia, align="R")
        self.set_text_color(*CORPO)
        # o header deixa o cursor onde parou; sem devolver a margem, o primeiro
        # multi_cell da pagina nasce sem largura util
        self.set_xy(self.l_margin, self.t_margin)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*BORDA)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.2)
        self.set_font(self.fonte, "", 7)
        self.set_text_color(*DISCRETO)
        y = self.get_y()
        self.cell(0, 3.6, RODAPE, new_x="LMARGIN", new_y="NEXT")
        self.set_xy(self.l_margin, y)
        self.cell(0, 3.6, f"Página {self.page_no()}", align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 3.6, AVISO, align="C")
        self.set_text_color(*CORPO)

    def inline(self, texto: str, altura=4.8, tamanho=9.5, cor=CORPO):
        self.set_text_color(*cor)
        for i, parte in enumerate(re.split(r"\*\*(.+?)\*\*", texto.replace("`", ""))):
            if not parte:
                continue
            self.set_font(self.fonte, "B" if i % 2 else "", tamanho)
            self.write(altura, parte)
        self.ln(altura)
        self.set_text_color(*CORPO)


def limpar(texto: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", texto).replace("`", "").strip()


def blocos(linhas: list[str]):
    i, saida = 0, []
    while i < len(linhas):
        linha = linhas[i].rstrip()
        if linha.lstrip().startswith("|"):
            tabela = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                celulas = [c.strip() for c in linhas[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in celulas):
                    tabela.append([limpar(c) for c in celulas])
                i += 1
            saida.append(("tabela", tabela))
            continue
        if linha.startswith("> "):
            saida.append(("citacao", linha[2:]))
        elif linha.startswith("### "):
            saida.append(("h3", linha[4:]))
        elif linha.startswith("## "):
            saida.append(("h2", linha[3:]))
        elif linha.startswith("# "):
            saida.append(("h1", linha[2:]))
        elif linha.startswith("- "):
            saida.append(("item", linha[2:]))
        elif linha.strip() in ("---", "***"):
            saida.append(("regua", ""))
        elif linha.strip():
            saida.append(("p", linha.strip()))
        else:
            saida.append(("vazio", ""))
        i += 1
    return saida


def juntar(itens):
    """Linha quebrada no .md e continuacao do mesmo paragrafo."""
    saida = []
    for tipo, conteudo in itens:
        if tipo in ("p", "citacao") and saida and saida[-1][0] == tipo:
            saida[-1] = (tipo, saida[-1][1] + " " + conteudo)
        else:
            saida.append((tipo, conteudo))
    return saida


def desenhar_tabela(pdf: Relatorio, linhas: list[list[str]]):
    if not linhas:
        return
    colunas = max(len(l) for l in linhas)
    linhas = [l + [""] * (colunas - len(l)) for l in linhas]
    largura = pdf.w - pdf.l_margin - pdf.r_margin

    # largura minima pela maior palavra da coluna, nao so pela proporcao de
    # texto: senao "R.10/627" e "13/10/1982" quebram no meio, porque a coluna
    # ao lado tem frase longa e leva quase tudo
    pdf.set_font(pdf.fonte, "", 8)
    minimos = []
    for c in range(colunas):
        palavras = [p for l in linhas for p in l[c].split()] or [""]
        maior = max((pdf.get_string_width(p) for p in palavras), default=0)
        minimos.append(min(maior + 3.5, largura * 0.32))

    pesos = [max(len(l[c]) for l in linhas) or 1 for c in range(colunas)]
    larguras = [largura * p / sum(pesos) for p in pesos]
    for _ in range(8):
        falta = sum(max(0.0, minimos[i] - larguras[i]) for i in range(colunas))
        if falta < 0.05:
            break
        folgados = [i for i in range(colunas) if larguras[i] > minimos[i]]
        sobra = sum(larguras[i] - minimos[i] for i in folgados)
        if sobra <= 0:
            break
        for i in range(colunas):
            larguras[i] = max(larguras[i], minimos[i])
        for i in folgados:
            larguras[i] -= falta * (larguras[i] - minimos[i]) / sobra
    fator = largura / sum(larguras)
    larguras = [w * fator for w in larguras]

    pdf.set_draw_color(*BORDA)
    pdf.set_text_color(*CORPO)
    # a tabela usa a cor de preenchimento corrente nas linhas alternadas, e nao
    # so o cell_fill_color; sem fixar aqui ela herda o vermelho da caixa de
    # sintese e as linhas saem ilegiveis
    pdf.set_fill_color(*LINHA_ALT)
    pdf.set_font(pdf.fonte, "", 8)
    cabecalho = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=MARINHO)
    zebra = (FontFace(color=CORPO, fill_color=(255, 255, 255)),
             FontFace(color=CORPO, fill_color=LINHA_ALT))
    with pdf.table(col_widths=larguras, line_height=4.3, text_align="LEFT",
                   padding=(1.4, 1.6), borders_layout="ALL",
                   headings_style=cabecalho,
                   cell_fill_mode=TableCellFillMode.NONE) as tabela:
        for n, linha in enumerate(linhas):
            # estilo explicito por linha: o cell_fill_mode sozinho estava
            # pintando a tabela inteira, e a alternancia some
            fila = tabela.row(style=None if n == 0 else zebra[n % 2])
            for celula in linha:
                fila.cell(celula)
    pdf.ln(2.5)


def caixa_sintese(pdf: Relatorio, texto: str):
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    direita_original = pdf.r_margin
    pdf.set_font(pdf.fonte, "", 9.5)
    # mede e escreve com a mesma largura util, senao a caixa fica curta e o
    # texto vaza pelo rodape do retangulo
    linhas = pdf.multi_cell(largura - 8, 4.8, limpar(texto), dry_run=True,
                            output="LINES")
    altura = len(linhas) * 4.8 + 5
    if pdf.get_y() + altura > pdf.h - pdf.b_margin:
        pdf.add_page()
    y = pdf.get_y()
    pdf.set_fill_color(*CAIXA_FUNDO)
    pdf.rect(pdf.l_margin, y, largura, altura, "F")
    pdf.set_fill_color(*CAIXA_FILETE)
    pdf.rect(pdf.l_margin, y, 1.2, altura, "F")

    pdf.set_right_margin(direita_original + 4)
    pdf.set_xy(pdf.l_margin + 4, y + 2.5)
    pdf.set_text_color(*CAIXA_TEXTO)
    for i, parte in enumerate(re.split(r"\*\*(.+?)\*\*", texto.replace("`", ""))):
        if parte:
            pdf.set_font(pdf.fonte, "B" if i % 2 else "", 9.5)
            pdf.write(4.8, parte)
    pdf.set_right_margin(direita_original)
    pdf.set_text_color(*CORPO)
    pdf.set_fill_color(*LINHA_ALT)
    pdf.set_xy(pdf.l_margin, y + altura + 3)


def croqui_png(dxf: Path, destino: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import ezdxf
        from ezdxf.addons.drawing.matplotlib import qsave
    except ImportError:
        return None
    doc = ezdxf.readfile(dxf)
    # bg explicito: o model space do CAD e escuro e o croqui sairia ilegivel
    # num PDF branco. Montar o eixo na mao nao resolve - o draw_layout refaz as
    # cores da camada; o qsave e o caminho que respeita o bg.
    # A camada de aviso fica de fora: ela alarga a extensao e espreme a
    # geometria: o PDF ja traz o mesmo aviso em tipografia de verdade.
    qsave(doc.modelspace(), str(destino), bg="#FFFFFF", dpi=200,
          size_inches=(9, 9), filter_func=lambda e: e.dxf.layer != "AVISO")
    try:
        from PIL import Image, ImageChops
        img = Image.open(destino).convert("RGB")
        caixa = ImageChops.difference(
            img, Image.new("RGB", img.size, (255, 255, 255))).getbbox()
        if caixa:
            img.crop(caixa).save(destino)
    except ImportError:
        pass
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("markdown")
    ap.add_argument("--croqui", default=None)
    ap.add_argument("--rev", default="01")
    args = ap.parse_args()

    md = Path(args.markdown)
    itens = juntar(blocos(md.read_text(encoding="utf-8").splitlines()))
    nome = md.stem.replace("triagem-", "")
    ref = f"TRIAGEM-{nome}/{date.today().year} - Rev. {args.rev}"

    pdf = Relatorio(ref)
    pdf.add_page()

    titulo = next((c for t, c in itens if t == "h1"), md.stem)
    pdf.set_font(pdf.fonte, "B", 19)
    pdf.set_text_color(*MARINHO)
    pdf.multi_cell(0, 8.5, limpar(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.fonte, "", 11)
    pdf.set_text_color(*SECAO)
    pdf.multi_cell(0, 5.5, f"Emitido em {date.today().strftime('%d/%m/%Y')}"
                           f"  —  {ref}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*CORPO)
    pdf.ln(4)

    visto_h1 = False
    for tipo, conteudo in itens:
        if tipo == "h1":
            if not visto_h1:
                visto_h1 = True
                continue
            pdf.ln(2)
            pdf.set_font(pdf.fonte, "B", 14)
            pdf.set_text_color(*MARINHO)
            pdf.multi_cell(0, 6.5, limpar(conteudo), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*CORPO)
        elif tipo == "h2":
            pdf.ln(3.5)
            pdf.set_font(pdf.fonte, "B", 11)
            pdf.set_text_color(*SECAO)
            pdf.multi_cell(0, 5.5, limpar(conteudo), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*CORPO)
            pdf.ln(1)
        elif tipo == "h3":
            pdf.ln(1.5)
            pdf.set_font(pdf.fonte, "B", 9.5)
            pdf.set_text_color(*MARINHO)
            pdf.multi_cell(0, 5, limpar(conteudo), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*CORPO)
        elif tipo == "tabela":
            desenhar_tabela(pdf, conteudo)
        elif tipo == "citacao":
            caixa_sintese(pdf, conteudo)
        elif tipo == "item":
            pdf.set_font(pdf.fonte, "", 9.5)
            pdf.set_text_color(*SECAO)
            pdf.cell(4, 4.8, "•")
            pdf.set_text_color(*CORPO)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(0, 4.8, limpar(conteudo), align="J",
                           new_x="LMARGIN", new_y="NEXT")
        elif tipo == "regua":
            pdf.ln(1)
            pdf.set_draw_color(*BORDA)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2.5)
        elif tipo == "p":
            pdf.inline(conteudo)
            pdf.ln(1.2)
        elif tipo == "vazio":
            pdf.ln(1)

    if args.croqui and Path(args.croqui).exists():
        png = croqui_png(Path(args.croqui), md.parent / "_croqui_preview.png")
        if png:
            pdf.add_page()
            pdf.set_font(pdf.fonte, "B", 14)
            pdf.set_text_color(*MARINHO)
            pdf.cell(0, 7, "Anexo — Croqui esquemático",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*CORPO)
            pdf.ln(1)
            pdf.inline("**Verde contínuo:** descrito na matrícula. "
                       "**Vermelho tracejado:** arbitrado pelo script para "
                       "fechar a área registral — forma e posição não "
                       "correspondem à divisa real. Sem georreferência.",
                       tamanho=9)
            pdf.ln(2)
            largura = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.image(str(png), w=largura)
            pdf.ln(2)
            pdf.set_font(pdf.fonte, "", 8)
            pdf.set_text_color(*SECAO)
            pdf.multi_cell(0, 4, "Figura 1 — Croqui esquemático da Matrícula "
                                 f"{nome.replace('M', '')}. Alinhamentos com rumo e "
                                 "distância conforme a matrícula; restante do "
                                 "perímetro arbitrado.", align="C")
            pdf.set_text_color(*CORPO)
            png.unlink(missing_ok=True)

    saida = md.with_suffix(".pdf")
    pdf.output(str(saida))
    print(f"{saida.name}  |  {pdf.page_no()} pagina(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
