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
    # Trava que pode cair em qualquer ponto do fluxo — peso neutro de meio.
    "Pendência Documental": 3,
    "Análise Jurídica": 4, "Pronto para Protocolo": 4, "Protocolada": 4,
    "Encaminhada para Medição": 5, "Medição Realizada": 5, "Fechar Medição": 5,
    "Gerar NF": 5, "NF Gerada": 5, "Falta Pagamento": 5,
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
    "Pendência Documental": "Aguardando documento do cliente (matrícula, CCIR, CAR, ITR, procuração, CNH). Confira no andamento QUAL documento falta antes de cobrar.",
    "Análise Jurídica": "Aguardando documento do cliente (matrícula, CCIR, CAR, procuração) ou parecer jurídico.",
    "Pronto para Protocolo": "Pronta e não protocolada — normalmente falta documento ou assinatura do cliente.",
    "Protocolada": "No órgão (INCRA/cartório/prefeitura) — verificar exigência em aberto.",
    "Encaminhada para Medição": "Serviço entregue, medição não fechada — receita travada aqui.",
    "Medição Realizada": "Medição fechada e NF não emitida — faturamento pendente.",
    "Fechar Medição": "Medição aberta aguardando fechamento — passo interno antes de faturar.",
    "Gerar NF": "Medição fechada aguardando emissão da NF.",
    "NF Gerada": "NF emitida e não recebida — cobrança financeira direta.",
    "Falta Pagamento": "NF emitida e vencida sem pagamento — cobrança financeira direta.",
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


def buscar(url, key, tabela, select, **extra):
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    params = {"select": select, **extra}
    r = requests.get(f"{url}/rest/v1/{tabela}", params=params, headers=headers, timeout=60)
    if r.status_code != 200:
        sys.exit(f"Supabase retornou HTTP {r.status_code} em '{tabela}': {r.text[:400]}")
    return r.json()


