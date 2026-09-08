"""Monta o instalador de um programa de servico local.

Cada programa tem um `instalador/build.py` de poucas linhas que diz o proprio
nome e como copiar as ferramentas que ele chama; todo o resto -- congelar com o
PyInstaller, conferir, compactar e embrulhar -- e igual e mora aqui.

O pacote so vira instalador depois de passar no `--autoteste` do proprio
programa. Sem console nao existe mensagem de erro na partida: uma instalacao
quebrada apenas nao abriria, e ninguem saberia por que.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

COMUM = Path(__file__).resolve().parent


def limpar(pasta):
    """Apaga a pasta mesmo com arquivo somente-leitura dentro.

    Ferramentas de terceiros (o ExifTool, por exemplo) distribuem arquivos
    marcados somente-leitura; o shutil desiste neles e a reconstrucao morre com
    "Acesso negado".
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


def zipar(pasta, saida):
    """Compacta com a raiz achatada: o zip contem o conteudo, nao a pasta."""
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


def construir(nome, chave, descricao, script, projeto, aqui, copiar_ferramentas,
              extras_pyinstaller=()):
    """Gera `Instalar <nome>.exe` e `<nome> - portatil.zip` em `aqui/dist`.

    `copiar_ferramentas(destino)` recebe a pasta do programa ja congelado e deve
    colocar la dentro tudo o que ele chama por fora, mais o `config.json` com os
    caminhos relativos a essa pasta.
    """
    for pasta in (aqui / "build", aqui / "dist", aqui / "dist_app"):
        limpar(pasta)

    def pyinstaller(*args):
        rodar([sys.executable, "-m", "PyInstaller", *args], cwd=aqui)

    passo(f"1/5  Empacotando o {nome} com o Python dentro")
    pyinstaller(
        "--noconfirm", "--clean", "--windowed", "--name", nome,
        "--distpath", aqui / "dist_app", "--workpath", aqui / "build" / "app",
        "--specpath", aqui / "build",
        "--paths", projeto,
        *extras_pyinstaller,
        script,
    )
    app = aqui / "dist_app" / nome
    if not (app / f"{nome}.exe").exists():
        raise SystemExit(f"o PyInstaller nao gerou {nome}.exe")

    passo("2/5  Levando as ferramentas para dentro do pacote")
    copiar_ferramentas(app)

    passo("3/5  Conferindo o pacote antes de embrulhar")
    r = subprocess.run([str(app / f"{nome}.exe"), "--autoteste"],
                       capture_output=True, text=True, timeout=600, cwd=str(app))
    print(r.stdout.rstrip() or r.stderr.rstrip())
    if r.returncode != 0:
        raise SystemExit("o pacote nao passou no autoteste; instalador nao foi gerado")

    passo("4/5  Compactando")
    embrulho = zipar(app, aqui / "build" / "app.zip")
    print(f"  {embrulho.name}: {tamanho(embrulho)} (pasta crua: {tamanho(app)})")

    passo("5/5  Gerando o instalador")
    ficha = aqui / "build" / "programa.json"
    ficha.write_text(json.dumps(dict(nome=nome, chave=chave, descricao=descricao),
                                indent=2, ensure_ascii=False), encoding="utf-8")
    pyinstaller(
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", f"Instalar {nome}",
        "--distpath", aqui / "dist", "--workpath", aqui / "build" / "inst",
        "--specpath", aqui / "build",
        "--add-data", f"{embrulho}{os.pathsep}.",
        "--add-data", f"{ficha}{os.pathsep}.",
        COMUM / "instalar.py",
    )
    instalador = aqui / "dist" / f"Instalar {nome}.exe"
    if not instalador.exists():
        raise SystemExit("o instalador nao foi gerado")
    shutil.copy2(embrulho, aqui / "dist" / f"{nome} - portatil.zip")

    print("\nPRONTO")
    for p in sorted((aqui / "dist").iterdir()):
        print(f"  {p.name:36s} {tamanho(p)}")
    print(f"\n  {aqui / 'dist'}")
