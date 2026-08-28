"""Consulta a cota de coordenadas sobre um modelo digital (DSM/DTM).

Le o raster com o GDAL que vem do QGIS. Nao reprojeta nada: as coordenadas
precisam estar no mesmo sistema do raster -- a janela mostra qual e para
conferencia.
"""

import json
import re
import subprocess
from pathlib import Path

# Em UTM no hemisferio sul o Norte passa de 7 milhoes e o Leste fica na casa das
# centenas de milhar. Isso permite descobrir a ordem das colunas sem perguntar.
LIMITE_NORTE = 1_000_000


def carregar_config(base_dir):
    with open(Path(base_dir) / "config.json", encoding="utf-8") as f:
        return json.load(f)


def ferramentas(cfg):
    binario = Path(cfg["gdalBin"])
    info = binario / "gdalinfo.exe"
    consulta = binario / "gdallocationinfo.exe"
    faltando = [str(p) for p in (info, consulta) if not p.exists()]
    if faltando:
        raise FileNotFoundError(
            "Nao encontrei o GDAL. Esperava estes arquivos:\n  "
            + "\n  ".join(faltando)
            + "\n\nConfira o caminho em config.json (vem junto com o QGIS)."
        )
    return info, consulta


def info_modelo(gdalinfo, tif):
    """Sistema de coordenadas, resolucao e extensao do raster."""
    bruto = subprocess.run([str(gdalinfo), "-json", str(tif)],
                           capture_output=True, text=True, timeout=120)
    if bruto.returncode != 0:
        raise RuntimeError(f"O GDAL nao conseguiu abrir o arquivo:\n{bruto.stderr.strip()[:300]}")
    d = json.loads(bruto.stdout)

    wkt = (d.get("coordinateSystem") or {}).get("wkt", "")
    achado = re.search(r'\["([^"]+)"', wkt)
    sistema = achado.group(1) if achado else "nao informado"

    cantos = d.get("cornerCoordinates", {})
    ll = cantos.get("lowerLeft", [0, 0])
    ur = cantos.get("upperRight", [0, 0])
    banda = (d.get("bands") or [{}])[0]
    return dict(
        sistema=sistema,
        pixel=abs(d.get("geoTransform", [0, 0])[1]),
        e_min=min(ll[0], ur[0]), e_max=max(ll[0], ur[0]),
        n_min=min(ll[1], ur[1]), n_max=max(ll[1], ur[1]),
        nodata=banda.get("noDataValue"),
        geografico=abs(ur[0]) <= 180 and abs(ur[1]) <= 90,
    )


def numero(texto):
    """Aceita 1234.56 e 1234,56 (virgula decimal brasileira)."""
    t = texto.strip().replace(" ", "")
    if t.count(",") == 1 and "." not in t:
        t = t.replace(",", ".")
    return float(t)


def separar_campos(linha):
    """Quebra a linha sem confundir separador com virgula decimal."""
    for sep in ("\t", ";"):
        if sep in linha:
            return [c.strip() for c in linha.split(sep)]
    if re.search(r"\S[ ]+\S", linha):
        return linha.split()
    return [c.strip() for c in linha.split(",")]


def interpretar(texto, ordem="auto"):
    """Le o texto colado e devolve (pontos, erros).

    Aceita 'nome E N', 'E N', com virgula, ponto-e-virgula, tabulacao ou espaco.
    Quando `ordem` e 'auto', descobre qual coluna e o Norte pela ordem de
    grandeza -- em UTM sul o Norte passa de 1 milhao e o Leste nao.
    """
    pontos, erros = [], []
    for i, linha in enumerate(texto.splitlines(), 1):
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        campos = [c for c in separar_campos(linha) if c != ""]
        if len(campos) < 2:
            erros.append(f"linha {i}: precisa de pelo menos dois numeros")
            continue

        nome = ""
        numeros = []
        for c in campos:
            try:
                numeros.append(numero(c))
            except ValueError:
                if not nome and not numeros:
                    nome = c
                # texto depois dos numeros e ignorado (descricao, codigo)
        if len(numeros) < 2:
            erros.append(f"linha {i}: nao entendi os numeros em \"{linha.strip()[:40]}\"")
            continue

        a, b = numeros[0], numeros[1]
        if ordem == "en":
            e, n = a, b
        elif ordem == "ne":
            e, n = b, a
        else:
            grande_a, grande_b = a > LIMITE_NORTE, b > LIMITE_NORTE
            if grande_b and not grande_a:
                e, n = a, b
            elif grande_a and not grande_b:
                e, n = b, a
            else:
                erros.append(f"linha {i}: nao da para saber qual valor e o Norte; "
                             "escolha a ordem das colunas em vez de deixar automatico")
                continue
        pontos.append(dict(nome=nome or f"P{len(pontos) + 1}", e=e, n=n))
    return pontos, erros


def consultar(gdallocationinfo, tif, pontos, info=None):
    """Consulta todas as cotas de uma vez pela entrada padrao do GDAL.

    Ponto fora do raster volta como linha vazia, entao a correspondencia com a
    ordem de entrada e preservada.
    """
    if not pontos:
        return []
    entrada = "".join(f"{p['e']!r} {p['n']!r}\n" for p in pontos)
    saida = subprocess.run(
        [str(gdallocationinfo), "-valonly", "-geoloc", str(tif)],
        input=entrada, capture_output=True, text=True, timeout=900)
    # devolve 1 quando algum ponto cai fora; isso nao e falha
    linhas = saida.stdout.splitlines()

    nodata = (info or {}).get("nodata")
    fora_extensao = None
    if info:
        def fora(p):
            return not (info["e_min"] <= p["e"] <= info["e_max"]
                        and info["n_min"] <= p["n"] <= info["n_max"])
        fora_extensao = fora

    resultado = []
    for i, p in enumerate(pontos):
        bruto = linhas[i].strip() if i < len(linhas) else ""
        item = dict(p, cota=None, situacao="")
        if not bruto:
            item["situacao"] = ("fora do modelo" if fora_extensao and fora_extensao(p)
                                else "sem dado")
        else:
            try:
                v = float(bruto)
            except ValueError:
                item["situacao"] = "resposta inesperada do GDAL"
            else:
                if nodata is not None and abs(v - float(nodata)) < 1e-6:
                    item["situacao"] = "vazio no modelo"
                else:
                    item["cota"] = v
                    item["situacao"] = "ok"
        resultado.append(item)
    return resultado
