# -*- coding: utf-8 -*-
"""Renderiza os cards dos carrosséis e as capas de Reel a partir da pauta.json.

    python render.py pauta.json

Não decide nada: tudo (texto, imagem de fundo, diagrama) vem do JSON. Quem
escolhe é a etapa de redação. Aqui só se garante que nada estoura margem,
colide com o rodapé ou repete imagem de fundo.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import sys
from PIL import ImageDraw

import marca as M
import diagramas


def _fundo(img, pasta, bg, capa=False):
    if not bg:
        M.curvas_textura(img, 900 if capa else 1080,
                         densidade=9 if capa else 4, alpha=46 if capa else 18)
        return
    caminho = bg if os.path.isabs(bg) else os.path.join(pasta, bg)
    if not os.path.exists(caminho):
        raise SystemExit(f"imagem de fundo não encontrada: {caminho}")
    if capa:
        M.foto_fundo(img, caminho, dim=0.56, top_scrim=880, bot_scrim=400,
                     scrim_a=215)
    else:
        M.foto_fundo(img, caminho, dim=0.58, top_scrim=810, bot_scrim=300,
                     scrim_a=205)


def card_capa(card, pasta, page, total):
    img, d = M.canvas(M.CARD_W, M.CARD_H)
    _fundo(img, pasta, card.get("bg"), capa=True)
    d = ImageDraw.Draw(img)

    d.line([(M.MARGIN, 150), (M.MARGIN + 130, 150)], fill=M.ACCENT, width=6)
    M.tracked(d, (M.MARGIN, 178), card.get("rotulo", "").upper(),
              M.font(M.BOLD_F, 26), M.GREY, track=7)

    f, linhas, lh = M.fit_block(d, card["titulo"], M.BLACK_F,
                                M.CARD_W - M.MARGIN * 2, 560, 108, 1.06)
    y = 330
    for ln in linhas:
        d.text((M.MARGIN, y), ln, font=f, fill=M.WHITE)
        y += lh

    if card.get("sub"):
        y += 46
        d.line([(M.MARGIN, y), (M.MARGIN + 70, y)], fill=M.ACCENT, width=4)
        y += 34
        fs = M.font(M.REG_F, 40)
        for ln in M.wrap(d, card["sub"], fs, M.CARD_W - M.MARGIN * 2 - 60):
            d.text((M.MARGIN, y), ln, font=fs, fill=(178, 194, 210))
            y += 52

    M.rodape(d, page, total)
    return img


def card_corpo(card, pasta, page, total):
    img, d = M.canvas(M.CARD_W, M.CARD_H)
    _fundo(img, pasta, card.get("bg"))
    d = ImageDraw.Draw(img)
    M.rotulo(d, 150, card.get("rotulo", "").upper(), M.CARD_W)

    f, linhas, lh = M.fit_block(d, card["texto"], M.SEMI_F,
                                M.CARD_W - M.MARGIN * 2, 440, 58, 1.30)
    y = 290
    for ln in linhas:
        d.text((M.MARGIN, y), ln, font=f, fill=M.WHITE)
        y += lh

    diag = dict(card.get("diagrama") or {})
    if diag:
        if card.get("bg"):
            diag.setdefault("massa_alpha", 190) if diag.get("tipo") == "perfil_mata" else None
        diagramas.desenhar(img, diag)
        d = ImageDraw.Draw(img)

    if card.get("selo"):
        M.tracked(d, (M.MARGIN, 1108), card["selo"], M.font(M.BOLD_F, 26),
                  M.ACCENT, track=6)

    M.rodape(d, page, total)
    return img


def capa_reel(peca, pasta):
    """1080x1920. Todo o texto dentro da faixa 420-1500, que é o recorte 1:1
    da grade do perfil - fora dela o texto some na grade ou atrás da UI."""
    capa = peca["capa"]
    img, d = M.canvas(M.STORY_W, M.STORY_H)
    bg = capa.get("bg")
    if bg:
        caminho = bg if os.path.isabs(bg) else os.path.join(pasta, bg)
        M.foto_fundo(img, caminho, dim=0.56, top_scrim=1300, bot_scrim=360,
                     scrim_a=215, zoom=capa.get("zoom", 1.0),
                     anchor_y=capa.get("anchor_y", 0.5))
    else:
        M.curvas_textura(img, 1500, densidade=8, alpha=44)
    d = ImageDraw.Draw(img)

    y = 540
    d.line([(M.MARGIN, y), (M.MARGIN + 130, y)], fill=M.ACCENT, width=6)
    M.tracked(d, (M.MARGIN, y + 28), capa.get("rotulo", "").upper(),
              M.font(M.BOLD_F, 27), M.GREY, track=7)

    f, linhas, lh = M.fit_block(d, capa["titulo"], M.BLACK_F,
                                M.STORY_W - M.MARGIN * 2, 460, 112, 1.06)
    y = 700
    for ln in linhas:
        d.text((M.MARGIN, y), ln, font=f, fill=M.WHITE)
        y += lh

    if capa.get("sub"):
        y += 44
        d.line([(M.MARGIN, y), (M.MARGIN + 70, y)], fill=M.ACCENT, width=4)
        y += 34
        fs = M.font(M.REG_F, 42)
        for ln in M.wrap(d, capa["sub"], fs, M.STORY_W - M.MARGIN * 2):
            d.text((M.MARGIN, y), ln, font=fs, fill=(178, 194, 210))
            y += 54

    ys = 1400
    d.line([(M.MARGIN, ys), (M.MARGIN + 96, ys)], fill=M.ACCENT, width=5)
    M.tracked(d, (M.MARGIN, ys + 26), "AJ TOPOGEO", M.font(M.BOLD_F, 25),
              M.GREY, track=5)
    return img


def main(caminho_pauta):
    with open(caminho_pauta, encoding="utf-8") as fh:
        pauta = json.load(fh)
    pasta = pauta["pasta_saida"]
    os.makedirs(pasta, exist_ok=True)

    usados, gerados = {}, []
    for peca in pauta["pecas"]:
        pid = peca["id"]
        if peca["formato"] == "carrossel":
            total = len(peca["cards"])
            for i, card in enumerate(peca["cards"], 1):
                img = (card_capa if card.get("tipo") == "capa" else card_corpo)(
                    card, pasta, i, total)
                nome = f"{pid}_CARD_{i}_{card.get('slug', 'card')}.jpg"
                gerados.append(M.salvar(img, pasta, nome))
                if card.get("bg"):
                    usados.setdefault(card["bg"], []).append(nome)
        elif peca["formato"] == "reel":
            img = capa_reel(peca, pasta)
            nome = f"{pid}_CAPA_REEL.jpg"
            gerados.append(M.salvar(img, pasta, nome))
            if peca["capa"].get("bg"):
                usados.setdefault(peca["capa"]["bg"], []).append(nome)

    repetidas = {k: v for k, v in usados.items() if len(v) > 1}
    for p in gerados:
        print("gerado:", os.path.basename(p))
    if repetidas:
        print("\nATENÇÃO - imagem de fundo repetida (cada card deve ter a sua):")
        for k, v in repetidas.items():
            print(f"  {k} -> {', '.join(v)}")
        sys.exit(2)
    print(f"\n{len(gerados)} arquivos em {pasta}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python render.py pauta.json")
    main(sys.argv[1])
