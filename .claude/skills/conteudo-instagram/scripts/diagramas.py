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
        frot = font(BOLD_F, 22)
        # rótulo centrado no marcador e preso à margem; quando dois se
        # encavalam na horizontal, o segundo sobe uma linha em vez de colar.
        itens = []
        for pos, texto, alvo in marcas:
            xp = x0 + int((x1 - x0) * pos)
            w = largura(d, texto, frot, 4)
            lx = int(max(x0, min(xp - w / 2, x1 - w)))
            itens.append([xp, texto, alvo, lx, w])
        itens.sort(key=lambda it: it[3])
        linhas_dir = []  # borda direita já ocupada em cada linha de rótulo
        for it in itens:
            lx, w = it[3], it[4]
            r = 0
            while r < len(linhas_dir) and lx < linhas_dir[r] + 16:
                r += 1
            if r == len(linhas_dir):
                linhas_dir.append(0)
            linhas_dir[r] = lx + w
            it.append(r)
        for xp, texto, alvo, lx, w, r in itens:
            ys = _terreno_v(xp, x0, x1, top)
            yc = ys - _dossel_v(xp, x0, x1)
            yp = {"solo": ys, "meio": (ys + yc) / 2, "copa": yc}[alvo]
            ylab = ytopo - 18 - r * 32
            d.line([(xp, yp), (xp, ylab + 22)], fill=ORANGE + (255,), width=3)
            d.ellipse([xp - 7, yp - 7, xp + 7, yp + 7], fill=ORANGE + (255,))
            tracked(d, (lx, ylab), texto, frot, ORANGE, track=4)

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


# --------------------------------------------- corte_via_pv (locação de PV)

