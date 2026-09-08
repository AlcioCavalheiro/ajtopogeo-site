"""Gera os arquivos de marca a partir do LOGO.png da empresa.

    py gestor/marca/gerar.py

Sai aqui nesta pasta:

  ajtopogeo.ico    o globo, quadrado, de 16 a 256 px -- icone dos executaveis,
                   dos atalhos e da janela
  ajtopogeo.png    o logo inteiro, para o topo das janelas

Os dois saem com fundo transparente. O logo de origem e RGB sobre branco, e
recortar esse fundo exige cuidado em dois pontos:

- **nao da para inundar a partir das bordas**: o desenho tem preto proprio (os
  contornos e o texto), e a inundacao os levaria junto;
- **nao da para tirar todo pixel branco**: as linhas brancas entre as placas
  fazem parte do globo.

Entao o fundo do globo sai pela silhueta eliptica dele, que e exata, e o do
texto sai por transparencia proporcional a luminosidade, que preserva o
serrilhado suave das letras.

Precisa de Pillow e numpy, so na maquina que gera. Os arquivos ficam versionados.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
ORIGEM = AQUI.parent / "LOGO.png"

# O LOGO.png tem uma setinha de redimensionar colada no canto inferior direito,
# resquicio de captura de tela. Tudo abaixo desta linha e descartado.
LIMITE_RODAPE = 600


def caixa_do_globo(logo, margem=7):
    """Envolvente do globo, pelo azul, com folga para o contorno preto."""
    a = np.asarray(logo).astype(int)
    azul = (a[:, :, 2] > a[:, :, 0] + 30) & (a[:, :, 2] > 80)
    ys, xs = np.where(azul)
    return (max(int(xs.min()) - margem, 0), max(int(ys.min()) - margem, 0),
            min(int(xs.max()) + margem + 1, logo.width),
            min(int(ys.max()) + margem + 1, logo.height))


def alfa_por_luminosidade(im, opaco=205, transparente=250):
    """Transparencia proporcional ao quanto o pixel se afasta do branco.

    Preserva a suavidade das bordas do texto: um pixel cinza de anti-serrilhado
    vira meio transparente, em vez de virar um degrau.
    """
    l = np.asarray(im.convert("L")).astype(float)
    alfa = (transparente - l) * (255.0 / (transparente - opaco))
    return Image.fromarray(np.clip(alfa, 0, 255).astype(np.uint8), "L")


def quadrar(im, folga=0.06):
    """Centraliza numa tela quadrada com uma folga proporcional."""
    lado = int(max(im.size) * (1 + 2 * folga))
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.paste(im, ((lado - im.width) // 2, (lado - im.height) // 2), im)
    return tela


def main():
    if not ORIGEM.exists():
        raise SystemExit(f"nao achei {ORIGEM}")
    logo = Image.open(ORIGEM).convert("RGB")
    caixa = caixa_do_globo(logo)

    # --- icone: so o globo. Em 16 px o texto "AJ TopoGeo" vira borrao, e o
    # globo sozinho e o que se reconhece na barra de tarefas.
    globo = logo.crop(caixa).convert("RGBA")
    silhueta = Image.new("L", globo.size, 0)
    ImageDraw.Draw(silhueta).ellipse((0, 0, globo.width - 1, globo.height - 1), fill=255)
    globo.putalpha(silhueta)
    icone = quadrar(globo)
    destino_ico = AQUI / "ajtopogeo.ico"
    icone.save(destino_ico, sizes=[(n, n) for n in (256, 128, 64, 48, 32, 24, 16)])
    print(f"  {destino_ico.name}: globo {globo.size} -> quadrado {icone.size}")

    # --- faixa: o logo inteiro, para o topo da janela. Fora do globo vale a
    # transparencia por luminosidade; dentro dele, a silhueta manda, para as
    # linhas brancas entre as placas nao sumirem.
    justo = logo.crop((0, 0, logo.width, LIMITE_RODAPE))
    recorte = alfa_por_luminosidade(justo).getbbox()
    faixa = justo.crop(recorte).convert("RGBA")
    alfa = alfa_por_luminosidade(justo.crop(recorte))
    dentro = Image.new("L", faixa.size, 0)
    ImageDraw.Draw(dentro).ellipse(
        (caixa[0] - recorte[0], caixa[1] - recorte[1],
         caixa[2] - recorte[0] - 1, caixa[3] - recorte[1] - 1), fill=255)
    faixa.putalpha(Image.composite(Image.new("L", faixa.size, 255), alfa, dentro))

    altura = 56
    faixa = faixa.resize((round(faixa.width * altura / faixa.height), altura),
                         Image.LANCZOS)
    destino_png = AQUI / "ajtopogeo.png"
    faixa.save(destino_png)
    print(f"  {destino_png.name}: recorte {recorte} -> {faixa.size}")


if __name__ == "__main__":
    main()
