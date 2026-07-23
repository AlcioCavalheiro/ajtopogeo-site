# -*- coding: utf-8 -*-
"""Gera os recortes SEGURA_ que viram fundo de card e capa.

    python recortar.py recortes.json

recortes.json:
[
  {"nome": "SEGURA_dossel.jpg", "fonte": "C:/.../voo.MP4", "t": 34.2,
   "corte_topo": 0.26, "centro_x": 0.40, "proporcao": "4:5"},
  {"nome": "SEGURA_canteiro.jpg", "fonte": "C:/.../foto.JPG",
   "corte_topo": 0.42, "centro_x": 0.62, "proporcao": "4:5"}
]

`corte_topo` existe para um motivo só: tirar do quadro o horizonte com a
silhueta da cidade, a sede da fazenda, a placa do veículo - qualquer coisa que
identifique o cliente ou o local. Sempre confira o recorte gerado olhando.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import sys

import cv2
from PIL import Image

PROPORCOES = {"4:5": 0.8, "9:16": 0.5625, "1:1": 1.0}
DESTINOS = {"4:5": (1080, 1350), "9:16": (1080, 1920), "1:1": (1080, 1080)}


def _frame(fonte, t):
    cap = cv2.VideoCapture(fonte)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    ok, fr = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"não consegui ler {fonte} em {t}s")
    return Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))


def recortar(im, prop, corte_topo=0.0, centro_x=0.5, corte_base=0.0):
    W, H = im.size
    y0 = int(H * corte_topo)
    y1 = int(H * (1 - corte_base))
    alt = y1 - y0
    razao = PROPORCOES[prop]
    larg = int(alt * razao)
    if larg > W:
        larg = W
        alt = int(larg / razao)
        y0 = min(y0, H - alt)
    cx = int(W * centro_x)
    x0 = max(0, min(W - larg, cx - larg // 2))
    return im.crop((x0, y0, x0 + larg, y0 + alt)).resize(
        DESTINOS[prop], Image.LANCZOS)


def main(caminho):
    with open(caminho, encoding="utf-8") as fh:
        itens = json.load(fh)
    pasta = os.path.dirname(os.path.abspath(caminho))
    nomes = [i["nome"] for i in itens]
    if len(set(nomes)) != len(nomes):
        raise SystemExit("nomes repetidos em recortes.json")

    for it in itens:
        fonte = it["fonte"]
        if not os.path.exists(fonte):
            raise SystemExit("fonte não existe: " + fonte)
        if "t" in it:
            im = _frame(fonte, it["t"])
        else:
            im = Image.open(fonte).convert("RGB")
        prop = it.get("proporcao", "4:5")
        out = recortar(im, prop, it.get("corte_topo", 0.0),
                       it.get("centro_x", 0.5), it.get("corte_base", 0.0))
        destino = it.get("pasta") or pasta
        os.makedirs(destino, exist_ok=True)
        p = os.path.join(destino, it["nome"])
        out.save(p, quality=93)
        aviso = ""
        if im.width < 1000:
            aviso = "  [origem em baixa resolução - ampliado]"
        print(f"gerado: {it['nome']}  ({im.width}x{im.height} -> "
              f"{DESTINOS[prop][0]}x{DESTINOS[prop][1]}){aviso}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python recortar.py recortes.json")
    main(sys.argv[1])
