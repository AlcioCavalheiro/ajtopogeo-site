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
import os
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

# As duas ultimas colunas do arquivo de geotag NAO sao documentacao: o programa
# de fotogrametria usa como PESO de cada foto no ajuste do bloco. E o peso entra
# como exp(-residuo^2 / 2*sigma^2) -- uma foto declarada com 5 cm e que esteja
# 1 m fora vale exp(-200), que em ponto flutuante e simplesmente zero.
#
# Isso nao degrada devagar, quebra: no AQUARELA o Pix4D chegou a 2.170.541 pontos
# de amarracao, os pesos deram underflow, os pontos cairam para 19.887 (perda de
# 99%) e o passo 1 abortou com "unknown exception". A precisao declarada era
# 0,05/0,10 m e o residuo medio real era 1,14 m.
#
# Por isso os valores abaixo sao folgados de proposito. Declarar mais aperto do
# que a solucao entrega nao melhora nada -- so tira do ajuste a liberdade de
# corrigir o geotag pela geometria das imagens, que e justamente o que ele sabe
# fazer melhor que o GNSS.
SIGMA_REALISTA = {
    1: (0.15, 0.30),   # Q=1 solucao fixa
    2: (1.00, 2.00),   # Q=2 float -- a foto pode estar metros fora
}
SIGMA_REALISTA_PADRAO = (2.00, 4.00)   # single, dgps ou desconhecido


def sigma_da_foto(foto, modo, piso=None):
    """Precisao a declarar para a foto, conforme a qualidade da epoca.

    `piso` e a discordancia medida entre duas solucoes independentes naquela
    foto: quando ela e maior que o valor de tabela, e ela que vale. E medicao,
    nao estimativa, e serve exatamente para o caso em que a epoca se declara
    fixa mas nao esta.
    """
    if modo == "formal":
        return math.hypot(foto["sdn"], foto["sde"]), foto["sdu"]
    h, v = SIGMA_REALISTA.get(foto["q"], SIGMA_REALISTA_PADRAO)
    if piso:
        h, v = max(h, piso[0]), max(v, piso[1])
    return h, v


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
        raise RuntimeError(f"Nenhum arquivo .MRK encontrado em {projeto}.\n\n"
                           "A pasta precisa conter a pasta do voo, com as fotos e os "
                           "arquivos .MRK, .OBS e .NAV do drone.")
    pastas_drone = {m.parent for m in mrks}

    voos = []
    for mrk in mrks:
        rover_obs = mrk.with_suffix(".OBS")
        rover_nav = mrk.with_suffix(".NAV")
        faltando = [p.name for p in (rover_obs, rover_nav) if not p.exists()]
        if faltando:
            raise RuntimeError(f"O voo {mrk.parent.name} esta sem "
                               f"{', '.join(faltando)}.")
        fotos = sorted(p for p in mrk.parent.iterdir() if p.suffix.upper() == ".JPG")
        if not fotos:
            continue  # pasta de voo sem foto (so log) nao interessa
        voos.append(dict(mrk=mrk, rover_obs=rover_obs, rover_nav=rover_nav,
                         fotos=fotos, nome=mrk.parent.name))
    if not voos:
        raise RuntimeError(f"Nenhuma foto .JPG encontrada junto dos .MRK em {projeto}.")

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
        if base_navs:
            achados = ", ".join(sorted({n.suffix or n.name[-4:] for n in base_navs}))
            detalhe = (
                f"Encontrei os arquivos de NAVEGACAO da base ({achados}), mas nao o de "
                "OBSERVACAO -- normalmente com extensao .26O ou .OBS.\n\n"
                "E no arquivo de observacao que estao as medidas do receptor; sem ele "
                "nao existe PPK. Copie-o do receptor da base para a mesma pasta dos "
                "arquivos de navegacao.")
        else:
            detalhe = f"Nao achei nem observacao nem navegacao da base em {projeto}."
        raise RuntimeError("Nao encontrei o arquivo de observacao da base.\n\n"
                           + detalhe + extra)

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
    """Le o cabecalho: versao, receptor, antena, intervalo e periodo coberto.

    Serve para escolher a base com criterio e para avisar antes de processar,
    em vez de deixar o RTKLIB falhar com uma mensagem generica.
    """
    d = dict(caminho=caminho, versao=0.0, receptor="", marcador="", antena="",
             altura_antena=None, intervalo=None, inicio=None, fim=None)
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
                elif rot == "ANT # / TYPE":
                    d["antena"] = linha[20:40].rstrip()
                elif rot == "INTERVAL":
                    try:
                        d["intervalo"] = float(linha[:10])
                    except ValueError:
                        pass
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


