# -*- coding: utf-8 -*-
"""Identidade visual da AJ TopoGeo e primitivas de desenho.

Cores e tipografia batem com o css/style.css do site. Mexer aqui muda a cara
de todas as artes de Instagram - confira contra o site antes.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# --- paleta (css/style.css) ---
BG = (13, 27, 42)        # --azul    #0d1b2a
PANEL = (17, 34, 51)     # --azul2   #112233
AZUL3 = (26, 58, 92)     # --azul3   #1a3a5c
ACCENT = (62, 143, 196)  # --verde   #3E8FC4
WHITE = (240, 244, 248)  # --branco  #f0f4f8
GREY = (136, 153, 170)   # --cinza   #8899aa
ORANGE = (226, 168, 92)  # cota/marcação - só para o dado que o post destaca
AGUA = (96, 178, 232)

# --- tipografia: Segoe UI substitui a Inter do site ---
_F = "C:/Windows/Fonts/"
BLACK_F = _F + "seguibl.ttf"
BOLD_F = _F + "segoeuib.ttf"
SEMI_F = _F + "seguisb.ttf"
REG_F = _F + "segoeui.ttf"

CARD_W, CARD_H = 1080, 1350   # carrossel 4:5
STORY_W, STORY_H = 1080, 1920  # reel / story 9:16
MARGIN = 90

# Faixa que sobrevive ao recorte 1:1 da grade do perfil, num 9:16.
SAFE_TOP, SAFE_BOT = 420, 1500

_cache = {}


def font(path, size):
    k = (path, size)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(path, size)
    return _cache[k]


def tracked(d, xy, text, f, fill, track=6, center=False):
    """Texto com letter-spacing manual; devolve a largura ocupada."""
    total = sum(d.textlength(c, font=f) + track for c in text) - track
    x, y = xy
    if center:
        x -= total / 2
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + track
    return total


def largura(d, text, f, track=0):
    return sum(d.textlength(c, font=f) + track for c in text) - (track if text else 0)


def wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if d.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def fit_block(d, text, path, max_w, max_h, start, line_ratio=1.16, min_size=26):
    """Maior corpo que cabe na caixa. Evita estouro de margem em texto longo."""
    size = start
    while size > min_size:
        f = font(path, size)
        lines = wrap(d, text, f, max_w)
        lh = int(size * line_ratio)
        if len(lines) * lh <= max_h:
            return f, lines, lh
        size -= 2
    f = font(path, min_size)
    return f, wrap(d, text, f, min_size and max_w), int(min_size * line_ratio)


def canvas(w=CARD_W, h=CARD_H):
    img = Image.new("RGBA", (w, h), BG + (255,))
    return img, ImageDraw.Draw(img)


def foto_fundo(img, caminho, dim=0.58, blur=0.8, top_scrim=800, bot_scrim=330,
               scrim_a=205, zoom=1.0, anchor_y=0.5):
    """Frame de campo ao fundo: nítido, escurecido só o quanto o texto exige.

    dim mais alto = mais escuro. O degradê do topo é linear de propósito: com
    curva, a faixa do meio clareia demais e o corpo de texto perde contraste.
    anchor_y < 0.5 puxa o enquadramento para cima, jogando o assunto para baixo.
    """
    W, H = img.size
    # exif_transpose aplica a orientação EXIF (foto de celular/câmera vem com a
    # rotação no metadado); sem isso a imagem sai deitada, ao contrário do que o
    # navegador mostra no site. No-op para imagem sem orientação.
    ph = ImageOps.exif_transpose(Image.open(caminho)).convert("RGB")
    s = max(W / ph.width, H / ph.height) * zoom
    ph = ph.resize((int(ph.width * s) + 1, int(ph.height * s) + 1), Image.LANCZOS)
    lx = (ph.width - W) // 2
    ty = int((ph.height - H) * anchor_y)
    ph = ph.crop((lx, ty, lx + W, ty + H))
    if blur:
        ph = ph.filter(ImageFilter.GaussianBlur(blur))
    ph = ph.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=3))
    ph = Image.blend(ph, Image.new("RGB", (W, H), BG), dim)
    img.paste(ph.convert("RGBA"), (0, 0))

    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        a = 0
        if y < top_scrim:
            a = int(scrim_a * (1 - y / top_scrim))
        if y > H - bot_scrim:
            a = max(a, int(160 * ((y - (H - bot_scrim)) / bot_scrim) ** 1.25))
        if a:
            gd.line([(0, y), (W, y)], fill=BG + (a,))
    img.alpha_composite(grad)


def curvas_textura(img, y_start, densidade=9, alpha=40):
    """Curvas de nível como textura. Só para card sem foto de fundo."""
    W, H = img.size
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(densidade):
        base = y_start + i * 46
        amp = 26 + (i % 3) * 14
        pts = []
        for x in range(-40, W + 40, 6):
            t = x / W * math.pi * 2.4 + i * 0.7
            pts.append((x, base + math.sin(t) * amp + math.sin(t * 2.1 + 1.3) * amp * 0.35))
        d.line(pts, fill=ACCENT + (alpha,), width=2)
    img.alpha_composite(ov)


def rotulo(d, y, texto, w=CARD_W, cor=ACCENT, tamanho=27, com_linha=True):
    tracked(d, (MARGIN, y), texto, font(BOLD_F, tamanho), cor, track=7)
    if com_linha:
        d.line([(MARGIN, y + 58), (w - MARGIN, y + 58)], fill=(30, 55, 80), width=2)


def rodape(d, page, total, w=CARD_W, h=CARD_H, assinatura="AJ TOPOGEO"):
    y = h - 118
    d.line([(MARGIN, y), (MARGIN + 96, y)], fill=ACCENT, width=5)
    tracked(d, (MARGIN, y + 26), assinatura, font(SEMI_F, 24), GREY, track=5)
    if total:
        pg = f"{page:02d}/{total:02d}"
        f = font(SEMI_F, 24)
        d.text((w - MARGIN - d.textlength(pg, font=f), y + 26), pg, font=f,
               fill=(70, 92, 114))


def salvar(img, pasta, nome, q=95):
    os.makedirs(pasta, exist_ok=True)
    p = os.path.join(pasta, nome)
    img.convert("RGB").save(p, quality=q)
    return p
