# -*- coding: utf-8 -*-
"""Monta um Reel NARRADO de notícia a partir da pauta.json.

    py reel_noticia.py pauta.json

Diferente do montar_reel.py da rotina de campo (que corta vídeo com som
ambiente), este monta um slideshow 1080x1920 sobre FOTOS do acervo, com
locução neural (edge-tts) e sem música. É o formato para notícia, que não
tem filmagem de campo nova.

Cada peça de formato "reel" com a chave "narracao" vira o Reel. O primeiro
slide é a capa; o último costuma ser o CTA. Estrutura de um slide:

  {
    "tipo": "capa" | "slide",
    "imagem": "img/marco-geodesico.jpg",   // fundo (abs, ou relativo à raiz)
    "narracao": "o que a locução fala neste slide",   // escrito para o OUVIDO
    "texto": "O QUE APARECE ESCRITO",                 // escrito para o OLHO
    "estilo": "label" | "linha" | "destaque",         // só slide de corpo
    "rotulo": "NOVIDADE", "titulo": "...", "sub": "..."  // só capa
  }

Regras herdadas da rotina de campo:
- nada de música embutida; a trilha é só a locução;
- legenda fica tempo suficiente na tela (o slide dura pelo menos o tempo da
  locução + folga, sempre acima do mínimo de leitura);
- todo texto dentro da faixa 420–1500 (recorte 1:1 da grade + UI do player).

A narração é escrita à parte da legenda de propósito: "m²", "nº", siglas e
números ficam bons para ler mas ruins para ouvir. Quem escreve a pauta separa
os dois campos.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import asyncio
import json
import os
import re
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw

# marca.py vive nos scripts da rotina de conteúdo; reusar sem duplicar a marca
_AQUI = os.path.dirname(os.path.abspath(__file__))
_MARCA = os.path.normpath(os.path.join(_AQUI, "..", "..", "conteudo-instagram", "scripts"))
sys.path.insert(0, _MARCA)
import marca as M  # noqa: E402

try:
    import edge_tts
except ImportError:
    raise SystemExit("edge-tts não instalado no venv. Veja o README da rotina.")

FF = imageio_ffmpeg.get_ffmpeg_exe()
RW, RH = M.STORY_W, M.STORY_H
VOZ_PADRAO = "pt-BR-AntonioNeural"
MIN_SLIDE = 3.2          # piso de tempo de leitura
LEAD, TAIL = 0.35, 0.75  # folga antes e depois da fala em cada slide


# ---------------------------------------------------------------- narração ---
async def _tts(texto, voz, rate, destino):
    await edge_tts.Communicate(texto, voz, rate=rate).save(destino)


def narrar(texto, voz, rate, destino):
    asyncio.run(_tts(texto, voz, rate, destino))
    return destino


def dur_audio(caminho):
    """Duração em segundos, lida do próprio ffmpeg (não há ffprobe no venv)."""
    r = subprocess.run([FF, "-i", caminho], capture_output=True, text=True,
                       errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        raise SystemExit("não consegui medir a duração de " + caminho)
    h, mn, sec = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(sec)


# ------------------------------------------------------------------ frames ---
# raiz do repo: scripts -> radar-noticias -> skills -> .claude -> repo
_REPO = os.path.normpath(os.path.join(_AQUI, "..", "..", "..", ".."))


def _resolver_img(bg):
    if not bg:
        return None
    if os.path.isabs(bg) and os.path.exists(bg):
        return bg
    if os.path.exists(bg):                       # relativo ao cwd
        return os.path.abspath(bg)
    cam = os.path.join(_REPO, bg)                # relativo à raiz do repo
    if os.path.exists(cam):
        return cam
    raise SystemExit("imagem de fundo não encontrada: " + bg)


def _scrim_legenda(d, y0, y1, a_max=190):
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        a = int(a_max * min(1.0, t * 3.0) * (1 - max(0.0, (t - 0.75) / 0.25)))
        if a > 0:
            d.line([(0, y), (RW, y)], fill=M.BG + (a,))


def frame_capa(slide):
    img, _ = M.canvas(RW, RH)
    bg = _resolver_img(slide.get("imagem"))
    if bg:
        M.foto_fundo(img, bg, dim=0.56, top_scrim=1300, bot_scrim=380,
                     scrim_a=215, zoom=slide.get("zoom", 1.0),
                     anchor_y=slide.get("anchor_y", 0.5))
    else:
        M.curvas_textura(img, 1500, densidade=8, alpha=44)
    d = ImageDraw.Draw(img)

    y = 560
    d.line([(M.MARGIN, y), (M.MARGIN + 130, y)], fill=M.ACCENT, width=6)
    M.tracked(d, (M.MARGIN, y + 28), slide.get("rotulo", "").upper(),
              M.font(M.BOLD_F, 27), M.GREY, track=7)

    f, linhas, lh = M.fit_block(d, slide["titulo"], M.BLACK_F,
                                RW - M.MARGIN * 2, 470, 112, 1.06)
    y = 720
    for ln in linhas:
        d.text((M.MARGIN, y), ln, font=f, fill=M.WHITE)
        y += lh

    if slide.get("sub"):
        y += 40
        d.line([(M.MARGIN, y), (M.MARGIN + 70, y)], fill=M.ACCENT, width=4)
        y += 34
        fs = M.font(M.REG_F, 42)
        for ln in M.wrap(d, slide["sub"], fs, RW - M.MARGIN * 2):
            d.text((M.MARGIN, y), ln, font=fs, fill=(178, 194, 210))
            y += 54

    ys = 1410
    d.line([(M.MARGIN, ys), (M.MARGIN + 96, ys)], fill=M.ACCENT, width=5)
    M.tracked(d, (M.MARGIN, ys + 26), "AJ TOPOGEO", M.font(M.BOLD_F, 25),
              M.GREY, track=5)
    return img


def frame_slide(slide):
    img, _ = M.canvas(RW, RH)
    bg = _resolver_img(slide.get("imagem"))
    if bg:
        M.foto_fundo(img, bg, dim=0.60, top_scrim=520, bot_scrim=520,
                     scrim_a=170, zoom=slide.get("zoom", 1.0),
                     anchor_y=slide.get("anchor_y", 0.5))
    else:
        M.curvas_textura(img, 1200, densidade=6, alpha=30)
    d = ImageDraw.Draw(img)
    _scrim_legenda(d, 980, 1520)

    if slide.get("rotulo"):
        d.line([(M.MARGIN, 470), (M.MARGIN + 110, 470)], fill=M.ACCENT, width=6)
        M.tracked(d, (M.MARGIN, 500), slide["rotulo"].upper(),
                  M.font(M.BOLD_F, 30), M.GREY, track=7)

    estilo = slide.get("estilo", "linha")
    texto = slide.get("texto", "")
    if texto:
        size = 84 if estilo == "destaque" else (46 if estilo == "label" else 62)
        path = M.BLACK_F if estilo == "destaque" else (
            M.BOLD_F if estilo == "label" else M.SEMI_F)
        f, linhas, lh = M.fit_block(d, texto, path, RW - M.MARGIN * 2, 430,
                                    size, 1.22)
        y = 1470 - len(linhas) * lh
        d.line([(M.MARGIN, y - 34), (M.MARGIN + 80, y - 34)], fill=M.ACCENT,
               width=5)
        for ln in linhas:
            d.text((M.MARGIN, y), ln, font=f, fill=M.WHITE)
            y += lh
    return img


def render_frame(slide, caminho):
    img = (frame_capa if slide.get("tipo") == "capa" else frame_slide)(slide)
    img.convert("RGB").save(caminho, quality=95)
    return caminho


# ------------------------------------------------------------------ vídeo ---
_ZW, _ZH = int(RW * 1.10), int(RH * 1.10)   # margem de 10% para o pan
_MX, _MY = _ZW - RW, _ZH - RH


def clipe(frame_png, audio_mp3, dur, saida, i=0, fade_in=False, fade_out=False):
    """Um slide: foto com um pan lento (Ken Burns barato via crop animado) +
    a locução, encaixados na mesma duração para concatenar em cortes secos.

    O zoompan do ffmpeg era inviável aqui (lento e estourava o arquivo com
    -loop); o crop animado sobre um scale único dá o mesmo movimento a custo
    quase nulo. O sentido do pan alterna por slide, para não ficar mecânico.
    """
    d = f"{dur:.3f}"
    # cantos de origem/destino do pan, alternando o sentido horizontal
    if i % 2 == 0:
        xa, xb = 0, _MX
    else:
        xa, xb = _MX, 0
    ya, yb = 0, _MY
    xexpr = f"({xa})+({xb}-({xa}))*(t/{d})"
    yexpr = f"({ya})+({yb}-({ya}))*(t/{d})"
    vf = (f"scale={_ZW}:{_ZH},"
          f"crop={RW}:{RH}:x='{xexpr}':y='{yexpr}',format=yuv420p")
    if fade_in:
        vf += ",fade=t=in:st=0:d=0.5"
    if fade_out:
        vf += f",fade=t=out:st={max(dur-0.6, 0.1):.3f}:d=0.6"

    af = (f"adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad,atrim=0:{d},"
          f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo")
    if fade_in:
        af += ",afade=t=in:st=0:d=0.3"
    if fade_out:
        af += f",afade=t=out:st={max(dur-0.6, 0.1):.3f}:d=0.6"

    cmd = [FF, "-y", "-loop", "1", "-framerate", "30", "-t", d,
           "-i", frame_png, "-i", audio_mp3,
           "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
           saida]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stderr[-3500:])
        raise SystemExit("ffmpeg falhou no slide " + os.path.basename(frame_png))
    return saida


def concat(clipes, saida, trabalho):
    lista = os.path.join(trabalho, "concat.txt")
    with open(lista, "w", encoding="utf-8") as fh:
        for c in clipes:
            fh.write("file '%s'\n" % c.replace("\\", "/"))
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", lista,
           "-c", "copy", "-movflags", "+faststart", saida]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stderr[-3500:])
        raise SystemExit("ffmpeg falhou no concat")
    return saida


def tira(frames, destino):
    """Tira de miniaturas dos slides, para o guia PDF."""
    minis = []
    for fp in frames:
        im = Image.open(fp).convert("RGB").resize((300, 533), Image.LANCZOS)
        minis.append(im)
    if not minis:
        return
    larg = 300 * len(minis) + 12 * (len(minis) - 1)
    faixa = Image.new("RGB", (larg, 533), (13, 27, 42))
    x = 0
    for im in minis:
        faixa.paste(im, (x, 0))
        x += 312
    faixa.save(destino, quality=90)


def montar(peca, pasta, trabalho, voz, rate):
    slides = peca["narracao"]
    frames, audios, durs = [], [], []
    for i, s in enumerate(slides):
        fp = render_frame(s, os.path.join(trabalho, f"{peca['id']}_f{i}.jpg"))
        # o primeiro slide (capa) também vira a capa avulsa para upload no Reel
        if i == 0 and s.get("tipo") == "capa":
            import shutil
            shutil.copyfile(fp, os.path.join(pasta, f"{peca['id']}_CAPA_REEL.jpg"))
        ap = narrar(s["narracao"], s.get("voz", voz), s.get("rate", rate),
                    os.path.join(trabalho, f"{peca['id']}_a{i}.mp3"))
        d = dur_audio(ap)
        frames.append(fp)
        audios.append(ap)
        durs.append(max(d + LEAD + TAIL, MIN_SLIDE))

    clipes = []
    n = len(slides)
    for i in range(n):
        clipes.append(clipe(frames[i], audios[i], durs[i],
                            os.path.join(trabalho, f"{peca['id']}_c{i}.mp4"),
                            i=i, fade_in=(i == 0), fade_out=(i == n - 1)))

    saida = os.path.join(pasta, f"{peca['id']}_REEL.mp4")
    concat(clipes, saida, trabalho)
    tira(frames, os.path.join(pasta, f"{peca['id']}_cenas.jpg"))

    total = sum(durs)
    mb = os.path.getsize(saida) / 1e6
    print(f"gerado: {os.path.basename(saida)}  {total:.1f}s  {mb:.1f} MB  "
          f"{len(slides)} slides")
    if total < 12:
        print("  ATENÇÃO: Reel curto (<12s); considere mais um slide.")
    if total > 75:
        print("  ATENÇÃO: acima de ~75s a retenção cai; corte um slide.")
    return saida


def main(caminho_pauta):
    with open(caminho_pauta, encoding="utf-8") as fh:
        pauta = json.load(fh)
    pasta = pauta["pasta_saida"]
    trabalho = pauta.get("pasta_trabalho", pasta)
    voz = pauta.get("voz", VOZ_PADRAO)
    rate = pauta.get("rate", "+0%")
    os.makedirs(pasta, exist_ok=True)
    os.makedirs(trabalho, exist_ok=True)
    achou = False
    for peca in pauta["pecas"]:
        if peca.get("formato") == "reel" and peca.get("narracao"):
            montar(peca, pasta, trabalho, voz, rate)
            achou = True
    if not achou:
        print("nenhuma peça de formato reel com 'narracao' na pauta")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: py reel_noticia.py pauta.json")
    main(sys.argv[1])