def achar_antex(cfg):
    """Arquivo de calibracao de antena (ANTEX) que acompanha o RTKLIB.

    A distribuicao EX 2.5.1 traz o igs20 completo, com a CNTT300 da base entre as
    antenas calibradas. Nao precisa baixar nada nem guardar .atx junto do projeto.
    """
    atx = sorted(Path(cfg["rtklibBin"]).glob("*.atx"))
    return atx[-1] if atx else None


def antena_no_antex(antex, nome):
    """Diz se aquele modelo de antena tem calibracao dentro do arquivo ANTEX.

    Vale conferir porque o RTKLIB NAO reclama quando nao acha a antena: ele
    simplesmente nao aplica correcao nenhuma, e o viés de 6 a 8 cm em altura
    passa despercebido.
    """
    alvo = f"{nome:<20.20s}"
    try:
        with open(antex, encoding="latin-1") as f:
            for linha in f:
                if linha[60:].startswith("TYPE / SERIAL NO") and linha[:20] == alvo:
                    return True
    except OSError:
        pass
    return False


def escrever_conf(caminho, lat, lon, h, altura_antena, elmask=15,
                  anttype=None, antex=None):
    """Gera a configuracao do RTKLIB.

    Duas escolhas aqui foram medidas contra o PPK do DJI Terra no voo AQUARELA
    (188 fotos, base ComNav a menos de 200 m) e valem para qualquer voo:

    armode=continuous, e nao fix-and-hold. O fix-and-hold trava a ambiguidade e
    SUSTENTA um travamento errado por minutos de voo -- com selo de "fixa". Com
    ele, 22 das 188 fotos ficaram a mais de 50 cm da referencia; com continuous,
    so as 6 que ficaram declaradas float. A fixacao ainda subiu de 88% para 97%.

    gloarmode=off. O GLONASS e FDMA: cada satelite transmite numa frequencia
    diferente, e o atraso de hardware do receptor varia com a frequencia. Em
    GPS/Galileo/BeiDou esse atraso cancela na dupla diferenca; no GLONASS so
    cancela se base e rover forem do mesmo fabricante. Base ComNav com rover DJI
    nunca sao, entao sobra viés interfrequencia suficiente para o LAMBDA
    arredondar para o inteiro errado passando no teste de razao. O GLONASS
    continua entrando na posicao, so sai da resolucao de ambiguidade.
    """
    texto = f"""pos1-posmode       =kinematic
pos1-frequency     =l1+l2
pos1-soltype       =combined
pos1-elmask        ={elmask}
pos1-dynamics      =on
pos1-tidecorr      =off
pos1-ionoopt       =brdc
pos1-tropopt       =saas
pos1-sateph        =brdc
pos1-navsys        =45

pos2-armode        =continuous
pos2-gloarmode     =off
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
"""
    # a altura de antena leva do marco ate o ARP (a base do equipamento); o
    # centro de fase fica mais alguns centimetros acima, e quanto depende da
    # frequencia. Sem declarar a antena, esses 6 a 8 cm entram inteiros na altura
    # de todas as fotos.
    if anttype and antex:
        texto += (f"ant2-anttype       ={anttype}\n"
                  f"file-rcvantfile    ={Path(antex).as_posix()}\n")
    caminho.write_text(texto, encoding="utf-8")


def ler_mrk(caminho):
    """Le o arquivo de eventos do drone: instante do disparo e braco de alavanca.

    N, E e V vem em milimetros no referencial NED -- o terceiro eixo aponta para
    BAIXO. Faz sentido fisico: a antena fica em cima do drone e a camera embaixo,
    no gimbal, entao V positivo quer dizer "camera abaixo da antena" e a altura
    da camera se obtem SUBTRAINDO V.
    """
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


