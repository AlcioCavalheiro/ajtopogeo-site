"""Instalador comum dos programas de servico local da AJ TopoGeo.

Vira um unico "Instalar <programa>.exe" que carrega o programa inteiro dentro de
si -- o Python e as ferramentas de linha de comando que ele chama. Na maquina de
destino nao precisa instalar mais nada.

Instala **por usuario**, em %LOCALAPPDATA%\\Programs, de proposito: instalacao em
Arquivos de Programas exigiria elevacao, e pedir UAC e o que costuma travar o
processo em maquina de cliente ou em ambiente controlado por TI.

Este arquivo nao sabe qual programa esta instalando: nome, chave de registro e
descricao vem do `programa.json` que o build embute junto. E o que permite que
o PPK das Fotos e a Consulta de Cota usem o mesmo instalador.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import winreg
import zipfile
from pathlib import Path

EMBRULHO = "app.zip"
FICHA = "programa.json"


def _ficha():
    raiz = getattr(sys, "_MEIPASS", None)
    caminho = (Path(raiz) if raiz else Path(__file__).parent) / FICHA
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


PROGRAMA = _ficha()
NOME = PROGRAMA["nome"]
DESCRICAO = PROGRAMA.get("descricao", "")
TITULO = f"Instalar {NOME} - AJ TopoGeo"
CHAVE_DESINSTALAR = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                     + PROGRAMA["chave"])

# o instalador e "windowed": sem console, um subprocesso comum abriria uma
# janela preta piscando a cada atalho criado
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def relatar(texto):
    """Escreve sem quebrar quando nao existe console (sys.stdout e None)."""
    try:
        print(texto, flush=True)
    except (AttributeError, OSError, ValueError):
        pass


def recurso(nome):
    """Arquivo que veio dentro do executavel."""
    raiz = getattr(sys, "_MEIPASS", None)
    return Path(raiz) / nome if raiz else Path(__file__).parent / nome


def destino_padrao():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / NOME


def area_de_trabalho():
    # o Desktop pode estar redirecionado para o OneDrive; o caminho do shell e a
    # unica resposta confiavel, entao pergunta-se ao proprio Windows
    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
            capture_output=True, text=True, timeout=30, check=True,
            creationflags=SEM_JANELA).stdout.strip()
        if saida:
            return Path(saida)
    except (subprocess.SubprocessError, OSError):
        pass
    return Path.home() / "Desktop"


def menu_iniciar():
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def criar_atalho(atalho, alvo, pasta_trabalho, descricao=""):
    """Cria um .lnk sem depender de biblioteca externa.

    O VBScript e o caminho mais portatil: o WScript.Shell existe em toda
    instalacao do Windows, e nao exige pywin32 nem elevacao.
    """
    atalho.parent.mkdir(parents=True, exist_ok=True)
    vbs = (f'Set s = CreateObject("WScript.Shell")\n'
           f'Set a = s.CreateShortcut("{atalho}")\n'
           f'a.TargetPath = "{alvo}"\n'
           f'a.WorkingDirectory = "{pasta_trabalho}"\n'
           f'a.IconLocation = "{alvo}, 0"\n'
           f'a.Description = "{descricao}"\n'
           f'a.Save\n')
    with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False,
                                     encoding="latin-1") as f:
        f.write(vbs)
        script = f.name
    try:
        subprocess.run(["cscript", "//nologo", script], capture_output=True, timeout=60,
                       creationflags=SEM_JANELA)
    finally:
        Path(script).unlink(missing_ok=True)
    return atalho.exists()


def escrever_desinstalador(pasta):
    """Um .bat que apaga atalhos, registro e a propria pasta.

    A pasta nao pode ser apagada por um script que roda de dentro dela, entao a
    ultima linha entrega a tarefa a um cmd separado, que espera o .bat terminar.
    """
    (pasta / "Desinstalar.bat").write_text(f"""@echo off
