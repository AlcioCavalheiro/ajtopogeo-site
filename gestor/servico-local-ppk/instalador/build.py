"""Gera o instalador do PPK das Fotos.

    py instalador/build.py

Sai em `instalador/dist`:

  Instalar PPK das Fotos.exe   instalador de um clique, sem administrador
  PPK das Fotos - portatil.zip mesma coisa para quem prefere so descompactar

Precisa, na maquina que constroi (nao na de destino): Python com pyproj e
PyInstaller, mais o RTKLIB e o ExifTool em `C:\\Users\\<voce>\\ferramentas-ppk`
ou onde o config.json de desenvolvimento apontar.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PROJETO = AQUI.parent
NOME = "PPK das Fotos"

# do RTKLIB so estes dois arquivos importam: o processador e a calibracao de
# antena. O resto da distribuicao (interface grafica, manual, exemplos) soma
# dezenas de megabytes que ninguem usaria aqui dentro.
RTKLIB_ARQUIVOS = ["rnx2rtkp.exe"]
RTKLIB_PADROES = ["igs*.atx"]


def limpar(pasta):
    """Apaga a pasta mesmo com arquivo somente-leitura dentro.

    O ExifTool distribui os .pm marcados somente-leitura; o shutil desiste neles
    e a reconstrucao morre com "Acesso negado".
    """
    if not Path(pasta).exists():
        return
    def liberar(func, caminho, _erro):
        os.chmod(caminho, stat.S_IWRITE)
        func(caminho)
    shutil.rmtree(pasta, onexc=liberar)


def passo(t):
    print(f"\n=== {t} ===", flush=True)


def rodar(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd[:6]), "..." if len(cmd) > 6 else "", flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def pyinstaller(*args):
    rodar([sys.executable, "-m", "PyInstaller", *args], cwd=AQUI)


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
    limpar(alvo_exif)
    # o exiftool_files e o interpretador Perl do ExifTool: sem ele o .exe nao roda
    shutil.copytree(origem_exif, alvo_exif,
                    ignore=shutil.ignore_patterns("*.zip", "*(-k).exe"))
    print("  ExifTool: exiftool.exe + exiftool_files")

    (destino / "config.json").write_text(json.dumps({
        "rtklibBin": "ferramentas/RTKLIB",
        "exiftoolBin": "ferramentas/exiftool",
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def zipar(pasta, saida):
    """Compacta a pasta com a raiz achatada: o zip contem o conteudo, nao a pasta."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(pasta))
    return saida


def tamanho(p):
    n = p.stat().st_size if p.is_file() else sum(
        f.stat().st_size for f in p.rglob("*") if f.is_file())
    return f"{n / 1024 / 1024:.0f} MB"


def main():
    for pasta in (AQUI / "build", AQUI / "dist", AQUI / "dist_app"):
        limpar(pasta)

    passo("1/5  Empacotando o programa com o Python dentro")
    pyinstaller(
        "--noconfirm", "--clean", "--windowed", "--name", NOME,
        "--distpath", AQUI / "dist_app", "--workpath", AQUI / "build" / "app",
        "--specpath", AQUI / "build",
        "--paths", PROJETO,
        "--hidden-import", "ppk_fotos",
        "--collect-data", "pyproj",
        PROJETO / "ppk_janela.py",
    )
    app = AQUI / "dist_app" / NOME
    if not (app / f"{NOME}.exe").exists():
        raise SystemExit(f"o PyInstaller nao gerou {NOME}.exe")

    passo("2/5  Levando o RTKLIB e o ExifTool para dentro do pacote")
    copiar_ferramentas(app)

    passo("3/5  Conferindo o pacote antes de embrulhar")
    r = subprocess.run([str(app / f"{NOME}.exe"), "--autoteste"],
                       capture_output=True, text=True, timeout=300, cwd=str(app))
    print(r.stdout.rstrip() or r.stderr.rstrip())
    if r.returncode != 0:
        raise SystemExit("o pacote nao passou no autoteste; instalador nao foi gerado")

    passo("4/5  Compactando")
    embrulho = zipar(app, AQUI / "build" / "app.zip")
    print(f"  {embrulho.name}: {tamanho(embrulho)} (pasta crua: {tamanho(app)})")

    passo("5/5  Gerando o instalador")
    pyinstaller(
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", f"Instalar {NOME}",
        "--distpath", AQUI / "dist", "--workpath", AQUI / "build" / "inst",
        "--specpath", AQUI / "build",
        "--add-data", f"{embrulho}{os.pathsep}.",
        AQUI / "instalar.py",
    )
    instalador = AQUI / "dist" / f"Instalar {NOME}.exe"
    if not instalador.exists():
        raise SystemExit("o instalador nao foi gerado")
    shutil.copy2(embrulho, AQUI / "dist" / f"{NOME} - portatil.zip")

    print("\nPRONTO")
    for p in sorted((AQUI / "dist").iterdir()):
        print(f"  {p.name:34s} {tamanho(p)}")
    print(f"\n  {AQUI / 'dist'}")


if __name__ == "__main__":
    main()
