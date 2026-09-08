"""Gera o instalador do PPK das Fotos.

    py instalador/build.py

Sai em `instalador/dist`:

  Instalar PPK das Fotos.exe   instalador de um clique, sem administrador
  PPK das Fotos - portatil.zip mesma coisa para quem prefere so descompactar

Precisa, na maquina que constroi (nao na de destino): Python com pyproj e
PyInstaller, mais o RTKLIB e o ExifTool onde o config.json de desenvolvimento
apontar. O trabalho comum aos dois programas mora em `gestor/instalador-comum`.
"""

import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PROJETO = AQUI.parent
sys.path.insert(0, str(PROJETO.parent / "instalador-comum"))
import empacotar  # noqa: E402

NOME = "PPK das Fotos"

# do RTKLIB so estes dois arquivos importam: o processador e a calibracao de
# antena. O resto da distribuicao (interface grafica, manual, exemplos) soma
# dezenas de MB que ninguem usaria aqui dentro.
RTKLIB_ARQUIVOS = ["rnx2rtkp.exe"]
RTKLIB_PADROES = ["igs*.atx"]


def copiar_ferramentas(destino):
    """Leva o RTKLIB e o ExifTool para dentro do pacote."""
    cfg = json.loads((PROJETO / "config.json").read_text(encoding="utf-8"))
    origem_rtk = Path(cfg["rtklibBin"])
    origem_exif = Path(cfg["exiftoolBin"])
    for p in (origem_rtk, origem_exif):
        if not p.exists():
            raise SystemExit(f"nao achei as ferramentas em {p} (confira o config.json)")

    alvo_rtk = destino / "ferramentas" / "RTKLIB"
    alvo_rtk.mkdir(parents=True, exist_ok=True)
    levados = []
    for nome in RTKLIB_ARQUIVOS:
        shutil.copy2(origem_rtk / nome, alvo_rtk / nome)
        levados.append(nome)
    for padrao in RTKLIB_PADROES:
        achados = sorted(origem_rtk.glob(padrao))
        if not achados:
            raise SystemExit(f"nao achei nenhum {padrao} em {origem_rtk}: sem o ANTEX a "
                             "altura das fotos sai 6 a 8 cm baixa")
        # so o mais recente; sao dezenas de MB cada
        shutil.copy2(achados[-1], alvo_rtk / achados[-1].name)
        levados.append(achados[-1].name)
    print("  RTKLIB:", ", ".join(levados))

    alvo_exif = destino / "ferramentas" / "exiftool"
    empacotar.limpar(alvo_exif)
    # o exiftool_files e o interpretador Perl do ExifTool: sem ele o .exe nao roda
    shutil.copytree(origem_exif, alvo_exif,
                    ignore=shutil.ignore_patterns("*.zip", "*(-k).exe"))
    print("  ExifTool: exiftool.exe + exiftool_files")

    (destino / "config.json").write_text(json.dumps({
        "rtklibBin": "ferramentas/RTKLIB",
        "exiftoolBin": "ferramentas/exiftool",
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    empacotar.construir(
        nome=NOME, chave="AJTopoGeo_PPKFotos",
        descricao="PPK das fotos de drone: processa o log do voo contra a base "
                  "RINEX e escreve o geotag no formato do DJI Terra. Leva o "
                  "Python, o RTKLIB e o ExifTool ja embutidos.",
        script=PROJETO / "ppk_janela.py", projeto=PROJETO, aqui=AQUI,
        copiar_ferramentas=copiar_ferramentas,
        extras_pyinstaller=("--hidden-import", "ppk_fotos", "--collect-data", "pyproj"))
