"""Ferramentas AJ TopoGeo: os programas de servico local numa janela so.

Um executavel, um atalho, uma instalacao. Cada programa vira uma aba e continua
sendo o mesmo codigo de antes -- `ppk_janela.Janela` e `cota_janela.Janela`,
montados aqui dentro com `embutido=True` em vez de abrirem janela propria. Nao
existe copia de tela nenhuma neste arquivo: melhoria feita no PPK aparece na aba
do PPK sem ninguem precisar lembrar de repetir.

As abas sao carregadas uma a uma, cada qual com a sua rede de protecao. Se o
GDAL faltar na maquina, a aba do modelo digital explica o que houve e a aba do
PPK abre normalmente -- que e a diferenca entre um programa com um defeito e um
programa que nao abre.
"""

import importlib
import sys
import traceback
from pathlib import Path
from tkinter import BOTH, END, Tk, ttk

TITULO = "Ferramentas AJ TopoGeo"

# Rodando do fonte, os modulos moram nas pastas irmas. Empacotado, o PyInstaller
# ja os colocou dentro do executavel e mexer no sys.path so atrapalharia.
if not getattr(sys, "frozen", False):
    _AQUI = Path(__file__).resolve().parent
    for _pasta in ("marca", "servico-local-ppk", "consulta-cota"):
        sys.path.insert(0, str(_AQUI.parent / _pasta))

import marca  # noqa: E402

# rotulo da aba, modulo da tela, e o que a aba faz em uma linha
PAINEIS = (
    ("  PPK das Fotos  ", "ppk_janela",
     "processa o log do voo contra a base RINEX e escreve o geotag"),
    ("  Consulta de Cota  ", "cota_janela",
     "cota de pontos, declividade com mapa em PDF e curvas de nivel"),
)


def area_util(raiz):
    """A tela menos a barra de tarefas, no mesmo pixel que o tkinter usa.

    `winfo_screenheight` conta a tela inteira. Pedir esse tamanho deixa o rodape
    da janela atras da barra de tarefas, e o botao de baixo -- que e sempre o que
    executa -- fica inalcancavel. Quem sabe o que sobra e o proprio Windows.

    O processo nao se declara ciente de DPI, entao o Windows entrega os numeros
    ja divididos pela escala da tela: sao os mesmos pixels do tkinter.
    """
    largura, altura = raiz.winfo_screenwidth(), raiz.winfo_screenheight()
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        SPI_GETWORKAREA = 48
        if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0,
                                                      ctypes.byref(r), 0):
            largura, altura = r.right - r.left, r.bottom - r.top
    except Exception:  # noqa: BLE001 - fora do Windows, vale a tela inteira
        pass
    return largura, altura


def explicar_falha(quadro, rotulo, erro):
    """Poe o motivo na propria aba, em vez de deixar o programa nao abrir."""
    for filho in quadro.winfo_children():
        filho.destroy()
    dentro = ttk.Frame(quadro, padding=16)
    dentro.pack(fill=BOTH, expand=True)
    ttk.Label(dentro, text=f"{rotulo.strip()}: esta parte nao carregou",
              font=("Segoe UI", 12, "bold"), foreground="#a4232b").pack(anchor="w")
    ttk.Label(dentro, wraplength=820, justify="left", foreground="#555",
              text="O resto do programa continua funcionando. Para saber o que faltou, "
                   "abra o Prompt de Comando na pasta do programa e rode "
                   f'"{TITULO}.exe" --autoteste.').pack(anchor="w", pady=(6, 10))
    texto = ttk.Frame(dentro)
    texto.pack(fill=BOTH, expand=True)
    from tkinter import scrolledtext
    caixa = scrolledtext.ScrolledText(texto, wrap="word", font=("Consolas", 9))
    caixa.pack(fill=BOTH, expand=True)
    caixa.insert(END, f"{erro.__class__.__name__}: {erro}\n\n"
                 + "".join(traceback.format_exception(erro)))
    caixa.config(state="disabled")


class Principal:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title(TITULO)
        # A aba da consulta e a mais alta das duas, e agora divide a altura com o
        # cabecalho e a fila de abas. Em tela pequena a janela desejada nao
        # caberia e a tabela de resultado ficaria fora do alcance -- entao pede-se
        # o menor entre o desejado e o que a area util comporta, descontando a
        # barra de titulo.
        largura, altura = area_util(raiz)
        raiz.geometry(f"{min(1080, largura - 40)}x{min(980, altura - 45)}")
        raiz.minsize(900, 620)
        marca.aplicar_icone(raiz)

        corpo = ttk.Frame(raiz, padding=(12, 12, 12, 8))
        corpo.pack(fill=BOTH, expand=True)
        marca.cabecalho(corpo, TITULO,
                        "PPK das fotos de drone e consulta ao modelo digital do "
                        "terreno, no mesmo programa.")

        abas = ttk.Notebook(corpo)
        abas.pack(fill=BOTH, expand=True)
        self.telas = {}
        for rotulo, modulo, _ in PAINEIS:
            quadro = ttk.Frame(abas)
            abas.add(quadro, text=rotulo)
            try:
                self.telas[modulo] = importlib.import_module(modulo).Janela(
                    quadro, embutido=True)
            # BaseException porque o modulo pode morrer com SystemExit na
            # importacao; deixar isso passar mataria o programa inteiro
            except BaseException as e:  # noqa: BLE001
                explicar_falha(quadro, rotulo, e)


def autoteste():
    """Confere a instalacao das duas partes: `Ferramentas AJ TopoGeo.exe --autoteste`.

    Devolve zero so quando as duas passam. E o que o build e o instalador
    consultam antes de dar o servico por concluido -- sem console, uma
    instalacao incompleta apenas nao abriria a aba, e ninguem saberia por que.
    """
    ruim = 0
    for rotulo, modulo, _ in PAINEIS:
        print(f"\n=== {rotulo.strip()} ===")
        try:
            ruim |= importlib.import_module(modulo).autoteste()
        except BaseException as e:  # noqa: BLE001
            print(f"  nao carregou: {e.__class__.__name__}: {e}")
            ruim = 1
    print("\nInstalacao completa." if not ruim else "\nFALTA alguma coisa; veja acima.")
    return ruim


def main():
    if "--autoteste" in sys.argv:
        sys.exit(autoteste())
    raiz = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:  # noqa: BLE001 - tema e cosmetico
        pass
    Principal(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