def escrever_fotos_corrigidas(exiftool, corrigidas, destino, progresso=None, lote=200):
    """Grava copias das fotos com a coordenada do PPK no lugar da do voo.

    `corrigidas` e uma lista de (caminho_da_foto, lat, lon, altitude).

    Escreve em TRES lugares porque a DJI guarda a posicao em todos, e software
    que le so o XMP pegaria o valor antigo se mexessemos apenas no EXIF:
    EXIF GPS, XMP-drone-dji GpsLatitude/GpsLongitude e XMP AbsoluteAltitude.

    A altitude vai como elipsoidal com referencia "acima do nivel do mar", que e
    exatamente a convencao que a propria DJI usa no arquivo original -- trocar
    isso criaria incoerencia com o que os programas esperam do Matrice.

    Os originais nunca sao tocados: o ExifTool escreve com -o em outra pasta.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    escritas, falhas = 0, []

    for inicio in range(0, len(corrigidas), lote):
        pedaco = corrigidas[inicio:inicio + lote]
        # O ExifTool se RECUSA a sobrescrever com -o, sem falhar: num
        # reprocessamento a copia antiga ficaria intacta e o programa contaria
        # como gravada. Apagar antes e o que garante que a pasta reflita este
        # processamento, e nao uma mistura de dois.
        for caminho, *_ in pedaco:
            (destino / Path(caminho).name).unlink(missing_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".args", delete=False,
                                         encoding="utf-8") as f:
            for caminho, lat, lon, alt in pedaco:
                f.write(f"-GPSLatitude={lat!r}\n-GPSLongitude={lon!r}\n"
                        f"-GPSAltitude={alt!r}\n"
                        f"-GPSLatitudeRef={'S' if lat < 0 else 'N'}\n"
                        f"-GPSLongitudeRef={'W' if lon < 0 else 'E'}\n"
                        "-GPSAltitudeRef=0\n"
                        f"-XMP-drone-dji:GpsLatitude={lat!r}\n"
                        f"-XMP-drone-dji:GpsLongitude={lon!r}\n"
                        f"-XMP-drone-dji:AbsoluteAltitude={alt!r}\n"
                        f"-o\n{destino}{os.sep}\n{caminho}\n-execute\n")
            # -m tolera o aviso de maker notes que todo arquivo DJI provoca ao
            # ser reescrito; sem ele o ExifTool recusa a gravacao
            f.write("-common_args\n-n\n-m\n-q\n")
            lista = f.name
        try:
            r = subprocess.run([str(exiftool), "-charset", "filename=utf8", "-@", lista],
                               capture_output=True, text=True, timeout=7200)
        finally:
            Path(lista).unlink(missing_ok=True)

        for caminho, *_ in pedaco:
            if (destino / Path(caminho).name).exists():
                escritas += 1
            else:
                falhas.append(Path(caminho).name)
        if progresso:
            progresso(f"    {escritas} de {len(corrigidas)} fotos gravadas...")
        if r.returncode != 0 and not escritas:
            raise RuntimeError("O ExifTool nao conseguiu gravar as fotos:\n"
                               + (r.stderr.strip()[:300] or "sem detalhe"))
    return escritas, falhas


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


def posicionar_base(rnx2rtkp, base_obs, navs, trabalho):
    """Posiciona a base sozinha, por ponto simples, so para conferir o digitado.

    Nao entra no calculo das fotos -- e uma testemunha independente. Um erro na
    coordenada da base entra 1:1 em todas as fotos e NAO aparece em nenhuma
    estatistica do PPK, porque e comum a todas as epocas. Ponto simples acerta a
    altura em 2 ou 3 metros, o que ja basta para pegar os dois enganos que
    realmente acontecem: digitar altitude ortometrica no lugar da elipsoidal
    (5 a 10 m no Brasil) e trocar de marco ou errar digito.
    """
    import statistics as st

    conf = Path(trabalho) / "base_single.conf"
    conf.write_text("""pos1-posmode       =single
