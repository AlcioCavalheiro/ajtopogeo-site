#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotina 8 — Relatório geral de OS abertas e orçamentos.

Puxa do Supabase a ficha completa de cada OS em aberto (cliente, obra, valor,
andamento, responsável) e os orçamentos com status Enviado — aguardando
resposta do cliente. Ao contrário da rotina de cobrança (os_paradas.py),
aqui não há priorização nem narrativa — é o retrato completo do que está em
aberto, para consulta ou para o PDF de acompanhamento.

Uso:
    py rotinas/relatorio_geral.py                     # markdown no console
    py rotinas/relatorio_geral.py --json               # dados crus
    py rotinas/relatorio_geral.py --dossie <arquivo>    # grava JSON para o PDF

Lê SUPABASE_URL e SUPABASE_SERVICE_KEY de .env.local na raiz do projeto.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from os_paradas import (  # noqa: E402
    ETAPA_DE_STATUS, STATUS_ENCERRADOS, brl, buscar, buscar_ordens, carregar_env,
    dias_desde,
)

# Ordem de exibição das seções de status — mesma ordem de fluxo de
# ETAPA_DE_STATUS (os_paradas.py). Status fora do mapa vão para o fim.
_ORDEM_STATUS = list(ETAPA_DE_STATUS.keys())

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Status de orçamento que já viraram OS ou morreram — não entram como "em aberto".
ORCAMENTO_STATUS_ABERTOS = {"Enviado", "Rascunho"}


def historico_andamento(os_reg, limite=5):
    """Últimas entradas do histórico da OS, mais recente primeiro.

    O campo 'andamento' é jsonb: lista de {txt, data, hora, user}, com 'data'
    já em pt-BR (string), não ISO — formatado no próprio Gestor no momento
    do lançamento.
    """
    andamento = os_reg.get("andamento")
    if not isinstance(andamento, list) or not andamento:
        return []
    saida = []
    for item in reversed(andamento[-limite:]):
        if isinstance(item, dict):
            txt = item.get("txt") or item.get("texto") or item.get("descricao") or ""
            quando = " ".join(x for x in (item.get("data"), item.get("hora")) if x)
            usuario = item.get("user") or ""
            saida.append({"txt": txt[:300], "quando": quando, "usuario": usuario})
        else:
            saida.append({"txt": str(item)[:300], "quando": "", "usuario": ""})
    return saida


def montar_fichas_os(ordens, orcamentos_por_id, orcamentos_por_numero):
    abertas = [o for o in ordens if (o.get("status") or "") not in STATUS_ENCERRADOS]
    fichas = []
    for o in abertas:
        cliente = (o.get("clientes") or {}) or {}
        obra = (o.get("_obra") or {}) or {}
        valor_total = float(o.get("orcamento_valor") or 0)
        recebido = float(o.get("_recebido") or 0)

        orca_origem = None
        if o.get("orcamento_id"):
            orca_origem = orcamentos_por_id.get(o["orcamento_id"])
        elif o.get("orcamento_numero"):
            orca_origem = orcamentos_por_numero.get(o["orcamento_numero"])

        fichas.append({
            "numero": o.get("numero") or f"id:{o.get('id')}",
            "tipo": o.get("tipo") or "",
            "status": o.get("status") or "(sem status)",
            "cliente": cliente.get("nome") or "(sem cliente vinculado)",
            "telefone": cliente.get("telefone") or "",
            "email": cliente.get("email") or "",
            "obra": obra.get("nome") or "",
            "municipio": obra.get("municipio") or "",
            "valor_total": valor_total,
            "recebido": recebido,
            "previsto": float(o.get("_previsto") or 0),
            "valor_aberto": max(0.0, valor_total - recebido),
            "quitada": recebido > 0 and (valor_total - recebido) < 0.01,
            "dias_parada": dias_desde(o.get("atualizado_em") or o.get("created_at")) or 0,
            "responsavel": o.get("responsavel") or "",
            "obs": (o.get("obs") or "")[:400],
            "orcamento_numero": (orca_origem or {}).get("numero") or o.get("orcamento_numero") or "",
            "historico": historico_andamento(o),
        })
    fichas.sort(key=lambda f: (-f["dias_parada"]))
    return fichas


def agrupar_por_status(fichas):
    """Agrupa as fichas de OS por status, na ordem do fluxo técnico.

    Dentro de cada grupo mantém a ordem recebida (dias parada, decrescente).
    Status fora de ETAPA_DE_STATUS vão para o fim, ordenados por quantidade.
    """
    por_status = {}
    for f in fichas:
        por_status.setdefault(f["status"], []).append(f)

    conhecidos = [s for s in _ORDEM_STATUS if s in por_status]
    desconhecidos = sorted(
        (s for s in por_status if s not in _ORDEM_STATUS),
        key=lambda s: -len(por_status[s]),
    )
    return {status: por_status[status] for status in conhecidos + desconhecidos}


def montar_fichas_orcamentos(orcamentos, obras_por_id):
    fichas = []
    for orc in orcamentos:
        cliente = (orc.get("clientes") or {}) or {}
        obra = obras_por_id.get(orc.get("obra_id")) or {}
        status = orc.get("status") or "(sem status)"
        dias = dias_desde(orc.get("created_at")) or 0
        validade = orc.get("validade")
        vencido = False
        if validade and status == "Enviado":
            try:
                vencido = datetime.fromisoformat(str(validade)).date() < datetime.now().date()
            except ValueError:
                vencido = False
        fichas.append({
            "numero": orc.get("numero") or f"id:{orc.get('id')}",
            "status": status,
            "cliente": cliente.get("nome") or "(sem cliente vinculado)",
            "valor_total": float(orc.get("valor_total") or 0),
            "obra": obra.get("nome") or "",
            "municipio": obra.get("municipio") or "",
            "local_endereco": orc.get("local_endereco") or "",
            "data_emissao": (orc.get("created_at") or "")[:10],
            "dias_desde_envio": dias,
            "validade": validade or "",
            "vencido": vencido,
            "os_gerada": orc.get("os_gerada") or "",
        })
    fichas.sort(key=lambda f: -f["dias_desde_envio"])
    return fichas


