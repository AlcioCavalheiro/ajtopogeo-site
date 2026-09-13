"""Relatorio da Fazenda: aba do programa unico, ou janela propria rodando sozinho.

Tres abas sobre o mesmo perimetro: o relatorio em PDF, a imagem de uma data
(RGB, NDVI, modelo de elevacao em GeoTIFF) e a serie de NDVI do periodo.
"""

import queue
import re
import sys
import threading
import traceback
import webbrowser
from datetime import date, timedelta
from pathlib import Path
from tkinter import (BOTH, END, LEFT, RIGHT, BooleanVar, StringVar, Tk, X, filedialog,
                     messagebox, scrolledtext, ttk)

TITULO = "Relatorio da Fazenda - AJ TopoGeo"
DESCRICAO = ("Relatorio tecnico em PDF a partir do perimetro em KML: CAR e SIGEF, imagem de "
             "satelite, NDVI, relevo, chuva e referencias de valor da terra.")

# Rodando por pythonw nao existe console: falha na partida ficaria invisivel.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "marca"))

try:
    import marca
    import fazenda_fontes as fontes
    import fazenda_geo as geo
    import fazenda_imagens as imagens
    import fazenda_relatorio as relatorio
except Exception:  # noqa: BLE001
    _erro = traceback.format_exc()
    if __name__ != "__main__":
        # importado pelo programa unico: quem importou mostra a falha na aba e
        # mantem o resto do programa de pe
        raise
    try:
        Path(__file__).with_name("erro_na_partida.txt").write_text(_erro, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter.messagebox as _mb
        _r = Tk()
        _r.withdraw()
        _mb.showerror(TITULO, "O programa nao conseguiu iniciar.\n\n" + _erro.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        pass
    raise SystemExit(1)

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB",
       "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]


def data_iso(texto):
    """Aceita 2026-09-13 ou 13/09/2026; devolve AAAA-MM-DD ou None."""
    t = texto.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return t
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


class Janela:
    """A tela do relatorio.

    `raiz` e a janela quando o programa roda sozinho, ou o quadro da aba quando
    ele vem dentro do programa unico. `embutido=True` pula o que pertence a
    janela e troca o cabecalho com logo por uma linha de descricao.
    """

    def __init__(self, raiz, embutido=False):
        self.raiz = raiz
        if not embutido:
            raiz.title(TITULO)
            raiz.geometry("900x860")
            raiz.minsize(780, 640)
            marca.aplicar_icone(raiz)
        self.fila = queue.Queue()
        self.rodando = False
        self.parar = threading.Event()
        self.botoes = []

        corpo = ttk.Frame(raiz, padding=12)
        corpo.pack(fill=BOTH, expand=True)
        if embutido:
            ttk.Label(corpo, text=DESCRICAO, foreground="#555", wraplength=900,
                      justify="left").pack(anchor="w", pady=(0, 10))
        else:
            marca.cabecalho(corpo, "Relatorio da Fazenda", DESCRICAO)

        # ---------- perimetro e saida: fora das abas, valem para as tres ----------
        bloco = ttk.LabelFrame(corpo, text=" Perimetro e pasta de saida ", padding=10)
        bloco.pack(fill=X, pady=(0, 8))
        self.kml = StringVar()
        self.saida = StringVar(value=str(Path.home() / "Documents"))
        for rotulo, var, comando in (("Perimetro (KML/KMZ):", self.kml, self.escolher_kml),
                                     ("Pasta de saida:", self.saida, self.escolher_saida)):
            linha = ttk.Frame(bloco)
            linha.pack(fill=X, pady=2)
            ttk.Label(linha, text=rotulo, width=20).pack(side=LEFT)
            ttk.Button(linha, text="Escolher...", command=comando).pack(side=RIGHT, padx=(6, 0))
            ttk.Entry(linha, textvariable=var).pack(side=LEFT, fill=X, expand=True)

        abas = ttk.Notebook(corpo)
        abas.pack(fill=X)
        self.montar_aba_relatorio(abas)
        self.montar_aba_data(abas)
        self.montar_aba_serie(abas)

        rodape = ttk.Frame(corpo)
        rodape.pack(fill=X, pady=(8, 6))
        # parada em modo determinado e vazia: em modo indeterminado a barra do
        # ttk mostra um bloco verde mesmo sem nada rodando
        self.barra = ttk.Progressbar(rodape, mode="determinate", value=0)
        self.barra.pack(side=LEFT, fill=X, expand=True)
        self.botao_parar = ttk.Button(rodape, text="Parar", command=self.pedir_parada, state="disabled")
        self.botao_parar.pack(side=LEFT, padx=(10, 0))

        self.log = scrolledtext.ScrolledText(corpo, height=12, wrap="none", font=("Consolas", 9),
                                             state="disabled")
        self.log.pack(fill=BOTH, expand=True)
        self.atualizar_bases()
        self.raiz.after(120, self.drenar)

    # ================= abas =================

    def _campo(self, pai, linha, rotulo, var, largura=34, dica=""):
        ttk.Label(pai, text=rotulo).grid(row=linha, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(pai, textvariable=var, width=largura).grid(row=linha, column=1, sticky="w", pady=3)
        if dica:
            ttk.Label(pai, text=dica, foreground="#888").grid(row=linha, column=2, sticky="w", padx=8)

    def montar_aba_relatorio(self, abas):
        aba = ttk.Frame(abas, padding=10)
        abas.add(aba, text="  Relatorio PDF  ")
        self.nome = StringVar(value="")
        self.municipio = StringVar()
        self.uf = StringVar(value="MS")
        self.responsavel = StringVar()
        self.empresa = StringVar(value="AJ TopoGeo")
        self.rl = StringVar(value="20")
        self.dias = StringVar(value="365")
        self.nuvem = StringVar(value="70")
        self.com_serie = BooleanVar(value=True)

        grade = ttk.Frame(aba)
        grade.pack(fill=X)
        self._campo(grade, 0, "Nome do imovel:", self.nome, 40)
        self._campo(grade, 1, "Municipio:", self.municipio, 40, "em branco: identifica pelo CAR")
        ttk.Label(grade, text="UF:").grid(row=2, column=0, sticky="w", pady=3)
        uf = ttk.Combobox(grade, textvariable=self.uf, values=UFS, width=6, state="readonly")
        uf.grid(row=2, column=1, sticky="w", pady=3)
        uf.bind("<<ComboboxSelected>>", lambda _e: self.atualizar_bases())
        self._campo(grade, 3, "Responsavel tecnico:", self.responsavel, 56)
        self._campo(grade, 4, "Empresa:", self.empresa, 40)
        self._campo(grade, 5, "Reserva Legal (%):", self.rl, 8, "20 fora da Amazonia Legal")
        self._campo(grade, 6, "Janela de busca (dias):", self.dias, 8)
        self._campo(grade, 7, "Nuvem max. na cena (%):", self.nuvem, 8)
        ttk.Checkbutton(grade, text="Incluir serie temporal de NDVI (alguns minutos a mais)",
                        variable=self.com_serie).grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self.situacao_bases = ttk.Label(aba, text="", foreground="#555", font=("Consolas", 8),
                                        justify="left")
        self.situacao_bases.pack(anchor="w", pady=(8, 6))
        botao = ttk.Button(aba, text="GERAR RELATORIO", command=self.gerar_relatorio)
        botao.pack(fill=X, ipady=6)
        self.botoes.append(botao)

    def montar_aba_data(self, abas):
        aba = ttk.Frame(abas, padding=10)
        abas.add(aba, text="  Imagem de uma data  ")
        hoje = date.today()
        self.d_ini = StringVar(value=(hoje - timedelta(days=90)).strftime("%d/%m/%Y"))
        self.d_fim = StringVar(value=hoje.strftime("%d/%m/%Y"))
        self.d_nuvem = StringVar(value="60")
        self.d_ndvi = BooleanVar(value=True)
        self.d_mde = BooleanVar(value=True)
        grade = ttk.Frame(aba)
        grade.pack(fill=X)
        self._campo(grade, 0, "Data inicial:", self.d_ini, 12)
        self._campo(grade, 1, "Data final:", self.d_fim, 12)
        self._campo(grade, 2, "Nuvem max. na cena (%):", self.d_nuvem, 8)
        ttk.Checkbutton(grade, text="NDVI (GeoTIFF + PNG)", variable=self.d_ndvi).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Checkbutton(grade, text="Modelo de elevacao GLO-30 + declividade", variable=self.d_mde).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(aba, text="Escolhe a cena com menos nuvem SOBRE O IMOVEL no periodo e grava os "
                            "GeoTIFF em SIRGAS 2000 / UTM.", foreground="#555").pack(anchor="w", pady=(8, 6))
        botao = ttk.Button(aba, text="BUSCAR E BAIXAR", command=self.gerar_data)
        botao.pack(fill=X, ipady=6)
        self.botoes.append(botao)

    def montar_aba_serie(self, abas):
        aba = ttk.Frame(abas, padding=10)
        abas.add(aba, text="  Serie de NDVI  ")
        hoje = date.today()
        self.s_ini = StringVar(value=(hoje - timedelta(days=365)).strftime("%d/%m/%Y"))
        self.s_fim = StringVar(value=hoje.strftime("%d/%m/%Y"))
        self.s_nuvem = StringVar(value="80")
        self.s_nuvem_area = StringVar(value="15")
        self.s_validos = StringVar(value="80")
        self.s_rasters = BooleanVar(value=False)
        grade = ttk.Frame(aba)
        grade.pack(fill=X)
        self._campo(grade, 0, "Data inicial:", self.s_ini, 12)
        self._campo(grade, 1, "Data final:", self.s_fim, 12)
        self._campo(grade, 2, "Nuvem max. na cena (%):", self.s_nuvem, 8)
        self._campo(grade, 3, "Nuvem max. no imovel (%):", self.s_nuvem_area, 8)
        self._campo(grade, 4, "Cobertura valida min. (%):", self.s_validos, 8)
        ttk.Checkbutton(grade, text="Gravar o raster de NDVI de cada data (pesado)",
                        variable=self.s_rasters).grid(row=5, column=0, columnspan=3, sticky="w", pady=2)
        botao = ttk.Button(aba, text="GERAR SERIE", command=self.gerar_serie)
        botao.pack(fill=X, ipady=6, pady=(8, 0))
        self.botoes.append(botao)

    # ================= entrada =================

    def escolher_kml(self):
        c = filedialog.askopenfilename(title="Perimetro do imovel",
                                       filetypes=[("KML / KMZ", "*.kml *.kmz"), ("Todos", "*.*")])
        if c:
            self.kml.set(c)
            if not self.nome.get().strip():
                self.nome.set(Path(c).stem.replace("_", " "))
            self.saida.set(str(Path(c).parent))

    def escolher_saida(self):
        c = filedialog.askdirectory(title="Pasta de saida")
        if c:
            self.saida.set(c)

    def atualizar_bases(self):
        linhas = [f"{chave:14s} {texto}" for chave, texto in
                  fontes.situacao_das_bases(geo.pasta_do_programa(), self.uf.get())]
        self.situacao_bases.config(text="Bases:\n" + "\n".join(linhas))

    def _conferir_entrada(self):
        kml, saida = self.kml.get().strip(), self.saida.get().strip()
        if not kml or not Path(kml).is_file():
            messagebox.showwarning(TITULO, "Escolha o arquivo KML ou KMZ do perimetro.")
            return None
        if not saida or not Path(saida).is_dir():
            messagebox.showwarning(TITULO, "Escolha uma pasta de saida que exista.")
            return None
        return kml, saida

    def _numeros(self, pares):
        valores = []
        for var, rotulo in pares:
            try:
                valores.append(float(var.get().replace(",", ".")))
            except ValueError:
                messagebox.showwarning(TITULO, f"Valor invalido em \"{rotulo}\".")
                return None
        return valores

    def _datas(self, *vars_):
        saida = [data_iso(v.get()) for v in vars_]
        if None in saida:
            messagebox.showwarning(TITULO, "Datas no formato 13/09/2026.")
            return None
        if saida[0] > saida[1]:
            messagebox.showwarning(TITULO, "A data inicial e depois da final.")
            return None
        return saida

    # ================= execucao =================

    def gerar_relatorio(self):
        entrada = self._conferir_entrada()
        if not entrada:
            return
        nums = self._numeros([(self.rl, "Reserva Legal"), (self.dias, "Janela de busca"),
                              (self.nuvem, "Nuvem max.")])
        if not nums:
            return
        nome = self.nome.get().strip() or Path(entrada[0]).stem
        # tudo o que vem de widget e lido aqui, na thread da janela: tocar em
        # StringVar de dentro da thread de trabalho derruba o tkinter
        args = (entrada[0], entrada[1], nome, self.municipio.get(), self.uf.get(),
                self.responsavel.get().strip(), self.empresa.get().strip(), nums[0], int(nums[1]),
                nums[2], self.com_serie.get())
        self.iniciar(relatorio.gerar_relatorio, args, "relatorio")

    def gerar_data(self):
        entrada = self._conferir_entrada()
        datas = entrada and self._datas(self.d_ini, self.d_fim)
        nums = datas and self._numeros([(self.d_nuvem, "Nuvem max.")])
        if not nums:
            return
        args = (entrada[0], entrada[1], datas[0], datas[1], nums[0], self.d_ndvi.get(), self.d_mde.get())
        self.iniciar(imagens.processar_data_unica, args, "pasta")

    def gerar_serie(self):
        entrada = self._conferir_entrada()
        datas = entrada and self._datas(self.s_ini, self.s_fim)
        nums = datas and self._numeros([(self.s_nuvem, "Nuvem max. na cena"),
                                        (self.s_nuvem_area, "Nuvem max. no imovel"),
                                        (self.s_validos, "Cobertura valida")])
        if not nums:
            return
        args = (entrada[0], entrada[1], datas[0], datas[1], nums[0], nums[1], nums[2], self.s_rasters.get())
        self.iniciar(imagens.processar_serie, args, "pasta")

    def iniciar(self, alvo, args, tipo):
        if self.rodando:
            return
        self.rodando = True
        self.parar.clear()
        for b in self.botoes:
            b.config(state="disabled")
        self.botao_parar.config(state="normal")
        self.barra.config(mode="indeterminate")
        self.barra.start(12)
        self.log.config(state="normal")
        self.log.delete("1.0", END)
        self.log.config(state="disabled")
        threading.Thread(target=self.trabalhar, args=(alvo, args, tipo), daemon=True).start()

    def trabalhar(self, alvo, args, tipo):
        try:
            resultado = alvo(*args, log=lambda t: self.fila.put(("log", t)), cancelar=self.parar.is_set)
            self.fila.put(("fim", (tipo, resultado)))
        except imagens.Cancelado:
            self.fila.put(("cancelado", None))
        # BaseException: um SystemExit dentro do processamento mataria a thread
        # em silencio e deixaria a barra girando para sempre
        except BaseException as e:  # noqa: BLE001
            self.fila.put(("erro", (str(e) or e.__class__.__name__, traceback.format_exc())))

    def pedir_parada(self):
        self.parar.set()
        self.escrever(">> parada pedida; termina a leitura em curso e para.")

    def escrever(self, texto):
        self.log.config(state="normal")
        self.log.insert(END, texto + "\n")
        self.log.see(END)
        self.log.config(state="disabled")

    def encerrar(self):
        self.rodando = False
        self.barra.stop()
        self.barra.config(mode="determinate", value=0)
        self.botao_parar.config(state="disabled")
        for b in self.botoes:
            b.config(state="normal")

    def drenar(self):
        try:
            while True:
                tipo, carga = self.fila.get_nowait()
                if tipo == "log":
                    self.escrever(carga)
                elif tipo == "fim":
                    self.encerrar()
                    qual, caminho = carga
                    pergunta = ("Relatorio gerado.\n\nAbrir o PDF?" if qual == "relatorio"
                                else "Arquivos gravados.\n\nAbrir a pasta?")
                    if messagebox.askyesno(TITULO, pergunta):
                        webbrowser.open(Path(caminho).as_uri() if qual == "relatorio" else str(caminho))
                elif tipo == "cancelado":
                    self.encerrar()
                    self.escrever("")
                    self.escrever("Parado a pedido.")
                elif tipo == "erro":
                    self.encerrar()
                    mensagem, detalhe = carga
                    self.escrever("")
                    self.escrever("FALHOU: " + mensagem)
                    self.escrever(detalhe)
                    messagebox.showerror(TITULO, mensagem[:400])
        except queue.Empty:
            pass
        self.raiz.after(120, self.drenar)


def autoteste():
    """Confere a instalacao sem abrir janela e sem precisar de internet."""
    problemas = []
    raiz = geo.pasta_do_programa()
    print("pasta do programa:", raiz)
    try:
        lib = geo.biblioteca()
        faltando = [f for f in ("GDALOpenEx", "OGR_G_MakeValid", "OGR_G_Intersection", "GDALWarp")
                    if not hasattr(lib, f)]
        drivers = {d: bool(lib.GDALGetDriverByName(d.encode())) for d in ("GTiff", "GeoJSON", "GML", "MEM")}
        print(f"  {'biblioteca GDAL':18s} {'OK   ' if not faltando else 'FALTA'} "
              f"{geo.curvas._localizar(Path(geo.carregar_config()['gdalBin'])).name}"
              + (f" sem {', '.join(faltando)}" if faltando else ""))
        print(f"  {'drivers':18s} " + ", ".join(f"{d} {'OK' if ok else 'FALTA'}" for d, ok in drivers.items()))
        if faltando or not all(drivers.values()):
            problemas.append("GDAL incompleto")
    except Exception as e:  # noqa: BLE001
        print(f"  {'biblioteca GDAL':18s} FALHOU  {e}")
        problemas.append("GDAL nao carregou")
    try:
        import certifi
        ok = Path(certifi.where()).is_file()
        print(f"  {'certificados':18s} {'OK   ' if ok else 'FALTA'} {certifi.where()}")
        if not ok:
            problemas.append("certificados")
    except ImportError:
        print(f"  {'certificados':18s} FALTA  certifi")
        problemas.append("certifi")
    import matplotlib
    import pyproj
    import reportlab
    print(f"  {'bibliotecas':18s} OK    matplotlib {matplotlib.__version__}, reportlab "
          f"{reportlab.Version}, pyproj {pyproj.__version__}")
    for chave, texto in fontes.situacao_das_bases(raiz, "MS"):
        print(f"  {'base ' + chave:18s} {texto}")
        if chave in ("vtn", "mercado", "modulo_fiscal") and texto == "AUSENTE":
            problemas.append(f"base {chave}")
    print("FALTANDO: " + ", ".join(problemas) if problemas else "Instalacao completa.")
    return 1 if problemas else 0


def relatorio_por_linha(argv):
    """`--relatorio perimetro.kml pasta [UF] [--sem-serie]`: gera o PDF sem janela.

    Existe para conferir o pacote instalado de ponta a ponta. O autoteste nao
    usa a rede de proposito -- o instalador roda em maquina sem internet --, e
    por isso nao prova que o curl, os certificados e o matplotlib congelados
    funcionam juntos. Isto prova.
    """
    posicionais = [a for a in argv[argv.index("--relatorio") + 1:] if not a.startswith("--")]
    if len(posicionais) < 2:
        print("uso: --relatorio perimetro.kml pasta_de_saida [UF] [--sem-serie]")
        return 2
    kml, pasta = Path(posicionais[0]), Path(posicionais[1])
    uf = posicionais[2].upper() if len(posicionais) > 2 else "MS"
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        pdf = relatorio.gerar_relatorio(kml, pasta, kml.stem.replace("_", " "), "", uf, "",
                                        "AJ TopoGeo", 20.0, 365, 70.0, "--sem-serie" not in argv,
                                        log=lambda t: print(t, flush=True), cancelar=lambda: False)
    except Exception:  # noqa: BLE001
        print(traceback.format_exc(), flush=True)
        return 1
    print(f"PDF: {pdf}", flush=True)
    return 0


def main():
    if "--autoteste" in sys.argv:
        sys.exit(autoteste())
    if "--relatorio" in sys.argv:
        sys.exit(relatorio_por_linha(sys.argv))
    raiz = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:  # noqa: BLE001
        pass
    Janela(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
