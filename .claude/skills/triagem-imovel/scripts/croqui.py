"""Croqui esquematico a partir do que a matricula descreve.

Uso:
    python croqui.py <spec.json> [--saida <pasta>]

Matricula antiga raramente fecha: descreve alguns alinhamentos com rumo e
distancia e resolve o resto com divisa natural ("segue o corrego", "acompanha
a serra"). Este script desenha em escala o que esta descrito e fecha o resto
com um traco arbitrado, dimensionado para a figura encerrar a area registral.

O trecho arbitrado NAO e levantamento. Por isso sai em camada separada,
tracejado, rotulado ao longo de todo o percurso, e o DXF carrega um bloco de
aviso. Croqui que nao se identifica como hipotese vira, duas semanas depois,
prova de divisa em reuniao com confrontante.

Formato do spec (JSON):
{
  "titulo": "Matricula 627 - Fazenda Taboquinha II",
  "local": "Bandeirantes/MS",
  "area_registral_m2": 1342861,
  "origem": "marco na margem da serra de Maracaju",
  "referencial": "rumos magneticos de 1982, sem datum",
  "lado_fechamento": "direita",
  "trecho_arbitrado": "corrego sem denominacao, corrego do meio e serra",
  "segmentos": [
    {"rumo": "76 35 SW", "dist": 770.00, "obs": "divisa com a area B"}
  ]
}

`rumo` aceita "76 35 SW", "76o35' SW" ou azimute decimal ("256.583").
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

CAMADA_DESCRITO = "DESCRITO-NA-MATRICULA"
CAMADA_ARBITRADO = "ARBITRADO-NAO-LEVANTADO"
CAMADA_ROTULO = "ROTULOS"
CAMADA_CHAMADA = "LINHAS-DE-CHAMADA"
CAMADA_AVISO = "AVISO"


class Rotulos:
    """Coloca rotulo fora do desenho, puxado por linha de chamada.

    Alinhamento curto ao lado de alinhamento longo - 4,65 m contra 770,00 m -
    empilha rotulo em cima de rotulo no meio do croqui. Aqui cada rotulo sai
    perpendicular ao seu segmento e vai se afastando ate achar espaco livre,
    alternando de lado, com uma linha fina ligando ao ponto que ele descreve.
    """

    def __init__(self, msp, escala):
        self.msp, self.escala = msp, escala
        self.ocupados = []

    @staticmethod
    def _colide(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def _caixa(self, x, y, texto, altura):
        larg = len(texto) * altura * 0.62
        folga = altura * 0.35
        return (x - larg / 2 - folga, y - altura / 2 - folga,
                x + larg / 2 + folga, y + altura / 2 + folga)

    def reservar(self, x, y, texto, altura):
        self.ocupados.append(self._caixa(x, y, texto, altura))

    def colocar(self, alvo, direcao, texto, altura, tentativas=24):
        """`alvo` e o ponto descrito; `direcao` e o vetor unitario do segmento."""
        nx, ny = -direcao[1], direcao[0]
        for i in range(tentativas):
            lado = 1 if i % 2 == 0 else -1
            dist = self.escala * (1.4 + 1.35 * (i // 2))
            x, y = alvo[0] + nx * dist * lado, alvo[1] + ny * dist * lado
            caixa = self._caixa(x, y, texto, altura)
            if all(not self._colide(caixa, o) for o in self.ocupados):
                break
        self.ocupados.append(caixa)
        self.msp.add_line(alvo, (x, y), dxfattribs={"layer": CAMADA_CHAMADA})
        self.msp.add_circle(alvo, radius=altura * 0.12,
                            dxfattribs={"layer": CAMADA_CHAMADA})
        return x, y


def azimute(rumo: str) -> float:
    """Converte rumo por quadrante em azimute decimal. Aceita azimute direto."""
    texto = rumo.strip().upper().replace("º", " ").replace("°", " ")
    texto = texto.replace("'", " ").replace('"', " ").replace("-", " ")
    quad = re.findall(r"NE|NW|SE|SW", texto.replace(" ", ""))
    numeros = [float(x.replace(",", ".")) for x in re.findall(r"\d+[.,]?\d*", texto)]
    if not numeros:
        raise ValueError(f"rumo sem numero: {rumo!r}")

    ang = numeros[0]
    if len(numeros) > 1:
        ang += numeros[1] / 60
    if len(numeros) > 2:
        ang += numeros[2] / 3600
    if not quad:
        return ang % 360  # ja era azimute
    return {"NE": ang, "SE": 180 - ang, "SW": 180 + ang, "NW": 360 - ang}[quad[0]] % 360


def rumo_texto(rumo: str) -> str:
    """Devolve o rumo em forma canonica: 76 35 SW -> 76°35' SW."""
    texto = str(rumo).strip().upper().replace("º", " ").replace("°", " ")
    texto = texto.replace("'", " ").replace('"', " ").replace("-", " ")
    quad = re.findall(r"NE|NW|SE|SW", texto.replace(" ", ""))
    n = [float(x.replace(",", ".")) for x in re.findall(r"\d+[.,]?\d*", texto)]
    if not n:
        return str(rumo)
    if not quad and len(n) == 1:
        return f"Az {n[0]:.4f}°"  # azimute decimal puro, sem minuto/segundo
    saida = f"{int(n[0])}°"
    if len(n) > 1:
        saida += f"{int(n[1]):02d}'"
    if len(n) > 2:
        saida += f'{int(n[2]):02d}"'
    return f"{saida} {quad[0]}" if quad else f"Az {saida}"


