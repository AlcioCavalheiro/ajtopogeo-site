"""Gera o PDF da triagem a partir do markdown, no padrao AJ TopoGeo.

Uso:
    python relatorio.py <triagem-XXX.md> [--croqui <croqui.dxf>] [--rev 01]

O .md continua sendo a fonte unica: este script so o compoe em pagina, com
cabecalho, rodape, numeracao e o croqui embutido quando existir. Editar o
relatorio significa editar o .md e rodar de novo.

Reconhece o subconjunto de markdown que a rotina de triagem produz: titulos
(#, ##, ###), paragrafos, listas com "-", tabelas com "|", regua "---" e
**negrito** no meio da linha.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF

EMPRESA = "AJ TopoGeo"
LINHA_EMPRESA = "Topografia • Agrimensura • Georreferenciamento — Sidrolândia/MS"
RODAPE = ("AJ TopoGeo  •  CNPJ 46.639.961/0001-41  •  @aj_topogeo  "
          "•  (67) 99348-0660")
AVISO = ("Triagem documental preliminar — não substitui levantamento "
         "georreferenciado nem certificação no INCRA/SIGEF.")

FONTES = [("Arial", "", r"C:\Windows\Fonts\arial.ttf"),
          ("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf"),
          ("Arial", "I", r"C:\Windows\Fonts\ariali.ttf")]


class Relatorio(FPDF):
    def __init__(self, titulo: str, subtitulo: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.titulo, self.subtitulo = titulo, subtitulo
        self.set_auto_page_break(True, margin=22)
        self.set_margins(18, 16, 18)
        self.fonte = "helvetica"
        if all(Path(c).exists() for _, _, c in FONTES):
            for fam, estilo, caminho in FONTES:
                self.add_font(fam, estilo, caminho)
            self.fonte = "Arial"

    def header(self):
        self.set_font(self.fonte, "B", 13)
        self.set_text_color(20, 20, 20)
        self.cell(0, 6, EMPRESA, new_x="LMARGIN", new_y="NEXT")
        self.set_font(self.fonte, "", 7.5)
        self.set_text_color(110, 110, 110)
        self.cell(0, 4, LINHA_EMPRESA, new_x="LMARGIN", new_y="NEXT")
        self.set_font(self.fonte, "B", 7.5)
        self.cell(0, 4, self.subtitulo, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y() + 1,
                  self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)
        self.set_text_color(20, 20, 20)

    def footer(self):
        self.set_y(-17)
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)
        self.set_font(self.fonte, "", 6.5)
        self.set_text_color(120, 120, 120)
        self.cell(0, 3.5, AVISO, new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 3.5, RODAPE)
        self.cell(0, 3.5, f"Página {self.page_no()}", align="R")
        self.set_text_color(20, 20, 20)

    def inline(self, texto: str, altura=4.6, tamanho=9):
        """Escreve uma linha tratando **negrito**."""
        for i, parte in enumerate(re.split(r"\*\*(.+?)\*\*", texto.replace("`", ""))):
            if not parte:
                continue
            self.set_font(self.fonte, "B" if i % 2 else "", tamanho)
            self.write(altura, parte)
        self.ln(altura)


def limpar(texto: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", texto).replace("`", "").strip()


def blocos(linhas: list[str]):
    """Agrupa as linhas do markdown em blocos (tipo, conteudo)."""
    i, saida = 0, []
    while i < len(linhas):
        linha = linhas[i].rstrip()
        if linha.startswith("|"):
            tabela = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                celulas = [c.strip() for c in linhas[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in celulas):
                    tabela.append([limpar(c) for c in celulas])
                i += 1
            saida.append(("tabela", tabela))
            continue
        if linha.startswith("### "):
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


def juntar_paragrafos(itens):
    """Linha quebrada no .md e continuacao do mesmo paragrafo."""
    saida = []
    for tipo, conteudo in itens:
        if tipo == "p" and saida and saida[-1][0] == "p":
            saida[-1] = ("p", saida[-1][1] + " " + conteudo)
        elif tipo == "item" and saida and saida[-1][0] == "item_cont":
            saida[-1] = ("item", saida[-1][1] + " " + conteudo)
        else:
            saida.append((tipo, conteudo))
    return saida


def desenhar_tabela(pdf: Relatorio, linhas: list[list[str]]):
    if not linhas:
        return
    colunas = max(len(l) for l in linhas)
    linhas = [l + [""] * (colunas - len(l)) for l in linhas]
    # coluna mais larga para a que tem mais texto
    pesos = [max(len(l[c]) for l in linhas) or 1 for c in range(colunas)]
    total = sum(pesos)
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    larguras = [max(largura * p / total, 14) for p in pesos]
    fator = largura / sum(larguras)
    larguras = [w * fator for w in larguras]

    pdf.set_font(pdf.fonte, "", 8)
    with pdf.table(col_widths=larguras, line_height=4.4, text_align="LEFT",
                   padding=1.2, borders_layout="MINIMAL") as tabela:
        for n, linha in enumerate(linhas):
            pdf.set_font(pdf.fonte, "B" if n == 0 else "", 8)
            fila = tabela.row()
            for celula in linha:
                fila.cell(celula)
    pdf.ln(2)


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
    # o bloco de aviso do DXF alarga muito a extensao e espreme a geometria na
    # pagina. Fica de fora daqui: o PDF ja traz o mesmo aviso em tipografia de
    # verdade, logo acima da imagem.
    qsave(doc.modelspace(), str(destino), bg="#FFFFFF", dpi=200,
          size_inches=(9, 9),
          filter_func=lambda e: e.dxf.layer != "AVISO")
    try:  # o qsave devolve quadrado; recorta a margem em branco que sobra
        from PIL import Image, ImageChops
        img = Image.open(destino).convert("RGB")
        fundo = Image.new("RGB", img.size, (255, 255, 255))
        caixa = ImageChops.difference(img, fundo).getbbox()
        if caixa:
            img.crop(caixa).save(destino)
    except ImportError:
        pass
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("markdown")
    ap.add_argument("--croqui", default=None, help="DXF a embutir no fim")
    ap.add_argument("--rev", default="01")
    args = ap.parse_args()

    md = Path(args.markdown)
    linhas = md.read_text(encoding="utf-8").splitlines()
    itens = juntar_paragrafos(blocos(linhas))

    titulo = next((c for t, c in itens if t == "h1"), md.stem)
    ref = f"TRIAGEM {md.stem.replace('triagem-', '')} — Rev. {args.rev}"

    pdf = Relatorio(titulo, ref)
    pdf.add_page()

    pdf.set_font(pdf.fonte, "B", 15)
    pdf.multi_cell(0, 7, limpar(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.fonte, "", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 5, f"Emitido em {date.today().strftime('%d/%m/%Y')}  •  {ref}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)
    pdf.ln(3)

    primeiro_h1 = True
    for tipo, conteudo in itens:
        if tipo == "h1":
            if primeiro_h1:
                primeiro_h1 = False
                continue
            pdf.ln(2)
            pdf.set_font(pdf.fonte, "B", 13)
            pdf.multi_cell(0, 6, limpar(conteudo), new_x="LMARGIN", new_y="NEXT")
        elif tipo == "h2":
            pdf.ln(3)
            pdf.set_font(pdf.fonte, "B", 10.5)
            pdf.set_fill_color(238, 238, 238)
            pdf.cell(0, 6, " " + limpar(conteudo), fill=True,
                     new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
        elif tipo == "h3":
            pdf.ln(1.5)
            pdf.set_font(pdf.fonte, "B", 9.5)
            pdf.multi_cell(0, 5, limpar(conteudo), new_x="LMARGIN", new_y="NEXT")
        elif tipo == "tabela":
            desenhar_tabela(pdf, conteudo)
        elif tipo == "item":
            pdf.set_font(pdf.fonte, "", 9)
            x = pdf.get_x()
            pdf.cell(4, 4.6, "•")
            pdf.set_x(x + 4)
            pdf.multi_cell(0, 4.6, limpar(conteudo), new_x="LMARGIN", new_y="NEXT")
        elif tipo == "regua":
            pdf.ln(1)
            pdf.set_draw_color(210, 210, 210)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)
        elif tipo == "p":
            pdf.set_font(pdf.fonte, "", 9)
            pdf.inline(conteudo)
            pdf.ln(1)
        elif tipo == "vazio":
            pdf.ln(1)

    if args.croqui and Path(args.croqui).exists():
        png = croqui_png(Path(args.croqui), md.parent / "_croqui_preview.png")
        if png:
            pdf.add_page()
            pdf.set_font(pdf.fonte, "B", 13)
            pdf.cell(0, 7, "Anexo — Croqui esquemático",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(pdf.fonte, "", 8.5)
            pdf.multi_cell(0, 4.6,
                           "Verde contínuo: descrito na matrícula. "
                           "Vermelho tracejado: arbitrado pelo script para fechar "
                           "a área registral — forma e posição "
                           "não correspondem à divisa real. Sem "
                           "georreferência.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            pdf.image(str(png), w=pdf.w - pdf.l_margin - pdf.r_margin)
            png.unlink(missing_ok=True)

    saida = md.with_suffix(".pdf")
    pdf.output(str(saida))
    print(f"{saida.name}  |  {pdf.page_no()} pagina(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
