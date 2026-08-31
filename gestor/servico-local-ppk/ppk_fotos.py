"""PPK das fotos de drone DJI (Matrice 4 RTK e similares).

Processa o log bruto do rover contra a base RINEX no RTKLIB, interpola a
trajetoria no instante exato de cada disparo (arquivo .MRK), aplica o braco
antena->camera e escreve o CSV no mesmo formato que o DJI Terra gera.

Uso:
  py ppk_fotos.py --projeto "D:\\LEV 2026-08-27" --base-e 751382.175 \
     --base-n 7739504.037 --base-z 646.246 --epsg 31981
"""

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pyproj

# O RTKLIB 2.5.1 rejeita o cabecalho RINEX 3.05 que o Matrice 4 exporta e
# devolve posicoes absurdas; reetiquetar para 3.04 nao altera os dados.
VERSAO_RINEX_ACEITA = "3.04"

# pasta onde o script grava os arquivos intermediarios; fica de fora da busca
# para que um reprocessamento nao eleja o proprio rover normalizado como base
PASTA_TRABALHO = "_ppk"

RAIO_TERRA = 6378137.0


def carregar_config(base_dir):
    with open(base_dir / "config.json", encoding="utf-8") as f:
        return json.load(f)


def achar_arquivos(projeto):
    """Descobre os voos e a base dentro da pasta do projeto.

    Um cartao costuma trazer varios voos, cada um na sua pasta com .MRK, .OBS,
    .NAV e as fotos. **Todas** essas pastas ficam de fora da busca pela base --
    excluir so a do primeiro voo faria o script eleger o segundo voo como base,
    e o RTKLIB nao produz solucao nenhuma nesse caso.
    """
    mrks = sorted(projeto.rglob("*.MRK"))
    if not mrks:
        sys.exit(f"nenhum arquivo .MRK encontrado em {projeto}")
    pastas_drone = {m.parent for m in mrks}

    voos = []
    for mrk in mrks:
        rover_obs = mrk.with_suffix(".OBS")
        rover_nav = mrk.with_suffix(".NAV")
        faltando = [p.name for p in (rover_obs, rover_nav) if not p.exists()]
        if faltando:
            sys.exit(f"o voo {mrk.parent.name} esta sem {', '.join(faltando)}")
        fotos = sorted(p for p in mrk.parent.iterdir() if p.suffix.upper() == ".JPG")
        if not fotos:
            continue  # pasta de voo sem foto (so log) nao interessa
        voos.append(dict(mrk=mrk, rover_obs=rover_obs, rover_nav=rover_nav,
                         fotos=fotos, nome=mrk.parent.name))
    if not voos:
        sys.exit(f"nenhuma foto .JPG encontrada junto dos .MRK em {projeto}")

    candidatos, base_navs, recusados = [], [], []
    for p in projeto.rglob("*"):
        if not p.is_file() or p.parent in pastas_drone:
            continue
        if PASTA_TRABALHO in p.relative_to(projeto).parts:
            continue
        nome = p.name.upper()
        if re.search(r"\.\d\d?O(\.OBS)?$|\.OBS$", nome):
            if parece_do_drone(p):
                recusados.append(p)     # voo solto fora da pasta de voo
            else:
                candidatos.append(p)
        elif re.search(r"\.\d\d[NGLCP]$|\.NAV$", nome):
            base_navs.append(p)

    if not candidatos:
        extra = ""
        if recusados:
            extra = ("\n\nEncontrei arquivos de observacao, mas todos parecem ser do "
                     "drone e nao de uma base:\n  "
                     + "\n  ".join(r.name for r in recusados[:5]))
        sys.exit(f"observacao da base nao encontrada em {projeto}." + extra)

    # prefere o RINEX 3 (multiconstelacao); em empate, o de periodo mais longo
    descritos = [descrever_rinex(p) for p in candidatos]
    def peso(d):
        duracao = (d["fim"][1] - d["inicio"][1]) if d["inicio"] and d["fim"] else 0
        return (d["versao"], duracao)
    melhor = max(descritos, key=peso)

    return dict(voos=voos, base_obs=melhor["caminho"], base=melhor,
                base_navs=base_navs, candidatos=descritos, recusados=recusados)


def conferir_cobertura(base, voos):
    """Avisa, antes de processar, se a base nao cobre o horario de algum voo."""
    avisos = []
    if not (base["inicio"] and base["fim"]):
        return avisos
    ini, fim = base["inicio"][1], base["fim"][1]
    for voo in voos:
        eventos = ler_mrk(voo["mrk"])
        if not eventos:
            continue
        t0 = min(e["tow"] for e in eventos.values())
        t1 = max(e["tow"] for e in eventos.values())
        if t0 < ini or t1 > fim:
            falta = max(ini - t0, 0) + max(t1 - fim, 0)
            avisos.append(
                f"{voo['nome']}: o voo vai de {hora_do_tow(t0)} a {hora_do_tow(t1)}, "
                f"mas a base so gravou de {hora_do_tow(ini)} a {hora_do_tow(fim)} "
                f"({falta / 60:.0f} min descobertos).")
    return avisos