def caminhar(segmentos: list[dict]) -> list[tuple[float, float]]:
    """Aplica os segmentos a partir da origem (0,0). X para leste, Y para norte."""
    pontos = [(0.0, 0.0)]
    for s in segmentos:
        az = math.radians(azimute(str(s["rumo"])))
        x, y = pontos[-1]
        pontos.append((x + s["dist"] * math.sin(az), y + s["dist"] * math.cos(az)))
    return pontos


def area_poligono(pontos: list[tuple[float, float]]) -> float:
    """Area com sinal, pela formula do cadarco."""
    s = sum(pontos[i][0] * pontos[i - 1][1] - pontos[i - 1][0] * pontos[i][1]
            for i in range(len(pontos)))
    return s / 2


def arco_de_fechamento(cadeia, area_alvo, lado="direita", passos=96):
    """Arco circular do fim da cadeia de volta ao inicio, dimensionado para a
    figura inteira encerrar area_alvo.

    A bisseccao roda sobre a area da figura efetivamente construida, nao sobre
    a formula do segmento circular. Decompor em "area do caminhamento + area do
    segmento" exige acertar o sinal da orientacao das duas partes, e errar esse
    sinal fecha a figura com o dobro da area do caminhamento de erro - sem
    nenhum sintoma visivel no desenho. Medir o poligono pronto tambem absorve a
    perda da discretizacao do arco.
    """
    inicio, fim = cadeia[0], cadeia[-1]
    cx, cy = fim[0] - inicio[0], fim[1] - inicio[1]
    corda = math.hypot(cx, cy)
    if corda < 1e-9 or area_alvo <= 0:
        return [], 0.0, 0.0

    sinal = -1.0 if lado == "direita" else 1.0
    nx, ny = sinal * (-cy / corda), sinal * (cx / corda)
    mx, my = (fim[0] + inicio[0]) / 2, (fim[1] + inicio[1]) / 2

    def construir(th):
        raio = corda / (2 * math.sin(th))
        centro = (mx - nx * raio * math.cos(th), my - ny * raio * math.cos(th))
        a0 = math.atan2(fim[1] - centro[1], fim[0] - centro[0])
        a1 = math.atan2(inicio[1] - centro[1], inicio[0] - centro[0])
        # so um dos dois sentidos percorre o angulo central 2*th
        ccw = (a1 - a0) % (2 * math.pi)
        sentido = 1.0 if abs(ccw - 2 * th) < abs(ccw - 2 * math.pi + 2 * th) else -1.0
        passo = (2 * th) / passos
        arco = [(centro[0] + raio * math.cos(a0 + sentido * passo * i),
                 centro[1] + raio * math.sin(a0 + sentido * passo * i))
                for i in range(1, passos + 1)]
        return arco, raio

    def area(th):
        arco, _ = construir(th)
        return abs(area_poligono(list(cadeia) + arco + [inicio]))

    lo, hi = 1e-4, math.pi - 1e-4
    if area(hi) < area_alvo:
        th = hi  # area registral grande demais para a corda: usa o maior arco
    else:
        for _ in range(120):
            th = (lo + hi) / 2
            if area(th) < area_alvo:
                lo = th
            else:
                hi = th
        th = (lo + hi) / 2

    arco, raio = construir(th)
    return arco, raio, 2 * th


