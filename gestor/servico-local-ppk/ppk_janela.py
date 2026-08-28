"""Janela para rodar o PPK das fotos de drone sem linha de comando.

Abre com o atalho "PPK das Fotos" na Area de Trabalho. O usuario escolhe a pasta
do voo, informa a coordenada da base (digitada ou lida do relatorio do IBGE-PPP)
e clica em Processar. No fim a janela diz, em portugues, se o resultado presta.
"""

import queue
import threading
import traceback
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, Tk, X, Y, filedialog, messagebox
from tkinter import scrolledtext, ttk

TITULO = "PPK das Fotos de Drone - AJ TopoGeo"

# Rodando por pythonw nao existe console: uma falha na partida (biblioteca
# faltando, arquivo movido) deixaria a janela simplesmente nao abrir, sem dizer
# nada. Entao o erro vira caixa de mensagem e arquivo de log ao lado do script.
try:
    import pyproj

    import ppk_fotos
except Exception:  # noqa: BLE001 - qualquer falha aqui precisa ser visivel
    _erro = traceback.format_exc()
    try:
        Path(__file__).with_name("erro_na_partida.txt").write_text(_erro, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter.messagebox as _mb
        _raiz = Tk()
        _raiz.withdraw()
        _mb.showerror(TITULO,
                      "O programa nao conseguiu iniciar.\n\n"
                      + _erro.strip().splitlines()[-1]
                      + "\n\nSe faltar biblioteca, abra o Prompt de Comando e rode:\n"
                        "    py -m pip install pyproj")
    except Exception:  # noqa: BLE001
        pass
    raise SystemExit(1)

# fusos UTM que cobrem o Brasil, em SIRGAS2000
FUSOS = {
    "18S (oeste do AC)": 31978, "19S (AC, AM, RO)": 31979, "20S (RO, MT, MS)": 31980,
    "21S (MS, MT, GO, PR)": 31981, "22S (SP, PR, SC, GO)": 31982,
    "23S (SP, MG, RJ, SC, RS)": 31983, "24S (MG, BA, ES, RJ)": 31984,
    "25S (BA, PE, AL, SE)": 31985,
}

CORES = {"ok": ("#0b6b3a", "#e6f4ea"), "atencao": ("#8a5300", "#fdf2e0"),
         "ruim": ("#a4232b", "#fdecea"), "neutro": ("#333333", "#f0f0f0")}


class Janela:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title(TITULO)
        raiz.geometry("780x680")
        raiz.minsize(680, 560)

        self.fila = queue.Queue()
        self.rodando = False

        corpo = ttk.Frame(raiz, padding=14)
        corpo.pack(fill=BOTH, expand=True)

        # ---------- pasta do voo ----------
        bloco = ttk.LabelFrame(corpo, text=" 1. Pasta do voo ", padding=10)
        bloco.pack(fill=X, pady=(0, 10))
        ttk.Label(bloco, text="A pasta que contem as fotos, o .MRK do drone e os arquivos da base.",
                  foreground="#555").pack(anchor="w", pady=(0, 6))
        linha = ttk.Frame(bloco)
        linha.pack(fill=X)
        self.pasta = StringVar()
        # o botao vai primeiro e ancorado a direita: se o campo for empacotado
        # antes, ele expande e empurra o botao para fora da janela
        ttk.Button(linha, text="Escolher...", command=self.escolher_pasta).pack(side=RIGHT, padx=(6, 0))
        ttk.Entry(linha, textvariable=self.pasta).pack(side=LEFT, fill=X, expand=True)

        # ---------- base ----------
        bloco = ttk.LabelFrame(corpo, text=" 2. Coordenada da base ", padding=10)
        bloco.pack(fill=X, pady=(0, 10))
        self.origem = StringVar(value="ppp")
        ttk.Radiobutton(bloco, text="Ler do relatorio do IBGE-PPP  (evita erro de digitacao)",
                        variable=self.origem, value="ppp",
                        command=self.trocar_origem).pack(anchor="w")

        self.quadro_ppp = ttk.Frame(bloco, padding=(22, 4, 0, 8))
        self.quadro_ppp.pack(fill=X)
        linha = ttk.Frame(self.quadro_ppp)
        linha.pack(fill=X)
        self.arquivo_ppp = StringVar()
        ttk.Button(linha, text="Escolher...", command=self.escolher_ppp).pack(side=RIGHT, padx=(6, 0))
        ttk.Entry(linha, textvariable=self.arquivo_ppp).pack(side=LEFT, fill=X, expand=True)
        self.resumo_ppp = ttk.Label(self.quadro_ppp, text="", foreground="#0b6b3a")
        self.resumo_ppp.pack(anchor="w", pady=(5, 0))

        ttk.Radiobutton(bloco, text="Digitar a coordenada em UTM",
                        variable=self.origem, value="utm",
                        command=self.trocar_origem).pack(anchor="w")
        self.quadro_utm = ttk.Frame(bloco, padding=(22, 4, 0, 0))
        self.norte, self.leste, self.cota = StringVar(), StringVar(), StringVar()
        self.fuso = StringVar(value="21S (MS, MT, GO, PR)")
        for rot, var, dica in (("Norte (N)", self.norte, "ex. 7685787.873"),
                               ("Leste (E)", self.leste, "ex. 712330.005"),
                               ("Altitude elipsoidal (h)", self.cota, "ex. 494.98")):
            li = ttk.Frame(self.quadro_utm)
            li.pack(fill=X, pady=2)
            ttk.Label(li, text=rot, width=22).pack(side=LEFT)
            ttk.Entry(li, textvariable=var, width=18).pack(side=LEFT)
            ttk.Label(li, text=dica, foreground="#888").pack(side=LEFT, padx=(8, 0))
        li = ttk.Frame(self.quadro_utm)
        li.pack(fill=X, pady=2)
        ttk.Label(li, text="Fuso", width=22).pack(side=LEFT)
        ttk.Combobox(li, textvariable=self.fuso, values=list(FUSOS), state="readonly",
                     width=24).pack(side=LEFT)
        ttk.Label(self.quadro_utm, text="A altitude tem de ser ELIPSOIDAL (do GNSS), nao ortometrica.",
                  foreground="#8a5300").pack(anchor="w", pady=(6, 0))

        # ---------- opcoes ----------
        bloco = ttk.LabelFrame(corpo, text=" 3. Processamento ", padding=10)
        bloco.pack(fill=X, pady=(0, 10))
        self.mascara = StringVar(value="auto")
        ttk.Radiobutton(bloco, text="Testar duas configuracoes e ficar com a melhor  (recomendado, demora o dobro)",
                        variable=self.mascara, value="auto").pack(anchor="w")
        ttk.Radiobutton(bloco, text="Rapido, configuracao padrao",
                        variable=self.mascara, value="15").pack(anchor="w")

        self.botao = ttk.Button(corpo, text="PROCESSAR", command=self.iniciar)
        self.botao.pack(fill=X, ipady=8, pady=(0, 8))
        self.barra = ttk.Progressbar(corpo, mode="indeterminate")

        self.veredito = ttk.Label(corpo, text="", padding=8, anchor="w", justify="left")
        self.log = scrolledtext.ScrolledText(corpo, height=12, wrap="word",
                                             font=("Consolas", 9), state="disabled")
        self.log.pack(fill=BOTH, expand=True)

        self.trocar_origem()
        self.raiz.after(120, self.drenar)

    # ---------------- interface ----------------

    def trocar_origem(self):
        if self.origem.get() == "ppp":
            self.quadro_utm.pack_forget()
            self.quadro_ppp.pack(fill=X)
        else:
            self.quadro_ppp.pack_forget()
            self.quadro_utm.pack(fill=X)

    def escolher_pasta(self):
        d = filedialog.askdirectory(title="Pasta do voo")
        if d:
            self.pasta.set(d)
            self.procurar_ppp_na_pasta(Path(d))

    def procurar_ppp_na_pasta(self, pasta):
        """Se houver um relatorio do IBGE-PPP junto do voo, ja aproveita."""
        for p in sorted(pasta.rglob("*.txt")):
            if "LEIAME" in p.name.upper():
                continue
            try:
                dados = ppk_fotos.ler_ppp_ibge(p)
            except (ValueError, OSError, IndexError):
                continue
            self.arquivo_ppp.set(str(p))
            self.mostrar_ppp(dados)
            self.escrever(f"Encontrei um relatorio do IBGE-PPP na pasta: {p.name}")
            return

    def escolher_ppp(self):
        f = filedialog.askopenfilename(title="Relatorio do IBGE-PPP",
                                       filetypes=[("Relatorio do IBGE-PPP", "*.txt"), ("Todos", "*.*")])
        if not f:
            return
        self.arquivo_ppp.set(f)
        try:
            self.mostrar_ppp(ppk_fotos.ler_ppp_ibge(f))
        except (ValueError, OSError, IndexError) as e:
            self.resumo_ppp.config(text=str(e), foreground="#a4232b")

    def mostrar_ppp(self, d):
        self.resumo_ppp.config(
            text=f"Marco {d['marco']}:  lat {d['lat']:.8f}   lon {d['lon']:.8f}   "
                 f"h {d['h']:.3f} m", foreground="#0b6b3a")

    def escrever(self, txt):
        self.log.config(state="normal")
        self.log.insert(END, txt + "\n")
        self.log.see(END)
        self.log.config(state="disabled")

    def mostrar_veredito(self, nivel, texto):
        cor, fundo = CORES[nivel]
        self.veredito.config(text=texto, foreground=cor, background=fundo)
        self.veredito.pack(fill=X, before=self.log, pady=(0, 8))

    # ---------------- execucao ----------------

    def coletar_base(self):
        if self.origem.get() == "ppp":
            caminho = self.arquivo_ppp.get().strip()
            if not caminho:
                raise ValueError("Escolha o relatorio do IBGE-PPP da base.")
            d = ppk_fotos.ler_ppp_ibge(caminho)
            return d["lat"], d["lon"], d["h"], f"marco {d['marco']} (IBGE-PPP)"
        try:
            n = float(self.norte.get().replace(",", "."))
            e = float(self.leste.get().replace(",", "."))
            z = float(self.cota.get().replace(",", "."))
        except ValueError:
            raise ValueError("Preencha Norte, Leste e altitude com numeros.")
        epsg = FUSOS[self.fuso.get()]
        lon, lat = pyproj.Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326",
                                               always_xy=True).transform(e, n)
        return lat, lon, z, f"UTM {self.fuso.get().split()[0]} digitada"

    def iniciar(self):
        if self.rodando:
            return
        pasta = Path(self.pasta.get().strip())
        if not pasta.is_dir():
            messagebox.showerror(TITULO, "Escolha a pasta do voo.")
            return
        try:
            lat, lon, z, origem = self.coletar_base()
        except (ValueError, OSError, IndexError) as e:
            messagebox.showerror(TITULO, str(e))
            return

        self.log.config(state="normal")
        self.log.delete("1.0", END)
        self.log.config(state="disabled")
        self.veredito.pack_forget()
        self.rodando = True
        self.botao.config(state="disabled", text="Processando...")
        self.barra.pack(fill=X, before=self.log, pady=(0, 8))
        self.barra.start(12)
        self.escrever(f"Base ({origem}): lat {lat:.8f}, lon {lon:.8f}, h {z:.3f} m")

        threading.Thread(target=self.trabalhar, args=(pasta, lat, lon, z), daemon=True).start()

    def trabalhar(self, pasta, lat, lon, z):
        try:
            cfg = ppk_fotos.carregar_config(Path(__file__).parent)
            fn = (ppk_fotos.processar_escolhendo_mascara if self.mascara.get() == "auto"
                  else ppk_fotos.processar)
            extra = {} if self.mascara.get() == "auto" else {"elmask": 15}
            r = fn(pasta, lat, lon, z, cfg, saida=pasta / "PPK FOTOS.txt",
                   progresso=lambda t: self.fila.put(("log", t)), **extra)
            self.fila.put(("fim", r))
        except Exception as e:  # noqa: BLE001 - a janela precisa mostrar qualquer falha
            self.fila.put(("erro", (str(e), traceback.format_exc())))

    def drenar(self):
        try:
            while True:
                tipo, carga = self.fila.get_nowait()
                if tipo == "log":
                    self.escrever(carga)
                elif tipo == "fim":
                    self.terminar(carga)
                elif tipo == "erro":
                    self.falhar(*carga)
        except queue.Empty:
            pass
        self.raiz.after(120, self.drenar)

    def encerrar_execucao(self):
        self.rodando = False
        self.barra.stop()
        self.barra.pack_forget()
        self.botao.config(state="normal", text="PROCESSAR")

    def terminar(self, r):
        self.encerrar_execucao()
        q = r["qualidade"]
        self.escrever("")
        self.escrever(f"Arquivo gerado: {r['saida']}")
        self.escrever(f"{r['escritas']} fotos com coordenada.")
        self.escrever("")
        for m in q["mensagens"]:
            self.escrever("  - " + m)

        titulo = {"ok": "PODE USAR", "atencao": "USE COM ATENCAO",
                  "ruim": "ESTE VOO TEM PROBLEMA"}[q["nivel"]]
        resumo = {
            "ok": "A trajetoria esta continua e a fixacao e boa. O arquivo esta pronto "
                  "para a fotogrametria.",
            "atencao": "O arquivo foi gerado, mas alguma coisa ficou abaixo do ideal. "
                       "Leia as observacoes abaixo antes de usar.",
            "ruim": "Nao use este resultado sem investigar. Veja as observacoes abaixo.",
        }[q["nivel"]]
        self.mostrar_veredito(q["nivel"], f"{titulo}\n{resumo}")
        self.ultimo = r
        if messagebox.askyesno(TITULO, f"{titulo}\n\n{resumo}\n\nAbrir a pasta do arquivo?"):
            webbrowser.open(str(Path(r["saida"]).parent))

    def falhar(self, msg, detalhe):
        self.encerrar_execucao()
        self.escrever("")
        self.escrever("FALHOU: " + msg)
        self.escrever(detalhe)
        self.mostrar_veredito("ruim", "NAO DEU PARA PROCESSAR\n" + msg)
        messagebox.showerror(TITULO, msg)


def main():
    raiz = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:  # noqa: BLE001 - tema e cosmetico
        pass
    Janela(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
