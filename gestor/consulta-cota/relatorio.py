"""Le o relatorio de processamento fotogrametrico: Pix4D (.xml) ou Agisoft (.pdf).

O que interessa daqui e o erro medio das posicoes de camera -- o quanto o ajuste
do bloco moveu as fotos em relacao as coordenadas que entraram. E o que vira
sigma do levantamento na janela.

O PDF do Agisoft e lido sem biblioteca de PDF, pela mesma razao que o mapa e
escrito sem uma: o programa e distribuido como executavel unico e a regra do
pacote e nao acrescentar dependencia. O trabalho aqui e maior do que no mapa
porque o Agisoft usa fonte Type0 com codificacao Identity -- os bytes do texto
sao numeros de glifo, nao letras --, mas o proprio PDF carrega o `ToUnicode`,
que e a tabela de volta. Com ela e o `zlib`, o texto sai inteiro.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path


# --------------------------------------------------------- PDF -> texto


def _objetos(dados: bytes) -> dict:
    """Todos os objetos do arquivo, por numero.

    Varredura direta em vez de seguir a tabela xref: o relatorio do Agisoft e
    PDF 1.4 classico, sem fluxo de objetos, e uma varredura nao quebra quando a
    tabela esta desatualizada -- o que acontece em arquivo que passou por editor.
    """
    achados = {}
    for m in re.finditer(rb"(\d+)\s+0\s+obj\b(.*?)\bendobj", dados, re.S):
        achados[int(m.group(1))] = m.group(2)
    return achados


def _fluxo(corpo: bytes) -> bytes | None:
    """Conteudo do stream do objeto, ja descomprimido quando for Flate."""
    m = re.search(rb"stream\r?\n", corpo)
    if not m:
        return None
    fim = corpo.rfind(b"endstream")
    if fim < 0:
        return None
    cru = corpo[m.end():fim]
    if cru.endswith(b"\r\n"):
        cru = cru[:-2]
    elif cru.endswith(b"\n") or cru.endswith(b"\r"):
        cru = cru[:-1]
    if b"/FlateDecode" in corpo[:m.start()]:
        try:
            return zlib.decompress(cru)
        except zlib.error:
            try:
                return zlib.decompressobj().decompress(cru)
            except zlib.error:
                return None
    return cru


# Uma faixa do bfrange tem duas formas, e as duas aparecem no mesmo arquivo:
#   <lo> <hi> <destino>        -- o destino anda junto com o codigo
#   <lo> <hi> [<d1> <d2> ...]  -- cada codigo tem o seu destino na lista
# Ler so a primeira faz a segunda casar com o primeiro elemento da lista e
# montar um mapa incrementando a partir dele: o texto sai como sequencia de
# letras seguidas, que parece texto e nao e.
_FAIXA = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(?:\[(.*?)\]|<([0-9A-Fa-f]+)>)",
                    re.S)


def _tabela_tounicode(cmap: bytes) -> dict:
    """Le o CMap ToUnicode: numero de glifo -> caractere."""
    tabela = {}
    texto = cmap.decode("latin-1", "replace")
    for bloco in re.findall(r"beginbfchar(.*?)endbfchar", texto, re.S):
        for origem, destino in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", bloco):
            tabela[int(origem, 16)] = _decodificar(destino)
    for bloco in re.findall(r"beginbfrange(.*?)endbfrange", texto, re.S):
        for ini, fim, lista, unico in _FAIXA.findall(bloco):
            comeco, termino = int(ini, 16), int(fim, 16)
            if lista:
                destinos = re.findall(r"<([0-9A-Fa-f]+)>", lista)
                for i, destino in enumerate(destinos):
                    if comeco + i <= termino:
                        tabela[comeco + i] = _decodificar(destino)
            else:
                base = int(unico, 16)
                for i in range(comeco, termino + 1):
                    tabela[i] = chr(base + i - comeco)
    return tabela


def _decodificar(hexa: str) -> str:
    """UTF-16BE do ToUnicode; um destino pode ter mais de um caractere."""
    try:
        return bytes.fromhex(hexa).decode("utf-16-be", "replace")
    except ValueError:
        return ""


def _mapas_de_fonte(objs: dict) -> dict:
    """Para cada objeto de fonte, a tabela de glifos dele."""
    mapas = {}
    for numero, corpo in objs.items():
        if b"/ToUnicode" not in corpo:
            continue
        m = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", corpo)
        if not m:
            continue
        fluxo = _fluxo(objs.get(int(m.group(1)), b""))
        if fluxo:
            mapas[numero] = _tabela_tounicode(fluxo)
    return mapas


def _cordas(fragmento: str):
    """Os pedacos de texto de um operador Tj ou TJ, em hexadecimal ou literal."""
    for m in re.finditer(r"<([0-9A-Fa-f\s]*)>|\(((?:[^()\\]|\\.)*)\)", fragmento):
        if m.group(1) is not None:
            yield ("hex", re.sub(r"\s", "", m.group(1)))
        else:
            yield ("lit", m.group(2))


def texto_do_pdf(caminho) -> str:
    """Texto do PDF, pagina a pagina, na ordem em que aparece."""
    dados = Path(caminho).read_bytes()
    if not dados.startswith(b"%PDF"):
        raise ValueError("Este arquivo nao e um PDF.")
    objs = _objetos(dados)
    mapas = _mapas_de_fonte(objs)

    partes = []
    for numero, corpo in objs.items():
        if b"/Type" not in corpo or b"/Page" not in corpo:
            continue
        if re.search(rb"/Type\s*/Pages\b", corpo):
            continue
        # De qual objeto de fonte cada apelido /Fxx desta pagina vem. O
        # /Resources costuma ser referencia indireta -- no relatorio do Agisoft
        # e sempre --, entao procurar as fontes dentro do objeto da pagina nao
        # acha nada e o texto sairia como numero de glifo cru.
        recursos = corpo
        ref = re.search(rb"/Resources\s+(\d+)\s+0\s+R", corpo)
        if ref:
            recursos = objs.get(int(ref.group(1)), b"")
        fontes = {}
        for apelido, alvo in re.findall(rb"/(\w+)\s+(\d+)\s+0\s+R", recursos):
            if int(alvo) in mapas:
                fontes[apelido.decode("latin-1")] = mapas[int(alvo)]

        for m in re.finditer(rb"/Contents\s+(\d+)\s+0\s+R", corpo):
            fluxo = _fluxo(objs.get(int(m.group(1)), b""))
            if fluxo:
                partes.append(_texto_do_fluxo(fluxo, fontes))
    return "\n".join(partes)


def _texto_do_fluxo(fluxo: bytes, fontes: dict) -> str:
    conteudo = fluxo.decode("latin-1", "replace")
    atual = {}
    saida = []
    # A quebra de linha e o ET, fim do bloco de texto -- nao o Td. O Agisoft
    # posiciona **cada glifo** com o seu proprio Td; tratar Td como quebra sai
    # com uma letra por linha, e ai nenhum rotulo casa.
    for m in re.finditer(r"/(\w+)\s+[\d.]+\s+Tf|(\[[^\]]*\]\s*TJ)|((?:<[^>]*>|\([^)]*\))\s*Tj)"
                         r"|\b(ET|T\*)\b", conteudo):
        if m.group(1):
            atual = fontes.get(m.group(1), atual)
        elif m.group(2) or m.group(3):
            pedaco = m.group(2) or m.group(3)
            texto = ""
            for tipo, bruto in _cordas(pedaco):
                if tipo == "hex":
                    if len(bruto) % 4 == 0 and atual:
                        # Identity: dois bytes por glifo
                        texto += "".join(atual.get(int(bruto[i:i + 4], 16), "")
                                         for i in range(0, len(bruto), 4))
                    else:
                        texto += bytes.fromhex(bruto).decode("latin-1", "replace")
                else:
                    texto += re.sub(r"\\(.)", r"\1", bruto)
            saida.append(texto)
        else:
            saida.append("\n")
    return "".join(saida)


# --------------------------------------------------------- Agisoft


def _numero(texto):
    try:
        return float(texto.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def ler_agisoft_pdf(caminho) -> dict:
    """Le o Processing Report do Agisoft Metashape.

    O numero que serve de sigma e a **Table 3, Average camera location error**:
    a diferenca media entre a posicao que o ajuste estimou para cada camera e a
    coordenada que entrou com a foto. E o equivalente ao RMS do bloco no Pix4D --
    precisao interna, nao acuracia.
    """
    texto = texto_do_pdf(caminho)
    if "Agisoft" not in texto and "Processing Report" not in texto:
        raise ValueError("Este PDF nao parece um relatorio do Agisoft Metashape.")

    limpo = re.sub(r"[ \t]+", " ", texto)

    def depois_de(rotulo, padrao=r"([-\d.,]+)"):
        m = re.search(re.escape(rotulo) + r"\s*:?\s*" + padrao, limpo)
        return _numero(m.group(1)) if m else None

    dados = dict(
        fonte="Agisoft Metashape",
        projeto=(re.search(r"^\s*(.+?)\s*\n\s*Processing Report", texto) or [None, ""])[1]
        if re.search(r"^\s*(.+?)\s*\n\s*Processing Report", texto) else "",
        processado=(re.search(r"Processing Report\s*\n\s*(.+)", texto).group(1).strip()
                    if re.search(r"Processing Report\s*\n\s*(.+)", texto) else ""),
        imagens=depois_de("Number of images"),
        altura_voo=depois_de("Flying altitude"),
        gsd_cm=depois_de("Ground resolution"),
        area_km2=depois_de("Coverage area"),
        reprojecao_px=depois_de("Reprojection error"),
        sigma=None, media=None,
    )

    # Table 3: os cinco numeros que seguem os cabecalhos de erro
    m = re.search(r"X error \(m\).{0,120}?Total error \(m\)\s*((?:[-\d.,]+\s+){4}[-\d.,]+)",
                  limpo, re.S)
    if m:
        v = [_numero(x) for x in m.group(1).split()]
        if len(v) >= 3 and None not in v[:3]:
            dados["rms"] = {"x": v[0], "y": v[1], "z": v[2]}
            dados["erro_xy"] = v[3] if len(v) > 3 else None
            dados["erro_total"] = v[4] if len(v) > 4 else None
    if not dados.get("rms"):
        raise ValueError("Achei o relatorio, mas nao a tabela de erro medio das "
                         "posicoes de camera (Table 3).")
    return dados


# --------------------------------------------------------- despacho


def ler(caminho) -> dict:
    """Le o relatorio, seja qual for o programa que o gerou."""
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".pdf":
        return ler_agisoft_pdf(caminho)

    import cota
    dados = cota.ler_relatorio_pix4d(caminho)
    dados.setdefault("fonte", "Pix4D")
    return dados


if __name__ == "__main__":
    import sys
    for chave, valor in ler(sys.argv[1]).items():
        print(f"  {chave:16s} {valor}")
