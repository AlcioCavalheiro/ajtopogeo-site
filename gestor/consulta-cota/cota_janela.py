"""Janela de consulta sobre o modelo digital do terreno.

Abre pelo atalho "Consulta de Cota". Escolhe o .tif uma vez e trabalha nas tres
abas: cota de coordenadas, declividade da area e curvas de nivel.
"""

import csv
import math
import queue
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, Tk, X, filedialog, messagebox
from tkinter import scrolledtext, ttk

TITULO = "Consulta de Cota - AJ TopoGeo"

# Rodando por pythonw nao existe console: falha na partida ficaria invisivel.
# a marca fica em gestor/marca; empacotado, o PyInstaller poe o modulo junto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "marca"))

try:
    import marca
    import cota
    import curvas
    import mapa
    import relatorio as leitor_relatorio
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


# Niveis de generalizacao da curva, em multiplos da equidistancia. Nao sao
# chutes: saem da comparacao com as curvas desenhadas a mao que o usuario
# mandou como referencia (9 linhas, 2,5 vertices por 100 m, 948 m de mediana).
# Medido no MDT do Sao Jorge, com equidistancia de 2 m:
#
#   detalhado     23,4 vertices/100 m   mediana   18 m
#   equilibrado   10,0                  mediana  140 m
#   prancha        3,5                  mediana 1736 m   <- a referencia tem 2,5 / 948 m
DESENHOS = {
    "Detalhado (tudo o que o modelo tem)": (0.5, 1.0, 4.0, 0.25),
    "Equilibrado": (1.0, 2.0, 50.0, 0.5),
    "Prancha (mais limpo, como curva desenhada)": (2.0, 4.0, 150.0, 1.5),
}


