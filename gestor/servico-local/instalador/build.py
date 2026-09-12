"""Gera o instalador do programa unico -- as duas ferramentas num executavel so.

    py instalador/build.py

Sai em `instalador/dist`:

  Instalar Ferramentas AJ TopoGeo.exe   instalador de um clique, sem administrador
  Ferramentas AJ TopoGeo - portatil.zip mesma coisa para quem prefere descompactar

Nada aqui refaz o trabalho dos dois builds antigos: as funcoes que desmontam o
RTKLIB, o ExifTool e o GDAL continuam morando em cada projeto e sao chamadas
daqui. O unico acrescimo e juntar os dois `config.json` num so -- e o que precisa
ser feito porque, instalado, os dois modulos leem o mesmo arquivo, o que esta ao
lado do executavel.

Precisa, **so na maquina que constroi**: Python com pyproj, PyInstaller e
pefile; o RTKLIB e o ExifTool onde o config.json do PPK apontar; e o QGIS onde o
config.json da Consulta apontar. Na maquina de destino nao precisa de nada.
"""

import importlib.util
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PROJETO = AQUI.parent
GESTOR = PROJETO.parent
PPK = GESTOR / "servico-local-ppk"
COTA = GESTOR / "consulta-cota"

sys.path.insert(0, str(GESTOR / "instalador-comum"))
import empacotar  # noqa: E402

NOME = "Ferramentas AJ TopoGeo"


def carregar_build(pasta, apelido):
    """Importa o build.py de um dos projetos com nome proprio.

    Os dois se chamam `build`: importados pelo nome do arquivo, o segundo
    encontraria o primeiro ja no cache de modulos e as ferramentas de um dos
    programas nunca entrariam no pacote.
    """
    caminho = pasta / "instalador" / "build.py"
    spec = importlib.util.spec_from_file_location(apelido, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[apelido] = modulo
    spec.loader.exec_module(modulo)
    return modulo


build_ppk = carregar_build(PPK, "build_ppk")
build_cota = carregar_build(COTA, "build_cota")


def copiar_ferramentas(destino):
    """Leva as ferramentas dos dois programas e escreve um config.json so."""
    print("  --- PPK das Fotos ---")
    build_ppk.copiar_ferramentas(destino)
    print("  --- Consulta de Cota ---")
    build_cota.copiar_ferramentas(destino)

    # cada um dos dois acabou de escrever o proprio config.json por cima do
    # outro; o que vale e a uniao dos dois, escrita por ultimo
    (destino / "config.json").write_text(json.dumps({
        "rtklibBin": "ferramentas/RTKLIB",
        "exiftoolBin": "ferramentas/exiftool",
        "gdalBin": "ferramentas/gdal",
        "gdalData": "ferramentas/gdal-data",
        "projData": "ferramentas/proj",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  config.json: os cinco caminhos, relativos a pasta do programa")


if __name__ == "__main__":
    empacotar.construir(
        nome=NOME, chave="AJTopoGeo_Ferramentas",
        descricao="Os dois programas de servico local numa janela so: PPK das fotos "
                  "de drone, e consulta ao modelo digital (cota de pontos, "
                  "declividade com mapa em PDF e curvas de nivel em DXF). Leva o "
                  "Python, o RTKLIB, o ExifTool e o GDAL ja embutidos.",
        script=PROJETO / "principal.py", projeto=PROJETO, aqui=AQUI,
        copiar_ferramentas=copiar_ferramentas,
        extras_pyinstaller=(
            # as telas e os motores dos dois programas moram nas pastas irmas
            "--paths", str(PPK), "--paths", str(COTA),
            "--hidden-import", "ppk_janela", "--hidden-import", "ppk_fotos",
            "--hidden-import", "cota_janela", "--hidden-import", "cota",
            "--hidden-import", "curvas", "--hidden-import", "mapa",
            "--hidden-import", "relatorio",
            "--collect-data", "pyproj", "--collect-submodules", "numpy"))
