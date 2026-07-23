# -*- coding: utf-8 -*-
"""Acrescenta a sessão ao arquivo de pauta do mês, no Drive.

    python registrar.py pauta.json

O arquivo do mês é a memória da rotina: é ele que impede repetir gancho, tema
ou foto já usados. Ler antes de escrever peça nova não é opcional.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os
import sys

DRIVE = r"G:\Meu Drive\EMPRESA\AJ TOPOGEO\_ROTINAS\INSTAGRAM"


def bloco(pauta):
    L = []
    L.append(f"\n---\n\n## {pauta['data']} · {pauta['servico']}\n")
    if pauta.get("contexto"):
        L.append(f"**Contexto técnico:** {pauta['contexto']}\n")
    L.append(f"**Arquivos:** `{pauta['pasta_saida']}`")
    L.append(f"**Guia em PDF:** `GUIA_PUBLICACAO_{pauta['data']}.pdf`\n")

    for p in pauta["pecas"]:
        L.append(f"### {p['id']} — {p.get('eixo','')} · {p['formato']}")
        L.append(f"**Gancho:** {p.get('titulo','')}")
        if p["formato"] == "carrossel":
            L.append(f"**Arte:** {p['id']}_CARD_1 a _{len(p['cards'])} (1080x1350)")
        else:
            L.append(f"**Arte:** {p['id']}_REEL.mp4 + {p['id']}_CAPA_REEL.jpg")
        L.append(f"**Hashtags:** {' '.join(p['hashtags'])}\n")

    fundos = []
    for p in pauta["pecas"]:
        if p["formato"] == "carrossel":
            for i, c in enumerate(p["cards"], 1):
                if c.get("bg"):
                    fundos.append((f"{p['id']}-{i}", c["bg"]))
        elif p.get("capa", {}).get("bg"):
            fundos.append((f"{p['id']} capa", p["capa"]["bg"]))
    if fundos:
        L.append("### Imagem de fundo por card (não reutilizar)")
        L.append("| Card | Imagem |")
        L.append("|---|---|")
        L += [f"| {k} | `{v}` |" for k, v in fundos]
        L.append("")

    L.append("### Ganchos usados nesta sessão")
    L += [f"- {p.get('titulo','')}" for p in pauta["pecas"]]

    if pauta.get("fora"):
        L.append("\n### Não reaproveitar")
        L += [f"- {i['material']} — {i['motivo']}" for i in pauta["fora"]]

    if pauta.get("pendencias"):
        L.append("\n### Pendências")
        L += [f"- **{i['item']}:** {i['situacao']}" for i in pauta["pendencias"]]

    return "\n".join(L) + "\n"


def main(caminho):
    with open(caminho, encoding="utf-8") as fh:
        pauta = json.load(fh)
    mes = pauta["data"][:7]
    destino = os.path.join(pauta.get("pasta_pauta", DRIVE), f"{mes}-pauta.md")
    os.makedirs(os.path.dirname(destino), exist_ok=True)

    novo = not os.path.exists(destino)
    with open(destino, "a", encoding="utf-8") as fh:
        if novo:
            fh.write(f"# Pauta Instagram @aj_topogeo — {mes}\n")
        fh.write(bloco(pauta))
    print(("criado: " if novo else "acrescentado a: ") + destino)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python registrar.py pauta.json")
    main(sys.argv[1])
