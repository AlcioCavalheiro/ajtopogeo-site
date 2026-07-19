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


def tesseract(imagem: bytes) -> str:
    cmd = [exe_tesseract(), "stdin", "stdout", "-l", "por"]
    # por.traineddata proprio, para nao depender de escrita em Program Files
    tessdata = Path(sys.prefix).parent / "tessdata"
    if (tessdata / "por.traineddata").exists():
        cmd += ["--tessdata-dir", str(tessdata)]
    return subprocess.run(
        cmd, input=imagem, check=True, capture_output=True, timeout=300,
    ).stdout.decode("utf-8", "replace")


def paginas_pdf(caminho: Path) -> int:
    try:
        import pymupdf
        with pymupdf.open(caminho) as pdf:
            return pdf.page_count
    except Exception:
        return 1


def ocr_pdf(origem: Path) -> str:
    """Rasteriza cada pagina a 300 dpi e passa no OCR. Devolve o texto."""
    import pymupdf
    partes = []
    with pymupdf.open(origem) as pdf:
        for i, pagina in enumerate(pdf, start=1):
            imagem = pagina.get_pixmap(dpi=300).tobytes("png")
            partes.append(f"\n\n--- pagina {i} ---\n\n" + tesseract(imagem))
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
        limite = MIN_CHARS_POR_PAGINA * paginas_pdf(arquivo)
        if len(texto.strip()) < limite:
            if not tem_ocr():
                return "SEM TEXTO - ler visualmente", len(texto.strip())
            try:
                texto = ocr_pdf(arquivo)
            except Exception as e:
                print(f"    OCR falhou: {e}", file=sys.stderr)
                return "SEM TEXTO - ler visualmente", len(texto.strip())
            status = "OCR"

    (saida / f"{arquivo.stem}.md").write_text(texto, encoding="utf-8")
    return status, len(texto.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("projeto", help="pasta do projeto (a que contem 01_DOCUMENTOS)")
    ap.add_argument("--entrada", default="01_DOCUMENTOS")
    ap.add_argument("--saida", default="10_TRIAGEM/_texto")
    ap.add_argument("--force", action="store_true",
                    help="reconverte mesmo se o .md ja estiver atualizado")
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