title Desinstalar {NOME}
echo Removendo {NOME}...
del /q "%USERPROFILE%\\Desktop\\{NOME}.lnk" 2>nul
del /q "%OneDrive%\\Desktop\\{NOME}.lnk" 2>nul
del /q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{NOME}.lnk" 2>nul
reg delete "HKCU\\{CHAVE_DESINSTALAR}" /f >nul 2>&1
echo Pronto. Esta pasta sera apagada em seguida.
start "" /min cmd /c "timeout /t 3 >nul & rmdir /s /q ""{pasta}"" "
""", encoding="latin-1")


def registrar(pasta, versao="1.0"):
    """Faz aparecer em Configuracoes > Aplicativos. HKCU nao pede administrador."""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE_DESINSTALAR) as k:
            tamanho = sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file())
            for nome, valor in (
                    ("DisplayName", f"{NOME} (AJ TopoGeo)"),
                    ("DisplayVersion", versao),
                    ("Publisher", "AJ TopoGeo"),
                    ("InstallLocation", str(pasta)),
                    ("UninstallString", f'"{pasta / "Desinstalar.bat"}"'),
                    ("DisplayIcon", str(pasta / f"{NOME}.exe"))):
                winreg.SetValueEx(k, nome, 0, winreg.REG_SZ, valor)
            winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, tamanho // 1024)
            winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        return True
    except OSError:
        return False


def instalar(destino, avisar=relatar):
    destino = Path(destino)
    embrulho = recurso(EMBRULHO)
    if not embrulho.exists():
        raise RuntimeError(f"O instalador esta incompleto: nao achei {EMBRULHO} dentro dele.")

    if destino.exists():
        avisar("Removendo a versao anterior...")
        # so a pasta do programa; nada do usuario mora aqui dentro
        shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)

    avisar(f"Copiando os arquivos para {destino}...")
    with zipfile.ZipFile(embrulho) as z:
        nomes = z.namelist()
        for i, nome in enumerate(nomes, 1):
            z.extract(nome, destino)
            if i % 200 == 0 or i == len(nomes):
                avisar(f"   {i} de {len(nomes)} arquivos...")

    exe = destino / f"{NOME}.exe"
    if not exe.exists():
        raise RuntimeError(f"A copia terminou mas {exe.name} nao apareceu em {destino}.")

    avisar("Conferindo a instalacao...")
    r = subprocess.run([str(exe), "--autoteste"], capture_output=True, text=True,
                       timeout=180, cwd=str(destino), creationflags=SEM_JANELA)
    for linha in (r.stdout or "").splitlines():
        avisar("   " + linha)
    if r.returncode != 0:
        raise RuntimeError("A instalacao ficou incompleta:\n"
                           + (r.stdout or r.stderr or "sem detalhe"))

    avisar("Criando os atalhos...")
    escrever_desinstalador(destino)
    feitos = []
    for pasta in (area_de_trabalho(), menu_iniciar()):
        if criar_atalho(pasta / f"{NOME}.lnk", exe, destino,
                        f"{NOME} - AJ TopoGeo"):
            feitos.append(str(pasta))
    registrar(destino)
    avisar("")
    avisar(f"Instalado em {destino}")
    for p in feitos:
        avisar(f"Atalho criado em {p}")
    return destino, exe


# ---------------------------------------------------------------- janela

def janela():
    from tkinter import BOTH, END, StringVar, Tk, X, filedialog, messagebox
    from tkinter import scrolledtext, ttk

    raiz = Tk()
    raiz.title(TITULO)
    raiz.geometry("640x430")
    try:
        ttk.Style().theme_use("vista")
    except Exception:  # noqa: BLE001 - tema e cosmetico
        pass

    quadro = ttk.Frame(raiz, padding=14)
    quadro.pack(fill=BOTH, expand=True)
    ttk.Label(quadro, text=f"Instalar {NOME}", font=("Segoe UI", 14, "bold")).pack(anchor="w")
    ttk.Label(quadro, wraplength=600, justify="left",
              text=(DESCRICAO + "\n\n" if DESCRICAO else "")
                   + "Vai tudo embutido: nao precisa instalar mais nada nesta maquina, "
                     "e nao pede senha de administrador.").pack(anchor="w", pady=(4, 12))

    caminho = StringVar(value=str(destino_padrao()))
    linha = ttk.Frame(quadro)
    linha.pack(fill=X)
    ttk.Label(linha, text="Pasta:").pack(side="left")
    ttk.Entry(linha, textvariable=caminho).pack(side="left", fill=X, expand=True, padx=6)

    def escolher():
        d = filedialog.askdirectory(title="Onde instalar")
        if d:
            caminho.set(str(Path(d) / NOME))
    ttk.Button(linha, text="Mudar...", command=escolher).pack(side="left")

    log = scrolledtext.ScrolledText(quadro, height=13, state="disabled",
                                    font=("Consolas", 9))
    log.pack(fill=BOTH, expand=True, pady=12)

    def escrever(t):
        log.config(state="normal")
        log.insert(END, t + "\n")
        log.see(END)
        log.config(state="disabled")
        raiz.update_idletasks()

    rodape = ttk.Frame(quadro)
    rodape.pack(fill=X)
    botao = ttk.Button(rodape, text="INSTALAR")
    botao.pack(side="right")

    def rodar():
        botao.config(state="disabled", text="Instalando...")
        try:
            destino, exe = instalar(caminho.get(), escrever)
        except Exception as e:  # noqa: BLE001 - o usuario precisa ver qualquer falha
            escrever("")
            escrever("FALHOU: " + str(e))
            escrever(traceback.format_exc())
            messagebox.showerror(TITULO, str(e))
            botao.config(state="normal", text="TENTAR DE NOVO")
            return
        botao.config(text="FECHAR", state="normal", command=raiz.destroy)
        if messagebox.askyesno(TITULO, "Instalado.\n\nAbrir o programa agora?"):
            subprocess.Popen([str(exe)], cwd=str(destino))
            raiz.destroy()

    botao.config(command=rodar)
    raiz.mainloop()


def main():
    if "--silencioso" in sys.argv:
        alvo = destino_padrao()
        for i, a in enumerate(sys.argv):
            if a == "--destino" and i + 1 < len(sys.argv):
                alvo = Path(sys.argv[i + 1])
        # sem console nao ha para onde imprimir, entao o relato vai para arquivo
        registro = Path(tempfile.gettempdir()) / f"instalar-{PROGRAMA['chave']}.log"
        linhas = []

        def anotar(t):
            linhas.append(t)
            relatar(t)
            registro.write_text(os.linesep.join(linhas), encoding="utf-8")

        try:
            instalar(alvo, anotar)
        except Exception as e:  # noqa: BLE001
            anotar("FALHOU: " + str(e))
            anotar(traceback.format_exc())
            return 1
        return 0
    janela()
    return 0


if __name__ == "__main__":
    sys.exit(main())
