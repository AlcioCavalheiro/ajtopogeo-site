"""Janela para consultar a cota de coordenadas sobre um modelo digital.

Abre pelo atalho "Consulta de Cota". Escolhe o .tif do DSM ou DTM, cola a lista
de coordenadas e recebe a cota de cada ponto.
"""

import csv
import math
import queue
import threading
import traceback
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, Tk, X, filedialog, messagebox
from tkinter import scrolledtext, ttk

TITULO = "Consulta de Cota - AJ TopoGeo"

# Rodando por pythonw nao existe console: falha na partida ficaria invisivel.
try:
    import cota
except Exception:  # noqa: BLE001
    _erro = traceback.format_exc()
    try:
        Path(__file__).with_name("erro_na_partida.txt").write_text(_erro, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter.messagebox as _mb
        _r = Tk()
        _r.withdraw()
        _mb.showerror(TITULO, "O programa nao conseguiu iniciar.\n\n"
                      + _erro.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        pass
    raise SystemExit(1)

ORDENS = {"Automatica (descobre sozinho)": "auto",
          "Leste, Norte": "en",
          "Norte, Leste": "ne"}

EXEMPLO = ("Cole aqui as coordenadas, uma por linha. Exemplos aceitos:\n"
           "\n"
           "M-01  713000,00  7686800,00\n"
           "713000;7686800\n"
           "P3,712800.50,7686600.25\n")


class Janela:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title(TITULO)
        raiz.geometry("900x720")
        raiz.minsize(760, 600)
        self.fila = queue.Queue()
        self.info = None
        self.resultado = []

        corpo = ttk.Frame(raiz, padding=12)
        corpo.pack(fill=BOTH, expand=True)

        # ---------- modelo ----------
        bloco = ttk.LabelFrame(corpo, text=" 1. Modelo digital (DSM ou DTM) ", padding=10)
        bloco.pack(fill=X, pady=(0, 8))
        linha = ttk.Frame(bloco)
        linha.pack(fill=X)
        self.tif = StringVar()
        ttk.Button(linha, text="Escolher...", command=self.escolher).pack(side=RIGHT, padx=(6, 0))
        ttk.Entry(linha, textvariable=self.tif).pack(side=LEFT, fill=X, expand=True)
        self.resumo = ttk.Label(bloco, text="Nenhum modelo carregado.", foreground="#666",
                                justify="left")
        self.resumo.pack(anchor="w", pady=(6, 0))

        # ---------- coordenadas ----------
        bloco = ttk.LabelFrame(corpo, text=" 2. Coordenadas ", padding=10)
        bloco.pack(fill=BOTH, expand=True, pady=(0, 8))
        topo = ttk.Frame(bloco)
        topo.pack(fill=X, pady=(0, 6))
        ttk.Label(topo, text="Ordem das colunas:").pack(side=LEFT)
        self.ordem = StringVar(value="Automatica (descobre sozinho)")
        ttk.Combobox(topo, textvariable=self.ordem, values=list(ORDENS), state="readonly",
                     width=26).pack(side=LEFT, padx=(6, 0))
        ttk.Button(topo, text="Carregar de arquivo...",
                   command=self.carregar_arquivo).pack(side=RIGHT)
        self.entrada = scrolledtext.ScrolledText(bloco, height=8, wrap="none",
                                                 font=("Consolas", 10))
        self.entrada.pack(fill=BOTH, expand=True)
        self.entrada.insert("1.0", EXEMPLO)
        self.entrada.bind("<FocusIn>", self.limpar_exemplo)

        # ---------- qualidade ----------
        bloco = ttk.LabelFrame(corpo, text=" 3. Incerteza ", padding=10)
        bloco.pack(fill=X, pady=(0, 8))
        self.local = StringVar(value="1")
        ttk.Checkbutton(bloco, variable=self.local, onvalue="1", offvalue="0",
                        text="Medir a variacao do modelo em volta de cada ponto  "
                             "(rapido; separa ruido de declividade)").pack(anchor="w")
        linha = ttk.Frame(bloco)
        linha.pack(fill=X, pady=(6, 0))
        ttk.Label(linha, text="Raio da analise [m]:").pack(side=LEFT)
        self.raio = StringVar(value="0,50")
        ttk.Entry(linha, textvariable=self.raio, width=8).pack(side=LEFT, padx=(6, 20))
        ttk.Label(linha, text="Sigma do levantamento [m]:").pack(side=LEFT)
        self.sigma_lev = StringVar(value="")
        ttk.Entry(linha, textvariable=self.sigma_lev, width=8).pack(side=LEFT, padx=(6, 0))
        ttk.Label(linha, text="(vertical)", foreground="#888").pack(side=LEFT, padx=(6, 0))
        self.relatorio = ttk.Label(bloco, text="", foreground="#666", justify="left")
        self.relatorio.pack(anchor="w", pady=(6, 0))

        self.botao = ttk.Button(corpo, text="CONSULTAR", command=self.consultar)
        self.botao.pack(fill=X, ipady=6, pady=(0, 8))

        # ---------- resultado ----------
        bloco = ttk.LabelFrame(corpo, text=" 4. Resultado ", padding=10)
        bloco.pack(fill=BOTH, expand=True)
        cols = ("ponto", "e", "n", "cota", "sigma", "declive", "total", "situacao")
        titulos = ("Ponto", "Leste (E)", "Norte (N)", "Cota",
                   "Sigma local", "Declive", "Sigma total", "Situacao")
        larguras = (90, 115, 125, 95, 90, 75, 90, 130)
        self.tabela = ttk.Treeview(bloco, columns=cols, show="headings", height=8)
        for c, t, w in zip(cols, titulos, larguras):
            self.tabela.heading(c, text=t)
            self.tabela.column(c, width=w, anchor="e" if c in ("e", "n", "cota") else "w")
        barra = ttk.Scrollbar(bloco, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.pack(side=LEFT, fill=BOTH, expand=True)
        barra.pack(side=RIGHT, fill="y")

        rodape = ttk.Frame(corpo)
        rodape.pack(fill=X, pady=(8, 0))
        self.situacao = ttk.Label(rodape, text="", foreground="#444")
        self.situacao.pack(side=LEFT)
        ttk.Button(rodape, text="Salvar CSV...", command=self.salvar).pack(side=RIGHT)
        ttk.Button(rodape, text="Copiar", command=self.copiar).pack(side=RIGHT, padx=(0, 6))

        self.raiz.after(120, self.drenar)

    # ---------------- interface ----------------

    def limpar_exemplo(self, _evento):
        if self.entrada.get("1.0", END).strip() == EXEMPLO.strip():
            self.entrada.delete("1.0", END)

    def escolher(self):
        f = filedialog.askopenfilename(title="Modelo digital",
                                       filetypes=[("Raster GeoTIFF", "*.tif *.tiff"),
                                                  ("Todos", "*.*")])
        if not f:
            return
        self.tif.set(f)
        self.resumo.config(text="Lendo o modelo...", foreground="#666")
        threading.Thread(target=self.ler_info, args=(f,), daemon=True).start()

    def ler_info(self, caminho):
        try:
            cfg = cota.carregar_config(Path(__file__).parent)
            gdalinfo, _ = cota.ferramentas(cfg)
            self.fila.put(("info", cota.info_modelo(gdalinfo, caminho)))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("info_erro", str(e)))
        # o relatorio do Pix4D fica previsivelmente ao lado do raster
        try:
            achado = cota.achar_relatorio(caminho)
            if achado:
                self.fila.put(("relatorio", cota.ler_relatorio_pix4d(achado)))
        except Exception:  # noqa: BLE001 - relatorio ausente ou ilegivel nao e erro
            pass

    def mostrar_info(self, i):
        self.info = i
        aviso = ""
        if i["geografico"]:
            aviso = ("\nATENCAO: este modelo esta em graus (latitude/longitude), nao em "
                     "metros. As coordenadas coladas precisam estar no mesmo sistema.")
        self.resumo.config(
            text=(f"Sistema: {i['sistema']}   |   pixel {i['pixel']:.3f}\n"
                  f"Abrange  E {i['e_min']:.1f} a {i['e_max']:.1f}   "
                  f"N {i['n_min']:.1f} a {i['n_max']:.1f}" + aviso),
            foreground="#a4232b" if aviso else "#0b6b3a")

    def mostrar_relatorio(self, d):
        """Preenche o sigma a partir do relatorio, deixando claro o que ele mede."""
        z = (d.get("rms") or d.get("sigma") or {}).get("z")
        if z is None:
            return
        if not self.sigma_lev.get().strip():
            self.sigma_lev.set(f"{z:.4f}".replace(".", ","))
        gsd = d.get("gsd_cm")
        regra = (f"   Sem ponto de apoio, a expectativa realista fica em "
                 f"{gsd * 1.5:.0f} a {gsd * 3:.0f} cm (1,5 a 3 x GSD)." if gsd else "")
        self.relatorio.config(
            text=(f"Relatorio do Pix4D: {d['projeto']} ({d['processado']}).  "
                  f"RMS vertical do bloco {z * 100:.1f} cm - preenchido acima.\n"
                  "Isso e PRECISAO INTERNA: mede o quanto o ajuste moveu as cameras em "
                  "relacao ao geotag que entrou, nao a posicao no terreno." + regra),
            foreground="#8a5300")

    def carregar_arquivo(self):
        f = filedialog.askopenfilename(title="Lista de coordenadas",
                                       filetypes=[("Texto e CSV", "*.txt *.csv"), ("Todos", "*.*")])
        if not f:
            return
        try:
            texto = Path(f).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as e:
            messagebox.showerror(TITULO, str(e))
            return
        self.entrada.delete("1.0", END)
        self.entrada.insert("1.0", texto)

    # ---------------- execucao ----------------

    def consultar(self):
        caminho = self.tif.get().strip()
        if not caminho or not Path(caminho).exists():
            messagebox.showerror(TITULO, "Escolha o arquivo do modelo digital (.tif).")
            return
        pontos, erros = cota.interpretar(self.entrada.get("1.0", END),
                                         ORDENS[self.ordem.get()])
        if erros and not pontos:
            messagebox.showerror(TITULO, "Nao consegui ler as coordenadas:\n\n"
                                 + "\n".join(erros[:8]))
            return
        if not pontos:
            messagebox.showerror(TITULO, "Cole as coordenadas na caixa de texto.")
            return
        if erros:
            messagebox.showwarning(TITULO, f"{len(erros)} linha(s) foram ignoradas:\n\n"
                                   + "\n".join(erros[:8]))

        # os campos sao lidos aqui, na linha principal: tkinter nao aceita
        # leitura de widget a partir da thread de trabalho
        try:
            raio = cota.numero(self.raio.get()) if self.raio.get().strip() else 0.50
        except ValueError:
            messagebox.showerror(TITULO, "O raio da analise precisa ser um numero.")
            return
        sigma_lev = None
        if self.sigma_lev.get().strip():
            try:
                sigma_lev = cota.numero(self.sigma_lev.get())
            except ValueError:
                messagebox.showerror(TITULO, "O sigma do levantamento precisa ser um numero.")
                return
        opcoes = dict(local=self.local.get() == "1", raio=raio, sigma_lev=sigma_lev)

        self.botao.config(state="disabled", text="Consultando...")
        self.situacao.config(text=f"consultando {len(pontos)} ponto(s)...")
        threading.Thread(target=self.trabalhar, args=(caminho, pontos, opcoes),
                         daemon=True).start()

    def trabalhar(self, caminho, pontos, opcoes):
        try:
            cfg = cota.carregar_config(Path(__file__).parent)
            gdalinfo, consulta = cota.ferramentas(cfg)
            info = self.info or cota.info_modelo(gdalinfo, caminho)
            resultado = cota.consultar(consulta, caminho, pontos, info)

            if opcoes["local"]:
                vizinhos = cota.analisar_vizinhanca(consulta, caminho, pontos, info,
                                                    raio=opcoes["raio"])
                for r, v in zip(resultado, vizinhos):
                    r["sigma_local"] = v["sigma"]
                    r["declividade"] = v["declividade"]

            for r in resultado:
                sl, sv = r.get("sigma_local"), opcoes["sigma_lev"]
                if r.get("cota") is None:
                    continue
                if sl is not None and sv is not None:
                    r["sigma_total"] = math.hypot(sl, sv)
                elif sv is not None:
                    r["sigma_total"] = sv
                elif sl is not None:
                    r["sigma_total"] = sl
            self.fila.put(("fim", resultado))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("erro", str(e)))

    def drenar(self):
        try:
            while True:
                tipo, carga = self.fila.get_nowait()
                if tipo == "info":
                    self.mostrar_info(carga)
                elif tipo == "info_erro":
                    self.resumo.config(text=carga, foreground="#a4232b")
                elif tipo == "relatorio":
                    self.mostrar_relatorio(carga)
                elif tipo == "fim":
                    self.terminar(carga)
                elif tipo == "erro":
                    self.botao.config(state="normal", text="CONSULTAR")
                    self.situacao.config(text="")
                    messagebox.showerror(TITULO, carga)
        except queue.Empty:
            pass
        self.raiz.after(120, self.drenar)

    def terminar(self, resultado):
        self.resultado = resultado
        self.botao.config(state="normal", text="CONSULTAR")
        self.tabela.delete(*self.tabela.get_children())
        for r in resultado:
            self.tabela.insert("", END, values=self.celulas(r))
        ok = sum(1 for r in resultado if r["cota"] is not None)
        falhas = len(resultado) - ok
        txt = f"{ok} de {len(resultado)} com cota"
        if falhas:
            txt += f"   |   {falhas} sem cota (veja a coluna Situacao)"
        self.situacao.config(text=txt, foreground="#8a5300" if falhas else "#0b6b3a")

    # ---------------- saida ----------------

    @staticmethod
    def celulas(r):
        def m(v, casas=3):
            return f"{v:.{casas}f}" if v is not None else "-"
        return (r["nome"], m(r["e"]), m(r["n"]), m(r.get("cota")),
                m(r.get("sigma_local")), 
                f"{r['declividade']*100:.1f}%" if r.get("declividade") is not None else "-",
                m(r.get("sigma_total")), r["situacao"])

    def linhas_texto(self):
        return [tuple(c if c != "-" else "" for c in self.celulas(r))
                for r in self.resultado]

    def copiar(self):
        if not self.resultado:
            return
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append("\n".join("\t".join(l) for l in self.linhas_texto()))
        self.situacao.config(text="copiado para a area de transferencia", foreground="#0b6b3a")

    def salvar(self):
        if not self.resultado:
            messagebox.showinfo(TITULO, "Nada para salvar ainda.")
            return
        f = filedialog.asksaveasfilename(title="Salvar resultado", defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")])
        if not f:
            return
        try:
            with open(f, "w", encoding="utf-8-sig", newline="") as saida:
                w = csv.writer(saida, delimiter=";")
                w.writerow(["Ponto", "Leste", "Norte", "Cota", "Sigma local", "Declive", "Sigma total", "Situacao"])
                w.writerows(self.linhas_texto())
        except OSError as e:
            messagebox.showerror(TITULO, str(e))
            return
        self.situacao.config(text=f"salvo em {f}", foreground="#0b6b3a")


def main():
    raiz = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:  # noqa: BLE001
        pass
    Janela(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