def hora_do_tow(tow):
    """Segundo da semana -> hora do dia, so para a mensagem ficar legivel."""
    s = int(tow) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def tow_gps(ano, mes, dia, hora, minuto, segundo):
    """Data/hora GPS -> (semana, segundo da semana), para comparar com o .MRK."""
    import datetime
    delta = (datetime.datetime(ano, mes, dia, hora, minuto, int(segundo))
             - datetime.datetime(1980, 1, 6))
    return delta.days // 7, (delta.days % 7) * 86400 + delta.seconds + (segundo - int(segundo))


def descrever_rinex(caminho):
    """Le o cabecalho: versao, receptor, altura de antena e periodo coberto.

    Serve para escolher a base com criterio e para avisar antes de processar,
    em vez de deixar o RTKLIB falhar com uma mensagem generica.
    """
    d = dict(caminho=caminho, versao=0.0, receptor="", marcador="",
             altura_antena=None, inicio=None, fim=None)
    try:
        with open(caminho, encoding="latin-1") as f:
            for linha in f:
                rot = linha[60:].strip()
                if rot == "RINEX VERSION / TYPE":
                    try:
                        d["versao"] = float(linha[:9].strip() or 0)
                    except ValueError:
                        pass
                elif rot == "MARKER NAME":
                    d["marcador"] = linha[:60].strip()
                elif rot == "REC # / TYPE / VERS":
                    d["receptor"] = linha[20:40].strip()
                elif rot == "ANTENNA: DELTA H/E/N":
                    try:
                        d["altura_antena"] = float(linha[:14])
                    except ValueError:
                        pass
                elif rot in ("TIME OF FIRST OBS", "TIME OF LAST OBS"):
                    c = linha[:43].split()
                    if len(c) >= 6:
                        try:
                            v = tow_gps(int(c[0]), int(c[1]), int(c[2]),
                                        int(c[3]), int(c[4]), float(c[5]))
                            d["inicio" if rot.startswith("TIME OF FIRST") else "fim"] = v
                        except ValueError:
                            pass
                elif rot == "END OF HEADER":
                    break
    except OSError:
        pass
    return d


def parece_do_drone(caminho):
    """O RINEX do rover DJI nao serve de base e nao pode ser candidato.

    Reconhecido pelo nome (DJI_...) e pela ausencia de altura de antena, que todo
    receptor montado em bastao registra e o de drone nao.
    """
    if re.match(r"^DJI_\d", caminho.name, re.IGNORECASE):
        return True
    d = descrever_rinex(caminho)
    return d["altura_antena"] is None and not d["marcador"]


def versao_rinex(caminho):
    try:
        with open(caminho, encoding="latin-1") as f:
            return float(f.readline()[:9].strip() or 0)
    except (OSError, ValueError):
        return 0.0


def normalizar_rinex(origem, destino):
    """Copia o RINEX rebaixando o cabecalho para a versao que o RTKLIB aceita."""
    with open(origem, encoding="latin-1") as fe, open(destino, "w", encoding="latin-1", newline="") as fs:
        cabecalho = fe.readline()
        if "RINEX VERSION / TYPE" in cabecalho:
            cabecalho = f"{VERSAO_RINEX_ACEITA:>9s}" + cabecalho[9:]
        fs.write(cabecalho)
        shutil.copyfileobj(fe, fs)