def corte_via_pv(img, cota=None, rotulos=None, descricao=None, top=760):
    """Corte transversal da via para locação de poço de visita (PV) de esgoto.

    Mostra a capa asfáltica como faixa na superfície, o fuste do poço descendo
    abaixo dela (tubo com anéis) com o tampão no nível do greide, o meio-fio na
    lateral e uma cota de amarração lateral ligando o centro do poço à face do
    meio-fio - a referência que sobrevive ao corte do asfalto.

    `cota` é o texto da medida; `rotulos` = [capa, fuste, tampão, meio-fio].
    """
    W, H = img.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1 = MARGIN, W - MARGIN

    padrao = ["CAPA ASFÁLTICA", "FUSTE DO POÇO", "TAMPÃO NO GREIDE", "MEIO-FIO"]
    rot = list(rotulos or [])
    while len(rot) < 4:
        rot.append(padrao[len(rot)])
    r_capa, r_fuste, r_tampao, r_mf = rot[0], rot[1], rot[2], rot[3]

    # --- geometria do corte -------------------------------------------------
    y_surf = top + 100                    # greide = topo da capa asfáltica
    band_h = 26
    y_band = y_surf + band_h              # base da capa
    x_pv = x0 + int((x1 - x0) * 0.35)     # centro do poço de visita
    fw = 42                               # meia-largura do fuste
    y_fuste = min(H - 210, y_surf + 290)  # profundidade desenhada do fuste
    x_mf = x0 + int((x1 - x0) * 0.85)     # face interna do meio-fio
    mf_w = 72
    y_mf_top = y_surf - 30
    y_mf_bot = y_surf + 100
    y_ground = y_fuste + 20

    # degradê de leitura atrás do diagrama (garante contraste sobre a foto)
    y_bg = top - 30
    for y in range(y_bg, min(H, y_ground + 8)):
        a = int(150 * _suave(y, y_bg, y_bg + 64))
        if a:
            d.line([(0, y), (W, y)], fill=(13, 27, 42, a))

    # subleito: pista à esquerda (mais baixa) e terreno/passeio à direita do
    # meio-fio (mais alto) - o meio-fio separa os dois níveis da via
    d.rectangle([x0 - 4, y_band, x_mf, y_ground], fill=(16, 34, 52, 168))
    d.rectangle([x_mf, y_mf_top, x1 + 4, y_ground], fill=(16, 34, 52, 168))
    for yy in range(int(y_band) + 22, int(y_ground), 34):   # hachura do solo
        d.line([(x0, yy), (x1, yy)], fill=(28, 52, 78, 90), width=1)

    # capa asfáltica (faixa escura na pista) + greide, só até a face do meio-fio
    d.rectangle([x0 - 4, y_surf, x_mf, y_band], fill=(9, 16, 26, 235))
    d.line([(x0 - 4, y_surf), (x_mf, y_surf)], fill=(170, 190, 208, 255), width=3)
    # terreno do outro lado do meio-fio, num nível acima do greide da pista
    d.line([(x_mf + mf_w, y_mf_top), (x1 + 4, y_mf_top)], fill=(150, 172, 194, 220), width=2)

    # fuste do poço: massa, anéis e paredes; centro tracejado
    d.rectangle([x_pv - fw, y_surf, x_pv + fw, y_fuste], fill=(38, 60, 86, 185))
    for yy in range(int(y_surf) + 46, int(y_fuste), 46):    # anéis
        d.line([(x_pv - fw, yy), (x_pv + fw, yy)], fill=(120, 145, 170, 210), width=2)
    for xx in (x_pv - fw, x_pv + fw):
        d.line([(xx, y_surf), (xx, y_fuste)], fill=(150, 172, 194, 240), width=4)
    d.line([(x_pv - fw, y_fuste), (x_pv + fw, y_fuste)], fill=(150, 172, 194, 240), width=4)
    _tracejada(d, [(x_pv, y_surf), (x_pv, y_fuste)], ORANGE + (150,), 2, dash=12, gap=10)

    # tampão no greide (elemento em destaque)
    tw = fw + 12
    d.rectangle([x_pv - tw, y_surf - 9, x_pv + tw, y_surf + 7], fill=ACCENT + (255,))
    d.line([(x_pv, y_surf - 9), (x_pv, y_surf + 7)], fill=(13, 27, 42, 210), width=2)

    # meio-fio (guia) na lateral
    d.rectangle([x_mf, y_mf_top, x_mf + mf_w, y_mf_bot], fill=(120, 145, 170, 235))
    d.rectangle([x_mf, y_mf_top, x_mf + mf_w, y_mf_bot], outline=(170, 190, 208, 255), width=2)

    # --- cota de amarração lateral: centro do PV -> face do meio-fio ---------
    y_dim = y_surf - 44
    d.line([(x_pv, y_dim), (x_mf, y_dim)], fill=ORANGE + (255,), width=3)
    d.line([(x_pv, y_dim - 4), (x_pv, y_surf - 2)], fill=ORANGE + (200,), width=2)
    d.line([(x_mf, y_dim - 4), (x_mf, y_mf_top)], fill=ORANGE + (200,), width=2)
    for xx, s in ((x_pv, 1), (x_mf, -1)):
        d.polygon([(xx, y_dim), (xx + 15 * s, y_dim - 7), (xx + 15 * s, y_dim + 7)],
                  fill=ORANGE + (255,))
    if cota:
        fc = font(BOLD_F, 27)
        wc = largura(d, cota, fc, 4)
        xc = int((x_pv + x_mf) / 2 - wc / 2)
        _rot(d, xc, y_dim - 42, cota, ORANGE, 27, x0, x1)

    # --- rótulos com linha de chamada (clampados à margem) ------------------
    def _leader(target, lx, ly, texto, cor, tam=22):
        f = font(BOLD_F, tam)
        w = largura(d, texto, f, 4)
        lx = int(max(x0, min(lx, x1 - w)))
        tracked(d, (lx, ly), texto, f, cor, track=4)
        tx, ty = target
        cx = lx if abs(tx - lx) <= abs(tx - (lx + w)) else lx + w
        cy = ly - 4 if ty < ly else ly + tam + 2
        d.line([(cx, cy), target], fill=cor + (220,), width=2)
        d.ellipse([tx - 5, ty - 5, tx + 5, ty + 5], fill=cor + (255,))

    _leader((x_pv - tw + 6, y_surf - 1), x0 + 4, y_surf - 54, r_tampao, ACCENT, 22)
    _leader((x0 + 165, y_surf + band_h // 2), x0 + 4, y_band + 22, r_capa, WHITE, 22)
    _leader((x_pv + fw, y_surf + 160), x_pv + fw + 44, y_surf + 146, r_fuste, WHITE, 22)
    _leader((x_mf + mf_w // 2, y_mf_bot), x_mf - 24, y_mf_bot + 18, r_mf, WHITE, 22)

    img.alpha_composite(layer)


DIAGRAMAS = {
    "perfil_mata": perfil_mata,
    "perfil_vertente": perfil_vertente,
    "corte_via_pv": corte_via_pv,
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
