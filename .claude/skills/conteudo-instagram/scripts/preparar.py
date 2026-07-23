# -*- coding: utf-8 -*-
"""Abre o material bruto e monta o inventário para a triagem visual.

    python preparar.py <zip|pasta|arquivo> [...] --saida <pasta_trabalho>

Descompacta, sonda cada mídia e gera contact sheets numerados por segundo,
que é o que a etapa de curadoria olha para escolher os cortes e barrar o que
fere sigilo. Escreve material.json com o inventário.

Vídeo de WhatsApp costuma vir em 478x850 - o inventário marca isso como
`baixa_resolucao`, porque ampliar não recupera detalhe e vale pedir o original.
"""
import argparse
import json
import os
import shutil
import sys
import zipfile

import cv2
import numpy as np

# console do Windows é cp1252: sem isso o relatório volta com mojibake
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
MIN_LARGURA_OK = 1000  # abaixo disso, ampliar para 1080 já degrada


def _coletar(entradas, trabalho):
    brutos = os.path.join(trabalho, "brutos")
    os.makedirs(brutos, exist_ok=True)
    achados = []
    for e in entradas:
        if os.path.isdir(e):
            for raiz, _, arqs in os.walk(e):
                for a in arqs:
                    achados.append(os.path.join(raiz, a))
        elif zipfile.is_zipfile(e):
            with zipfile.ZipFile(e) as z:
                for nome in z.namelist():
                    if nome.endswith("/"):
                        continue
                    destino = os.path.join(brutos, os.path.basename(nome))
                    with z.open(nome) as src, open(destino, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    achados.append(destino)
        elif os.path.isfile(e):
            achados.append(e)
        else:
            print("ignorado (não existe):", e)
    return achados


def _sheet_video(caminho, destino, passo=None, cols=8, tile=(150, 266)):
    cap = cv2.VideoCapture(caminho)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    dur = n / fps
    if passo is None:
        passo = max(0.5, round(dur / 24, 1))
    tiles, marcas = [], []
    t = 0.0
    while t < dur and len(tiles) < 48:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        if not ok:
            break
        fr = cv2.resize(fr, tile)
        cv2.putText(fr, f"{t:.1f}s", (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 255), 2)
        tiles.append(fr)
        marcas.append(round(t, 1))
        t += passo
    cap.release()
    if not tiles:
        return None, dur, fps, marcas
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    linhas = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(destino, np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return destino, dur, fps, marcas


def _miniatura(caminho, destino, alvo=900):
    im = cv2.imread(caminho)
    if im is None:
        return None, None
    h, w = im.shape[:2]
    s = alvo / max(h, w)
    cv2.imwrite(destino, cv2.resize(im, (int(w * s), int(h * s))),
                [cv2.IMWRITE_JPEG_QUALITY, 85])
    return destino, (w, h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entradas", nargs="+")
    ap.add_argument("--saida", required=True, help="pasta de trabalho")
    args = ap.parse_args()

    trabalho = args.saida
    sheets = os.path.join(trabalho, "sheets")
    os.makedirs(sheets, exist_ok=True)

    inventario = {"fotos": [], "videos": [], "ignorados": []}
    for caminho in _coletar(args.entradas, trabalho):
        ext = os.path.splitext(caminho)[1].lower()
        base = os.path.splitext(os.path.basename(caminho))[0]
        if ext in FOTO_EXT:
            dest = os.path.join(sheets, f"foto_{base}.jpg")
            m, dim = _miniatura(caminho, dest)
            if not m:
                inventario["ignorados"].append(caminho)
                continue
            inventario["fotos"].append({
                "arquivo": caminho, "miniatura": m,
                "largura": dim[0], "altura": dim[1],
                "baixa_resolucao": dim[0] < MIN_LARGURA_OK,
            })
        elif ext in VIDEO_EXT:
            dest = os.path.join(sheets, f"sheet_{base}.jpg")
            sheet, dur, fps, marcas = _sheet_video(caminho, dest)
            cap = cv2.VideoCapture(caminho)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            inventario["videos"].append({
                "arquivo": caminho, "sheet": sheet,
                "duracao_s": round(dur, 2), "fps": round(fps, 2),
                "largura": w, "altura": h,
                "tempos_no_sheet": marcas,
                "baixa_resolucao": w < MIN_LARGURA_OK,
            })
        else:
            inventario["ignorados"].append(caminho)

    caminho_json = os.path.join(trabalho, "material.json")
    with open(caminho_json, "w", encoding="utf-8") as fh:
        json.dump(inventario, fh, ensure_ascii=False, indent=2)

    print(f"fotos: {len(inventario['fotos'])} | vídeos: {len(inventario['videos'])}")
    for v in inventario["videos"]:
        alerta = "  [BAIXA RESOLUÇÃO]" if v["baixa_resolucao"] else ""
        print(f"  {os.path.basename(v['arquivo'])}  {v['duracao_s']}s  "
              f"{v['largura']}x{v['altura']}{alerta}")
        print(f"    sheet: {v['sheet']}")
    for f in inventario["fotos"]:
        alerta = "  [BAIXA RESOLUÇÃO]" if f["baixa_resolucao"] else ""
        print(f"  {os.path.basename(f['arquivo'])}  "
              f"{f['largura']}x{f['altura']}{alerta}")
    print("\ninventário:", caminho_json)
    print("OLHE OS SHEETS antes de escolher corte ou imagem de fundo.")


if __name__ == "__main__":
    main()
