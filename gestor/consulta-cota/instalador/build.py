"""Gera o instalador da Consulta de Cota.

    py instalador/build.py

Sai em `instalador/dist`:

  Instalar Consulta de Cota.exe   instalador de um clique, sem administrador
  Consulta de Cota - portatil.zip mesma coisa para quem prefere so descompactar

Precisa, **so na maquina que constroi**: Python com PyInstaller e pefile, e o
QGIS instalado onde o config.json de desenvolvimento aponta -- e de la que saem
o GDAL e as tabelas. Na maquina de destino nao precisa de QGIS nenhum.
"""

import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PROJETO = AQUI.parent
sys.path.insert(0, str(PROJETO.parent / "instalador-comum"))
import empacotar  # noqa: E402

NOME = "Consulta de Cota"

# os tres unicos executaveis que o programa chama
EXECUTAVEIS = ["gdalinfo.exe", "gdallocationinfo.exe", "gdaldem.exe"]


def dlls_necessarias(binario, alvos):
    """Fecho das DLLs que os executaveis precisam, dentro da pasta do QGIS.

    A pasta `bin` do QGIS tem 424 MB porque carrega Qt, GRASS, SAGA e o resto do
    programa. O GDAL de linha de comando usa uma fracao disso: seguindo a tabela
    de importacao de cada arquivo chega-se a 51 DLLs, 122 MB. O que nao estiver
    na pasta do QGIS e DLL do proprio Windows e nao entra no pacote.
    """
    import pefile

    disponivel = {p.name.lower(): p for p in binario.glob("*.dll")}

    def importadas(caminho):
        pe = pefile.PE(str(caminho), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        nomes = [e.dll.decode("latin-1").lower()
                 for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])]
        pe.close()
        return nomes

    vistos, fila = set(), list(alvos)
    while fila:
        nome = fila.pop()
        chave = nome.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        caminho = binario / nome if (binario / nome).exists() else disponivel.get(chave)
        if caminho is None:
            continue                      # DLL do Windows
        fila.extend(d for d in importadas(caminho) if d not in vistos)
    return [disponivel[n] for n in sorted(vistos) if n in disponivel]


def copiar_ferramentas(destino):
    """Desmonta do QGIS so o GDAL de linha de comando e as tabelas dele."""
    cfg = json.loads((PROJETO / "config.json").read_text(encoding="utf-8"))
    binario = Path(cfg["gdalBin"])
    if not binario.exists():
        raise SystemExit(f"nao achei o GDAL em {binario} (confira o config.json)")
    qgis = binario.parent

    alvo = destino / "ferramentas" / "gdal"
    alvo.mkdir(parents=True, exist_ok=True)
    for nome in EXECUTAVEIS:
        origem = binario / nome
        if not origem.exists():
            raise SystemExit(f"nao achei {origem}")
        shutil.copy2(origem, alvo / nome)
    dlls = dlls_necessarias(binario, EXECUTAVEIS)
    for d in dlls:
        shutil.copy2(d, alvo / d.name)
    mb = sum(d.stat().st_size for d in dlls) / 1024 / 1024
    print(f"  GDAL: {len(EXECUTAVEIS)} executaveis + {len(dlls)} DLLs ({mb:.0f} MB)")

    # GDAL_DATA: tabelas de formato e de sistema de coordenadas (3 MB)
    origem_dados = qgis / "apps" / "gdal" / "share" / "gdal"
    if not origem_dados.is_dir():
        raise SystemExit(f"nao achei o GDAL_DATA em {origem_dados}")
    empacotar.limpar(destino / "ferramentas" / "gdal-data")
    shutil.copytree(origem_dados, destino / "ferramentas" / "gdal-data")

    # PROJ_LIB: so o proj.db (9 MB). A pasta share/proj do QGIS tem 774 MB
    # porque carrega as grades de transformacao entre datums do mundo inteiro --
    # nada disso e usado aqui, que nao reprojeta nada.
    origem_proj = qgis / "share" / "proj" / "proj.db"
    if not origem_proj.exists():
        raise SystemExit(f"nao achei o proj.db em {origem_proj}")
    (destino / "ferramentas" / "proj").mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem_proj, destino / "ferramentas" / "proj" / "proj.db")
    print("  tabelas: gdal-data + proj.db")

    (destino / "config.json").write_text(json.dumps({
        "gdalBin": "ferramentas/gdal",
        "gdalData": "ferramentas/gdal-data",
        "projData": "ferramentas/proj",
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    empacotar.construir(
        nome=NOME, chave="AJTopoGeo_ConsultaCota",
        descricao="Cota de coordenadas sobre o modelo digital, declividade por faixa "
                  "e curvas de nivel em DXF para o CAD. Leva o Python e o GDAL ja "
                  "embutidos -- nao precisa de QGIS na maquina.",
        script=PROJETO / "cota_janela.py", projeto=PROJETO, aqui=AQUI,
        copiar_ferramentas=copiar_ferramentas,
        extras_pyinstaller=("--hidden-import", "cota", "--hidden-import", "curvas",
                            "--collect-submodules", "numpy"))
