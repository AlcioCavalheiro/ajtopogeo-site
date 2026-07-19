"""Converte a documentacao recebida em texto antes da analise da triagem.

Uso:
    C:\\Users\\ALCIO\\.ajtopogeo\\venv\\Scripts\\python.exe extrair_texto.py "<pasta do projeto>"

Le tudo de 01_DOCUMENTOS/ e escreve um .md por arquivo em 10_TRIAGEM/_texto/,
mais um _INDICE.md com o status de cada conversao. PDF sem camada de texto
(matricula escaneada) passa por OCR em portugues antes de converter.

Nada aqui escreve dado de cliente no repositorio: entrada e saida ficam na
pasta do projeto, no Drive.
"""

import argparse
import io
import shutil
import subprocess
import sys
from pathlib import Path

from markitdown import MarkItDown

# Extensoes que o markitdown resolve direto (texto embutido).
EXT_TEXTO = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".ods", ".pptx",
             ".html", ".htm", ".csv", ".json", ".xml", ".txt", ".msg", ".epub"}
EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Abaixo disso por pagina, o PDF e imagem escaneada, nao texto.
MIN_CHARS_POR_PAGINA = 120


def exe_tesseract() -> str | None:
    """No PATH, ou no caminho padrao do instalador (o app nao ve o PATH novo
    ate ser reiniciado)."""
    achado = shutil.which("tesseract")
    if achado:
        return achado
    padrao = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    return str(padrao) if padrao.exists() else None


def tem_ocr() -> bool:
    return exe_tesseract() is not None


def neutralizar_realce(imagem: bytes) -> bytes:
    """Marca-texto ciano/verde fica escuro na conversao para cinza, e o
    binarizador do tesseract come o texto por baixo dele - some sem deixar
    rastro, e a frase continua lendo como se estivesse inteira. max(R,G,B)
    joga qualquer cor saturada para branco e preserva o traco preto."""
    from PIL import Image, ImageChops
    img = Image.open(io.BytesIO(imagem)).convert("RGB")
    r, g, b = img.split()
    buf = io.BytesIO()
    ImageChops.lighter(ImageChops.lighter(r, g), b).save(buf, format="PNG")
    return buf.getvalue()


def tesseract(imagem: bytes) -> str:
    imagem = neutralizar_realce(imagem)
    cmd = [exe_tesseract(), "stdin", "stdout", "-l", "por"]
    # por.traineddata proprio, para nao depender de escrita em Program Files
    tessdata = Path(sys.prefix).parent / "tessdata"
    if (tessdata / "por.traineddata").exists():
        cmd += ["--tessdata-dir", str(tessdata)]
    return subprocess.run(
        cmd, input=imagem, check=True, capture_output=True, timeout=300,
    ).stdout.decode("utf-8", "replace")


def paginas_escaneadas(caminho: Path) -> list[int]:
    """Paginas cujo conteudo real e imagem.

    Certidao de cartorio costuma vir escaneada com uma tarja de texto de
    verdade por cima - selo, emolumentos, link de validacao. Contando so
    caractere, essa tarja passa do limite sozinha, o documento escapa do OCR e
    o .md sai com o selo e sem uma linha da matricula, marcado como OK. Por
    isso a decisao olha quanto da pagina esta coberto por imagem."""
    import pymupdf
    escaneadas = []
    with pymupdf.open(caminho) as pdf:
        for n, pagina in enumerate(pdf, start=1):
            area = abs(pagina.rect)
            if not area:
                continue
            imagem = sum(abs(r) for img in pagina.get_images(full=True)
                         for r in pagina.get_image_rects(img[0])) / area
            texto = sum(abs(pymupdf.Rect(b[:4]))
                        for b in pagina.get_text("blocks")) / area
            # so cobertura de imagem nao serve: certidao escaneada fica em 0,45
            # a 0,61 conforme a margem do scanner. O que separa e a imagem
            # dominar o texto - na tarja o texto ocupa 5% a 9% da pagina.
            if imagem > 0.2 and imagem > texto * 3:
                escaneadas.append(n)
    return escaneadas


