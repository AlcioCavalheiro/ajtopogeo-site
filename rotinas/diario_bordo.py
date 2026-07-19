#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotina 3 — Diário de bordo → OS.

Lê o diário de bordo de um dia de campo (texto), resolve a OS correspondente e
lança no Gestor: um registro de andamento, os custos de equipe (custos_os) e as
despesas do dia (pagamentos).

Uso:
    py rotinas/diario_bordo.py diario.txt                    # prévia, não grava
    py rotinas/diario_bordo.py diario.txt --os OS-JUL-009    # força a OS
    py rotinas/diario_bordo.py diario.txt --aplicar          # grava
    py rotinas/diario_bordo.py diario.txt --aplicar \\
        --reembolso 110,00 --reembolso-desc "Ajudante pago pela conta pessoal"

Lê SUPABASE_URL e SUPABASE_SERVICE_KEY de .env.local na raiz do projeto.
"""

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta a lib requests. Rode: py -m pip install requests")

# O console do Windows abre em cp1252 e quebra os acentos da prévia.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parent.parent

# Rótulos do diário, em forma normalizada (sem acento, minúsculo, sem emoji).
CAMPOS = {
    "data": ("data", "diario de bordo"),
    "local": ("local", "municipio", "cidade"),
    "cliente": ("cliente",),
    "os": ("os", "ordem de servico", "o.s."),
    "chegada": ("hora chegada", "chegada", "hora de chegada", "inicio"),
    "saida": ("hora saida", "saida", "hora de saida", "termino", "fim"),
    "servicos": ("servicos realizados", "servicos", "servico realizado",
                 "atividades", "atividades realizadas"),
    "pendencias": ("pendencias", "pendencia"),
    "gastos": ("gastos do dia", "gastos", "despesas", "despesas do dia"),
    "obs": ("observacoes", "observacao", "obs"),
}

# Para onde vai cada gasto. "equipe" cai em custos_os (Custo de Equipe da OS);
# o resto vira despesa em pagamentos, na categoria correspondente do Gestor.
DESTINO_GASTO = [
    ("equipe", "Diária", ("ajudante", "diarista", "auxiliar", "mao de obra",
                          "maodeobra", "peao", "braçal", "bracal", "equipe")),
    ("pagamento", "Combustível", ("combustivel", "gasolina", "diesel", "etanol",
                                  "posto", "abastecimento", "arla")),
    ("pagamento", "Alimentação", ("alimentacao", "almoco", "janta", "jantar",
                                  "refeicao", "lanche", "cafe", "comida",
                                  "marmita", "agua")),
    ("pagamento", "Equipamentos", ("equipamento", "bateria", "estaca", "piquete",
                                   "marco", "tinta", "material")),
    ("pagamento", "Infraestrutura", ("hospedagem", "hotel", "pousada", "diaria hotel")),
    ("pagamento", "Outros", ("pedagio", "balsa", "manutencao", "borracharia",
                             "pneu", "lavagem", "frete", "correio", "cartorio",
                             "taxa", "estacionamento")),
]

# Linhas de gasto que são fechamento de conta, não lançamento.
LINHAS_TOTAL = ("total", "soma", "somatorio", "total do dia", "total geral")


def normalizar(texto):
    """Minúsculo, sem acento e sem os invisíveis que vêm colados do WhatsApp."""
    texto = "".join(c for c in texto if unicodedata.category(c) not in ("Cf", "So", "Sk"))
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.strip().lower()


def limpar(texto):
    """Tira emoji, bullets e espaço sobrando, preservando acento e caixa."""
    texto = "".join(c for c in texto if unicodedata.category(c) not in ("Cf", "So", "Sk"))
    texto = texto.lstrip("*-–—•·>  \t")
    return re.sub(r"\s+", " ", texto).strip()


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


def cabecalho(key):
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"}


def buscar(url, key, tabela, select, **extra):
    params = {"select": select, **extra}
    r = requests.get(f"{url}/rest/v1/{tabela}", params=params,
                     headers=cabecalho(key), timeout=60)
    if r.status_code != 200:
        sys.exit(f"Supabase retornou HTTP {r.status_code} em '{tabela}': {r.text[:400]}")
    return r.json()


def inserir(url, key, tabela, payload):
    r = requests.post(f"{url}/rest/v1/{tabela}", json=payload,
                      headers={**cabecalho(key), "Prefer": "return=representation"},
                      timeout=60)
    if r.status_code not in (200, 201):
        sys.exit(f"Falha ao inserir em '{tabela}': HTTP {r.status_code} — {r.text[:400]}")
    return r.json()


def atualizar(url, key, tabela, payload, **filtro):
    r = requests.patch(f"{url}/rest/v1/{tabela}", json=payload, params=filtro,
                       headers={**cabecalho(key), "Prefer": "return=representation"},
                       timeout=60)
    if r.status_code not in (200, 204):
        sys.exit(f"Falha ao atualizar '{tabela}': HTTP {r.status_code} — {r.text[:400]}")
    return r.json() if r.text else []


# ─────────────────────────── leitura do diário ───────────────────────────

def ler_diario(texto):
    """Quebra o diário em campos. Cada rótulo abre uma seção até o próximo.

    O formato vem do WhatsApp e varia: o valor pode estar na mesma linha do
    rótulo ou nos bullets abaixo dele. As duas formas são aceitas.
    """
    campos = {k: [] for k in CAMPOS}
    atual = None

    for linha_bruta in texto.splitlines():
        linha = limpar(linha_bruta)
        if not linha:
            continue

        rotulo, tem_dois_pontos, resto = linha.partition(":")
        if tem_dois_pontos and len(rotulo) <= 40:
            # "Local:", "Hora chegada: 07H40" — rótulo aberto por dois-pontos.
            chave = achar_campo(rotulo)
        else:
            # Sem dois-pontos só vale rótulo isolado ("Local" numa linha só) ou
            # o título com a data. Match por prefixo aqui engoliria bullets de
            # conteúdo: "OS 12" e "Os pagamentos foram feitos..." começam com
            # "os" e viravam seção nova, esvaziando o campo.
            chave = achar_campo(linha, exato=True)

        if chave:
            atual = chave
            resto = limpar(resto)
            # "Diário de Bordo – Data - 16/07/2026" traz a data no próprio título.
            if chave == "data" and not resto:
                resto = limpar(rotulo)
            if resto:
                campos[chave].append(resto)
            continue

        if atual:
            campos[atual].append(linha)

    return campos


def achar_campo(rotulo, exato=False):
    alvo = normalizar(rotulo).rstrip(" -–—")
    for chave, apelidos in CAMPOS.items():
        for apelido in apelidos:
            if alvo == apelido:
                return chave
            if exato:
                continue
            if alvo.startswith(apelido + " ") or alvo.startswith(apelido + "-"):
                return chave
    # O título do diário abre a seção de data mesmo sem dois-pontos.
    if alvo.startswith("diario de bordo"):
        return "data"
    return None


def achar_data(valores):
    """Primeira data dd/mm/aaaa encontrada, devolvida como ISO."""
    for v in valores:
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", v)
        if m:
            d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if a < 100:
                a += 2000
            try:
                return datetime(a, mes, d).date().isoformat()
            except ValueError:
                return None
    return None


def achar_hora(valores):
    for v in valores:
        m = re.search(r"(\d{1,2})\s*[hH:]\s*(\d{2})?", v)
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return None


def ler_valor(texto):
    """Extrai o valor em reais de 'combustível - R$ 70,00'."""
    m = re.search(r"R?\$?\s*([\d][\d.\s]*,\d{2}|\d[\d.\s]*)\b", texto)
    if not m:
        return None
    bruto = m.group(1).replace(" ", "")
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    elif bruto.count(".") == 1 and len(bruto.split(".")[1]) == 3:
        bruto = bruto.replace(".", "")  # 1.200 é mil e duzentos, não 1,2
    try:
        return round(float(bruto), 2)
    except ValueError:
        return None


def classificar_gasto(descricao):
    alvo = normalizar(descricao)
    for destino, categoria, chaves in DESTINO_GASTO:
        if any(c in alvo for c in chaves):
            return destino, categoria, True
    return "pagamento", "Outros", False


def ler_gastos(linhas):
    """Devolve (lançamentos, total_declarado)."""
    itens, declarado = [], None
    for linha in linhas:
        if not linha:
            continue
        rotulo = normalizar(linha.split(":")[0].split("-")[0])
        if any(rotulo.startswith(t) for t in LINHAS_TOTAL):
            declarado = ler_valor(linha)
            continue
        valor = ler_valor(linha)
        if valor is None:
            continue
        # Descrição é tudo antes do valor, sem o separador solto no fim.
        desc = re.split(r"[-–—:]?\s*R?\$", linha)[0]
        desc = limpar(desc).rstrip(" -–—:") or linha
        desc = desc[:1].upper() + desc[1:]  # "combustível" vira "Combustível" na lista
        destino, categoria, certeza = classificar_gasto(desc)
        itens.append({"descricao": desc, "valor": valor, "destino": destino,
                      "categoria": categoria, "categoria_certa": certeza})
    return itens, declarado


# ─────────────────────────── resolução da OS ───────────────────────────

def so_alfanumerico(texto):
    return re.sub(r"[^a-z0-9]", "", normalizar(texto or ""))


def resolver_os(ordens, referencia, cliente):
    """Acha a OS do diário. Devolve (os, candidatas, motivo).

    O diário é escrito em campo e traz o número curto ("OS01"), enquanto o
    Gestor usa "OS-JUL-009". Match frouxo por dígito casa OS de meses
    diferentes — por isso, sem correspondência exata, esta função devolve
    candidatas para o usuário escolher em vez de decidir sozinha.
    """
    ref = so_alfanumerico(referencia)
    if ref:
        exatas = [o for o in ordens if so_alfanumerico(o.get("numero")) == ref]
        if len(exatas) == 1:
            return exatas[0], [], "número exato"

    alvo_cliente = normalizar(cliente or "")
    por_cliente = []
    if alvo_cliente:
        primeiro = alvo_cliente.split()[0] if alvo_cliente.split() else ""
        for o in ordens:
            nome = normalizar((o.get("clientes") or {}).get("nome") or "")
            if not nome:
                continue
            if alvo_cliente in nome or (primeiro and len(primeiro) >= 4 and primeiro in nome):
                por_cliente.append(o)

    if len(por_cliente) == 1:
        return por_cliente[0], [], "único do cliente"

    if por_cliente:
        return None, por_cliente, "várias OS deste cliente"
    return None, ordens, "nenhuma OS bate com o cliente do diário"


# ─────────────────────────── montagem dos lançamentos ───────────────────────────

def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def marca_diario(data_iso):
    """Assinatura que identifica o andamento deste diário — trava a duplicata."""
    return f"[diário {datetime.fromisoformat(data_iso).strftime('%d/%m/%Y')}]"


def bloco(titulo, itens):
    """Um item vira linha única; vários viram lista. Espelha o diário.

    O andamento é o que se lê meses depois para justificar prazo com cliente e
    para fechar medição — achatar três serviços num parágrafo só perde qual foi
    feito em qual dia.
    """
    itens = [i for i in itens if i]
    if not itens:
        return []
    if len(itens) == 1:
        return [f"{titulo}: {itens[0]}"]
    return [f"{titulo}:"] + [f"• {i}" for i in itens]


def montar_andamento(campos, data_iso, gastos, total):
    partes = []
    local = " / ".join(campos["local"]) if campos["local"] else ""
    chegada, saida = achar_hora(campos["chegada"]), achar_hora(campos["saida"])
    if local:
        partes.append(f"Campo em {local}")
    if chegada and saida:
        partes.append(f"{chegada} às {saida}")
    elif chegada or saida:
        partes.append(f"chegada {chegada}" if chegada else f"saída {saida}")

    linhas = [" · ".join([marca_diario(data_iso)] + partes)]
    linhas += bloco("Serviços realizados", campos["servicos"])
    linhas += bloco("Pendências", campos["pendencias"])
    if gastos:
        detalhe = "; ".join(f"{g['descricao']} {brl(g['valor'])}" for g in gastos)
        linhas.append(f"Gastos do dia: {brl(total)} — {detalhe}")
    linhas += bloco("Observações", campos["obs"])
    return "\n".join(linhas)


def montar_lancamentos(os_reg, data_iso, gastos, args):
    numero = os_reg.get("numero") or ""
    ref = f"{numero} · {datetime.fromisoformat(data_iso).strftime('%d/%m/%Y')}"
    custos, pagamentos = [], []

    for g in gastos:
        if g["destino"] == "equipe":
            custos.append({
                "os_id": os_reg["id"], "func_id": None,
                "tipo_custo": g["categoria"], "quantidade": 1,
                "valor_unit": g["valor"], "valor_total": g["valor"],
                "data": data_iso,
                "obs": f"{g['descricao']} — diário de bordo {ref}",
            })
        else:
            pagamentos.append({
                "descricao": f"{g['descricao']} — {ref}",
                "categoria": g["categoria"], "valor": g["valor"],
                "vencimento": data_iso, "data_pagamento": data_iso,
                "status": "Pago", "tipo_custo": "OS",
                "os_id": os_reg["id"], "os_manual": numero,
                "obs": f"Lançado do diário de bordo de {ref}",
            })

    if args.reembolso:
        valor = ler_valor(args.reembolso)
        if valor is None:
            sys.exit(f"Não entendi o valor do reembolso: {args.reembolso!r}")
        desc = args.reembolso_desc or "Gastos de campo pagos pela conta pessoal"
        pagamentos.append({
            "descricao": f"Reembolso — {desc} — {ref}",
            "categoria": "Pessoal", "valor": valor,
            "vencimento": data_iso, "data_pagamento": None,
            "status": "Pendente", "tipo_custo": "OS",
            "os_id": os_reg["id"], "os_manual": numero,
            "obs": f"Reembolso ao sócio — diário de bordo {ref}. "
                   f"Não é custo novo da OS: o gasto já está lançado à parte.",
            "_reembolso": True,
        })

    return custos, pagamentos


def checar_duplicata(url, key, os_reg, data_iso):
    """Avisa o que já existe nesta OS nesta data. Relançar dobra o custo."""
    achados = []
    marca = marca_diario(data_iso)
    for item in (os_reg.get("andamento") or []):
        txt = item.get("txt") if isinstance(item, dict) else str(item)
        if txt and marca in txt:
            achados.append(f"andamento já registrado com a marca {marca}")
            break
    custos = buscar(url, key, "custos_os", "id,valor_total,obs",
                    os_id=f"eq.{os_reg['id']}", data=f"eq.{data_iso}")
    if custos:
        achados.append(f"{len(custos)} custo(s) de equipe já lançado(s) em {data_iso}")
    pags = buscar(url, key, "pagamentos", "id,descricao,valor",
                  os_id=f"eq.{os_reg['id']}", vencimento=f"eq.{data_iso}")
    if pags:
        achados.append(f"{len(pags)} despesa(s) já lançada(s) em {data_iso}")
    return achados


# ─────────────────────────── saída ───────────────────────────

def imprimir_previa(os_reg, campos, data_iso, gastos, total, declarado,
                    custos, pagamentos, texto_andamento, duplicatas, motivo, args):
    cliente = (os_reg.get("clientes") or {}).get("nome") or "—"
    print(f"# Diário de bordo → {os_reg.get('numero')} — {cliente}\n")

    if motivo != "número exato":
        print(f"> ⛔ **OS identificada por {motivo}, não pelo número.** O diário "
              f"traz `{campos['os'][0] if campos['os'] else '—'}` e "
              f"`{campos['cliente'][0] if campos['cliente'] else '—'}`; o Gestor tem "
              f"`{os_reg.get('numero')}` de `{cliente}`. Confirme que é a mesma obra "
              f"e reaplique com `--os {os_reg.get('numero')}`. Custo lançado na OS "
              f"errada contamina o resultado das duas.\n")

    print(f"- Data do campo: **{datetime.fromisoformat(data_iso).strftime('%d/%m/%Y')}**")
    print(f"- Status atual da OS: **{os_reg.get('status') or '—'}**")
    if args.status:
        print(f"- Status será alterado para: **{args.status}**")
    print(f"- Total de gastos do diário: **{brl(total)}**")

    if declarado is not None and abs(declarado - total) > 0.009:
        print(f"\n> ⚠ O diário declara total de {brl(declarado)}, mas os itens somam "
              f"{brl(total)}. Diferença de {brl(abs(declarado - total))} — confira "
              f"antes de aplicar; pode faltar item ou ter valor trocado.")

    incertos = [g for g in gastos if not g["categoria_certa"]]
    if incertos:
        print(f"\n> ⚠ Sem categoria reconhecida (foram para *Outros*): "
              f"{', '.join(g['descricao'] for g in incertos)}. Confirme a "
              f"categoria antes de aplicar.")

    if duplicatas:
        print("\n> ⛔ **Já existe lançamento nesta OS nesta data:** "
              + "; ".join(duplicatas)
              + ". Aplicar de novo duplica o custo. Use --forcar se for intencional.")

    print("\n## Andamento a registrar\n")
    for linha in texto_andamento.split("\n"):
        print(f"> {linha}  ")

    if custos:
        print("\n## Custo de equipe (custos_os)\n")
        print("| Descrição | Tipo | Valor |")
        print("|---|---|---|")
        for c in custos:
            print(f"| {c['obs'].split(' — ')[0]} | {c['tipo_custo']} | {brl(c['valor_total'])} |")

    if pagamentos:
        print("\n## Despesas (pagamentos)\n")
        print("| Descrição | Categoria | Valor | Status |")
        print("|---|---|---|---|")
        for p in pagamentos:
            print(f"| {p['descricao']} | {p['categoria']} | {brl(p['valor'])} | {p['status']} |")

    faltando = [k for k in ("local", "servicos") if not campos[k]]
    if faltando:
        print(f"\n> ⚠ O diário não trouxe: {', '.join(faltando)}. "
              f"O andamento vai ficar incompleto.")

    if not args.aplicar:
        print("\n---\n\n**Prévia — nada foi gravado.** Rode de novo com `--aplicar` "
              "para lançar no Gestor.")


def imprimir_candidatas(candidatas, referencia, cliente, motivo):
    print(f"Não consegui identificar a OS: {motivo} "
          f"(diário diz OS {referencia or '—'!r}, cliente {cliente or '—'!r}).\n")
    if motivo.startswith("nenhuma"):
        print("Abaixo vão as OS mais recentes, não as do cliente — "
              "confira o nome do cliente no diário antes de escolher.\n")
    print("Candidatas:\n")
    for o in candidatas[:15]:
        nome = (o.get("clientes") or {}).get("nome") or "—"
        print(f"  {o.get('numero'):<16} {nome[:32]:<34} {o.get('status') or '—'}")
    print("\nRode de novo com --os <NÚMERO> para escolher. "
          "Não escolha por semelhança de número: OS de meses diferentes "
          "terminam no mesmo dígito e o custo iria para a obra errada.")


# ─────────────────────────── main ───────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Lança um diário de bordo na OS correspondente.")
    ap.add_argument("arquivo", help="arquivo de texto com o diário (ou - para stdin)")
    ap.add_argument("--os", metavar="NUMERO", help="força o número da OS (ex: OS-JUL-009)")
    ap.add_argument("--aplicar", action="store_true", help="grava no Gestor (sem isto, só prévia)")
    ap.add_argument("--forcar", action="store_true", help="grava mesmo com duplicata detectada")
    ap.add_argument("--status", metavar="STATUS", help="muda o status da OS ao aplicar")
    ap.add_argument("--reembolso", metavar="VALOR",
                    help="valor a devolver a quem pagou pela conta pessoal")
    ap.add_argument("--reembolso-desc", metavar="TEXTO", help="descrição do reembolso")
    ap.add_argument("--json", action="store_true", help="imprime o que seria gravado, em JSON")
    args = ap.parse_args()

    texto = (sys.stdin.read() if args.arquivo == "-"
             else Path(args.arquivo).read_text(encoding="utf-8"))
    campos = ler_diario(texto)

    data_iso = achar_data(campos["data"]) or achar_data([texto.splitlines()[0]])
    if not data_iso:
        sys.exit("Não achei a data do diário. Ela precisa estar como dd/mm/aaaa.")

    gastos, declarado = ler_gastos(campos["gastos"])
    total = round(sum(g["valor"] for g in gastos), 2)

    url, key = carregar_env()
    ordens = buscar(url, key, "ordens", "*,clientes(nome)", order="created_at.desc")

    referencia = args.os or (campos["os"][0] if campos["os"] else "")
    cliente = campos["cliente"][0] if campos["cliente"] else ""
    os_reg, candidatas, motivo = resolver_os(ordens, referencia, cliente)

    # --os é o número que o usuário confirmou. Se não bate exato, ele digitou
    # errado — não vale cair no palpite por cliente e gravar em outra OS.
    if args.os and motivo != "número exato":
        sys.exit(f"Não existe OS com o número {args.os!r} no Gestor. "
                 f"Confira em Ordens de Serviço e rode de novo.")

    if not os_reg:
        imprimir_candidatas(candidatas, referencia, cliente, motivo)
        sys.exit(2)

    texto_andamento = montar_andamento(campos, data_iso, gastos, total)
    custos, pagamentos = montar_lancamentos(os_reg, data_iso, gastos, args)
    duplicatas = checar_duplicata(url, key, os_reg, data_iso)

    if args.json:
        print(json.dumps({"os": os_reg.get("numero"), "data": data_iso,
                          "andamento": texto_andamento, "custos_os": custos,
                          "pagamentos": pagamentos, "duplicatas": duplicatas},
                         ensure_ascii=False, indent=2))
        return

    imprimir_previa(os_reg, campos, data_iso, gastos, total, declarado,
                    custos, pagamentos, texto_andamento, duplicatas, motivo, args)

    if not args.aplicar:
        return

    # Match por nome de cliente é palpite: o diário é escrito à mão em campo e
    # "Ademar" pode ser qualquer um dos Ademar da carteira. Só grava quando o
    # usuário confirmou o número, e o --os confirmado bate exato.
    if motivo != "número exato":
        sys.exit(f"\nAbortado: a OS foi deduzida por {motivo}. Confirme qual é e "
                 f"rode com --os {os_reg.get('numero')}.")

    if duplicatas and not args.forcar:
        sys.exit("\nAbortado: já há lançamento desta OS nesta data (ver acima). "
                 "Confira no Gestor e, se for mesmo para duplicar, use --forcar.")

    agora = datetime.now()
    item = {"txt": texto_andamento,
            "data": agora.strftime("%d/%m/%Y"),
            "hora": agora.strftime("%H:%M"),
            "user": "diário de bordo"}
    novo = [*(os_reg.get("andamento") or []), item]
    patch = {"andamento": novo, "atualizado_em": agora.astimezone().isoformat()}
    if args.status:
        patch["status"] = args.status
    atualizar(url, key, "ordens", patch, id=f"eq.{os_reg['id']}")
    print(f"\n✓ Andamento registrado em {os_reg.get('numero')}.")

    for c in custos:
        inserir(url, key, "custos_os", c)
        print(f"✓ Custo de equipe: {brl(c['valor_total'])}")

    for p in pagamentos:
        p = {k: v for k, v in p.items() if not k.startswith("_")}
        inserir(url, key, "pagamentos", p)
        print(f"✓ Despesa: {p['descricao']} — {brl(p['valor'])} ({p['status']})")

    print(f"\nTotal lançado na OS: {brl(total)}. "
          f"Confira em Financeiro → OS {os_reg.get('numero')}.")


if __name__ == "__main__":
    main()
