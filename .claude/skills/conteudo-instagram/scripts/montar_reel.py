# -*- coding: utf-8 -*-
"""Monta o Reel a partir das cenas descritas na pauta.json.

    python montar_reel.py pauta.json

Cada peça de formato "reel" precisa de:
  "cenas": [{"fonte": "...", "ini": 26.0, "fim": 30.0, "vel": 1.0,
             "texto": "VISTORIA DE LOCAL", "estilo": "label"}]

estilos: label (rótulo em versal) | linha (frase) | destaque (frase grande) |
assinatura (fecho da marca).

Som ambiente é a regra da rotina - nada de locução, nada de música de acervo.
O áudio bruto de campo estoura por causa do vento, então passa por um
passa-alta de 90 Hz e um limitador antes de sair.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw

import marca as M

FF = imageio_ffmpeg.get_ffmpeg_exe()
RW, RH = M.STORY_W, M.STORY_H


def _atempo(vel):
    """Cadeia de atempo para a velocidade pedida. O filtro atempo só aceita
    tempo em [0.5, 100]; câmera lenta (vel < 0.5) precisa de fatores encadeados
    (ex.: 0.4 = 0.5 x 0.8). Sem isso o ffmpeg aborta com 'Result too large'."""
    fatores, v = [], float(vel)
    while v < 0.5:
        fatores.append(0.5)
        v /= 0.5
    while v > 100.0:
        fatores.append(100.0)
        v /= 100.0
    fatores.append(v)
    return ",".join(f"atempo={f:.6g}" for f in fatores)


def _faixa(d, y0, y1, a_max=185):
    """Degradê atrás da legenda: sem isso o texto some no céu claro."""
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        a = int(a_max * min(1.0, t * 3.2) * (1 - max(0.0, (t - 0.72) / 0.28)))
        d.line([(0, y), (RW, y)], fill=M.BG + (max(a, 0),))


def overlay(texto, estilo, caminho):
    img = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not texto:
        img.save(caminho)
        return caminho
    _faixa(d, 1120, 1560)
    if estilo in ("label", "assinatura"):
        y = 1270 if estilo == "label" else 1268
        d.line([(M.MARGIN, y), (M.MARGIN + 130, y)], fill=M.ACCENT, width=6)
        f = M.font(M.BOLD_F, 46) if estilo == "label" else M.font(M.BLACK_F, 60)
        M.tracked(d, (M.MARGIN, y + 30), texto, f, M.WHITE,
                  track=9 if estilo == "label" else 10)
    else:
        size = 82 if estilo == "destaque" else 60
        f = M.font(M.BLACK_F if estilo == "destaque" else M.SEMI_F, size)
        linhas = M.wrap(d, texto, f, RW - M.MARGIN * 2)
        lh = int(size * 1.20)
        y = 1400 - len(linhas) * lh
        d.line([(M.MARGIN, y - 34), (M.MARGIN + 70, y - 34)], fill=M.ACCENT, width=5)
        for ln in linhas:
            d.text((M.MARGIN, y), ln, font=f, fill=M.WHITE)
            y += lh
    img.save(caminho)
    return caminho


def _tira_cenas(video, destino, duracoes):
    """Uma miniatura por cena, no meio dela. Vira a tira do Reel no PDF."""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    tiles, acc = [], 0.0
    for dur in duracoes:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((acc + dur / 2) * fps))
        ok, fr = cap.read()
        if ok:
            tiles.append(cv2.resize(fr, (300, 533)))
        acc += dur
    cap.release()
    if tiles:
        cv2.imwrite(destino, np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 90])


def montar(peca, pasta, trabalho):
    cenas = peca["cenas"]
    fontes, idx = [], {}
    for c in cenas:
        if c["fonte"] not in idx:
            idx[c["fonte"]] = len(fontes)
            fontes.append(c["fonte"])
    for f in fontes:
        if not os.path.exists(f):
            raise SystemExit("fonte de vídeo não existe: " + f)

    pngs, duracoes = [], []
    for i, c in enumerate(cenas):
        vel = c.get("vel", 1.0)
        duracoes.append((c["fim"] - c["ini"]) / vel)
        pngs.append(overlay(c.get("texto", ""), c.get("estilo", "linha"),
                            os.path.join(trabalho, f"{peca['id']}_ov{i}.png")))
    total = sum(duracoes)

    cmd = [FF, "-y"]
    for f in fontes:
        cmd += ["-i", f]
    for p, dur in zip(pngs, duracoes):
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", p]

    fc, rotulos = [], []
    base = len(fontes)
    for i, c in enumerate(cenas):
        src = idx[c["fonte"]]
        vel = c.get("vel", 1.0)
        dur = duracoes[i]
        pts = f"setpts=(PTS-STARTPTS)/{vel}" if vel != 1.0 else "setpts=PTS-STARTPTS"
        fc.append(
            f"[{src}:v]trim={c['ini']}:{c['fim']},{pts},"
            f"scale={RW}:{RH}:force_original_aspect_ratio=increase,"
            f"crop={RW}:{RH},fps=30,setsar=1[b{i}];")
        atempo = f",{_atempo(vel)}" if vel != 1.0 else ""
        fc.append(
            f"[{src}:a]atrim={c['ini']}:{c['fim']},asetpts=PTS-STARTPTS{atempo},"
            f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];")
        fc.append(
            f"[{base+i}:v]format=rgba,fade=t=in:st=0.25:d=0.4:alpha=1,"
            f"fade=t=out:st={max(dur-0.65, 0.3):.3f}:d=0.4:alpha=1[o{i}];")
        fc.append(f"[b{i}][o{i}]overlay=0:0:shortest=1[v{i}];")
        rotulos.append(f"[v{i}][a{i}]")

    fc.append("".join(rotulos) + f"concat=n={len(cenas)}:v=1:a=1[vc][ac];")
    fc.append("[vc]format=yuv420p[vout];")
    fc.append(f"[ac]highpass=f=90,alimiter=limit=0.72:level=false,"
              f"afade=t=in:st=0:d=0.5,afade=t=out:st={max(total-1.6, 0.1):.2f}:d=1.6[aout]")

    saida = os.path.join(pasta, f"{peca['id']}_REEL.mp4")
    cmd += ["-filter_complex", "".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida]

    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("ffmpeg falhou")
    _tira_cenas(saida, os.path.join(pasta, f"{peca['id']}_cenas.jpg"),
                duracoes)
    mb = os.path.getsize(saida) / 1e6
    print(f"gerado: {os.path.basename(saida)}  {total:.1f}s  {mb:.1f} MB")
    if total < 7:
        print("  ATENÇÃO: abaixo de 7s o Reel tem pouca entrega.")
    if total > 90:
        print("  ATENÇÃO: acima de 90s cai muito a retenção.")
    return saida


def main(caminho_pauta):
    with open(caminho_pauta, encoding="utf-8") as fh:
        pauta = json.load(fh)
    pasta = pauta["pasta_saida"]
    trabalho = pauta.get("pasta_trabalho", pasta)
    os.makedirs(pasta, exist_ok=True)
    os.makedirs(trabalho, exist_ok=True)
    achou = False
    for peca in pauta["pecas"]:
        if peca["formato"] == "reel" and peca.get("cenas"):
            montar(peca, pasta, trabalho)
            achou = True
    if not achou:
        print("nenhuma peça de formato reel com cenas na pauta")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python montar_reel.py pauta.json")
    main(sys.argv[1])
