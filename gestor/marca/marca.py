"""A marca da AJ TopoGeo nas janelas dos programas de servico local.

Os arquivos sao gerados por `gerar.py` a partir do LOGO.png da empresa e ficam
versionados aqui do lado. Rodando pelo fonte eles sao lidos desta pasta;
empacotado pelo PyInstaller, da pasta em que o executavel se descompacta.

Nada aqui e essencial ao funcionamento: se um arquivo faltar, a janela abre do
mesmo jeito, so sem o logo. Um programa que se recusa a abrir por causa de uma
imagem seria pior do que um sem imagem.
"""

import sys
from pathlib import Path

ICONE = "ajtopogeo.ico"
FAIXA = "ajtopogeo.png"


def pasta():
    """Onde estao os arquivos de marca, rodando do fonte ou empacotado."""
    raiz = getattr(sys, "_MEIPASS", None)
    return Path(raiz) if raiz else Path(__file__).resolve().parent


def aplicar_icone(janela):
    """Poe o globo na barra de titulo, na barra de tarefas e no Alt+Tab."""
    caminho = pasta() / ICONE
    try:
        # default=... vale para as caixas de mensagem tambem, que sao outras
        # janelas e sem isso apareceriam com o icone padrao do Tk
        janela.iconbitmap(default=str(caminho))
        return True
    except Exception:  # noqa: BLE001 - icone e enfeite, nao pode derrubar a janela
        return False


def cabecalho(pai, titulo, subtitulo=""):
    """Faixa com o logo, o nome do programa e uma linha de descricao."""
    from tkinter import LEFT, PhotoImage, X, ttk

    quadro = ttk.Frame(pai)
    quadro.pack(fill=X, pady=(0, 10))
    try:
        imagem = PhotoImage(file=str(pasta() / FAIXA))
        rotulo = ttk.Label(quadro, image=imagem)
        # sem guardar a referencia, o coletor de lixo do Python apaga a imagem e
        # sobra um retangulo vazio -- e o tropeco classico de imagem no tkinter
        rotulo.imagem = imagem
        rotulo.pack(side=LEFT, padx=(0, 12))
    except Exception:  # noqa: BLE001
        pass
    texto = ttk.Frame(quadro)
    texto.pack(side=LEFT, fill=X, expand=True)
    ttk.Label(texto, text=titulo, font=("Segoe UI", 13, "bold")).pack(anchor="w")
    if subtitulo:
        ttk.Label(texto, text=subtitulo, foreground="#555",
                  wraplength=560, justify="left").pack(anchor="w", pady=(2, 0))
    ttk.Separator(pai, orient="horizontal").pack(fill=X, pady=(0, 12))
    return quadro