def paginas_pdf(caminho: Path) -> int:
    try:
        import pymupdf
        with pymupdf.open(caminho) as pdf:
            return pdf.page_count
    except Exception:
        return 1


def montar_tabela(tabela) -> list[list[str]]:
    """A grade do find_tables se desalinha quando ha celula mesclada: cada linha
    cai em sub-colunas diferentes. Reancora pelo centro horizontal da celula,
    usando a linha mais completa como referencia de colunas."""
    dados = tabela.extract()
    linhas = []
    for i, linha in enumerate(tabela.rows):
        celulas = [((c[0] + c[2]) / 2, (t or "").strip().replace("\n", " "))
                   for c, t in zip(linha.cells, dados[i]) if c and (t or "").strip()]
        if celulas:
            linhas.append(celulas)
    if not linhas:
        return []

    colunas = [x for x, _ in max(linhas, key=len)]
    montadas = []
    for celulas in linhas:
        saida = [""] * len(colunas)
        for x, texto in celulas:
            i = min(range(len(colunas)), key=lambda c: abs(colunas[c] - x))
            saida[i] = f"{saida[i]} {texto}".strip() if saida[i] else texto
        montadas.append([c.replace("|", "\\|") for c in saida])
    return montadas


def tabelas_pdf(origem: Path) -> str:
    """O markitdown achata tabela em celulas soltas e perde a associacao entre
    vertice e coordenada. Reextrai preservando a linha."""
    import pymupdf
    blocos = []
    with pymupdf.open(origem) as pdf:
        for n, pagina in enumerate(pdf, start=1):
            for tabela in pagina.find_tables().tables:
                linhas = montar_tabela(tabela)
                if len(linhas) < 2 or len(linhas[0]) < 2:
                    continue
                corpo = [f"| {' | '.join(l)} |" for l in linhas]
                corpo.insert(1, "| " + " | ".join(["---"] * len(linhas[0])) + " |")
                blocos.append(f"**Tabela - pagina {n}**\n\n" + "\n".join(corpo))

    if not blocos:
        return ""
    return ("\n\n---\n\n## Tabelas reextraidas\n\n"
            "Mesmas tabelas acima, com a estrutura de linha preservada. Onde as "
            "duas versoes divergirem, confira no PDF original.\n\n"
            + "\n\n".join(blocos) + "\n")


def texto_misto(origem: Path, escaneadas: list[int]) -> str:
    """OCR so nas paginas escaneadas; nas demais usa o texto nativo, que e
    exato. Documento misto existe: relatorio nosso, digital, com mapa colado no
    meio - passar OCR nele inteiro trocaria texto exato por texto adivinhado."""
    import pymupdf
    partes = []
    with pymupdf.open(origem) as pdf:
        for n, pagina in enumerate(pdf, start=1):
            nativo = pagina.get_text().strip()
            if n in escaneadas:
                corpo = tesseract(pagina.get_pixmap(dpi=300).tobytes("png"))
                marca = "OCR"
                if nativo:
                    # tarja de selo/validacao do cartorio: exata, o OCR degrada
                    corpo += f"\n\n[tarja nativa da pagina, sem OCR]\n{nativo}"
            else:
                corpo, marca = nativo, "texto nativo"
            partes.append(f"\n\n--- pagina {n} ({marca}) ---\n\n{corpo}")
    return "".join(partes)