def buscar_dados():
    """Traz as OS abertas e os orçamentos Enviados (aguardando resposta do cliente).

    Orçamentos Aprovados/Recusados/Finalizados não entram no relatório — só
    servem aqui para achar, por 'orcamento_id'/'orcamento_numero', de qual
    orçamento cada OS aberta se originou.
    """
    url, key = carregar_env()
    ordens, soltos = buscar_ordens(url, key)
    orcamentos = buscar(url, key, "orcamentos", "*,clientes(nome,telefone,email)",
                        order="created_at.desc")
    obras = buscar(url, key, "obras", "id,nome,municipio")
    obras_por_id = {o["id"]: o for o in obras}

    orcamentos_por_id = {o["id"]: o for o in orcamentos}
    orcamentos_por_numero = {o["numero"]: o for o in orcamentos if o.get("numero")}

    fichas_os = montar_fichas_os(ordens, orcamentos_por_id, orcamentos_por_numero)
    enviados = [o for o in orcamentos if (o.get("status") or "") == "Enviado"]
    fichas_orc = montar_fichas_orcamentos(enviados, obras_por_id)

    return fichas_os, fichas_orc, soltos


def montar_dossie(fichas_os, fichas_orc):
    return {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "resumo": {
            "os_abertas": len(fichas_os),
            "contratado": round(sum(f["valor_total"] for f in fichas_os), 2),
            "recebido": round(sum(f["recebido"] for f in fichas_os), 2),
            "em_aberto": round(sum(f["valor_aberto"] for f in fichas_os), 2),
            "orcamentos_enviados": len(fichas_orc),
            "valor_enviados": round(sum(f["valor_total"] for f in fichas_orc), 2),
        },
        "os_por_status": agrupar_por_status(fichas_os),
        "orcamentos_enviados": fichas_orc,
    }


def imprimir_markdown(fichas_os, fichas_orc):
    hoje = datetime.now().strftime("%d/%m/%Y")
    print(f"# Relatório geral — OS e orçamentos — {hoje}\n")
    print(f"- OS em aberto: **{len(fichas_os)}**")
    print(f"- Contratado: {brl(sum(f['valor_total'] for f in fichas_os))}")
    print(f"- Em aberto a cobrar: {brl(sum(f['valor_aberto'] for f in fichas_os))}\n")

    print("---\n## OS abertas, por status\n")
    for status, lista in agrupar_por_status(fichas_os).items():
        total_status = sum(f["valor_aberto"] for f in lista)
        print(f"### {status}  ({len(lista)} · {brl(total_status)} em aberto)\n")
        for f in lista:
            print(f"#### {f['numero']} — {f['cliente']}")
            print(f"{f['tipo']} · parada há {f['dias_parada']} dias")
            if f["obra"]:
                print(f"Obra: {f['obra']}" + (f" ({f['municipio']})" if f["municipio"] else ""))
            print(f"Contratado {brl(f['valor_total'])} · recebido {brl(f['recebido'])} "
                  f"· em aberto **{brl(f['valor_aberto'])}**" + (" (quitada)" if f["quitada"] else ""))
            if f["responsavel"]:
                print(f"Responsável: {f['responsavel']}")
            if f["orcamento_numero"]:
                print(f"Origem: orçamento {f['orcamento_numero']}")
            if f["historico"]:
                print("Andamento recente:")
                for h in f["historico"]:
                    print(f"  - {h['quando']} — {h['txt']}" + (f" ({h['usuario']})" if h["usuario"] else ""))
            if f["obs"]:
                print(f"Obs: {f['obs']}")
            print()

    total = sum(f["valor_total"] for f in fichas_orc)
    print(f"---\n## Orçamentos enviados ({len(fichas_orc)} · {brl(total)})\n")
    for f in fichas_orc:
        linha = (f"- {f['numero']} — {f['cliente']} — {brl(f['valor_total'])} "
                 f"— enviado há {f['dias_desde_envio']} dias")
        if f["vencido"]:
            linha += " — **VENCIDO**"
        print(linha)


def main():
    ap = argparse.ArgumentParser(description="Relatório geral de OS abertas e orçamentos.")
    ap.add_argument("--json", action="store_true", help="imprime JSON em vez de Markdown")
    ap.add_argument("--dossie", metavar="ARQUIVO", help="grava o dossiê completo em JSON, para o PDF")
    args = ap.parse_args()

    fichas_os, fichas_orc, _soltos = buscar_dados()

    if args.dossie:
        destino = Path(args.dossie)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(montar_dossie(fichas_os, fichas_orc), ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"Dossiê gravado em: {destino}")
        print("Renderize com: py rotinas/relatorio_geral_pdf.py <dossie.json> <saida.pdf>")
        return

    if args.json:
        print(json.dumps(montar_dossie(fichas_os, fichas_orc), ensure_ascii=False, indent=2))
    else:
        imprimir_markdown(fichas_os, fichas_orc)


if __name__ == "__main__":
    main()