def desenhar(spec: dict, dxf: Path) -> dict:
    segmentos = spec["segmentos"]
    pontos = caminhar(segmentos)
    descrito = sum(s["dist"] for s in segmentos)

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    # cor verdadeira alem do indice: o verde e o vermelho puros da paleta ACI
    # ficam lavados sobre fundo branco, e o croqui vai para PDF branco
    descrito_l = doc.layers.add(CAMADA_DESCRITO, color=3)
    arbitrado_l = doc.layers.add(CAMADA_ARBITRADO, color=1, linetype="DASHED")
    descrito_l.rgb, arbitrado_l.rgb = (11, 110, 63), (193, 18, 31)
    descrito_l.dxf.lineweight = arbitrado_l.dxf.lineweight = 50  # 0,50 mm
    doc.layers.add(CAMADA_ROTULO, color=7).rgb = (40, 40, 40)
    doc.layers.add(CAMADA_CHAMADA, color=8).rgb = (130, 130, 130)
    doc.layers.add(CAMADA_AVISO, color=1).rgb = (150, 20, 25)
    doc.header["$LWDISPLAY"] = 1

    alvo = spec.get("area_registral_m2")
    arco, raio, varredura = [], 0.0, 0.0
    if alvo:
        arco, raio, varredura = arco_de_fechamento(
            pontos, abs(alvo), spec.get("lado_fechamento", "direita"))

    msp.add_lwpolyline(pontos, dxfattribs={"layer": CAMADA_DESCRITO})
    msp.add_lwpolyline([pontos[-1]] + arco + [pontos[0]] if arco
                       else [pontos[-1], pontos[0]],
                       dxfattribs={"layer": CAMADA_ARBITRADO})

    escala = max(descrito / 25, 12)
    # sem isto o tracejado do trecho arbitrado sai continuo num desenho de
    # centenas de metros, e some justamente o sinal de "isto e hipotese"
    doc.header["$LTSCALE"] = escala

    rotulos = Rotulos(msp, escala)
    alt_v, alt_s, alt_a = escala * 0.42, escala * 0.5, escala * 0.55

    # 1) o trecho arbitrado se identifica ao longo do percurso, nao so na
    # legenda. Vai primeiro para que os demais rotulos desviem dele.
    aviso = "TRECHO ARBITRADO - NAO LEVANTADO"
    for i in range(0, len(arco), max(len(arco) // 6, 1)):
        rotulos.reservar(arco[i][0], arco[i][1], aviso, alt_a)
        msp.add_text(aviso, height=alt_a,
                     dxfattribs={"layer": CAMADA_ARBITRADO}).set_placement(
            arco[i], align=TextEntityAlignment.MIDDLE_CENTER)

    # 2) vertices
    for i, p in enumerate(pontos):
        msp.add_circle(p, radius=escala / 5,
                       dxfattribs={"layer": CAMADA_DESCRITO})
    for i, p in enumerate(pontos):
        vizinho = pontos[i + 1] if i + 1 < len(pontos) else pontos[i - 1]
        comp = math.dist(p, vizinho) or 1.0
        direcao = ((vizinho[0] - p[0]) / comp, (vizinho[1] - p[1]) / comp)
        x, y = rotulos.colocar(p, direcao, f"P{i}", alt_v)
        msp.add_text(f"P{i}", height=alt_v,
                     dxfattribs={"layer": CAMADA_ROTULO}).set_placement(
            (x, y), align=TextEntityAlignment.MIDDLE_CENTER)

    # 3) alinhamentos
    for i, s in enumerate(segmentos):
        a, b = pontos[i], pontos[i + 1]
        meio = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        comp = math.dist(a, b) or 1.0
        direcao = ((b[0] - a[0]) / comp, (b[1] - a[1]) / comp)
        texto = f"{rumo_texto(s['rumo'])} - {s['dist']:.2f} m"
        x, y = rotulos.colocar(meio, direcao, texto, alt_s)
        msp.add_text(texto, height=alt_s,
                     dxfattribs={"layer": CAMADA_ROTULO}).set_placement(
            (x, y), align=TextEntityAlignment.MIDDLE_CENTER)

    arbitrado_m = raio * varredura if arco else math.dist(pontos[-1], pontos[0])
    linhas = [
        f"CROQUI ESQUEMATICO - {spec.get('titulo', '')}",
        spec.get("local", ""),
        "",
        "NAO E LEVANTAMENTO TOPOGRAFICO. NAO SERVE PARA LOCALIZAR O IMOVEL,",
        "INSTRUIR CERTIFICACAO NEM DEFINIR DIVISA EM CAMPO.",
        "",
        f"Verde continuo    = descrito na matricula: {len(segmentos)} alinhamento(s), "
        f"{descrito:.2f} m",
        f"Vermelho tracejado = ARBITRADO pelo script: {arbitrado_m:.2f} m",
        "",
        f"Origem: {spec.get('origem', 'arbitraria')} - coordenada local, sem datum.",
        f"Referencial: {spec.get('referencial', 'nao declarado na matricula')}",
        f"Trecho arbitrado corresponde a: {spec.get('trecho_arbitrado', '-')}",
        "",
        "O arco vermelho foi dimensionado apenas para a figura encerrar a area",
        "registral. Sua forma e sua posicao sao invencao do script - a divisa",
        "real e natural e nao esta descrita na matricula.",
    ]
    if alvo:
        linhas.insert(9, f"Area registral usada como alvo: {alvo / 10000:.4f} ha")

    todos = pontos + arco
    x = min(p[0] for p in todos)
    y = min(p[1] for p in todos) - escala * 4
    for i, linha in enumerate(linhas):
        msp.add_text(linha, height=escala * 0.7,
                     dxfattribs={"layer": CAMADA_AVISO}).set_placement(
            (x, y - i * escala * 1.1))

    doc.saveas(dxf)
    resultante = abs(area_poligono(todos + [pontos[0]]))
    erro = abs(resultante - alvo) / alvo * 100 if alvo else 0.0
    if erro > 1.0:
        # a figura tem que encerrar a area registral; se nao encerra, o croqui
        # esta dizendo uma area que a matricula nao diz
        print(f"ATENCAO: figura encerra {resultante / 10000:.4f} ha contra "
              f"{alvo / 10000:.4f} ha da matricula ({erro:.1f}% de erro)",
              file=sys.stderr)
    return {
        "descrito_m": descrito,
        "arbitrado_m": arbitrado_m,
        "area_resultante_ha": resultante / 10000,
        "erro_area_pct": erro,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", help="JSON com os segmentos lidos da matricula")
    ap.add_argument("--saida", default=None)
    args = ap.parse_args()

    caminho = Path(args.spec)
    spec = json.loads(caminho.read_text(encoding="utf-8"))
    saida = Path(args.saida) if args.saida else caminho.parent
    saida.mkdir(parents=True, exist_ok=True)
    nome = caminho.stem.replace("spec-", "")

    r = desenhar(spec, saida / f"croqui-{nome}.dxf")
    pct = 100 * r["arbitrado_m"] / (r["arbitrado_m"] + r["descrito_m"])

    tabela = "\n".join(
        f"| {i + 1} | {s['rumo']} | {s['dist']:.2f} m | {s.get('obs', '')} |"
        for i, s in enumerate(spec["segmentos"]))

    nota = f"""# Croqui - {spec.get('titulo', nome)}

**Este croqui e em parte invencao do script. Leia antes de usar.**

| | |
| --- | --- |
| Alinhamentos descritos na matricula | {len(spec['segmentos'])} |
| Extensao descrita | {r['descrito_m']:.2f} m |
| Extensao arbitrada pelo script | {r['arbitrado_m']:.2f} m |
| **Percentual arbitrado do perimetro** | **{pct:.0f}%** |
| Area encerrada pela figura | {r['area_resultante_ha']:.4f} ha |
| Area registral | {spec.get('area_registral_m2', 0) / 10000:.4f} ha |

## O que veio da matricula

| # | rumo | distancia | observacao |
| --- | --- | --- | --- |
{tabela}

Referencial: {spec.get('referencial', 'nao declarado')}. Origem em
{spec.get('origem', 'ponto arbitrario')}, coordenada local - o croqui **nao tem
georreferencia**, so forma e dimensao.

## O que o script produziu

O trecho vermelho tracejado, correspondente a: {spec.get('trecho_arbitrado', '-')}.

A matricula nao da rumo nem distancia nesse trecho. O arco foi dimensionado por
calculo para que a figura encerre a area registral - e a unica informacao real
embutida nele. **Forma e posicao sao arbitrarias.** A divisa verdadeira e
natural e segue acidente geografico, nao um arco.

## Como usar

Serve para conversar sobre ordem de grandeza e sobre a proporcao entre a divisa
descrita e o resto do perimetro, e para orientar onde procurar em campo. **Nao
serve** para localizar o imovel, instruir certificacao, definir divisa ou
embasar anuencia de confrontante.
"""
    (saida / f"croqui-{nome}.md").write_text(nota, encoding="utf-8")

    print(f"croqui-{nome}.dxf | descrito {r['descrito_m']:.2f} m, "
          f"arbitrado {r['arbitrado_m']:.2f} m ({pct:.0f}% do perimetro)")
    print(f"area encerrada: {r['area_resultante_ha']:.4f} ha")
    return 0


if __name__ == "__main__":
    sys.exit(main())