def escrever_conf(caminho, lat, lon, h, altura_antena, elmask=15):
    # elmaskhold fica em 15 de proposito: travar a ambiguidade em satelite baixo
    # derruba a taxa de fixacao (medido: 69% -> 49% num voo de 534 fotos).
    caminho.write_text(f"""pos1-posmode       =kinematic
pos1-frequency     =l1+l2
pos1-soltype       =combined
pos1-elmask        ={elmask}
pos1-dynamics      =on
pos1-tidecorr      =off
pos1-ionoopt       =brdc
pos1-tropopt       =saas
pos1-sateph        =brdc
pos1-navsys        =45

pos2-armode        =fix-and-hold
pos2-gloarmode     =fix-and-hold
pos2-bdsarmode     =on
pos2-arfilter      =on
pos2-arthres       =3
pos2-arthresmin    =3
pos2-arthresmax    =10
pos2-arthres1      =0.1
pos2-arlockcnt     =0
pos2-arelmask      ={elmask}
pos2-arminfix      =20
pos2-elmaskhold    =15
pos2-aroutcnt      =20
pos2-minfixsats    =4
pos2-minholdsats   =5
pos2-mindropsats   =10
pos2-maxage        =30
pos2-slipthres     =0.05
pos2-rejionno      =5.0
pos2-rejcode       =30.0
pos2-niter         =1
pos2-varholdamb    =0.1
pos2-gainholdamb   =0.01
pos2-syncsol       =on

out-solformat      =llh
out-outhead        =on
out-outopt         =on
out-timesys        =gpst
out-timeform       =tow
out-timendec       =6
out-degform        =deg
out-height         =ellipsoidal

ant2-postype       =llh
ant2-pos1          ={lat:.9f}
ant2-pos2          ={lon:.9f}
ant2-pos3          ={h:.4f}
ant2-antdele       =0.0000
ant2-antdeln       =0.0000
ant2-antdelu       ={altura_antena:.4f}
""", encoding="utf-8")


def ler_mrk(caminho):
    eventos = {}
    for linha in open(caminho, encoding="latin-1"):
        if not linha.strip():
            continue
        campos = linha.split()
        eventos[int(campos[0])] = dict(
            tow=float(campos[1]),
            n=float(re.search(r"([-\d.]+),N\b", linha).group(1)) / 1000.0,
            e=float(re.search(r"([-\d.]+),E\b", linha).group(1)) / 1000.0,
            v=float(re.search(r"([-\d.]+),V\b", linha).group(1)) / 1000.0,
        )
    return eventos


def ler_pos(caminho):
    epocas = []
    for linha in open(caminho, encoding="latin-1"):
        if linha.startswith("%") or not linha.strip():
            continue
        c = linha.split()
        epocas.append(dict(tow=float(c[1]), lat=float(c[2]), lon=float(c[3]),
                           h=float(c[4]), q=int(c[5]),
                           sdn=float(c[7]), sde=float(c[8]), sdu=float(c[9])))
    epocas.sort(key=lambda e: e["tow"])
    return epocas


def interpolar(epocas, tow):
    lo, hi = 0, len(epocas) - 1
    while lo < hi:
        meio = (lo + hi) // 2
        if epocas[meio]["tow"] < tow:
            lo = meio + 1
        else:
            hi = meio
    if lo == 0:
        return None
    a, b = epocas[lo - 1], epocas[lo]
    if not (a["tow"] <= tow <= b["tow"]):
        return None
    intervalo = b["tow"] - a["tow"]
    f = (tow - a["tow"]) / intervalo if intervalo else 0.0
    return dict(
        lat=a["lat"] + f * (b["lat"] - a["lat"]),
        lon=a["lon"] + f * (b["lon"] - a["lon"]),
        h=a["h"] + f * (b["h"] - a["h"]),
        q=max(a["q"], b["q"]),
        sdn=max(a["sdn"], b["sdn"]),
        sde=max(a["sde"], b["sde"]),
        sdu=max(a["sdu"], b["sdu"]),
    )


def ler_atitude(exiftool, fotos):
    # a lista de fotos vai num arquivo de argumentos: um voo de algumas centenas
    # de imagens estoura o limite de tamanho da linha de comando do Windows.
    with tempfile.NamedTemporaryFile("w", suffix=".args", delete=False,
                                     encoding="utf-8") as f:
        for p in fotos:
            f.write(f"{p}\n")
        lista = f.name
    try:
        saida = subprocess.run(
            [str(exiftool), "-charset", "filename=utf8", "-n", "-csv", "-FileName",
             "-GimbalYawDegree", "-GimbalPitchDegree", "-GimbalRollDegree",
             "-@", lista],
            capture_output=True, text=True, check=True).stdout
    finally:
        Path(lista).unlink(missing_ok=True)

    linhas = saida.strip().splitlines()
    cabecalho = linhas[0].split(",")
    idx = {nome: i for i, nome in enumerate(cabecalho)}
    atitude = {}
    for linha in linhas[1:]:
        c = linha.split(",")
        atitude[c[idx["FileName"]]] = (
            c[idx["GimbalYawDegree"]], c[idx["GimbalPitchDegree"]], c[idx["GimbalRollDegree"]])
    return atitude


def num(texto):
    """Formata igual ao DJI Terra: sem zeros a direita desnecessarios."""
    return f"{float(texto):g}"


# Tempo minimo de dado do rover antes da primeira foto para o filtro convergir.
# Nos dois voos medidos havia ~55 s e a ambiguidade ficou instavel; a pratica de
# campo e deixar o drone ligado e gravando alguns minutos antes de decolar.
CONVERGENCIA_MINIMA_S = 180


