#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotina 1 — Cobrança das OS paradas.

Puxa as ordens de serviço em aberto do Supabase, calcula um score de prioridade
(valor alto + tempo parado + proximidade de conclusão técnica) e imprime um
relatório em Markdown pronto para triagem.

Uso:
    py rotinas/os_paradas.py                # top 10 (padrão)
    py rotinas/os_paradas.py --top 20
    py rotinas/os_paradas.py --json         # saída bruta para pós-processamento
    py rotinas/os_paradas.py --min-dias 15  # só o que está parado há 15+ dias

Lê SUPABASE_URL e SUPABASE_SERVICE_KEY de .env.local na raiz do projeto.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta a lib requests. Rode: py -m pip install requests")

# O console do Windows abre em cp1252 e quebra os acentos do relatório.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parent.parent

# Status que significam "encerrada" — tudo que não estiver aqui conta como em aberto.
STATUS_ENCERRADOS = {
    "Recebido", "Concluída", "Concluida", "Cancelada", "Cancelado",
}

# Ordem do fluxo técnico. Quanto maior, mais perto de terminar/faturar.
ETAPA_DE_STATUS = {
    "Agendada": 1, "Logística / Preparação": 1,
    "Em campo": 2, "Em andamento": 2,
    "Processamento": 3, "Desenho": 3, "Revisão Técnica": 3,
    "Análise Jurídica": 4, "Pronto para Protocolo": 4, "Protocolada": 4,
    "Encaminhada para Medição": 5, "Medição Realizada": 5, "NF Gerada": 5,
    "Pronto para Enviar ao Cliente": 5, "Documentos Enviados ao Cliente": 5,
}
ETAPA_MAX = 5

# Hipótese de travamento por status. É ponto de partida para o rascunho,
# não verdade absoluta — confirmar no histórico da OS antes de cobrar.
MOTIVO_PROVAVEL = {
    "Agendada": "Nunca saiu para campo — falta agendar equipe ou confirmar acesso à área com o cliente.",
    "Logística / Preparação": "Preparação travada — pendência de logística, equipamento ou confirmação de data.",
    "Em campo": "Campo iniciado e não fechado — verificar se falta retorno à área ou dado bruto.",
    "Em andamento": "Execução em curso sem movimentação — checar se está parada por dependência externa.",
    "Processamento": "Dado bruto aguardando processamento interno.",
    "Desenho": "Aguardando desenho/CAD interno.",
    "Revisão Técnica": "Parada em revisão interna — depende de você liberar.",
    "Análise Jurídica": "Aguardando documento do cliente (matrícula, CCIR, CAR, procuração) ou parecer jurídico.",
    "Pronto para Protocolo": "Pronta e não protocolada — normalmente falta documento ou assinatura do cliente.",
    "Protocolada": "No órgão (INCRA/cartório/prefeitura) — verificar exigência em aberto.",
    "Encaminhada para Medição": "Serviço entregue, medição não fechada — receita travada aqui.",
    "Medição Realizada": "Medição fechada e NF não emitida — faturamento pendente.",
    "NF Gerada": "NF emitida e não recebida — cobrança financeira direta.",
    "Pronto para Enviar ao Cliente": "Produto pronto e não entregue ao cliente.",
    "Documentos Enviados ao Cliente": "Entregue — confirmar recebimento e liberar faturamento.",
}

# Peso de cada componente do score.
PESO_VALOR, PESO_PARADO, PESO_PROXIMIDADE = 0.40, 0.35, 0.25


def carregar_env():
    """Lê .env.local e devolve (url, service_key)."""
    env = RAIZ / ".env.local"
    if not env.exists():
        sys.exit(
            f"Não encontrei {env}\n"
            f"Copie .env.local.exemplo para .env.local e preencha a service_role key."
        )
    dados = {}
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        dados[chave.strip()] = valor.strip().strip('"').strip("'")

    url = dados.get("SUPABASE_URL", "").rstrip("/")
    key = dados.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key or key.startswith("cole_a"):
        sys.exit("SUPABASE_URL ou SUPABASE_SERVICE_KEY não preenchidos em .env.local")
    return url, key


def buscar_ordens(url, key):
    endpoint = f"{url}/rest/v1/ordens"
    params = {
        "select": "*,clientes(nome,telefone,email),obras(nome,municipio)",
        "order": "created_at.asc",
    }
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = requests.get(endpoint, params=params, headers=headers, timeout=60)
    if r.status_code != 200:
        sys.exit(f"Supabase retornou HTTP {r.status_code}: {r.text[:400]}")
    return r.json()


def dias_desde(iso):
    if not iso:
        return None
    texto = str(iso).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def ultimo_andamento(os_reg):
    """Texto da última entrada do histórico de andamento, se houver."""
    andamento = os_reg.get("andamento")
    if isinstance(andamento, list) and andamento:
        ultimo = andamento[-1]
        if isinstance(ultimo, dict):
            return (ultimo.get("txt") or ultimo.get("texto") or
                    ultimo.get("descricao") or json.dumps(ultimo, ensure_ascii=False))[:200]
        return str(ultimo)[:200]
    return None


