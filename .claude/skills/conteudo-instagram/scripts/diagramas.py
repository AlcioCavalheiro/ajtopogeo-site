# -*- coding: utf-8 -*-
"""Diagramas esquemáticos dos cards.

Cada diagrama é desenhado numa camada RGBA e composto sobre a foto de fundo,
com o maciço semitransparente para a imagem real aparecer por dentro do
desenho. É isso que faz o card explicar em vez de só afirmar.

Para criar um diagrama novo: escreva a função, registre em DIAGRAMAS e
documente no README. A chave é o que o JSON da pauta chama em `diagrama.tipo`.
"""
import math
from PIL import Image, ImageDraw

from marca import (ACCENT, WHITE, ORANGE, AGUA, MARGIN, BOLD_F, font, tracked,
                   largura)


# ------------------------------------------------------------------ helpers

def _tracejada(d, pts, cor, largura_px, dash=16, gap=12):
    acc, on, seg = 0.0, True, [pts[0]]
    for a, b in zip(pts, pts[1:]):
        acc += math.dist(a, b)
        seg.append(b)
        if (on and acc >= dash) or (not on and acc >= gap):
            if on and len(seg) > 1:
                d.line(seg, fill=cor, width=largura_px)
            on, acc, seg = not on, 0.0, [b]
    if on and len(seg) > 1:
        d.line(seg, fill=cor, width=largura_px)


def _suave(t, a, b):
    if t <= a:
        return 0.0
    if t >= b:
        return 1.0
    u = (t - a) / (b - a)
    return u * u * (3 - 2 * u)


def _rot(d, x, y, texto, cor, tam=23, x0=None, x1=None):
    """Rótulo que nunca estoura a margem."""
    f = font(BOLD_F, tam)
    w = largura(d, texto, f, 4)
    if x0 is not None and x1 is not None:
        x = max(x0, min(x, x1 - w))
    tracked(d, (x, y), texto, f, cor, track=4)


# ------------------------------------------------- perfil_mata (MDS x MDT)

def _solo_mata(x, x0, x1, ybase):
    t = (x - x0) / (x1 - x0)
    return ybase - 150 * (1 - t) ** 1.5 + 16 * math.sin(t * 5.2)


def _copa_mata(x, x0, x1):
    t = (x - x0) / (x1 - x0) * math.pi * 2
    return (132 + 26 * math.sin(t * 3.1) + 16 * math.sin(t * 7.7 + 0.8)
            + 9 * math.sin(t * 13.3))