def converter(md: MarkItDown, arquivo: Path, saida: Path) -> tuple[str, int]:
    """Converte um arquivo. Devolve (status, numero de caracteres)."""
    ext = arquivo.suffix.lower()

    if ext in EXT_IMAGEM:
        if not tem_ocr():
            return "SEM TEXTO - ler visualmente", 0
        try:
            texto = tesseract(arquivo.read_bytes())
        except Exception as e:
            print(f"    OCR falhou: {e}", file=sys.stderr)
            return "SEM TEXTO - ler visualmente", 0
        (saida / f"{arquivo.stem}.md").write_text(texto, encoding="utf-8")
        return "OCR", len(texto.strip())

    try:
        texto = md.convert(str(arquivo)).text_content
    except Exception as e:
        print(f"    erro: {e}", file=sys.stderr)
        return "FALHOU - ler visualmente", 0

    status = "OK"
    if ext == ".pdf":
        paginas = paginas_pdf(arquivo)
        escaneadas = paginas_escaneadas(arquivo)
        if not escaneadas and len(texto.strip()) < MIN_CHARS_POR_PAGINA * paginas:
            escaneadas = list(range(1, paginas + 1))  # sem texto e sem imagem
        if escaneadas:
            if not tem_ocr():
                return "SEM TEXTO - ler visualmente", len(texto.strip())
            try:
                texto = texto_misto(arquivo, escaneadas)
            except Exception as e:
                print(f"    OCR falhou: {e}", file=sys.stderr)
                return "SEM TEXTO - ler visualmente", len(texto.strip())
            status = f"OCR ({len(escaneadas)} de {paginas} pag.)"
        else:
            # so faz sentido com camada de texto; em pagina rasterizada nao acha
            try:
                tabelas = tabelas_pdf(arquivo)
            except Exception as e:
                print(f"    tabelas: {e}", file=sys.stderr)
                tabelas = ""
            if tabelas:
                texto += tabelas
                status = "OK + tabelas"

    (saida / f"{arquivo.stem}.md").write_text(texto, encoding="utf-8")
    return status, len(texto.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("projeto", help="pasta do projeto (a que contem 01_DOCUMENTOS)")
    ap.add_argument("--entrada", default="01_DOCUMENTOS")
    ap.add_argument("--saida", default="10_TRIAGEM/_texto")
    ap.add_argument("--force", action="store_true",
                    help="reconverte mesmo se o .md ja estiver atualizado")
    ap.add_argument("--filtro", default="",
                    help="so converte arquivo cujo nome contenha este trecho; "
                         "util em projeto antigo, de pasta cheia, quando a "
                         "triagem e de uma matricula so")
    args = ap.parse_args()

    projeto = Path(args.projeto)
    entrada = projeto / args.entrada
    saida = projeto / args.saida

    if not entrada.is_dir():
        print(f"nao encontrei {entrada}", file=sys.stderr)
        return 1
    saida.mkdir(parents=True, exist_ok=True)

    if not tem_ocr():
        print("aviso: tesseract ausente no PATH - PDF escaneado nao sera "
              "convertido, so marcado para leitura visual\n", file=sys.stderr)

    md = MarkItDown(enable_plugins=False)
    linhas = []

    for arquivo in sorted(entrada.rglob("*")):
        if not arquivo.is_file():
            continue
        if saida == arquivo.parent or saida in arquivo.parents:
            continue  # em projeto antigo a saida cai dentro da propria entrada
        if args.filtro and args.filtro.lower() not in arquivo.name.lower():
            continue
        ext = arquivo.suffix.lower()
        if ext not in EXT_TEXTO and ext not in EXT_IMAGEM:
            linhas.append((arquivo.name, "IGNORADO - formato nao textual", 0))
            continue

        destino = saida / f"{arquivo.stem}.md"
        if destino.exists() and not args.force and \
                destino.stat().st_mtime >= arquivo.stat().st_mtime:
            linhas.append((arquivo.name, "ja convertido",
                           len(destino.read_text(encoding="utf-8").strip())))
            continue

        print(f"  {arquivo.name}")
        status, chars = converter(md, arquivo, saida)
        linhas.append((arquivo.name, status, chars))

    indice = ["# Extracao de texto - documentos recebidos", "",
              "| arquivo | status | caracteres |", "| --- | --- | --- |"]
    indice += [f"| {nome} | {status} | {chars} |" for nome, status, chars in linhas]
    indice += ["", "Status `SEM TEXTO`, `FALHOU` ou `IGNORADO`: o arquivo nao virou "
               "texto e precisa ser lido no original antes de fechar a triagem."]
    (saida / "_INDICE.md").write_text("\n".join(indice) + "\n", encoding="utf-8")

    print(f"\n{len(linhas)} arquivo(s). Indice em {saida / '_INDICE.md'}")
    pendentes = [n for n, s, _ in linhas if s.startswith(("SEM TEXTO", "FALHOU", "IGNORADO"))]
    if pendentes:
        print("Pendente de leitura visual: " + ", ".join(pendentes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