def analisar(ordens, min_dias=0):
    abertas = [o for o in ordens if (o.get("status") or "") not in STATUS_ENCERRADOS]

    enriquecidas = []
    for o in abertas:
        parado = dias_desde(o.get("atualizado_em") or o.get("created_at")) or 0
        if parado < min_dias:
            continue
        cliente = (o.get("clientes") or {}) or {}
        obra = (o.get("obras") or {}) or {}
        status = o.get("status") or "(sem status)"
        enriquecidas.append({
            "numero": o.get("numero") or f"id:{o.get('id')}",
            "tipo": o.get("tipo") or "",
            "status": status,
            "cliente": cliente.get("nome") or "(sem cliente vinculado)",
            "telefone": cliente.get("telefone") or "",
            "email": cliente.get("email") or "",
            "obra": obra.get("nome") or "",
            "municipio": obra.get("municipio") or "",
            "valor": float(o.get("orcamento_valor") or 0),
            "dias_parada": parado,
            "etapa": ETAPA_DE_STATUS.get(status, 1),
            "responsavel": o.get("responsavel") or "",
            "motivo_provavel": MOTIVO_PROVAVEL.get(status, "Status fora do fluxo padrão — investigar manualmente."),
            "ultimo_andamento": ultimo_andamento(o),
            "obs": (o.get("obs") or "")[:300],
        })

    if not enriquecidas:
        return []

    max_valor = max((e["valor"] for e in enriquecidas), default=0) or 1
    max_dias = max((e["dias_parada"] for e in enriquecidas), default=0) or 1

    for e in enriquecidas:
        n_valor = e["valor"] / max_valor
        n_dias = e["dias_parada"] / max_dias
        n_prox = e["etapa"] / ETAPA_MAX
        e["score"] = round(
            100 * (PESO_VALOR * n_valor + PESO_PARADO * n_dias + PESO_PROXIMIDADE * n_prox), 1
        )

    enriquecidas.sort(key=lambda e: e["score"], reverse=True)
    return enriquecidas


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def imprimir_markdown(lista, top, total_abertas):
    hoje = datetime.now().strftime("%d/%m/%Y")
    recorte = lista[:top]
    travado = sum(e["valor"] for e in recorte)
    travado_geral = sum(e["valor"] for e in lista)

    print(f"# OS paradas — {hoje}\n")
    print(f"- OS em aberto analisadas: **{total_abertas}**")
    print(f"- Valor total em aberto: **{brl(travado_geral)}**")
    print(f"- Nas {len(recorte)} prioritárias abaixo: **{brl(travado)}**\n")
    print("---\n")

    for i, e in enumerate(recorte, 1):
        print(f"## {i}. {e['numero']} — {e['cliente']}  ·  score {e['score']}")
        linha = f"**{brl(e['valor'])}** · parada há **{e['dias_parada']} dias** · status: **{e['status']}**"
        print(linha)
        detalhe = []
        if e["tipo"]:
            detalhe.append(e["tipo"])
        if e["obra"]:
            detalhe.append(f"obra: {e['obra']}" + (f" ({e['municipio']})" if e["municipio"] else ""))
        if e["responsavel"]:
            detalhe.append(f"resp: {e['responsavel']}")
        if detalhe:
            print(" · ".join(detalhe))
        contato = " · ".join(x for x in (e["telefone"], e["email"]) if x)
        print(f"\n- **Motivo provável:** {e['motivo_provavel']}")
        if e["ultimo_andamento"]:
            print(f"- **Último andamento:** {e['ultimo_andamento']}")
        if e["obs"]:
            print(f"- **Obs da OS:** {e['obs']}")
        print(f"- **Contato:** {contato or '— sem contato cadastrado —'}")
        print()

    if len(lista) > top:
        resto = lista[top:]
        print("---\n")
        print(f"### Fila restante ({len(resto)} OS · {brl(sum(e['valor'] for e in resto))})\n")
        print("| OS | Cliente | Valor | Dias | Status |")
        print("|---|---|---|---|---|")
        for e in resto:
            print(f"| {e['numero']} | {e['cliente']} | {brl(e['valor'])} | {e['dias_parada']} | {e['status']} |")


def main():
    ap = argparse.ArgumentParser(description="Lista as OS paradas por prioridade de cobrança.")
    ap.add_argument("--top", type=int, default=10, help="quantas OS detalhar (padrão 10)")
    ap.add_argument("--min-dias", type=int, default=0, help="ignorar OS paradas há menos de N dias")
    ap.add_argument("--json", action="store_true", help="imprime JSON em vez de Markdown")
    args = ap.parse_args()

    url, key = carregar_env()
    ordens = buscar_ordens(url, key)
    lista = analisar(ordens, min_dias=args.min_dias)

    if not lista:
        print("Nenhuma OS em aberto no filtro atual.")
        return

    total_abertas = len([o for o in ordens if (o.get("status") or "") not in STATUS_ENCERRADOS])

    if args.json:
        print(json.dumps(lista[:args.top], ensure_ascii=False, indent=2))
    else:
        imprimir_markdown(lista, args.top, total_abertas)


if __name__ == "__main__":
    main()