class Janela:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title(TITULO)
        raiz.geometry("1060x860")
        raiz.minsize(900, 700)
        marca.aplicar_icone(raiz)
        self.fila = queue.Queue()
        self.info = None
        self.resultado = []
        self.faixas = []
        self.arquivo_curvas = None
        self.arquivo_declividade = None

        corpo = ttk.Frame(raiz, padding=12)
        corpo.pack(fill=BOTH, expand=True)
        marca.cabecalho(corpo, "Consulta de Cota",
                        "Cota de coordenadas sobre o modelo digital, e declividade "
                        "por faixa para projeto de terraco.")

        # ---------- modelo: fora das abas, vale para as duas ----------
        bloco = ttk.LabelFrame(corpo, text=" Modelo digital ", padding=10)
        bloco.pack(fill=X, pady=(0, 10))
        linha = ttk.Frame(bloco)
        linha.pack(fill=X)
        self.tif = StringVar()
        ttk.Button(linha, text="Escolher...", command=self.escolher).pack(side=RIGHT, padx=(6, 0))
        ttk.Entry(linha, textvariable=self.tif).pack(side=LEFT, fill=X, expand=True)
        self.resumo = ttk.Label(bloco, text="Nenhum modelo carregado.", foreground="#666",
                                justify="left")
        self.resumo.pack(anchor="w", pady=(6, 0))

        # O relatorio do Pix4D e achado sozinho pela arvore de pastas do projeto;
        # o do Agisoft nao segue essa arvore, e voo antigo pode ter sido movido de
        # lugar. Poder apontar o arquivo resolve os dois casos.
        linha = ttk.Frame(bloco)
        linha.pack(fill=X, pady=(8, 0))
        ttk.Label(linha, text="Relatorio:").pack(side=LEFT)
        self.caminho_relatorio = StringVar()
        ttk.Button(linha, text="Escolher...",
                   command=self.escolher_relatorio).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(linha, text="Limpar",
                   command=self.limpar_relatorio).pack(side=RIGHT, padx=(6, 0))
        ttk.Entry(linha, textvariable=self.caminho_relatorio).pack(side=LEFT, fill=X,
                                                                   expand=True, padx=(6, 0))

        abas = ttk.Notebook(corpo)
        abas.pack(fill=BOTH, expand=True)
        self.montar_aba_cota(abas)
        self.montar_aba_declive(abas)
        self.montar_aba_curvas(abas)

        self.raiz.after(120, self.drenar)

    # ================= aba 1: cota =================

    def montar_aba_cota(self, abas):
        aba = ttk.Frame(abas, padding=10)
        abas.add(aba, text="  Cota dos pontos  ")

        bloco = ttk.LabelFrame(aba, text=" Coordenadas ", padding=10)
        bloco.pack(fill=BOTH, expand=True, pady=(0, 8))
        topo = ttk.Frame(bloco)
        topo.pack(fill=X, pady=(0, 6))
        ttk.Label(topo, text="Ordem das colunas:").pack(side=LEFT)
        self.ordem = StringVar(value="Automatica (descobre sozinho)")
        ttk.Combobox(topo, textvariable=self.ordem, values=list(ORDENS), state="readonly",
                     width=26).pack(side=LEFT, padx=(6, 0))
        ttk.Button(topo, text="Carregar de arquivo...",
                   command=self.carregar_arquivo).pack(side=RIGHT)
        self.entrada = scrolledtext.ScrolledText(bloco, height=7, wrap="none",
                                                 font=("Consolas", 10))
        self.entrada.pack(fill=BOTH, expand=True)
        self.entrada.insert("1.0", EXEMPLO)
        self.entrada.bind("<FocusIn>", self.limpar_exemplo)

        bloco = ttk.LabelFrame(aba, text=" Incerteza ", padding=10)
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
        self.sigma_lev = {}
        for eixo, rot in (("e", "E"), ("n", "N"), ("z", "Z")):
            ttk.Label(linha, text=rot).pack(side=LEFT, padx=(8, 2))
            self.sigma_lev[eixo] = StringVar(value="")
            ttk.Entry(linha, textvariable=self.sigma_lev[eixo], width=8).pack(side=LEFT)
        self.relatorio = ttk.Label(bloco, text="", foreground="#666", justify="left")
        self.relatorio.pack(anchor="w", pady=(6, 0))

        self.botao = ttk.Button(aba, text="CONSULTAR", command=self.consultar)
        self.botao.pack(fill=X, ipady=6, pady=(0, 8))

        quadro = ttk.Frame(aba)
        quadro.pack(fill=BOTH, expand=True)
        cols = ("ponto", "e", "n", "cota", "se", "sn", "sz", "local", "declive", "situacao")
        titulos = ("Ponto", "Leste (E)", "Norte (N)", "Cota",
                   "sigma E", "sigma N", "sigma Z", "rugosidade", "declive", "Situacao")
        larguras = (80, 110, 120, 90, 70, 70, 70, 85, 70, 115)
        self.tabela = ttk.Treeview(quadro, columns=cols, show="headings", height=7)
        for c, t, w in zip(cols, titulos, larguras):
            self.tabela.heading(c, text=t)
            self.tabela.column(c, width=w,
                               anchor="w" if c in ("ponto", "situacao") else "e")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.pack(side=LEFT, fill=BOTH, expand=True)
        barra.pack(side=RIGHT, fill="y")

        rodape = ttk.Frame(aba)
        rodape.pack(fill=X, pady=(8, 0))
        self.situacao = ttk.Label(rodape, text="", foreground="#444")
        self.situacao.pack(side=LEFT)
        ttk.Button(rodape, text="Salvar CSV...", command=self.salvar).pack(side=RIGHT)
        ttk.Button(rodape, text="Copiar", command=self.copiar).pack(side=RIGHT, padx=(0, 6))

    # ================= aba 2: declividade =================

    def montar_aba_declive(self, abas):
        aba = ttk.Frame(abas, padding=10)
        abas.add(aba, text="  Declividade  ")

        ttk.Label(aba, justify="left", foreground="#555", text=
                  "Calcula a declividade a partir do modelo e mostra quanto de area cai em cada\n"
                  "faixa. Use o DTM (terreno), nao o DSM: sobre o DSM a conta sai da copa das\n"
                  "arvores e do telhado, e nao do chao.").pack(anchor="w", pady=(0, 10))

        self.botao_dec = ttk.Button(aba, text="GERAR DECLIVIDADE", command=self.gerar_declive)
        self.botao_dec.pack(fill=X, ipady=6, pady=(0, 4))
        self.barra_dec = ttk.Progressbar(aba, mode="indeterminate")

        quadro = ttk.Frame(aba)
        quadro.pack(fill=BOTH, expand=True, pady=(8, 0))
        cols = ("faixa", "classe", "ha", "pct")
        self.tab_dec = ttk.Treeview(quadro, columns=cols, show="headings", height=8)
        for c, t, w, a in (("faixa", "Declividade", 130, "w"),
                           ("classe", "Classe de relevo", 200, "w"),
                           ("ha", "Hectares", 120, "e"),
                           ("pct", "% da area", 110, "e")):
            self.tab_dec.heading(c, text=t)
            self.tab_dec.column(c, width=w, anchor=a)
        self.tab_dec.pack(side=LEFT, fill=BOTH, expand=True)
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.tab_dec.yview)
        self.tab_dec.configure(yscrollcommand=barra.set)
        barra.pack(side=RIGHT, fill="y")

        rodape = ttk.Frame(aba)
        rodape.pack(fill=X, pady=(8, 0))
        self.situacao_dec = ttk.Label(rodape, text="", foreground="#444", justify="left")
        self.situacao_dec.pack(side=LEFT)
        ttk.Button(rodape, text="Salvar CSV...",
                   command=self.salvar_declive).pack(side=RIGHT)
        ttk.Button(rodape, text="Copiar",
                   command=self.copiar_declive).pack(side=RIGHT, padx=(0, 6))
        self.botao_mapa = ttk.Button(rodape, text="MAPA EM PDF...", state="disabled",
                                     command=self.gerar_mapa)
        self.botao_mapa.pack(side=RIGHT, padx=(0, 6))

    # ================= aba 3: curvas de nivel =================

    def montar_aba_curvas(self, abas):
        aba = ttk.Frame(abas, padding=10)
        abas.add(aba, text="  Curvas de nivel  ")

        ttk.Label(aba, justify="left", foreground="#555", text=
                  "Gera as curvas de nivel do modelo em DXF, com a cota no Z de cada\n"
                  "vertice -- o Civil 3D consome direto como superficie. Use o DTM: sobre\n"
                  "o DSM a curva contorna copa de arvore e telhado. O DXF e o formato mais\n"
                  "lento de gravar; SHP e GPKG saem em uma fracao do tempo."
                  ).pack(anchor="w", pady=(0, 10))

        bloco = ttk.LabelFrame(aba, text=" Como desenhar ", padding=10)
        bloco.pack(fill=X, pady=(0, 8))
        grade = ttk.Frame(bloco)
        grade.pack(fill=X)

        self.eq = StringVar(value="1")
        self.mestra = StringVar(value="5")
        ttk.Label(grade, text="Equidistancia [m]:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(grade, textvariable=self.eq, width=8,
                     values=("0,5", "1", "2", "5")).grid(row=0, column=1, sticky="w", padx=(6, 20))
        ttk.Label(grade, text="Mestra a cada:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(grade, textvariable=self.mestra, from_=0, to=10, width=6,
                    ).grid(row=0, column=3, sticky="w", padx=(6, 0))
        ttk.Label(grade, text="curvas (0 desliga)", foreground="#777",
                  ).grid(row=0, column=4, sticky="w", padx=(6, 0))

        linha2 = ttk.Frame(bloco)
        linha2.pack(fill=X, pady=(8, 0))
        ttk.Label(linha2, text="Nivel de detalhe:").pack(side=LEFT)
        self.desenho = StringVar(value="Equilibrado")
        caixa = ttk.Combobox(linha2, textvariable=self.desenho, state="readonly",
                             width=38, values=list(DESENHOS))
        caixa.pack(side=LEFT, padx=(6, 8))
        caixa.bind("<<ComboboxSelected>>", self.aplicar_desenho)
        ttk.Label(linha2, text="preenche o ajuste fino abaixo", foreground="#777"
                  ).pack(side=LEFT)

        avancado = ttk.LabelFrame(aba, text=" Ajuste fino (o nivel de detalhe preenche; da para mudar) ",
                                  padding=10)
        avancado.pack(fill=X, pady=(0, 8))
        fina = ttk.Frame(avancado)
        fina.pack(fill=X)
        self.pixel = StringVar()
        self.suave = StringVar()
        self.minimo = StringVar()
        self.simpl = StringVar()
        self.vazio = StringVar()
        campos = (("Pixel de trabalho [m]:", self.pixel, "metade da equidistancia"),
                  ("Suavizacao [m]:", self.suave, "um pixel de trabalho"),
                  ("Descartar trechos abaixo de [m]:", self.minimo, "oito pixels"),
                  ("Simplificar ate [m]:", self.simpl, "meio pixel de trabalho"),
                  ("Vazio do modelo:", self.vazio, "o que o raster declarar"))
        for i, (rotulo, variavel, padrao) in enumerate(campos):
            ttk.Label(fina, text=rotulo).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(fina, textvariable=variavel, width=10).grid(row=i, column=1,
                                                                  sticky="w", padx=(6, 8))
            ttk.Label(fina, text="em branco: " + padrao, foreground="#777",
                      ).grid(row=i, column=2, sticky="w")

        self.eq.trace_add("write", lambda *_: self.aplicar_desenho())
        self.aplicar_desenho()

        self.botao_cur = ttk.Button(aba, text="GERAR CURVAS", command=self.gerar_curvas)
        self.botao_cur.pack(fill=X, ipady=6, pady=(4, 4))
        self.barra_cur = ttk.Progressbar(aba, mode="determinate", maximum=100)

        rodape = ttk.Frame(aba)
        rodape.pack(fill=X, pady=(8, 0))
        self.situacao_cur = ttk.Label(rodape, text="", foreground="#444", justify="left",
                                      wraplength=760)
        self.situacao_cur.pack(side=LEFT, fill=X, expand=True)
        self.botao_pasta = ttk.Button(rodape, text="Abrir a pasta",
                                      command=self.abrir_pasta_curvas, state="disabled")
        self.botao_pasta.pack(side=RIGHT)

    def aplicar_desenho(self, _evento=None):
        """Escreve nos campos os numeros do nivel escolhido.

        Preenche em vez de guardar escondido: o usuario ve o que foi aplicado e
        pode mexer em um numero so, que e como se trabalha de verdade.
        """
        fatores = DESENHOS.get(self.desenho.get())
        if not fatores:
            return
        try:
            eq = cota.numero(self.eq.get() or "1")
        except ValueError:
            return
        if eq <= 0:
            return
        for variavel, fator, casas in zip(
                (self.pixel, self.suave, self.minimo, self.simpl), fatores, (2, 2, 0, 2)):
            variavel.set(("%." + str(casas) + "f") % (eq * fator))

    def numero_opcional(self, variavel, rotulo):
        """Le um campo que pode ficar vazio, aceitando virgula decimal."""
        texto = variavel.get().strip()
        if not texto:
            return None
        try:
            return cota.numero(texto)
        except ValueError:
            raise ValueError(f"O campo \"{rotulo}\" nao e um numero: {texto}") from None

    def gerar_curvas(self):
        caminho = self.tif.get().strip()
        if not caminho or not Path(caminho).exists():
            messagebox.showerror(TITULO, "Escolha o arquivo do modelo digital (.tif).")
            return
        if "dsm" in Path(caminho).name.lower():
            if not messagebox.askyesno(
                    TITULO,
                    "O arquivo escolhido parece ser um DSM (modelo de superficie).\n\n"
                    "As curvas sairiam contornando a copa das arvores e os telhados, nao "
                    "o terreno. O certo e usar o DTM.\n\nGerar assim mesmo?"):
                return
        try:
            opcoes = dict(
                equidistancia=cota.numero(self.eq.get() or "1"),
                mestra_a_cada=int(self.mestra.get() or 0),
                pixel=self.numero_opcional(self.pixel, "Pixel de trabalho"),
                suavizacao=self.numero_opcional(self.suave, "Suavizacao"),
                comprimento_minimo=self.numero_opcional(self.minimo, "Descartar trechos"),
                simplificacao=self.numero_opcional(self.simpl, "Simplificar ate"),
                nodata=self.numero_opcional(self.vazio, "Vazio do modelo"),
            )
        except ValueError as e:
            messagebox.showerror(TITULO, str(e))
            return
        if opcoes["equidistancia"] <= 0:
            messagebox.showerror(TITULO, "A equidistancia precisa ser maior que zero.")
            return

        base = Path(caminho)
        saida = filedialog.asksaveasfilename(
            title="Salvar as curvas",
            initialfile=base.stem + "_curvas.dxf", initialdir=str(base.parent),
            defaultextension=".dxf",
            filetypes=[("DXF para CAD", "*.dxf"), ("Shapefile", "*.shp"),
                       ("GeoPackage", "*.gpkg"), ("GeoJSON", "*.geojson")])
        if not saida:
            return

        self.botao_cur.config(state="disabled", text="Gerando...")
        self.botao_pasta.config(state="disabled")
        self.barra_cur.stop()
        self.barra_cur.config(mode="determinate")
        self.barra_cur.pack(fill=X, pady=(0, 6))
        self.barra_cur["value"] = 0
        self.situacao_cur.config(text="lendo o modelo...", foreground="#444")
        threading.Thread(target=self.trabalhar_curvas, args=(caminho, saida, opcoes),
                         daemon=True).start()

    def trabalhar_curvas(self, caminho, saida, opcoes):
        # o GDAL chama o progresso milhares de vezes; so o que muda o inteiro na
        # barra vai para a fila, senao a janela gasta mais tempo redesenhando do
        # que o contorno gasta calculando
        ultimo = [-1]

        def progresso(fracao):
            pct = int(fracao * 100)
            if pct != ultimo[0]:
                ultimo[0] = pct
                self.fila.put(("curvas_andamento", pct))
                # Depois da ultima feicao ainda vem a gravacao em disco, que o
                # GDAL faz no fechamento e nao reporta. No DXF ela e a maior
                # parte do tempo -- medido, 36 s de 44 s. Sem dizer isso, a
                # barra ficaria cheia e parada, que e como travamento parece.
                if pct >= 100:
                    self.fila.put(("curvas_gravando", None))

        try:
            res = curvas.gerar_curvas(caminho, saida, progresso=progresso, **opcoes)
            self.fila.put(("curvas", res))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("curvas_erro", str(e)))

    def terminar_curvas(self, res):
        self.arquivo_curvas = Path(res["arquivo"])
        self.botao_cur.config(state="normal", text="GERAR CURVAS")
        self.barra_cur.stop()
        self.barra_cur.pack_forget()
        self.botao_pasta.config(state="normal")
        # o aviso e a unica defesa contra entregar curva de buraco como curva de
        # terreno: quando existe, ele manda no texto e na cor
        self.situacao_cur.config(
            text=curvas.resumo(res) + "\n" + self.arquivo_curvas.name,
            foreground="#a4232b" if res.get("aviso") else "#0b6b3a")

    def abrir_pasta_curvas(self):
        if self.arquivo_curvas and self.arquivo_curvas.exists():
            webbrowser.open(str(self.arquivo_curvas.parent))

    # ================= modelo =================

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
            cfg = cota.carregar_config()
            gdalinfo, _, _ = cota.ferramentas(cfg)
            self.fila.put(("info", cota.info_modelo(gdalinfo, caminho)))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("info_erro", str(e)))
        try:
            achado = cota.achar_relatorio(caminho)
            if achado:
                self.fila.put(("relatorio_achado", achado))
                self.fila.put(("relatorio", leitor_relatorio.ler(achado)))
        except Exception:  # noqa: BLE001 - relatorio ausente nao e erro
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

    def escolher_relatorio(self):
        f = filedialog.askopenfilename(
            title="Relatorio de processamento",
            filetypes=[("Relatorio de processamento", "*.xml;*.pdf"),
                       ("Pix4D (report.xml)", "*.xml"),
                       ("Agisoft (PDF)", "*.pdf"), ("Todos", "*.*")])
        if not f:
            return
        self.caminho_relatorio.set(f)
        self.carregar_relatorio(Path(f), avisar=True)

    def limpar_relatorio(self):
        self.caminho_relatorio.set("")
        self.relatorio.config(text="")
        for eixo in self.sigma_lev:
            self.sigma_lev[eixo].set("")

    def carregar_relatorio(self, caminho, avisar=False):
        """Le o relatorio e preenche os sigmas. Ausencia nao e erro."""
        try:
            self.mostrar_relatorio(leitor_relatorio.ler(caminho))
        except Exception as e:  # noqa: BLE001
            if avisar:
                messagebox.showerror(
                    TITULO,
                    "Nao consegui ler este relatorio.\n\n"
                    "O programa le o report.xml do Pix4D e o Processing Report em PDF do "
                    "Agisoft Metashape. Se for outro formato, digite os sigmas a mao nos "
                    "campos E, N e Z.\n\n" + str(e)[:250])
            self.relatorio.config(text="")

    def mostrar_relatorio(self, d, sobrescrever=True):
        valores = d.get("rms") or d.get("sigma") or {}
        z = valores.get("z")
        if z is None:
            return
        # Pix4D e Agisoft gravam x/y; no sistema projetado de saida x e Leste e
        # y e Norte
        for eixo, chave in (("e", "x"), ("n", "y"), ("z", "z")):
            v = valores.get(chave)
            # achado sozinho nao apaga o que foi digitado a mao; escolhido no
            # botao, sim -- ali o usuario esta justamente mandando trocar
            if v is not None and (sobrescrever or not self.sigma_lev[eixo].get().strip()):
                self.sigma_lev[eixo].set(f"{v:.4f}".replace(".", ","))

        fonte = d.get("fonte", "Pix4D")
        gsd = d.get("gsd_cm")
        regra = (f"   Sem ponto de apoio, a expectativa realista fica em "
                 f"{gsd * 1.5:.0f} a {gsd * 3:.0f} cm (1,5 a 3 x GSD)." if gsd else "")
        cabeca = f"{fonte}: {d.get('projeto') or '(sem nome)'}"
        if d.get("processado"):
            cabeca += f" ({d['processado']})"

        linhas = [f"{cabeca}.  Erro medio das cameras: "
                  f"E {valores.get('x', 0) * 100:.1f} cm, N {valores.get('y', 0) * 100:.1f} cm, "
                  f"Z {z * 100:.1f} cm - preenchido acima.",
                  "Isso e PRECISAO INTERNA: mede o quanto o ajuste moveu as cameras em "
                  "relacao ao geotag que entrou, nao a posicao no terreno." + regra]

        # Erro horizontal na casa do metro nao e ruido de ajuste: ou o geotag
        # entrou deslocado, ou o bloco nao amarrou. Declarar isso como sigma faz
        # o resto do programa confiar no que nao deve.
        cor = "#8a5300"
        pior = max(abs(valores.get("x") or 0), abs(valores.get("y") or 0))
        if pior > 0.5:
            cor = "#a4232b"
            linhas.append(
                f"ATENCAO: {pior * 100:.0f} cm de erro medio no plano e alto demais para "
                "ser so ajuste. Confira se o geotag usado no processamento foi o "
                "corrigido, e use ponto de apoio antes de fechar projeto com isto.")
        self.relatorio.config(text="\n".join(linhas), foreground=cor)

    # ================= consulta de cota =================

    def limpar_exemplo(self, _evento):
        if self.entrada.get("1.0", END).strip() == EXEMPLO.strip():
            self.entrada.delete("1.0", END)

    def carregar_arquivo(self):
        f = filedialog.askopenfilename(title="Lista de coordenadas",
                                       filetypes=[("Texto e CSV", "*.txt *.csv"),
                                                  ("Todos", "*.*")])
        if not f:
            return
        try:
            texto = Path(f).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as e:
            messagebox.showerror(TITULO, str(e))
            return
        self.entrada.delete("1.0", END)
        self.entrada.insert("1.0", texto)

    def consultar(self):
        caminho = self.tif.get().strip()
        if not caminho or not Path(caminho).exists():
            messagebox.showerror(TITULO, "Escolha o arquivo do modelo digital (.tif).")
            return
        pontos, erros = cota.interpretar(self.entrada.get("1.0", END),
                                         ORDENS[self.ordem.get()])
        if not pontos:
            messagebox.showerror(TITULO, "Nao consegui ler nenhuma coordenada.\n\n"
                                 + "\n".join(erros[:8]))
            return
        if erros:
            messagebox.showwarning(TITULO, f"{len(erros)} linha(s) ignoradas:\n\n"
                                   + "\n".join(erros[:8]))
        try:
            raio = cota.numero(self.raio.get()) if self.raio.get().strip() else 0.50
        except ValueError:
            messagebox.showerror(TITULO, "O raio da analise precisa ser um numero.")
            return
        sigma_lev = {}
        for eixo, var in self.sigma_lev.items():
            if not var.get().strip():
                continue
            try:
                sigma_lev[eixo] = cota.numero(var.get())
            except ValueError:
                messagebox.showerror(TITULO, f"O sigma {eixo.upper()} precisa ser um numero.")
                return

        self.botao.config(state="disabled", text="Consultando...")
        self.situacao.config(text=f"consultando {len(pontos)} ponto(s)...")
        opcoes = dict(local=self.local.get() == "1", raio=raio, sigma_lev=sigma_lev)
        threading.Thread(target=self.trabalhar, args=(caminho, pontos, opcoes),
                         daemon=True).start()

    def trabalhar(self, caminho, pontos, opcoes):
        try:
            cfg = cota.carregar_config()
            gdalinfo, consulta, _ = cota.ferramentas(cfg)
            info = self.info or cota.info_modelo(gdalinfo, caminho)
            resultado = cota.consultar(consulta, caminho, pontos, info)

            if opcoes["local"]:
                vizinhos = cota.analisar_vizinhanca(consulta, caminho, pontos, info,
                                                    raio=opcoes["raio"])
                for r, v in zip(resultado, vizinhos):
                    r["sigma_local"] = v["sigma"]
                    r["declividade"] = v["declividade"]

            lev = opcoes["sigma_lev"]
            for r in resultado:
                if r.get("cota") is None:
                    continue
                r["sigma_e"] = lev.get("e")
                r["sigma_n"] = lev.get("n")
                # orcamento vertical: levantamento + rugosidade + a parcela que a
                # incerteza horizontal vira em terreno inclinado
                parcelas = [v for v in (lev.get("z"), r.get("sigma_local")) if v is not None]
                declive = r.get("declividade")
                sh = [v for v in (lev.get("e"), lev.get("n")) if v is not None]
                if declive is not None and sh:
                    horizontal = math.hypot(*sh) if len(sh) == 2 else sh[0]
                    parcelas.append(declive * horizontal)
                if parcelas:
                    r["sigma_z"] = math.sqrt(sum(v * v for v in parcelas))
            self.fila.put(("fim", resultado))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("erro", str(e)))

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
            txt += f"   |   {falhas} sem cota (veja Situacao)"
        self.situacao.config(text=txt, foreground="#8a5300" if falhas else "#0b6b3a")

    @staticmethod
    def celulas(r):
        def m(v, casas=3):
            return f"{v:.{casas}f}" if v is not None else "-"
        declive = (f"{r['declividade'] * 100:.1f}%"
                   if r.get("declividade") is not None else "-")
        return (r["nome"], m(r["e"]), m(r["n"]), m(r.get("cota")),
                m(r.get("sigma_e")), m(r.get("sigma_n")), m(r.get("sigma_z")),
                m(r.get("sigma_local")), declive, r["situacao"])

    # ================= declividade =================

    def gerar_declive(self):
        caminho = self.tif.get().strip()
        if not caminho or not Path(caminho).exists():
            messagebox.showerror(TITULO, "Escolha o arquivo do modelo digital (.tif).")
            return
        if "dsm" in Path(caminho).name.lower():
            if not messagebox.askyesno(
                    TITULO,
                    "O arquivo escolhido parece ser um DSM (modelo de superficie).\n\n"
                    "A declividade sairia da copa das arvores e dos telhados, nao do "
                    "terreno. O certo e usar o DTM.\n\nGerar assim mesmo?"):
                return
        self.botao_dec.config(state="disabled", text="Calculando...")
        self.barra_dec.pack(fill=X, pady=(0, 6))
        self.barra_dec.start(12)
        self.situacao_dec.config(text="calculando a declividade...", foreground="#444")
        threading.Thread(target=self.trabalhar_declive, args=(caminho,), daemon=True).start()

    def trabalhar_declive(self, caminho):
        try:
            cfg = cota.carregar_config()
            gdalinfo, _, gdaldem = cota.ferramentas(cfg)
            saida = Path(caminho).with_name(Path(caminho).stem + "_declividade.tif")
            cota.gerar_declividade(gdaldem, caminho, saida)
            faixas = cota.areas_por_faixa(gdalinfo, saida)
            self.fila.put(("declive", (faixas, saida)))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("declive_erro", str(e)))

    def terminar_declive(self, carga):
        faixas, saida = carga
        self.faixas = faixas
        self.arquivo_declividade = Path(saida)
        self.botao_mapa.config(state="normal")
        self.botao_dec.config(state="normal", text="GERAR DECLIVIDADE")
        self.barra_dec.stop()
        self.barra_dec.pack_forget()
        self.tab_dec.delete(*self.tab_dec.get_children())
        for f in faixas:
            rot = f"{f['inicio']} a {f['fim']} %" if f["fim"] else f"acima de {f['inicio']} %"
            self.tab_dec.insert("", END, values=(rot, f["nome"],
                                                 f"{f['hectares']:.2f}",
                                                 f"{f['porcento']:.1f}%"))
        total = sum(f["hectares"] for f in faixas)
        terraceavel = sum(f["hectares"] for f in faixas if f["inicio"] < 13)
        self.situacao_dec.config(
            text=(f"area total {total:.2f} ha   |   ate 13% de declive: "
                  f"{terraceavel:.2f} ha ({100 * terraceavel / total:.0f}%)\n"
                  f"raster salvo em {saida.name}"),
            foreground="#0b6b3a")

    def gerar_mapa(self):
        if not self.faixas or not self.arquivo_declividade:
            messagebox.showerror(TITULO, "Calcule a declividade primeiro.")
            return
        if not self.arquivo_declividade.exists():
            messagebox.showerror(TITULO, "O raster de declividade nao esta mais no lugar:\n"
                                 + str(self.arquivo_declividade))
            return

        com_curvas = self.arquivo_curvas and Path(self.arquivo_curvas).exists()
        if not com_curvas:
            if not messagebox.askyesno(
                    TITULO,
                    "Ainda nao ha curvas de nivel geradas nesta sessao.\n\n"
                    "O mapa sai so com as classes de declividade. Para ter as curvas "
                    "desenhadas por cima, gere-as antes na aba 'Curvas de nivel'.\n\n"
                    "Gerar o mapa assim mesmo?"):
                return

        base = Path(self.tif.get().strip() or "mapa")
        saida = filedialog.asksaveasfilename(
            title="Salvar o mapa de declividade",
            initialfile=base.stem + "_declividade.pdf", initialdir=str(base.parent),
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not saida:
            return

        self.botao_mapa.config(state="disabled", text="Montando...")
        self.situacao_dec.config(text="montando o mapa...", foreground="#444")
        # tudo o que vem de widget e lido AQUI, na thread da janela: um StringVar
        # consultado de outra thread levanta "main thread is not in main loop"
        rotulos = dict(titulo=base.parent.name or base.stem,
                       sistema=(self.info or {}).get("sistema", ""),
                       modelo=base.name)
        threading.Thread(target=self.trabalhar_mapa,
                         args=(saida, self.arquivo_curvas if com_curvas else None,
                               self.arquivo_declividade, list(self.faixas), rotulos),
                         daemon=True).start()

    def trabalhar_mapa(self, saida, curvas_arquivo, declividade, faixas, rotulos):
        try:
            res = mapa.gerar_mapa(declividade, saida, faixas,
                                  curvas_arquivo=curvas_arquivo, **rotulos)
            self.fila.put(("mapa", res))
        except Exception as e:  # noqa: BLE001
            self.fila.put(("mapa_erro", str(e)))

    def terminar_mapa(self, res):
        self.botao_mapa.config(state="normal", text="MAPA EM PDF...")
        self.arquivo_mapa = Path(res["arquivo"])
        curvas_txt = (f", com {res['curvas']} curvas de nivel" if res["curvas"]
                      else ", sem curvas de nivel")
        self.situacao_dec.config(
            text=(f"mapa gerado: {self.arquivo_mapa.name}{curvas_txt}\n"
                  f"{res['hectares']:.2f} ha  |  barra de escala de {res['escala_barra']} m"),
            foreground="#0b6b3a")
        if messagebox.askyesno(TITULO, "Mapa de declividade gerado.\n\nAbrir agora?"):
            webbrowser.open(str(self.arquivo_mapa))

    def linhas_declive(self):
        return [((f"{f['inicio']} a {f['fim']}" if f["fim"] else f"> {f['inicio']}"),
                 f["nome"], f"{f['hectares']:.2f}", f"{f['porcento']:.1f}")
                for f in self.faixas]

    def copiar_declive(self):
        if not self.faixas:
            return
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append("\n".join("\t".join(l) for l in self.linhas_declive()))
        self.situacao_dec.config(text="copiado para a area de transferencia",
                                 foreground="#0b6b3a")

    def salvar_declive(self):
        if not self.faixas:
            messagebox.showinfo(TITULO, "Gere a declividade primeiro.")
            return
        f = filedialog.asksaveasfilename(title="Salvar faixas de declividade",
                                         defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")])
        if not f:
            return
        with open(f, "w", encoding="utf-8-sig", newline="") as saida:
            w = csv.writer(saida, delimiter=";")
            w.writerow(["Declividade (%)", "Classe de relevo", "Hectares", "% da area"])
            w.writerows(self.linhas_declive())
        self.situacao_dec.config(text=f"salvo em {f}", foreground="#0b6b3a")

    # ================= saida da aba de cota =================

    def linhas_texto(self):
        return [tuple(c if c != "-" else "" for c in self.celulas(r))
                for r in self.resultado]

    def copiar(self):
        if not self.resultado:
            return
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append("\n".join("\t".join(l) for l in self.linhas_texto()))
        self.situacao.config(text="copiado para a area de transferencia",
                             foreground="#0b6b3a")

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
                w.writerow(["Ponto", "Leste", "Norte", "Cota", "Sigma E", "Sigma N",
                            "Sigma Z", "Rugosidade", "Declive", "Situacao"])
                w.writerows(self.linhas_texto())
        except OSError as e:
            messagebox.showerror(TITULO, str(e))
            return
        self.situacao.config(text=f"salvo em {f}", foreground="#0b6b3a")

    # ================= fila =================

    def drenar(self):
        try:
            while True:
                tipo, carga = self.fila.get_nowait()
                if tipo == "info":
                    self.mostrar_info(carga)
                elif tipo == "info_erro":
                    self.resumo.config(text=carga, foreground="#a4232b")
                elif tipo == "relatorio_achado":
                    self.caminho_relatorio.set(str(carga))
                elif tipo == "relatorio":
                    self.mostrar_relatorio(carga, sobrescrever=False)
                elif tipo == "fim":
                    self.terminar(carga)
                elif tipo == "erro":
                    self.botao.config(state="normal", text="CONSULTAR")
                    self.situacao.config(text="")
                    messagebox.showerror(TITULO, carga)
                elif tipo == "declive":
                    self.terminar_declive(carga)
                elif tipo == "curvas_andamento":
                    self.barra_cur["value"] = carga
                    self.situacao_cur.config(text=f"gerando as curvas... {carga}%",
                                             foreground="#444")
                elif tipo == "curvas_gravando":
                    self.barra_cur.config(mode="indeterminate")
                    self.barra_cur.start(12)
                    self.situacao_cur.config(
                        text="curvas prontas; gravando o arquivo em disco...",
                        foreground="#444")
                elif tipo == "curvas":
                    self.terminar_curvas(carga)
                elif tipo == "curvas_erro":
                    self.botao_cur.config(state="normal", text="GERAR CURVAS")
                    self.barra_cur.stop()
                    self.barra_cur.pack_forget()
                    self.situacao_cur.config(text="")
                    messagebox.showerror(TITULO, carga)
                elif tipo == "mapa":
                    self.terminar_mapa(carga)
                elif tipo == "mapa_erro":
                    self.botao_mapa.config(state="normal", text="MAPA EM PDF...")
                    self.situacao_dec.config(text="")
                    messagebox.showerror(TITULO, carga)
                elif tipo == "declive_erro":
                    self.botao_dec.config(state="normal", text="GERAR DECLIVIDADE")
                    self.barra_dec.stop()
                    self.barra_dec.pack_forget()
                    self.situacao_dec.config(text="")
                    messagebox.showerror(TITULO, carga)
        except queue.Empty:
            pass
        self.raiz.after(120, self.drenar)


def autoteste():
    """Confere a instalacao sem abrir janela: `Consulta de Cota.exe --autoteste`.

    Existe porque, sem console, uma instalacao quebrada apenas nao abre. Aqui a
    falha sai escrita e com codigo de saida, e e isso que o instalador consulta
    antes de dar o servico por concluido.
    """
    from pathlib import Path as _P
    try:
        cfg = cota.carregar_config()
    except OSError as e:
        print("config.json:", e)
        return 1
    print("pasta do programa:", cota.pasta_do_programa())
    problemas = []
    try:
        info, consulta, dem = cota.ferramentas(cfg)
        for rotulo, caminho in (("gdalinfo", info), ("gdallocationinfo", consulta),
                                ("gdaldem", dem)):
            print(f"  {rotulo:16s} OK    {caminho}")
    except FileNotFoundError as e:
        print(e)
        return 1
    for rotulo, chave in (("GDAL_DATA", "gdalData"), ("PROJ_LIB", "projData")):
        pasta = cfg.get(chave)
        ok = pasta and _P(pasta).is_dir()
        print(f"  {rotulo:16s} {'OK   ' if ok else 'AUSENTE'} {pasta or '(nao declarado)'}")
    # so rodar nao basta: sem as tabelas o GDAL abre o raster e nao sabe dizer
    # o sistema de coordenadas, que e a conferencia que a janela mostra
    import subprocess as _sp
    r = _sp.run([str(info), "--version"], capture_output=True, text=True, timeout=120)
    print("  " + (r.stdout.strip() or r.stderr.strip() or "sem resposta"))
    if r.returncode != 0:
        problemas.append("gdalinfo nao executou")

    # A aba de curvas nao usa executavel: fala com a propria DLL por ctypes. Se
    # o pacote vier com um GDAL velho demais, o simbolo nao existe e a falha so
    # apareceria no primeiro uso, com a janela ja aberta.
    try:
        lib = curvas.abrir_biblioteca(cfg)
        tem = hasattr(lib, "GDALContourGenerateEx")
        print(f"  {'biblioteca GDAL':16s} OK    {curvas._localizar(_P(cfg['gdalBin'])).name}")
        print(f"  {'curvas de nivel':16s} {'OK   ' if tem else 'FALTA'} "
              f"GDALContourGenerateEx")
        if not tem:
            problemas.append("GDALContourGenerateEx ausente")
    except Exception as e:  # noqa: BLE001
        print(f"  {'curvas de nivel':16s} FALHOU  {e}")
        problemas.append("biblioteca do GDAL nao carregou")
    print("FALTANDO: " + ", ".join(problemas) if problemas else "Instalacao completa.")
    return 1 if problemas else 0


def main():
    import sys as _sys
    if "--autoteste" in _sys.argv:
        _sys.exit(autoteste())
    raiz = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:  # noqa: BLE001
        pass
    Janela(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
