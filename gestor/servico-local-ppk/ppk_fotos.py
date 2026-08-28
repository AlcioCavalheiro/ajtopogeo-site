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
    mrk = sorted(projeto.rglob("*.MRK"))
    if not mrk:
        sys.exit(f"nenhum arquivo .MRK encontrado em {projeto}")
    mrk = mrk[0]
    pasta_drone = mrk.parent

    rover_obs = mrk.with_suffix(".OBS")
    rover_nav = mrk.with_suffix(".NAV")
    for p in (rover_obs, rover_nav):
        if not p.exists():
            sys.exit(f"arquivo do rover nao encontrado: {p}")

    fotos = sorted(p for p in pasta_drone.iterdir() if p.suffix.upper() == ".JPG")
    if not fotos:
        sys.exit(f"nenhuma foto .JPG em {pasta_drone}")

    # a base e todo OBS/NAV que nao esta na pasta do drone
    base_obs, base_navs = None, []
    for p in projeto.rglob("*"):
        if not p.is_file() or p.parent == pasta_drone:
            continue
        if PASTA_TRABALHO in p.relative_to(projeto).parts:
            continue
        nome = p.name.upper()
        if re.search(r"\.\d\d?O(\.OBS)?$|\.OBS$", nome):
            # prefere o RINEX 3 (multiconstelacao) quando existir os dois
            if base_obs is None or versao_rinex(p) > versao_rinex(base_obs):
                base_obs = p
        elif re.search(r"\.\d\d[NGLCP]$|\.NAV$", nome):
            base_navs.append(p)
    if base_obs is None:
        sys.exit(f"observacao da base nao encontrada em {projeto}")

    return dict(mrk=mrk, rover_obs=rover_obs, rover_nav=rover_nav,
                base_obs=base_obs, base_navs=base_navs, fotos=fotos)


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

    aqui = Path(__file__).parent
    cfg = carregar_config(aqui)
    rnx2rtkp = Path(cfg["rtklibBin"]) / "rnx2rtkp.exe"
    exiftool = Path(cfg["exiftoolBin"]) / "exiftool.exe"
    for p in (rnx2rtkp, exiftool):
        if not p.exists():
            sys.exit(f"ferramenta nao encontrada: {p}\nconfira o config.json")

    arq = achar_arquivos(args.projeto)
    trabalho = args.projeto / PASTA_TRABALHO
    trabalho.mkdir(exist_ok=True)

    altura_antena = args.altura_antena
    if altura_antena is None:
        altura_antena = 0.0
        for linha in open(arq["base_obs"], encoding="latin-1"):
            if "ANTENNA: DELTA H/E/N" in linha:
                altura_antena = float(linha[:14])
                break
            if "END OF HEADER" in linha:
                break

    transformador = pyproj.Transformer.from_crs(f"EPSG:{args.epsg}", "EPSG:4326", always_xy=True)
    lon, lat = transformador.transform(args.base_e, args.base_n)

    print(f"base: {lat:.9f}, {lon:.9f}, h={args.base_z:.3f} (antena +{altura_antena:.3f} m)")
    print(f"rover: {arq['rover_obs'].name}   base: {arq['base_obs'].name}")

    rover_obs = trabalho / "rover.obs"
    rover_nav = trabalho / "rover.nav"
    base_obs = trabalho / "base.obs"
    normalizar_rinex(arq["rover_obs"], rover_obs)
    normalizar_rinex(arq["rover_nav"], rover_nav)
    normalizar_rinex(arq["base_obs"], base_obs)

    conf = trabalho / "rtklib.conf"
    escrever_conf(conf, lat, lon, args.base_z, altura_antena, args.elmask)
    pos = trabalho / "trajetoria.pos"

    entradas = [str(rover_obs), str(base_obs), str(rover_nav)]
    entradas += [str(p) for p in arq["base_navs"]]
    subprocess.run([str(rnx2rtkp), "-k", str(conf), "-o", str(pos), *entradas],
                   capture_output=True, check=True)

    epocas = ler_pos(pos)
    if not epocas:
        sys.exit("o RTKLIB nao produziu solucao; confira os arquivos da base")
    fixas = sum(1 for e in epocas if e["q"] == 1)
    print(f"trajetoria: {len(epocas)} epocas, {fixas} fixas ({100*fixas//len(epocas)}%)")

    eventos = ler_mrk(arq["mrk"])
    atitude = ler_atitude(exiftool, arq["fotos"])

    saida = args.saida or (args.projeto / "PPK FOTOS.txt")
    escritas, faltando = 0, []
    with open(saida, "w", encoding="utf-8", newline="") as f:
        for foto in arq["fotos"]:
            achado = re.search(r"_(\d+)_[A-Z]\.JPG$", foto.name, re.IGNORECASE)
            if not achado:
                faltando.append(foto.name)
                continue
            evento = eventos.get(int(achado.group(1)))
            if evento is None:
                faltando.append(foto.name)
                continue
            p = interpolar(epocas, evento["tow"])
            if p is None:
                faltando.append(foto.name)
                continue

            lat_cam = p["lat"] + (evento["n"] / RAIO_TERRA) * 180 / math.pi
            lon_cam = p["lon"] + (evento["e"] / (RAIO_TERRA * math.cos(math.radians(p["lat"])))) * 180 / math.pi
            h_cam = p["h"] - evento["v"]

            # desvio formal do filtro, como sai do RTKLIB -- e otimista: no voo
            # de referencia prometia 7 mm em altura e a diferenca real contra o
            # DJI Terra foi de 19 cm. Serve para pesar as fotos no ajuste do
            # bloco, nao como estimativa de acuracia.
            hacc = math.hypot(p["sdn"], p["sde"])
            vacc = p["sdu"]
            yaw, pitch, roll = atitude.get(foto.name, ("", "", ""))

            f.write(f"{foto.name},{lat_cam!r},{lon_cam!r},{h_cam!r},"
                    f"{num(yaw)},{num(pitch)},{num(roll)},{hacc:.5f},{vacc:.5f}\n")
            escritas += 1

    print(f"escritas {escritas} fotos em {saida}")
    if faltando:
        print(f"sem solucao para {len(faltando)}: {', '.join(faltando[:5])}")


if __name__ == "__main__":
    main()