def perfil_mata(img, top=780, mds=False, mdt=False, cota=None, pontos=False,
                massa_alpha=190):
    """Mata em corte. Serve para explicar MDS x MDT, altura de dossel,
    ponto levantado no chão. `cota` é o texto da medida (ex.: "+15 m")."""
    W, H = img.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1 = MARGIN, W - MARGIN
    ybase = top + 300
    xs = list(range(x0, x1 + 1, 4))
    solo = [(x, _solo_mata(x, x0, x1, ybase)) for x in xs]
    topo = [(x, _solo_mata(x, x0, x1, ybase) - _copa_mata(x, x0, x1)) for x in xs]

    d.polygon(topo + solo[::-1], fill=(23, 48, 72, massa_alpha))
    for xt in range(x0 + 14, x1, 27):  # troncos: leitura de mata, não de gráfico
        ys = _solo_mata(xt, x0, x1, ybase)
        d.line([(xt, ys), (xt, ys - _copa_mata(xt, x0, x1) + 34)],
               fill=(31, 62, 92, 220), width=3)
    d.line(solo, fill=(70, 92, 114, 255), width=3)

    if mds:
        _tracejada(d, topo, ACCENT + (255,), 4)
        _rot(d, x0 + 6, topo[0][1] - 44, "MDS", ACCENT, 25, x0, x1)
    if mdt:
        d.line(solo, fill=WHITE + (255,), width=4)
        _rot(d, x0 + 6, solo[0][1] + 30, "MDT", WHITE, 25, x0, x1)
    if pontos:
        for xp in range(x0 + 34, x1, 66):
            yp = _solo_mata(xp, x0, x1, ybase)
            d.line([(xp, yp - 6), (xp, yp - 22)], fill=ORANGE + (255,), width=2)
            d.ellipse([xp - 6, yp - 6, xp + 6, yp + 6], fill=ORANGE + (255,))
    if cota:
        xc = x0 + int((x1 - x0) * 0.62)
        i = min(range(len(xs)), key=lambda k: abs(xs[k] - xc))
        yt, yb = topo[i][1], solo[i][1]
        d.line([(xc, yt), (xc, yb)], fill=ORANGE + (255,), width=3)
        for yy, dy in ((yt, 1), (yb, -1)):
            d.polygon([(xc, yy), (xc - 9, yy + 17 * dy), (xc + 9, yy + 17 * dy)],
                      fill=ORANGE + (255,))
        _rot(d, xc + 22, (yt + yb) // 2 - 16, cota, ORANGE, 30, x0, x1)

    img.alpha_composite(layer)


# ------------------------------------------- perfil_vertente (água / relevo)

def _terreno_v(x, x0, x1, ytop, drop=250):
    t = (x - x0) / (x1 - x0)
    return (ytop + drop * _suave(t, 0.26, 0.82)
            + 5 * math.sin(t * 21) + 3 * math.sin(t * 47 + 1.2))


def _dossel_v(x, x0, x1):
    t = (x - x0) / (x1 - x0)
    env = _suave(t, 0.28, 0.40) * (1 - _suave(t, 0.90, 0.99))
    return max(0.0, (118 + 22 * math.sin(t * 24 * math.pi)
                     + 13 * math.sin(t * 51 + 0.8)) * env)


def perfil_vertente(img, top=830, topo_rotulo="LOTEAMENTO", agua=False,
                    marcas=None, curvas=False, lancamento=False):
    """Vertente: ocupação no platô, mata na encosta, fundo de vale.

    Serve para drenagem, terraplenagem, talvegue, APP de fundo de vale.
    `marcas` é lista de (posicao_0a1, texto, alvo) com alvo em
    solo | meio | copa - o pino tem que aterrissar na cota certa.
    """
    W, H = img.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1 = MARGIN, W - MARGIN
    xs = list(range(x0, x1 + 1, 3))
    solo = [(x, _terreno_v(x, x0, x1, top)) for x in xs]
    ybot = max(p[1] for p in solo) + 48

    d.polygon(solo + [(x1, ybot), (x0, ybot)], fill=(16, 34, 52, 150))
    copa = [(x, _terreno_v(x, x0, x1, top) - _dossel_v(x, x0, x1)) for x in xs]
    d.polygon(copa + solo[::-1], fill=(23, 48, 72, 190))
    for xt in range(x0 + 12, x1, 26):
        ys = _terreno_v(xt, x0, x1, top)
        h = _dossel_v(xt, x0, x1)
        if h > 30:
            d.line([(xt, ys), (xt, ys - h + 30)], fill=(31, 62, 92, 210), width=3)

    # ocupação no platô
    xq0, xq1 = x0 + 6, x0 + int((x1 - x0) * 0.25)
    yq = _terreno_v(xq0, x0, x1, top)
    d.line([(xq0, yq - 2), (xq1, _terreno_v(xq1, x0, x1, top) - 2)],
           fill=(120, 145, 170, 235), width=4)
    for i, xb in enumerate(range(xq0 + 8, xq1 - 10, 34)):
        yb = _terreno_v(xb, x0, x1, top)
        hh = 26 if i % 2 == 0 else 19
        d.rectangle([xb, yb - 6 - hh, xb + 24, yb - 6], fill=(142, 168, 194, 240))
    if topo_rotulo:
        _rot(d, xq0, yq - 78, topo_rotulo, (178, 198, 216), 24, x0, x1)

    d.line(solo, fill=(150, 172, 194, 240), width=4)

    if curvas:
        for k in range(1, 7):
            seg = [(x, y + k * 26) for x, y in solo if y + k * 26 < ybot - 6]
            if len(seg) > 2:
                d.line(seg, fill=ACCENT + (70,), width=2)
        _rot(d, x0 + 6, top + 6 * 26 + 18, "CURVAS DE NÍVEL", ACCENT, 23, x0, x1)

    if agua:
        pts = [(x, _terreno_v(x, x0, x1, top) - 16)
               for x in range(xq0 + 20, x1 - 26, 6)]
        d.line(pts, fill=AGUA + (255,), width=6)
        ax, ay = pts[-1]
        bx, by = pts[-14]
        ang = math.atan2(ay - by, ax - bx)
        for s in (2.5, -2.5):
            d.line([(ax, ay), (ax - 26 * math.cos(ang + s / 6),
                               ay - 26 * math.sin(ang + s / 6))],
                   fill=AGUA + (255,), width=6)
        xl = x0 + int((x1 - x0) * 0.47)
        _rot(d, xl, _terreno_v(xl, x0, x1, top) - 62, "ÁGUA PLUVIAL", AGUA, 24, x0, x1)

    if marcas:
        ytopo = min(_terreno_v(x, x0, x1, top) - _dossel_v(x, x0, x1)
                    for x in xs) - 52
        for pos, texto, alvo in marcas:
            xp = x0 + int((x1 - x0) * pos)
            ys = _terreno_v(xp, x0, x1, top)
            yc = ys - _dossel_v(xp, x0, x1)
            yp = {"solo": ys, "meio": (ys + yc) / 2, "copa": yc}[alvo]
            d.line([(xp, yp), (xp, ytopo + 14)], fill=ORANGE + (255,), width=3)
            d.ellipse([xp - 7, yp - 7, xp + 7, yp + 7], fill=ORANGE + (255,))
            _rot(d, xp - 6, ytopo - 18, texto, ORANGE, 22, x0, x1)

    if lancamento:
        xp = x0 + int((x1 - x0) * 0.9)
        yp = _terreno_v(xp, x0, x1, top)
        d.ellipse([xp - 12, yp - 12, xp + 12, yp + 12], outline=ORANGE + (255,), width=4)
        d.ellipse([xp - 5, yp - 5, xp + 5, yp + 5], fill=ORANGE + (255,))
        d.line([(xp, yp - 18), (xp, yp - 44)], fill=ORANGE + (255,), width=3)
        f = font(BOLD_F, 23)
        t = "PONTO DE LANÇAMENTO"
        _rot(d, xp - largura(d, t, f, 4) - 18, yp - 78, t, ORANGE, 23, x0, x1)

    img.alpha_composite(layer)


DIAGRAMAS = {
    "perfil_mata": perfil_mata,
    "perfil_vertente": perfil_vertente,
}


def desenhar(img, spec):
    """spec: {"tipo": "...", ...demais kwargs}. Sem tipo, não desenha nada."""
    if not spec:
        return
    s = dict(spec)
    tipo = s.pop("tipo", None)
    if not tipo:
        return
    fn = DIAGRAMAS.get(tipo)
    if fn is None:
        raise SystemExit(f"diagrama desconhecido: {tipo}. Ver DIAGRAMAS em diagramas.py")
    if "marcas" in s and s["marcas"]:
        s["marcas"] = [tuple(m) for m in s["marcas"]]
    fn(img, **s)