pos1-frequency     =l1
pos1-elmask        =15
pos1-navsys        =45
pos1-ionoopt       =brdc
pos1-tropopt       =saas
pos1-sateph        =brdc
out-solformat      =llh
out-outhead        =on
out-timesys        =gpst
out-timeform       =tow
out-degform        =deg
out-height         =ellipsoidal
""", encoding="utf-8")
    pos = Path(trabalho) / "base_single.pos"
    try:
        # -ti 5 decima para uma epoca a cada 5 s: sobram centenas de solucoes,
        # suficiente para a mediana, e o arquivo de horas roda em segundos
        subprocess.run([str(rnx2rtkp), "-k", str(conf), "-ti", "5", "-o", str(pos),
                        str(base_obs), *[str(n) for n in navs]],
                       capture_output=True, check=True, timeout=600)
        epocas = ler_pos(pos)
    except (subprocess.SubprocessError, OSError):
        return None
    if len(epocas) < 20:
        return None
    return dict(n=len(epocas),
                lat=st.median([e["lat"] for e in epocas]),
                lon=st.median([e["lon"] for e in epocas]),
                h=st.median([e["h"] for e in epocas]))


def conferir_base(observada, lat, lon, h_arp):
    """Compara a coordenada digitada com a que a propria base enxerga no ceu."""
    if not observada:
        return []
    dn = (observada["lat"] - lat) * math.pi / 180 * RAIO_TERRA
    de = (observada["lon"] - lon) * math.pi / 180 * RAIO_TERRA * math.cos(math.radians(lat))
    dh = math.hypot(dn, de)
    dv = observada["h"] - h_arp

    avisos = []
    if dh > 50 or abs(dv) > 50:
        raise RuntimeError(
            "A coordenada digitada nao bate com o lugar onde a base estava.\n\n"
            f"Posicionando a base sozinha pelo satelite, ela cai a {dh:.0f} m no plano "
            f"e {dv:+.0f} m em altura da coordenada informada. Ponto simples erra "
            "poucos metros, nunca dezenas.\n\n"
            "Confira se a coordenada e deste marco, se o fuso/EPSG esta certo e se "
            "nenhum digito trocou. Um erro na base entra inteiro em todas as fotos.")
    if abs(dv) > 8:
        avisos.append(
            f"A altura digitada esta {dv:+.1f} m da que a base enxerga sozinha no ceu. "
            "Posicionamento por ponto simples erra alguns metros, entao isso nao e prova "
            "de erro -- mas pede conferencia, porque o engano mais comum e informar "
            "altitude ORTOMETRICA (do nivel do mar) onde o programa espera ELIPSOIDAL. "
            "No Brasil as duas diferem de 5 a 10 m, e o erro entra inteiro em todas as "
            "fotos sem aparecer em nenhuma estatistica.")
    if dh > 10:
        avisos.append(
            f"A coordenada horizontal esta {dh:.0f} m da posicao que a base enxerga "
            "sozinha. Confira o EPSG/fuso e o marco.")
    return avisos


def calcular_fotos(voo, epocas, eventos, atitude):
    """Posicao de cada foto: trajetoria interpolada no disparo + braco de alavanca."""
    fotos, faltando = [], []
    for foto in voo["fotos"]:
        achado = re.search(r"_(\d+)_[A-Z]\.JPG$", foto.name, re.IGNORECASE)
        evento = eventos.get(int(achado.group(1))) if achado else None
        p = interpolar(epocas, evento["tow"]) if evento else None
        if p is None:
            faltando.append(foto.name)
            continue
        yaw, pitch, roll = atitude.get(foto.name, ("", "", ""))
        fotos.append(dict(
            nome=foto.name, caminho=str(foto), voo=voo["nome"], tow=evento["tow"],
            lat=p["lat"] + (evento["n"] / RAIO_TERRA) * 180 / math.pi,
            lon=p["lon"] + (evento["e"] / (RAIO_TERRA * math.cos(math.radians(p["lat"])))) * 180 / math.pi,
            h=p["h"] - evento["v"],   # V do .MRK aponta para baixo (NED)
            q=p["q"], sdn=p["sdn"], sde=p["sde"], sdu=p["sdu"],
            yaw=yaw, pitch=pitch, roll=roll))
    return fotos, faltando


def escrever_geotag(caminho, fotos, sigma="realista", piso=None):
    """Grava o CSV no formato do DJI Terra."""
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        for foto in fotos:
            hacc, vacc = sigma_da_foto(foto, sigma,
                                       (piso or {}).get(foto["nome"]))
            f.write(f"{foto['nome']},{foto['lat']!r},{foto['lon']!r},{foto['h']!r},"
                    f"{num(foto['yaw'])},{num(foto['pitch'])},{num(foto['roll'])},"
                    f"{hacc:.5f},{vacc:.5f}\n")
    return len(fotos)


def comparar_fotos(a, b):
    """Discordancia entre duas solucoes, so nas fotos que ficaram FIXAS nas duas.

    Restringir as fixas e o que torna o teste util. Uma foto em float pode estar
    metros fora nas duas solucoes sem que isso diga nada sobre a ambiguidade: foi
    assim que a versao anterior acusou 84 cm de divergencia no AQUARELA, um voo
    que, medido contra o PPK do DJI Terra, tem TODAS as fotos fixas dentro de
    6 cm no plano e 4 cm em altura. Restrito as fixas, o mesmo teste da 0,6 cm de
    mediana -- que e a verdade.
    """
    ia = {f["nome"]: f for f in a if f["q"] == 1}
    ib = {f["nome"]: f for f in b if f["q"] == 1}
    dh, dv, por_foto = [], [], {}
    for nome in ia.keys() & ib.keys():
        x, y = ia[nome], ib[nome]
        dn = (x["lat"] - y["lat"]) * math.pi / 180 * RAIO_TERRA
        de = (x["lon"] - y["lon"]) * math.pi / 180 * RAIO_TERRA * math.cos(math.radians(x["lat"]))
        h, v = math.hypot(dn, de), abs(x["h"] - y["h"])
        dh.append(h)
        dv.append(v)
        por_foto[nome] = (h, v)
    if not dh:
        return None
    dh.sort()
    dv.sort()
    def pct(serie, q):
        return serie[int(q * (len(serie) - 1))]
    return dict(n=len(dh), por_foto=por_foto,
                dh_mediana=pct(dh, 0.5), dh_p90=pct(dh, 0.9), dh_max=dh[-1],
                dv_mediana=pct(dv, 0.5), dv_p90=pct(dv, 0.9), dv_max=dv[-1])


def conferir_qualidade(fotos, total_fotos, inicio_rover=None, comparacao=None,
                       intervalo_base=None):
    """Confere se a trajetoria presta, sem precisar de referencia externa."""
    avaliadas = len(fotos)
    fixas = sum(1 for f in fotos if f["q"] == 1)
    pct = 100.0 * fixas / avaliadas if avaliadas else 0.0

    msgs, nivel = [], "ok"

    def rebaixar(novo):
        nonlocal nivel
        ordem = {"ok": 0, "atencao": 1, "ruim": 2}
        if ordem[novo] > ordem[nivel]:
            nivel = novo

    msgs.append(f"{fixas} de {avaliadas} fotos ({pct:.0f}%) em solucao fixa.")
    # com a configuracao atual um voo saudavel fixa acima de 90%; o que sobra em
    # float costuma estar metros fora, e por isso o geotag ja declara 1,00/2,00 m
    # nessas fotos -- o ajuste do bloco resolve pela imagem
    if pct < 40:
        rebaixar("ruim")
        msgs.append("Fixacao muito baixa: a maioria das fotos entra na fotogrametria "
                    "com peso quase nulo, e o bloco fica sem amarracao.")
    elif pct < 70:
        rebaixar("atencao")
        msgs.append("Fixacao mediana. As fotos em float estao declaradas com 1,00/2,00 m "
                    "e vao contar pouco no ajuste.")

    if comparacao:
        n = comparacao["n"]
        p90 = comparacao["dv_p90"] * 100
        maxv = comparacao["dv_max"] * 100
        if n < 20:
            rebaixar("atencao")
            msgs.append(
                f"A ambiguidade nao foi confirmada de forma independente: as duas "
                f"mascaras de elevacao so fixaram juntas em {n} foto(s). Isso nao quer "
                "dizer que esteja errado -- quer dizer que nao ha como verificar por "
                "aqui. Para amarracao absoluta, use ponto de apoio em campo.")
        elif p90 > 20:
            rebaixar("ruim")
            msgs.append(
                f"Duas solucoes independentes DISCORDAM nas mesmas fotos: {p90:.0f} cm no "
                f"percentil 90 e ate {maxv:.0f} cm em altura, em {n} fotos que ambas "
                "declararam fixas. Trocar so a mascara de elevacao nao deveria mover "
                "nada; se move, a ambiguidade nao esta firme e as fotos saem em "
                "patamares diferentes. E o defeito mais perigoso porque NAO aparece no "
                "desvio que o programa reporta.")
        elif p90 > 5:
            rebaixar("atencao")
            msgs.append(f"As duas mascaras concordam apenas razoavelmente: {p90:.0f} cm no "
                        f"percentil 90 em altura ({n} fotos fixas nas duas).")
        else:
            msgs.append(f"Ambiguidade confirmada: duas solucoes independentes concordam em "
                        f"{comparacao['dv_mediana'] * 100:.1f} cm de mediana em altura "
                        f"({n} fotos fixas nas duas).")

    if inicio_rover is not None and inicio_rover < CONVERGENCIA_MINIMA_S:
        msgs.append(
            f"So havia {inicio_rover:.0f} s de dado antes da primeira foto, pouco para o "
            "filtro convergir com folga. Isso NAO se resolve esperando no chao: o drone "
            "comeca a gravar o log bruto ja em altitude de voo, e da sempre a mesma "
            "sobra de menos de um minuto. Quem manda nisso e o firmware, nao o operador.")

    if intervalo_base and intervalo_base > 0.5:
        msgs.append(
            f"A base gravou a cada {intervalo_base:g} s e o drone grava 5 vezes por "
            "segundo, entao a maioria das epocas usa observacao da base extrapolada. "
            "Funciona, mas no proximo voo configure a base para 5 Hz.")

    if avaliadas < total_fotos:
        rebaixar("atencao")
        msgs.append(f"{total_fotos - avaliadas} foto(s) ficaram sem coordenada.")

    return dict(pct_fixas=pct, fotos_fixas=fixas, fotos_avaliadas=avaliadas,
                comparacao=comparacao, nivel=nivel, mensagens=msgs)


def processar(projeto, lat, lon, base_z, cfg, elmask=15, altura_antena=None,
              saida=None, progresso=None, trabalho=None, sigma="realista",
              copiar_para=None, piso=None, conferir_coordenada=True, comparacoes=None):
    """Roda o PPK completo e devolve o resultado com as metricas de qualidade.

    `trabalho` permite tirar os arquivos intermediarios de dentro do projeto.
    Dois processamentos simultaneos da mesma pasta se sobrescreveriam sem isso.

    `piso` (nome da foto -> (sigma_h, sigma_v) medidos) eleva a precisao
    declarada onde duas solucoes independentes discordaram.

    `copiar_para` grava, alem do CSV, uma copia de cada foto com a coordenada
    do PPK ja no EXIF. Custa o tamanho do acervo em disco.
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

    b = arq["base"]
    if altura_antena is None:
        altura_antena = b["altura_antena"] if b["altura_antena"] is not None else 0.0
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

    # calibracao da antena da base: sem ela sobra viés de 6 a 8 cm em TODAS as
    # alturas, e o RTKLIB nao avisa que deixou de aplicar
    antex = achar_antex(cfg)
    anttype = b["antena"].strip()
    if not anttype:
        aviso("ATENCAO  O RINEX da base nao diz o modelo da antena, entao nao da para "
              "aplicar a calibracao de centro de fase. Pode sobrar de 6 a 8 cm "
              "sistematicos na altura de todas as fotos.")
        anttype = None
    elif not antex:
        aviso(f"ATENCAO  Nao achei arquivo ANTEX junto do RTKLIB, entao a antena "
              f"{anttype.strip()} entra sem calibracao (6 a 8 cm em altura).")
        anttype = None
    elif not antena_no_antex(antex, b["antena"]):
        aviso(f"ATENCAO  A antena {anttype.strip()} nao esta no {antex.name}: entra sem "
              "calibracao de centro de fase (6 a 8 cm em altura).")
        anttype = None
    else:
        aviso(f"      antena {anttype.strip()} calibrada pelo {antex.name}.")

    aviso(f"{len(voos)} voo(s) na pasta, {total_fotos} fotos no total.")

    for a in conferir_cobertura(b, voos):
        aviso(f"ATENCAO  {a}")

    base_obs = trabalho / "base.obs"
    normalizar_rinex(arq["base_obs"], base_obs)
    conf = trabalho / "rtklib.conf"
    escrever_conf(conf, lat, lon, base_z, altura_antena, elmask,
                  anttype=b["antena"] if anttype else None, antex=antex)

    # testemunha independente da coordenada digitada, antes de gastar o
    # processamento inteiro em cima de uma base errada
    if conferir_coordenada:
        aviso("Conferindo a coordenada da base contra o ceu...")
        # a mesma navegacao do PPK, pelo mesmo motivo: a do receptor da base
        # piora o resultado, e aqui isso viraria alarme falso de altura
        rover_nav_conf = trabalho / "nav_conferencia.nav"
        normalizar_rinex(voos[0]["rover_nav"], rover_nav_conf)
        observada = posicionar_base(rnx2rtkp, base_obs, [rover_nav_conf], trabalho)
        if observada:
            for a in conferir_base(observada, lat, lon, base_z + altura_antena):
                aviso(f"ATENCAO  {a}")
        else:
            aviso("      (nao deu para posicionar a base sozinha; conferencia pulada)")

    saida = Path(saida) if saida else (projeto / "PPK FOTOS.txt")
    todas, faltando, por_voo = [], [], []

    for i, voo in enumerate(voos, 1):
        aviso(f"--- Voo {i} de {len(voos)}: {voo['nome']} ({len(voo['fotos'])} fotos) ---")
        rover_obs = trabalho / f"rover_{i}.obs"
        rover_nav = trabalho / f"rover_{i}.nav"
        normalizar_rinex(voo["rover_obs"], rover_obs)
        normalizar_rinex(voo["rover_nav"], rover_nav)
        # SO a navegacao do proprio drone. Juntar a da base ARRASA a solucao:
        # medido no AQUARELA, 96% das fotos em solucao fixa com o .NAV do drone
        # sozinho e 27% ao acrescentar o .26N (GPS) da base ComNav -- os outros
        # arquivos da base (.26G, .26C, .26L) sao inofensivos, o estrago e so do
        # GPS. O drone grava as efemerides com a data rolada para 2007 (o salto
        # de 1024 semanas do GPS), e o RTKLIB so as reencaixa na semana certa
        # quando elas sao a unica fonte; com as duas fontes ele alterna entre os
        # dois conjuntos ao longo do voo e a ambiguidade reinicia toda hora.
        entradas = [str(rover_obs), str(base_obs), str(rover_nav)]

        aviso(f"    processando no RTKLIB (mascara {elmask} graus)...")
        pos = trabalho / f"trajetoria_{i}_{elmask}.pos"
        subprocess.run([str(rnx2rtkp), "-k", str(conf), "-o", str(pos), *entradas],
                       capture_output=True, check=True)
        epocas = ler_pos(pos)
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

        eventos = ler_mrk(voo["mrk"])
        aviso("    lendo a atitude do gimbal...")
        atitude = ler_atitude(exiftool, voo["fotos"])

        fotos, sem_solucao = calcular_fotos(voo, epocas, eventos, atitude)
        todas.extend(fotos)
        faltando.extend(sem_solucao)

        convergencia = None
        if eventos and epocas:
            convergencia = min(e["tow"] for e in eventos.values()) - epocas[0]["tow"]
        q = conferir_qualidade(fotos, len(voo["fotos"]), inicio_rover=convergencia,
                               comparacao=(comparacoes or {}).get(voo["nome"]),
                               intervalo_base=b["intervalo"])
        aviso(f"    {q['pct_fixas']:.0f}% em solucao fixa  ->  {q['nivel'].upper()}")
        por_voo.append(dict(nome=voo["nome"], qualidade=q))

    escritas = escrever_geotag(saida, todas, sigma=sigma, piso=piso)
    qualidade = juntar_qualidade(por_voo)

    pasta_copias = None
    if copiar_para:
        pasta_copias = Path(copiar_para)
        aviso(f"Gravando copias das fotos com a coordenada corrigida em "
              f"{pasta_copias.name}...")
        n, ruins = escrever_fotos_corrigidas(
            exiftool, [(f["caminho"], f["lat"], f["lon"], f["h"]) for f in todas],
            pasta_copias, progresso=aviso)
        aviso(f"{n} foto(s) gravadas." + (f" {len(ruins)} falharam." if ruins else ""))

    return dict(saida=saida, escritas=escritas, faltando=faltando, por_voo=por_voo,
                fotos=todas, pasta_copias=pasta_copias, base=b,
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


def processar_escolhendo_mascara(projeto, lat, lon, base_z, cfg, saida=None,
                                 altura_antena=None, progresso=None, trabalho=None,
                                 sigma="realista", copiar_para=None):
    """Processa com 15 e com 10 graus, compara as duas e entrega a melhor.

    A comparacao nao e so para escolher: e a unica verificacao independente que
    existe sem ponto de apoio em campo. Mudar a mascara troca o conjunto de
    satelites, entao a ambiguidade e resolvida de novo por outro caminho -- se as
    duas solucoes caem no mesmo lugar nas fotos que ambas declaram fixas, a
    ambiguidade esta firme; se nao caem, esta trocando durante o voo.

    A discordancia medida ainda vira PISO da precisao declarada em cada foto:
    onde as duas solucoes divergem 20 cm, o geotag sai com 20 cm, e a
    fotogrametria pesa aquela foto pelo que ela realmente vale.
    """
    def aviso(t):
        if progresso:
            progresso(t)

    trabalho = Path(trabalho) if trabalho else (projeto / PASTA_TRABALHO)
    trabalho.mkdir(parents=True, exist_ok=True)
    tentativas = []
    for k, elmask in enumerate((15, 10)):
        aviso(f"--- Tentativa com mascara de {elmask} graus ---")
        r = processar(projeto, lat, lon, base_z, cfg, elmask=elmask,
                      altura_antena=altura_antena, trabalho=trabalho, sigma=sigma,
                      conferir_coordenada=(k == 0),
                      saida=trabalho / f"geotag_{elmask}.txt", progresso=progresso)
        aviso(f"Mascara {elmask}: {r['qualidade']['pct_fixas']:.0f}% das fotos em solucao fixa.")
        tentativas.append(r)

    cmp = comparar_fotos(tentativas[0]["fotos"], tentativas[1]["fotos"])
    melhor = max(tentativas, key=lambda r: r["qualidade"]["pct_fixas"])
    if cmp:
        aviso(f"As duas solucoes fixaram juntas em {cmp['n']} fotos e discordam "
              f"{cmp['dv_mediana'] * 100:.1f} cm em altura na mediana "
              f"(ate {cmp['dv_max'] * 100:.0f} cm).")
        if cmp["dv_max"] > 1.0:
            melhor = tentativas[0]
            aviso("Como ha foto com mais de 1 m de divergencia, fico com a mascara de "
                  "15 graus, que e a mais conservadora.")

    # a solucao vencedora ja esta calculada: aqui so se reescreve o geotag no
    # lugar definitivo, agora com o piso de precisao medido, e se copiam as fotos
    aviso(f"Escolhida a mascara de {melhor['elmask']} graus.")
    saida = Path(saida) if saida else (projeto / "PPK FOTOS.txt")
    piso = cmp["por_foto"] if cmp else None
    escritas = escrever_geotag(saida, melhor["fotos"], sigma=sigma, piso=piso)

    # a qualidade e recalculada porque agora existe a comparacao independente
    por_voo = []
    for v in melhor["por_voo"]:
        fotos_voo = [f for f in melhor["fotos"] if f["voo"] == v["nome"]]
        parcial = comparar_fotos(
            [f for f in tentativas[0]["fotos"] if f["voo"] == v["nome"]],
            [f for f in tentativas[1]["fotos"] if f["voo"] == v["nome"]])
        q = conferir_qualidade(fotos_voo, v["qualidade"]["fotos_avaliadas"],
                               comparacao=parcial,
                               intervalo_base=melhor["base"]["intervalo"])
        # a mensagem de convergencia so existe no calculo original
        for m in v["qualidade"]["mensagens"][1:]:
            if m.startswith("So havia"):
                q["mensagens"].append(m)
        por_voo.append(dict(nome=v["nome"], qualidade=q))

    pasta_copias = None
    if copiar_para:
        exiftool = Path(cfg["exiftoolBin"]) / "exiftool.exe"
        pasta_copias = Path(copiar_para)
        aviso(f"Gravando copias das fotos com a coordenada corrigida em "
              f"{pasta_copias.name}...")
        n, ruins = escrever_fotos_corrigidas(
            exiftool, [(f["caminho"], f["lat"], f["lon"], f["h"]) for f in melhor["fotos"]],
            pasta_copias, progresso=aviso)
        aviso(f"{n} foto(s) gravadas." + (f" {len(ruins)} falharam." if ruins else ""))

    final = dict(melhor)
    final.update(saida=saida, escritas=escritas, por_voo=por_voo,
                 pasta_copias=pasta_copias, comparacao=cmp,
                 qualidade=juntar_qualidade(por_voo))
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
    ap.add_argument("--elmask", default="auto",
                    help="mascara de elevacao em graus. 'auto' roda 15 e 10, compara as "
                         "duas solucoes e entrega a melhor -- e a unica conferencia "
                         "independente que existe sem ponto de apoio em campo")
    ap.add_argument("--sigma", choices=("realista", "formal"), default="realista",
                    help="o que escrever nas colunas de precisao. 'realista' usa a "
                         "qualidade da epoca (fixa/float) e e o que o programa de "
                         "fotogrametria precisa como peso; 'formal' escreve o desvio "
                         "do RTKLIB, otimista, so para conferencia")
    ap.add_argument("--saida", type=Path, default=None)
    args = ap.parse_args()

    cfg = carregar_config(Path(__file__).parent)
    transformador = pyproj.Transformer.from_crs(f"EPSG:{args.epsg}", "EPSG:4326", always_xy=True)
    lon, lat = transformador.transform(args.base_e, args.base_n)

    try:
        if args.elmask == "auto":
            r = processar_escolhendo_mascara(
                args.projeto, lat, lon, args.base_z, cfg,
                altura_antena=args.altura_antena, saida=args.saida,
                sigma=args.sigma, progresso=print)
        else:
            r = processar(args.projeto, lat, lon, args.base_z, cfg,
                          elmask=int(args.elmask), altura_antena=args.altura_antena,
                          saida=args.saida, sigma=args.sigma, progresso=print)
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
