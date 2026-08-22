# -*- coding: utf-8 -*-
"""Monta o Reel com locução narrada, dirigido pelo áudio.

    python montar_reel_narrado.py pauta.json

Diferença para o `montar_reel.py`: lá a cena manda e o áudio segue; aqui a
locução manda e a cena é cortada para caber nela. Cada cena traz uma `fala`;
o trecho é sintetizado com edge-tts, medido, e a janela de vídeo é esticada ou
encurtada para bater exatamente com a duração do trecho mais as respirações.

Cena de peça de formato "reel", no modo narrado:

  {"fonte": "...", "ini": 4.0, "vel": 1.0, "texto": "LOCAÇÃO DE RUAS",
   "estilo": "label", "fala": "A rua ainda não existe."}

`fim` deixa de valer como corte - fica só como anotação de curadoria. Quem
define o corte é a fala. Configuração opcional na peça:

  "narracao": {"voz": "pt-BR-AntonioNeural", "rate": "+7%",
               "lead": 0.35, "tail": 0.55, "ambiente": 0.22}

O som ambiente de campo continua na peça, abaixado, por baixo da voz - o que
não entra é música. Fonte sem trilha (o MP4 do drone não grava áudio) entra
com silêncio e a voz sustenta a cena sozinha.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import asyncio
import json
import os
import subprocess
import sys
import wave

import imageio_ffmpeg

import marca as M
from montar_reel import _atempo, _tem_audio, _tira_cenas, overlay

FF = imageio_ffmpeg.get_ffmpeg_exe()
RW, RH = M.STORY_W, M.STORY_H

VOZ = "pt-BR-AntonioNeural"
RATE = "+7%"
LEAD = 0.35      # respiração antes da fala entrar
TAIL = 0.55      # respiração depois que a fala acaba
AMBIENTE = 0.22  # ganho do som de campo por baixo da voz


def _sintetizar(texto, destino_wav, voz=VOZ, rate=RATE):
    """edge-tts entrega mp3; converte para WAV 48k mono para medir e mixar."""
    import edge_tts
    mp3 = destino_wav[:-4] + ".mp3"

    async def _go():
        await edge_tts.Communicate(texto, voz, rate=rate).save(mp3)

    asyncio.run(_go())
    r = subprocess.run(
        [FF, "-y", "-hide_banner", "-loglevel", "error", "-i", mp3,
         "-ar", "48000", "-ac", "1", destino_wav],
        capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("falhou converter a locução para WAV: " + texto[:50])
    _aparar_silencio(destino_wav)
    return destino_wav


def _aparar_silencio(caminho, limiar=0.02, guarda=0.06):
    """Tira o silêncio que a edge-tts põe nas pontas de cada trecho.

    A voz neural entrega ~0,16 s de silêncio antes e ~0,82 s depois da fala.
    Como aqui a duração da cena é a duração do trecho, esse silêncio viraria
    um segundo de cena parada por fala - quase seis segundos num Reel de seis
    cenas. Apara-se aqui e a respiração volta controlada por `lead`/`tail`.
    """
    import numpy as np
    with wave.open(caminho, "rb") as w:
        par, n, sr = w.getparams(), w.getnframes(), w.getframerate()
        dados = np.frombuffer(w.readframes(n), dtype=np.int16)
    forte = np.where(np.abs(dados.astype(np.float32) / 32768) > limiar)[0]
    if forte.size == 0:
        return
    g = int(guarda * sr)
    ini = max(0, int(forte[0]) - g)
    fim = min(len(dados), int(forte[-1]) + g)
    with wave.open(caminho, "wb") as w:
        w.setparams(par)
        w.setnframes(0)
        w.writeframes(dados[ini:fim].tobytes())


def _dur_wav(caminho):
    with wave.open(caminho, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def montar(peca, pasta, trabalho):
    cfg = peca.get("narracao") or {}
    voz = cfg.get("voz", VOZ)
    rate = cfg.get("rate", RATE)
    lead = float(cfg.get("lead", LEAD))
    tail = float(cfg.get("tail", TAIL))
    amb_gain = float(cfg.get("ambiente", AMBIENTE))

    cenas = peca["cenas"]
    if not any(c.get("fala") for c in cenas):
        raise SystemExit(f"{peca['id']}: nenhuma cena tem 'fala' - use "
                         f"montar_reel.py para o modo som ambiente")

    fontes, idx = [], {}
    for c in cenas:
        if c["fonte"] not in idx:
            idx[c["fonte"]] = len(fontes)
            fontes.append(c["fonte"])
    for f in fontes:
        if not os.path.exists(f):
            raise SystemExit("fonte de vídeo não existe: " + f)
    com_audio = {f: _tem_audio(f) for f in fontes}

    # 1. locução primeiro: é ela que define a duração de cada cena
    falas, duracoes = [], []
    print("locução:")
    for i, c in enumerate(cenas):
        fala = (c.get("fala") or "").strip()
        if fala:
            wav = _sintetizar(fala, os.path.join(
                trabalho, f"{peca['id']}_voz{i}.wav"), voz, rate)
            d = _dur_wav(wav)
            falas.append(wav)
            duracoes.append(round(lead + d + tail, 3))
            print(f"  cena {i+1}: {d:5.2f}s de voz -> cena de "
                  f"{duracoes[-1]:5.2f}s   \"{fala[:58]}\"")
        else:
            falas.append(None)
            dur = c.get("fim", c["ini"] + 3.0) - c["ini"]
            duracoes.append(round(dur / c.get("vel", 1.0), 3))
            print(f"  cena {i+1}: sem fala -> cena de {duracoes[-1]:5.2f}s")
    total = round(sum(duracoes), 3)

    pngs = [overlay(c.get("texto", ""), c.get("estilo", "linha"),
                    os.path.join(trabalho, f"{peca['id']}_nov{i}.png"))
            for i, c in enumerate(cenas)]

    # 2. filtergraph
    cmd = [FF, "-y", "-hide_banner"]
    for f in fontes:
        cmd += ["-i", f]
    base_png = len(fontes)
    for p, dur in zip(pngs, duracoes):
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", p]
    base_voz = base_png + len(pngs)
    ordem_voz = {}
    for i, w in enumerate(falas):
        if w:
            ordem_voz[i] = base_voz + len(ordem_voz)
            cmd += ["-i", w]

    fc, lv, la, ln = [], [], [], []
    for i, c in enumerate(cenas):
        src = idx[c["fonte"]]
        vel = c.get("vel", 1.0)
        dur = duracoes[i]
        ini = c["ini"]
        fim = ini + dur * vel          # janela de origem que a fala exige
        pts = f"setpts=(PTS-STARTPTS)/{vel}" if vel != 1.0 else "setpts=PTS-STARTPTS"
        # tpad=stop_mode=clone antes do overlay: sem ele, um trim que passa do
        # fim do arquivo - ou um trecho de vídeo VFR, comum em drone e celular -
        # entrega menos quadros que o pedido, e o overlay=shortest=1 encurta a
        # cena inteira. Clonando o último quadro a base bate a duração exata e
        # o overlay pode entrar sem shortest.
        # "espelhar": vídeo de câmera frontal sai invertido, e a logo da
        # camisa da equipe aparece de trás para frente. hflip devolve a marca
        # legível. Só use em cena sem placa, painel ou número no quadro - o
        # espelho inverteria essa informação também.
        flip = "hflip," if c.get("espelhar") else ""
        # zoom/anchor_x/anchor_y: reenquadramento da cena, mesma semântica dos
        # cards (0 mantém o topo/esquerda, 1 o rodapé/direita, 0,5 centraliza).
        # Sem isso, um plate 16:9 de drone vira sempre o terço central da
        # largura em altura cheia - e quando o piloto enquadrou o chão, o
        # assunto cai no quinto de baixo, justo onde a interface do player do
        # Instagram cobre. zoom com anchor_y=1 corta o céu/terra morta do topo
        # e sobe o assunto para fora dessa faixa.
        z = float(c.get("zoom", 1.0))
        ax, ay = float(c.get("anchor_x", 0.5)), float(c.get("anchor_y", 0.5))
        sw, sh = int(RW * z) // 2 * 2, int(RH * z) // 2 * 2
        fc.append(
            f"[{src}:v]trim={ini}:{fim},{pts},{flip}"
            f"scale={sw}:{sh}:force_original_aspect_ratio=increase,"
            f"crop={RW}:{RH}:x=(iw-ow)*{ax:.4f}:y=(ih-oh)*{ay:.4f},"
            f"fps=30,setsar=1,"
            f"tpad=stop_mode=clone:stop_duration=6,"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[b{i}];")
        fc.append(
            f"[{base_png+i}:v]format=rgba,fade=t=in:st=0.25:d=0.4:alpha=1,"
            f"fade=t=out:st={max(dur-0.75, 0.3):.3f}:d=0.45:alpha=1[o{i}];")
        fc.append(f"[b{i}][o{i}]overlay=0:0[v{i}];")
        lv.append(f"[v{i}]")

        # som ambiente da própria cena, abaixado, com fade nas pontas para não
        # estalar quando a cena seguinte vem de fonte muda (drone)
        if com_audio[c["fonte"]]:
            atempo = f",{_atempo(vel)}" if vel != 1.0 else ""
            fc.append(
                f"[{src}:a]atrim={ini}:{fim},asetpts=PTS-STARTPTS{atempo},"
                f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d=0.35,"
                f"afade=t=out:st={max(dur-0.4, 0.05):.3f}:d=0.4[m{i}];")
        else:
            fc.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000,"
                f"atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo[m{i}];")
        la.append(f"[m{i}]")

        if falas[i]:
            ms = int(lead * 1000)
            fc.append(
                f"[{ordem_voz[i]}:a]aresample=48000,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"adelay={ms}|{ms},apad,atrim=0:{dur:.3f},"
                f"asetpts=PTS-STARTPTS[n{i}];")
        else:
            fc.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000,"
                f"atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo[n{i}];")
        ln.append(f"[n{i}]")

    n = len(cenas)
    fc.append("".join(lv) + f"concat=n={n}:v=1:a=0[vc];")
    fc.append("".join(la) + f"concat=n={n}:v=0:a=1[ambc];")
    fc.append("".join(ln) + f"concat=n={n}:v=0:a=1[narc];")
    fc.append("[vc]format=yuv420p[vout];")
    # passa-alta de 90 Hz tira o ronco de vento antes de o ambiente ir para
    # debaixo da voz; o limitador segura o pico do vento no microfone
    fc.append(f"[ambc]highpass=f=90,volume={amb_gain:.3f},"
              f"alimiter=limit=0.9:level=false[ambx];")
    fc.append("[narc][ambx]amix=inputs=2:duration=first:normalize=0[mix];")
    fc.append(f"[mix]loudnorm=I=-14:TP=-1.5:LRA=11,"
              f"afade=t=in:st=0:d=0.35,"
              f"afade=t=out:st={max(total-0.9, 0.1):.2f}:d=0.9[aout]")

    saida = os.path.join(pasta, f"{peca['id']}_REEL.mp4")
    cmd += ["-filter_complex", "".join(fc), "-map", "[vout]", "-map", "[aout]",
            # teto de bitrate: sem ele um plate de drone 4K rebaixado para
            # 1080x1920 sai perto de 24 Mbps (90 MB em meio minuto) e o upload
            # trava no celular. 14 Mbps não muda nada no que se vê e corta o
            # arquivo pela metade - o Instagram recomprime para bem menos.
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-maxrate", "14M", "-bufsize", "28M",
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", saida]

    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("ffmpeg falhou")
    _tira_cenas(saida, os.path.join(pasta, f"{peca['id']}_cenas.jpg"), duracoes)
    mb = os.path.getsize(saida) / 1e6
    print(f"gerado: {os.path.basename(saida)}  {total:.1f}s  {mb:.1f} MB "
          f"(narrado, voz {voz} {rate})")
    mudo = sum(d for c, d in zip(cenas, duracoes) if not com_audio[c["fonte"]])
    if mudo:
        print(f"  {mudo:.1f}s de {total:.1f}s vêm de fonte sem trilha (drone) - "
              f"nesse trecho só existe a locução, e a pausa entre frases fica "
              f"em silêncio absoluto.")
    if total < 12:
        print("  ATENÇÃO: reel narrado abaixo de 12s não fecha o raciocínio.")
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
        raise SystemExit("uso: python montar_reel_narrado.py pauta.json")
    main(sys.argv[1])