def concordancia_ida_volta(frente, tras):
    """Quanto as duas passagens do filtro concordam entre si.

    Ida e volta resolvem a ambiguidade de forma independente. Onde as duas
    chegam em solucao fixa, a ambiguidade e confiavel; se quase nunca coincidem,
    a solucao esta trocando de ambiguidade e as fotos saem em patamares
    diferentes. Manobra real do drone aparece igual nas duas passagens, entao
    este teste nao confunde voo com defeito -- foi por isso que substituiu a
    checagem por aceleracao, que deixava passar um degrau de 37 cm.
    """
    import bisect

    tt = [e["tow"] for e in tras]
    ambas, difs = 0, []
    for e in frente:
        if e["q"] != 1:
            continue
        i = bisect.bisect_left(tt, e["tow"])
        if 0 <= i < len(tras) and abs(tras[i]["tow"] - e["tow"]) < 1e-6 and tras[i]["q"] == 1:
            ambas += 1
            difs.append(abs(e["h"] - tras[i]["h"]) * 100)
    total = max(len(frente), len(tras)) or 1
    difs.sort()
    return dict(pct_ambas=100.0 * ambas / total, epocas_ambas=ambas,
                fix_frente=sum(1 for e in frente if e["q"] == 1),
                fix_tras=sum(1 for e in tras if e["q"] == 1),
                dif_mediana=difs[len(difs) // 2] if difs else None,
                dif_p90=difs[int(0.9 * (len(difs) - 1))] if difs else None,
                dif_maxima=difs[-1] if difs else None)


def conferir_qualidade(epocas, eventos, escritas, total_fotos,
                       ida_volta=None, inicio_rover=None):
    """Confere se a trajetoria presta, sem precisar de referencia externa."""
    import bisect

    tows = [e["tow"] for e in epocas]
    fixas = avaliadas = 0
    for ev in eventos.values():
        i = bisect.bisect_left(tows, ev["tow"])
        if 0 < i < len(epocas):
            avaliadas += 1
            fixas += epocas[i - 1]["q"] == 1
    pct = 100.0 * fixas / avaliadas if avaliadas else 0.0

    msgs, nivel = [], "ok"

    def rebaixar(novo):
        nonlocal nivel
        if {"ok": 0, "atencao": 1, "ruim": 2}[novo] > {"ok": 0, "atencao": 1, "ruim": 2}[nivel]:
            nivel = novo

    msgs.append(f"{fixas} de {avaliadas} fotos ({pct:.0f}%) em solucao fixa.")
    if pct < 30:
        rebaixar("ruim")
        msgs.append("Fixacao muito baixa: as coordenadas podem errar decimetros.")
    elif pct < 60:
        rebaixar("atencao")
        msgs.append("Fixacao mediana.")

    if ida_volta:
        # Sao tres situacoes diferentes, e confundi-las gera alarme falso:
        # poucas epocas em comum e FALTA DE EVIDENCIA, nao prova de erro. So da
        # para falar em divergencia quando as duas passagens fixam na mesma epoca
        # e mesmo assim discordam.
        n = ida_volta["epocas_ambas"]
        p90 = ida_volta["dif_p90"]
        if n < 30:
            rebaixar("atencao")
            msgs.append(
                f"A ambiguidade nao foi confirmada de forma independente: as passagens de "
                f"ida e volta fixaram juntas em apenas {n} epoca(s) "
                f"(ida fixou {ida_volta['fix_frente']}, volta {ida_volta['fix_tras']}). "
                "Isso nao quer dizer que esteja errado -- quer dizer que nao ha como "
                "verificar por aqui. Pode haver deslocamento sistematico de alguns "
                "centimetros. Para amarracao absoluta, use ponto de apoio em campo.")
        elif p90 is not None and p90 > 30:
            rebaixar("ruim")
            msgs.append(
                f"Ida e volta fixam juntas em {n} epocas e DISCORDAM: {p90:.0f} cm no "
                "percentil 90. Como resolvem a ambiguidade de forma independente, isso "
                "indica que a solucao troca de ambiguidade durante o voo e as fotos saem "
                "em patamares diferentes. E o defeito mais perigoso porque NAO aparece no "
                "desvio que o programa reporta.")
        elif p90 is not None and p90 > 10:
            rebaixar("atencao")
            msgs.append(f"Ida e volta fixam juntas em {n} epocas e concordam de forma "
                        f"apenas razoavel ({p90:.0f} cm no percentil 90).")
        else:
            msgs.append(f"Ambiguidade confirmada: ida e volta fixam juntas em {n} epocas "
                        f"e concordam em {ida_volta['dif_mediana']:.0f} cm na mediana.")

    if inicio_rover is not None and inicio_rover < CONVERGENCIA_MINIMA_S:
        msgs.append(
            f"So havia {inicio_rover:.0f} s de dado antes da primeira foto, pouco para o "
            "filtro convergir com folga. Isso NAO se resolve esperando no chao: o drone "
            "comeca a gravar o log bruto ja em altitude de voo, e da sempre a mesma "
            "sobra de menos de um minuto. Quem manda nisso e o firmware, nao o operador.")

    if escritas < total_fotos:
        rebaixar("atencao")
        msgs.append(f"{total_fotos - escritas} foto(s) ficaram sem coordenada.")

    return dict(pct_fixas=pct, fotos_fixas=fixas, fotos_avaliadas=avaliadas,
                ida_volta=ida_volta, nivel=nivel, mensagens=msgs)


def processar(projeto, lat, lon, base_z, cfg, elmask=15, altura_antena=None,
              saida=None, progresso=None, conferir=True, trabalho=None):
    """Roda o PPK completo e devolve o resultado com as metricas de qualidade.

    `trabalho` permite tirar os arquivos intermediarios de dentro do projeto.
    Dois processamentos simultaneos da mesma pasta se sobrescreveriam sem isso.
    """
    def aviso(txt):
        if progresso:
            progresso(txt)

    rnx2rtkp = Path(cfg["rtklibBin"]) / "rnx2rtkp.exe"
    exiftool = Path(cfg["exiftoolBin"]) / "exiftool.exe"
    for p in (rnx2rtkp, exiftool):
        if not p.exists():
            raise FileNotFoundError(f"ferramenta nao encontrada: {p} (confira o config.json)")

    arq = achar_arquivos(projeto)
    trabalho = Path(trabalho) if trabalho else (projeto / PASTA_TRABALHO)
    trabalho.mkdir(parents=True, exist_ok=True)

    if altura_antena is None:
        altura_antena = 0.0
        for linha in open(arq["base_obs"], encoding="latin-1"):
            if "ANTENNA: DELTA H/E/N" in linha:
                altura_antena = float(linha[:14])
                break
            if "END OF HEADER" in linha:
                break
    # base em RINEX 2.11 grava L2 em codigo-P enquanto o drone grava L2C: a
    # ambiguidade nunca fixa e o erro passa de 1 m. Melhor parar aqui e explicar
    # do que devolver um resultado ruim com cara de bom.
    versao = versao_rinex(arq["base_obs"])
    if versao and versao < 3:
        raise RuntimeError(
            f"A base esta em RINEX {versao:.2f} ({arq['base_obs'].name}) e nesse formato "
            "o processamento nao fecha: ela grava L2 em codigo-P enquanto o drone grava "
            "L2C, a ambiguidade nunca fixa e o erro fica acima de 1 metro.\n\n"
            "Exporte a base de novo, em RINEX 3.04 com todas as constelacoes, pelo "
            "programa do receptor ComNav, e coloque o arquivo na pasta do voo.")

    voos = arq["voos"]
    total_fotos = sum(len(v["fotos"]) for v in voos)
    b = arq["base"]
    periodo = (f", gravou de {hora_do_tow(b['inicio'][1])} a {hora_do_tow(b['fim'][1])}"
               if b["inicio"] and b["fim"] else "")
    aviso(f"Base: {arq['base_obs'].name} (RINEX {b['versao']:.2f}"
          f"{', ' + b['receptor'] if b['receptor'] else ''}{periodo}).")
    aviso(f"      antena {altura_antena:.3f} m sobre o marco.")
    # com varias bases na pasta, mostrar as descartadas evita escolha silenciosa errada
    if len(arq["candidatos"]) > 1:
        outros = [d for d in arq["candidatos"] if d["caminho"] != arq["base_obs"]]
        aviso("      (descartadas: "
              + ", ".join(f"{d['caminho'].name} RINEX {d['versao']:.2f}" for d in outros[:4])
              + ")")
    if arq["recusados"]:
        aviso(f"      ({len(arq['recusados'])} arquivo(s) do drone fora das pastas de voo "
              "foram ignorados como base)")
    aviso(f"{len(voos)} voo(s) na pasta, {total_fotos} fotos no total.")

    for a in conferir_cobertura(b, voos):
        aviso(f"ATENCAO  {a}")

    base_obs = trabalho / "base.obs"
    normalizar_rinex(arq["base_obs"], base_obs)
    conf = trabalho / "rtklib.conf"
    escrever_conf(conf, lat, lon, base_z, altura_antena, elmask)

    saida = Path(saida) if saida else (projeto / "PPK FOTOS.txt")
    escritas, faltando, por_voo = 0, [], []

    with open(saida, "w", encoding="utf-8", newline="") as f:
        for i, voo in enumerate(voos, 1):
            aviso(f"--- Voo {i} de {len(voos)}: {voo['nome']} ({len(voo['fotos'])} fotos) ---")
            rover_obs = trabalho / f"rover_{i}.obs"
            rover_nav = trabalho / f"rover_{i}.nav"
            normalizar_rinex(voo["rover_obs"], rover_obs)
            normalizar_rinex(voo["rover_nav"], rover_nav)
            entradas = [str(rover_obs), str(base_obs), str(rover_nav)]
            entradas += [str(p) for p in arq["base_navs"]]

            def rodar(caminho_conf, caminho_pos, _entradas=entradas):
                subprocess.run([str(rnx2rtkp), "-k", str(caminho_conf),
                                "-o", str(caminho_pos), *_entradas],
                               capture_output=True, check=True)
                return ler_pos(caminho_pos)

            aviso(f"    processando no RTKLIB (mascara {elmask} graus)...")
            epocas = rodar(conf, trabalho / f"trajetoria_{i}.pos")
            if not epocas:
                # diz o que foi conferido, em vez de mandar o usuario adivinhar
                eventos = ler_mrk(voo["mrk"])
                t0 = min(e["tow"] for e in eventos.values()) if eventos else None
                detalhe = [f"O RTKLIB nao produziu solucao para o voo {voo['nome']}.", ""]
                detalhe.append(f"Base usada:  {arq['base_obs'].name}"
                               f"  (RINEX {b['versao']:.2f})")
                if b["inicio"] and b["fim"]:
                    detalhe.append(f"  base gravou de {hora_do_tow(b['inicio'][1])} "
                                   f"a {hora_do_tow(b['fim'][1])}")
                if t0 is not None:
                    t1 = max(e["tow"] for e in eventos.values())
                    detalhe.append(f"  voo aconteceu de {hora_do_tow(t0)} a {hora_do_tow(t1)}")
                    if b["inicio"] and (t0 < b["inicio"][1] or t1 > b["fim"][1]):
                        detalhe.append("\n>> A base NAO cobre o horario do voo. "
                                       "E essa a causa mais provavel.")
                    else:
                        detalhe.append("\nOs horarios batem, entao o problema esta nos "
                                       "dados: confira se a base saiu em RINEX 3.04 com "
                                       "todas as constelacoes e se o arquivo nao esta "
                                       "truncado.")
                raise RuntimeError("\n".join(detalhe))

            # ida e volta separadas, so para conferir se a ambiguidade e confiavel
            ida_volta = None
            if conferir:
                aviso("    conferindo a ambiguidade (ida e volta separadas)...")
                passagens = {}
                for tipo in ("forward", "backward"):
                    c = trabalho / f"rtklib_{tipo}.conf"
                    c.write_text(conf.read_text(encoding="utf-8").replace(
                        "pos1-soltype       =combined",
                        f"pos1-soltype       ={tipo}"), encoding="utf-8")
                    passagens[tipo] = rodar(c, trabalho / f"trajetoria_{i}_{tipo}.pos")
                if passagens["forward"] and passagens["backward"]:
                    ida_volta = concordancia_ida_volta(passagens["forward"],
                                                       passagens["backward"])

            eventos = ler_mrk(voo["mrk"])
            aviso("    lendo a atitude do gimbal...")
            atitude = ler_atitude(exiftool, voo["fotos"])

            escritas_voo = 0
            for foto in voo["fotos"]:
                achado = re.search(r"_(\d+)_[A-Z]\.JPG$", foto.name, re.IGNORECASE)
                evento = eventos.get(int(achado.group(1))) if achado else None
                p = interpolar(epocas, evento["tow"]) if evento else None
                if p is None:
                    faltando.append(foto.name)
                    continue

                lat_cam = p["lat"] + (evento["n"] / RAIO_TERRA) * 180 / math.pi
                lon_cam = p["lon"] + (evento["e"] / (RAIO_TERRA * math.cos(math.radians(p["lat"])))) * 180 / math.pi
                h_cam = p["h"] - evento["v"]
                hacc = math.hypot(p["sdn"], p["sde"])
                vacc = p["sdu"]
                yaw, pitch, roll = atitude.get(foto.name, ("", "", ""))

                f.write(f"{foto.name},{lat_cam!r},{lon_cam!r},{h_cam!r},"
                        f"{num(yaw)},{num(pitch)},{num(roll)},{hacc:.5f},{vacc:.5f}\n")
                escritas_voo += 1
            escritas += escritas_voo

            convergencia = None
            if eventos and epocas:
                convergencia = min(e["tow"] for e in eventos.values()) - epocas[0]["tow"]
            q = conferir_qualidade(epocas, eventos, escritas_voo, len(voo["fotos"]),
                                   ida_volta=ida_volta, inicio_rover=convergencia)
            aviso(f"    {q['pct_fixas']:.0f}% em solucao fixa  ->  {q['nivel'].upper()}")
            por_voo.append(dict(nome=voo["nome"], qualidade=q))

    qualidade = juntar_qualidade(por_voo)
    return dict(saida=saida, escritas=escritas, faltando=faltando, por_voo=por_voo,
                altura_antena=altura_antena, elmask=elmask, qualidade=qualidade)


def juntar_qualidade(por_voo):
    """Resume a qualidade de varios voos: o pior nivel manda."""
    if not por_voo:
        return dict(nivel="ruim", pct_fixas=0.0, mensagens=["nenhum voo processado."])
    ordem = {"ok": 0, "atencao": 1, "ruim": 2}
    pior = max((v["qualidade"]["nivel"] for v in por_voo), key=lambda n: ordem[n])
    avaliadas = sum(v["qualidade"]["fotos_avaliadas"] for v in por_voo)
    fixas = sum(v["qualidade"]["fotos_fixas"] for v in por_voo)
    pct = 100.0 * fixas / avaliadas if avaliadas else 0.0

    msgs = [f"{len(por_voo)} voo(s), {fixas} de {avaliadas} fotos ({pct:.0f}%) em solucao fixa."]
    if len(por_voo) > 1:
        for v in por_voo:
            q = v["qualidade"]
            msgs.append(f"  {v['nome']}: {q['pct_fixas']:.0f}% fixa - {q['nivel'].upper()}")
    # detalha so os voos que nao ficaram bons, para nao repetir texto igual 8 vezes
    for v in por_voo:
        q = v["qualidade"]
        if q["nivel"] == "ok":
            continue
        msgs.append(f"[{v['nome']}]")
        msgs.extend("  " + m for m in q["mensagens"][1:])
    return dict(nivel=pior, pct_fixas=pct, fotos_fixas=fixas, fotos_avaliadas=avaliadas,
                mensagens=msgs)


def ler_ppp_ibge(caminho):
    """Le o relatorio .txt do IBGE-PPP e devolve a coordenada do marco.

    O HGEO do relatorio ja e a altitude elipsoidal NO MARCO: o IBGE desconta a
    altura de antena informada na epoca daquele rastreio. A altura de antena do
    voo e outra e sai do cabecalho do RINEX da base -- nao usar a do relatorio.
    """
    campos = {}
    for linha in open(caminho, encoding="latin-1"):
        partes = linha.split(None, 1)
        if len(partes) == 2:
            campos[partes[0].strip().upper()] = partes[1].strip()

    faltando = [c for c in ("LAT", "LON", "HGEO") if c not in campos]
    if faltando:
        raise ValueError("Este arquivo nao parece um relatorio do IBGE-PPP "
                         f"(faltam os campos {', '.join(faltando)}).")

    # o arquivo _LEIAME.txt tem os mesmos rotulos, mas com a descricao do campo
    # no lugar do valor -- por isso a validacao e sobre os numeros, nao os rotulos
    def numeros(txt, quantos):
        partes = txt.split()[:quantos]
        if len(partes) < quantos:
            raise ValueError
        return [float(x.replace(",", ".")) for x in partes]

    try:
        gl = numeros(campos["LAT"], 3)
        go = numeros(campos["LON"], 3)
        h = numeros(campos["HGEO"], 1)[0]
    except ValueError:
        raise ValueError("Este arquivo tem os rotulos do IBGE-PPP mas nao os valores. "
                         "Escolha o relatorio de resultados, nao o _LEIAME.") from None

    def graus(bruto, n):
        return (-1 if bruto.lstrip().startswith("-") else 1) * (abs(n[0]) + n[1] / 60 + n[2] / 3600)

    return dict(marco=campos.get("MARCO", "").split()[0] if campos.get("MARCO") else "",
                lat=graus(campos["LAT"], gl), lon=graus(campos["LON"], go), h=h,
                processado=campos.get("PROCES", ""))


def comparar_saidas(caminho_a, caminho_b):
    """Diferenca entre dois arquivos de geotag, em cm, foto a foto."""
    def ler(p):
        d = {}
        for linha in open(p, encoding="utf-8"):
            if linha.strip():
                c = linha.split(",")
                d[c[0]] = (float(c[1]), float(c[2]), float(c[3]))
        return d

    a, b = ler(caminho_a), ler(caminho_b)
    dn, de, dh = [], [], []
    for nome in a.keys() & b.keys():
        pa, pb = a[nome], b[nome]
        dn.append((pa[0] - pb[0]) * math.pi / 180 * RAIO_TERRA * 100)
        de.append((pa[1] - pb[1]) * math.pi / 180 * RAIO_TERRA * math.cos(math.radians(pa[0])) * 100)
        dh.append((pa[2] - pb[2]) * 100)
    if not dh:
        return None
    maior = max(max(abs(x) for x in v) for v in (dn, de, dh))
    return dict(n=len(dh), maior=maior,
                media=(sum(dn) / len(dn), sum(de) / len(de), sum(dh) / len(dh)))


def processar_escolhendo_mascara(projeto, lat, lon, base_z, cfg, saida=None,
                                 altura_antena=None, progresso=None, trabalho=None):
    """Processa com 15 e com 10 graus e fica com a que fixa mais.

    Confere antes que as duas concordam: se divergirem muito, a de 10 graus
    esta pegando satelite baixo demais e nao merece confianca.
    """
    def aviso(t):
        if progresso:
            progresso(t)

    trabalho = Path(trabalho) if trabalho else (projeto / PASTA_TRABALHO)
    trabalho.mkdir(parents=True, exist_ok=True)
    tentativas = []
    for elmask in (15, 10):
        aviso(f"--- Tentativa com mascara de {elmask} graus ---")
        r = processar(projeto, lat, lon, base_z, cfg, elmask=elmask,
                      altura_antena=altura_antena, conferir=False, trabalho=trabalho,
                      saida=trabalho / f"geotag_{elmask}.txt", progresso=progresso)
        aviso(f"Mascara {elmask}: {r['qualidade']['pct_fixas']:.0f}% das fotos em solucao fixa.")
        tentativas.append(r)

    melhor = max(tentativas, key=lambda r: r["qualidade"]["pct_fixas"])
    cmp = comparar_saidas(tentativas[0]["saida"], tentativas[1]["saida"])
    if cmp:
        aviso(f"As duas solucoes concordam: diferenca media de "
              f"{abs(cmp['media'][2]):.1f} cm em altura, maior diferenca {cmp['maior']:.0f} cm.")
        if cmp["maior"] > 100:
            melhor = tentativas[0]
            aviso("Diferenca grande demais entre as duas: ficando com a mascara de 15 graus, "
                  "que e a mais conservadora.")

    # roda de novo a vencedora, agora com a conferencia de ida e volta -- que e o
    # indicador que realmente diz se a ambiguidade e confiavel
    aviso(f"Escolhida a mascara de {melhor['elmask']} graus. Conferindo essa solucao...")
    final = processar(projeto, lat, lon, base_z, cfg, elmask=melhor["elmask"],
                      altura_antena=altura_antena, conferir=True, trabalho=trabalho,
                      saida=saida or (projeto / "PPK FOTOS.txt"), progresso=progresso)
    final["comparacao"] = cmp
    return final


def main():
    ap = argparse.ArgumentParser(description="PPK das fotos de drone DJI")
    ap.add_argument("--projeto", required=True, type=Path)
    ap.add_argument("--base-e", required=True, type=float)
    ap.add_argument("--base-n", required=True, type=float)
    ap.add_argument("--base-z", required=True, type=float)
    ap.add_argument("--epsg", default="31981", help="EPSG da coordenada da base (padrao SIRGAS2000/UTM 21S)")
    ap.add_argument("--altura-antena", type=float, default=None,
                    help="altura da antena sobre o marco; por padrao le do cabecalho da base")
    ap.add_argument("--elmask", type=int, default=15,
                    help="mascara de elevacao em graus. 15 e o recomendado pela T2R; "
                         "10 costuma fixar bastante mais epocas em voo com boa visada")
    ap.add_argument("--saida", type=Path, default=None)
    args = ap.parse_args()

    cfg = carregar_config(Path(__file__).parent)
    transformador = pyproj.Transformer.from_crs(f"EPSG:{args.epsg}", "EPSG:4326", always_xy=True)
    lon, lat = transformador.transform(args.base_e, args.base_n)

    try:
        r = processar(args.projeto, lat, lon, args.base_z, cfg, elmask=args.elmask,
                      altura_antena=args.altura_antena, saida=args.saida,
                      progresso=print)
    except (FileNotFoundError, RuntimeError) as erro:
        sys.exit(str(erro))

    print(f"escritas {r['escritas']} fotos em {r['saida']}")
    if r["faltando"]:
        print(f"sem solucao para {len(r['faltando'])}: {', '.join(r['faltando'][:5])}")
    print()
    for linha in r["qualidade"]["mensagens"]:
        print(f"  {linha}")


if __name__ == "__main__":
    main()