def buscar_ordens(url, key):
    """Traz as ordens com cliente, obra e o quanto já foi recebido de cada uma.

    Não existe FK entre ordens e obras no schema, então o embed do PostgREST
    falha com PGRST200 — a união é feita por obra_id aqui.

    Recebimentos só são somados quando têm os_id preenchido. Os que estão
    soltos (ligados por texto livre em 'descricao') NÃO são adivinhados: uma
    descrição com só o nome do cliente pode se referir a qualquer uma das OS
    dele, e há clientes com várias OS de valor idêntico. Casar por semelhança
    faria cobrar quem já pagou. Eles voltam separados, para conciliação manual.
    """
    ordens = buscar(url, key, "ordens",
                    "*,clientes(nome,telefone,email)", order="created_at.asc")
    obras = buscar(url, key, "obras", "id,nome,municipio")
    recebimentos = buscar(url, key, "recebimentos",
                          "id,os_id,valor,status,data_recebimento,descricao,vencimento")

    por_obra = {o["id"]: o for o in obras}

    recebido_por_os, previsto_por_os = {}, {}
    soltos = []
    for r in recebimentos:
        valor = float(r.get("valor") or 0)
        alvo = r.get("os_id")
        if not alvo:
            soltos.append(r)
            continue
        if (r.get("status") or "") == "Recebido":
            recebido_por_os[alvo] = recebido_por_os.get(alvo, 0.0) + valor
        else:
            previsto_por_os[alvo] = previsto_por_os.get(alvo, 0.0) + valor

    for os_reg in ordens:
        oid = os_reg.get("id")
        os_reg["_obra"] = por_obra.get(os_reg.get("obra_id")) or {}
        os_reg["_recebido"] = recebido_por_os.get(oid, 0.0)
        os_reg["_previsto"] = previsto_por_os.get(oid, 0.0)

    return ordens, soltos


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
        obra = (o.get("_obra") or {}) or {}
        status = o.get("status") or "(sem status)"
        valor_total = float(o.get("orcamento_valor") or 0)
        recebido = float(o.get("_recebido") or 0)
        enriquecidas.append({
            "numero": o.get("numero") or f"id:{o.get('id')}",
            "tipo": o.get("tipo") or "",
            "status": status,
            "cliente": cliente.get("nome") or "(sem cliente vinculado)",
            "telefone": cliente.get("telefone") or "",
            "email": cliente.get("email") or "",
            "obra": obra.get("nome") or "",
            "municipio": obra.get("municipio") or "",
            "valor_total": valor_total,
            "recebido": recebido,
            "previsto": float(o.get("_previsto") or 0),
            # O que ainda dá para cobrar. É este que manda no ranking:
            # OS quitada com pendência só técnica não é caso de cobrança.
            "valor": max(0.0, valor_total - recebido),
            "quitada": recebido > 0 and (valor_total - recebido) < 0.01,
            "dias_parada": parado,
            "etapa": ETAPA_DE_STATUS.get(status, 3),
            "status_mapeado": status in ETAPA_DE_STATUS,
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


def imprimir_markdown(lista, top, total_abertas, soltos=None):
    hoje = datetime.now().strftime("%d/%m/%Y")
    recorte = lista[:top]
    travado = sum(e["valor"] for e in recorte)
    travado_geral = sum(e["valor"] for e in lista)
    contratado = sum(e["valor_total"] for e in lista)
    recebido_geral = sum(e["recebido"] for e in lista)
    quitadas = [e for e in lista if e["quitada"]]

    print(f"# OS paradas — {hoje}\n")
    print(f"- OS em aberto: **{total_abertas}**")
    print(f"- Valor contratado: {brl(contratado)}")
    print(f"- Já recebido (vinculado): {brl(recebido_geral)}")
    print(f"- **Em aberto a cobrar: {brl(travado_geral)}**")
    if quitadas:
        print(f"- OS já quitadas com pendência apenas técnica: **{len(quitadas)}** "
              f"(não são cobrança)")
    print(f"- Nas {len(recorte)} prioritárias abaixo: **{brl(travado)}**\n")

    # Status novo no Gestor que ainda não está nos mapas deste script cai num
    # motivo genérico e numa etapa neutra — avisar em vez de mascarar.
    desconhecidos = sorted({e["status"] for e in lista if not e["status_mapeado"]})
    if desconhecidos:
        print(f"> ⚠ Status sem mapeamento (motivo e etapa são chutes): "
              f"{', '.join(desconhecidos)}. Atualize ETAPA_DE_STATUS e "
              f"MOTIVO_PROVAVEL em rotinas/os_paradas.py.\n")

    print("---\n")

    for i, e in enumerate(recorte, 1):
        print(f"## {i}. {e['numero']} — {e['cliente']}  ·  score {e['score']}")
        linha = (f"**{brl(e['valor'])} em aberto** · parada há "
                 f"**{e['dias_parada']} dias** · status: **{e['status']}**")
        if e["recebido"]:
            linha += (f"\ncontratado {brl(e['valor_total'])} · "
                      f"já recebido {brl(e['recebido'])}")
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

    print("---\n")
    print(f"## Todas as OS em aberto ({len(lista)})\n")
    print("| # | OS | Cliente | Contratado | Recebido | Em aberto | Dias | Status |")
    print("|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(lista, 1):
        marca = " ✓quitada" if e["quitada"] else ""
        print(f"| {i} | {e['numero']} | {e['cliente'][:28]} | {brl(e['valor_total'])} "
              f"| {brl(e['recebido'])} | **{brl(e['valor'])}**{marca} "
              f"| {e['dias_parada']} | {e['status']} |")

    if soltos:
        recs = [r for r in soltos if (r.get("status") or "") == "Recebido"]
        total = sum(float(r.get("valor") or 0) for r in recs)
        print("\n---\n")
        print(f"## ⚠ Recebimentos sem OS vinculada ({len(recs)} · {brl(total)})\n")
        print("Não foram descontados de nenhuma OS porque não têm `os_id`. "
              "Se algum destes corresponder a uma OS da lista acima, o valor "
              "**em aberto** dela está superestimado — concilie antes de cobrar.\n")
        print("| Descrição | Valor | Data |")
        print("|---|---|---|")
        for r in sorted(recs, key=lambda x: -float(x.get("valor") or 0)):
            print(f"| {r.get('descricao') or '—'} | {brl(r.get('valor') or 0)} "
                  f"| {r.get('data_recebimento') or '—'} |")


def montar_dossie_base(lista, soltos):
    """Parte factual do dossiê do PDF: números, lista completa e não conciliados.

    A narrativa (cobrancas, internas, observacoes, proxima_semana) é escrita
    por cima disto a cada semana — ver .claude/skills/cobranca-os.
    """
    recs = [r for r in soltos if (r.get("status") or "") == "Recebido"]
    return {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "resumo": {
            "os_abertas": len(lista),
            "contratado": round(sum(e["valor_total"] for e in lista), 2),
            "recebido": round(sum(e["recebido"] for e in lista), 2),
            "em_aberto": round(sum(e["valor"] for e in lista), 2),
        },
        "todas_os": [{
            "numero": e["numero"],
            "cliente": e["cliente"],
            "contratado": e["valor_total"],
            "recebido": e["recebido"],
            "em_aberto": e["valor"],
            "quitada": e["quitada"],
            "dias": e["dias_parada"],
            "status": e["status"],
        } for e in lista],
        "recebimentos_sem_os": [{
            "descricao": r.get("descricao") or "—",
            "valor": float(r.get("valor") or 0),
            "data": r.get("data_recebimento") or "—",
        } for r in sorted(recs, key=lambda x: -float(x.get("valor") or 0))],
        "cobrancas": [],
        "internas": [],
        "observacoes": [],
        "proxima_semana": [],
    }


def main():
    ap = argparse.ArgumentParser(description="Lista as OS paradas por prioridade de cobrança.")
    ap.add_argument("--top", type=int, default=10, help="quantas OS detalhar (padrão 10)")
    ap.add_argument("--min-dias", type=int, default=0, help="ignorar OS paradas há menos de N dias")
    ap.add_argument("--json", action="store_true", help="imprime JSON em vez de Markdown")
    ap.add_argument("--dossie", metavar="ARQUIVO",
                    help="grava a base factual do dossiê do PDF neste caminho")
    args = ap.parse_args()

    url, key = carregar_env()
    ordens, soltos = buscar_ordens(url, key)
    lista = analisar(ordens, min_dias=args.min_dias)

    if not lista:
        print("Nenhuma OS em aberto no filtro atual.")
        return

    total_abertas = len([o for o in ordens if (o.get("status") or "") not in STATUS_ENCERRADOS])

    if args.dossie:
        destino = Path(args.dossie)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(montar_dossie_base(lista, soltos), ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"Base do dossiê gravada em: {destino}")
        print("Preencha cobrancas / internas / observacoes / proxima_semana "
              "e renderize com rotinas/relatorio_pdf.py")
        return

    if args.json:
        print(json.dumps({"os": lista, "recebimentos_sem_os": soltos},
                         ensure_ascii=False, indent=2))
    else:
        imprimir_markdown(lista, args.top, total_abertas, soltos)


if __name__ == "__main__":
    main()
