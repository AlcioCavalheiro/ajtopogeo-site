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
from datetime import datetime, timedelta
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
# o resto vira despesa em pagamentos.
#
# As categorias abaixo são as que o Gestor já usa de fato, não as do <select>
# do formulário — o banco tem "Pedágio", "Material de Campo" e "Manutenção de
# Equipamento", que não estão no dropdown. Mandar gasto de campo para "Outros"
# o mistura com contabilidade e seguro, que é o que mora lá.
DESTINO_GASTO = [
    ("equipe", "Diária", ("ajudante", "diarista", "auxiliar", "mao de obra",
                          "maodeobra", "peao", "braçal", "bracal", "equipe")),
    ("pagamento", "Combustível", ("combustivel", "gasolina", "diesel", "etanol",
                                  "posto", "abastecimento", "arla")),
    ("pagamento", "Alimentação", ("alimentacao", "almoco", "janta", "jantar",
                                  "refeicao", "lanche", "cafe", "comida",
                                  "marmita", "agua")),
    ("pagamento", "Pedágio", ("pedagio",)),
    ("pagamento", "Transporte / Frete", ("frete", "transporte", "balsa", "uber",
                                         "taxi", "estacionamento")),
    ("pagamento", "Manutenção de Equipamento", ("manutencao", "borracharia",
                                                "pneu", "lavagem", "conserto",
                                                "revisao")),
    ("pagamento", "Material de Campo", ("estaca", "piquete", "marco", "tinta",
                                        "material", "cimento", "prego")),
    ("pagamento", "Equipamentos", ("equipamento", "bateria", "gps", "receptor",
                                   "drone", "trena", "bastao")),
    ("pagamento", "Taxas e Emolumentos", ("cartorio", "emolumento", "certidao",
                                          "taxa", "protocolo")),
]

# Linhas de gasto que são fechamento de conta, não lançamento.
LINHAS_TOTAL = ("total", "soma", "somatorio", "total do dia", "total geral")

# Movimento de caixa que a equipe anota junto dos gastos: o adiantamento que
# saiu para o campo e o que sobrou dele. Não é custo da obra — o custo são os
# itens que o adiantamento pagou, e somar os dois conta o dinheiro duas vezes.
LINHAS_CAIXA = ("pix", "saldo", "adiantamento", "vale", "transferencia",
                "deposito", "troco", "sobra", "restante", "devolucao")

# O diário vem colado do WhatsApp e traz a menção de quem foi marcado na
# mensagem ("@Fulano"). Não é conteúdo do dia e não pode entrar no andamento
# da OS, que é documento de obra e pode ir para o cliente no relatório.
MENCAO_WHATSAPP = re.compile(r"^@[^\d]{1,60}$")


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
        if not linha or MENCAO_WHATSAPP.match(linha):
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


def _num_para_float(bruto):
    """Converte o número já isolado ('1.200,00', '69,00', '1.200') em reais."""
    bruto = bruto.replace(" ", "")
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    elif bruto.count(".") == 1 and len(bruto.split(".")[1]) == 3:
        bruto = bruto.replace(".", "")  # 1.200 é mil e duzentos, não 1,2
    try:
        return round(float(bruto), 2)
    except ValueError:
        return None


def ler_valor(texto):
    """Extrai o valor em reais de uma linha de gasto.

    A quantia de verdade nem sempre é o primeiro número da linha: "30 Estacas:
    R$69,00" traz a quantidade antes do preço e "Combustível: 154,39" vem sem
    cifrão. Por isso a busca segue uma ordem de preferência — (a) o número logo
    depois de 'R$'/'$', senão (b) o número com centavos em vírgula, senão (c) o
    último número da linha — em vez de agarrar o primeiro número cru.
    """
    m = re.search(r"R?\$\s*([\d][\d.\s]*,\d{2}|\d[\d.\s]*)", texto)
    if m:
        return _num_para_float(m.group(1))
    decimais = re.findall(r"\d[\d.\s]*,\d{2}", texto)
    if decimais:
        return _num_para_float(decimais[-1])
    numeros = re.findall(r"\d[\d.\s]*", texto)
    if numeros:
        return _num_para_float(numeros[-1])
    return None


def classificar_gasto(descricao):
    alvo = normalizar(descricao)
    for destino, categoria, chaves in DESTINO_GASTO:
        if any(c in alvo for c in chaves):
            return destino, categoria, True
    return "pagamento", "Outros", False


def ler_gastos(linhas):
    """Devolve (lançamentos, total_declarado, linhas_de_caixa)."""
    itens, declarado, caixa = [], None, []
    for linha in linhas:
        if not linha:
            continue
        rotulo = normalizar(linha.split(":")[0].split("-")[0])
        if any(rotulo.startswith(t) for t in LINHAS_TOTAL):
            declarado = ler_valor(linha)
            continue
        if any(rotulo.startswith(c) for c in LINHAS_CAIXA):
            caixa.append(linha)
            continue
        valor = ler_valor(linha)
        if valor is None:
            continue
        # Descrição é tudo antes do valor. Com "R$" o corte é nele (a quantidade
        # antes fica na descrição: "30 Estacas: R$69,00" → "30 Estacas"); sem
        # cifrão, corta no último número para o valor não vazar para o texto
        # ("Combustível: 154,39" → "Combustível").
        partes = re.split(r"[-–—:]?\s*R?\$", linha, maxsplit=1)
        if len(partes) > 1:
            desc = partes[0]
        else:
            nums = list(re.finditer(r"\d[\d.\s]*(?:,\d{2})?", linha))
            desc = linha[:nums[-1].start()] if nums else linha
        desc = limpar(desc).rstrip(" -–—:") or linha
        desc = desc[:1].upper() + desc[1:]  # "combustível" vira "Combustível" na lista
        destino, categoria, certeza = classificar_gasto(desc)
        itens.append({"descricao": desc, "valor": valor, "destino": destino,
                      "categoria": categoria, "categoria_certa": certeza})
    return itens, declarado, caixa


# ─────────────────────────── cadeia cliente → orçamento → OS ───────────────────────────

MESES = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")

# Quem assina o serviço. É o responsável técnico de todas as OS da carteira.
RESPONSAVEL = "ALCIO MARQUES CAVALHEIRO JUNIOR"

# Deslocamento é item próprio no orçamento, sempre a R$ 1,50/km — a taxa é a
# mesma em todos os orçamentos da carteira que cobram km.
ITEM_KM = "Mobilização e Desmobilização de Equipe"
VALOR_KM = 1.5


def proximo_numero(url, key, tabela, prefixo):
    """Replica a numeração do Gestor: prefixo + sequencial de 3 dígitos.

    O Gestor ordena por 'numero' desc e soma 1 no maior — mesma conta aqui,
    para a OS criada pela rotina não colidir com a criada pela tela.
    """
    achados = buscar(url, key, tabela, "numero",
                     numero=f"like.{prefixo}%", order="numero.desc", limit="1")
    seq = 0
    if achados:
        resto = (achados[0].get("numero") or "").replace(prefixo, "")
        try:
            seq = int(resto)
        except ValueError:
            seq = 0
    return f"{prefixo}{seq + 1:03d}"


def achar_cliente(url, key, nome):
    """Clientes cujo nome se encaixa no informado, nos dois sentidos.

    Cliente duplicado espalha OS do mesmo dono em dois cadastros e quebra o
    histórico — por isso qualquer semelhança vira bloqueio, não escolha.
    """
    alvo = normalizar(nome)
    parecidos = []
    for c in buscar(url, key, "clientes", "id,nome,telefone,cidade"):
        atual = normalizar(c.get("nome") or "")
        if not atual:
            continue
        if alvo == atual or alvo in atual or atual in alvo:
            parecidos.append(c)
    return parecidos


def montar_cadeia(url, key, args, data_iso, campos):
    """Prepara (cliente, orçamento, OS) sem gravar nada."""
    if not args.cliente:
        sys.exit("--criar-os exige --cliente com o nome do cliente.")
    valor = ler_valor(args.valor or "")
    if valor is None:
        sys.exit("--criar-os exige --valor com o valor combinado do serviço.")

    servico = (campos["servicos"][0] if campos["servicos"] else "Serviço de campo")
    local = campos["local"][0] if campos["local"] else None
    digitos = re.sub(r"\D", "", args.cpfcnpj or "")
    tipo_pessoa = "PJ" if len(digitos) == 14 else "PF"

    cliente = {
        "nome": args.cliente.strip(),
        "tipo": tipo_pessoa,
        "telefone": args.telefone or None,
        "cpfcnpj": args.cpfcnpj or None,
        "cidade": args.cidade or local,
        "estado": "MS",
        "ativo": True,
    }

    hoje = datetime.now().date()
    forma = args.pagamento or "À vista"

    itens = [{"nome": servico, "unidade": "serviço", "quantidade": 1,
              "valor_unitario": valor, "descricao": servico}]
    km = float(args.km) if args.km else 0
    if km:
        itens.append({"nome": ITEM_KM, "unidade": "km", "quantidade": km,
                      "valor_unitario": VALOR_KM,
                      "descricao": f"Deslocamento de equipe e equipamento — {km:g} km"})
        valor = round(valor + km * VALOR_KM, 2)

    orcamento = {
        "numero": proximo_numero(url, key, "orcamentos", f"ORC-{hoje.year}-"),
        "descricao": servico,
        "valor_total": valor,
        "itens": itens,
        # Nasce Aprovado porque o serviço já foi executado: é registro
        # retroativo de uma combinação que nunca passou pelo sistema.
        "status": "Aprovado",
        "validade": (hoje + timedelta(days=30)).isoformat(),
        "pagamento": {"forma": forma, "parcelas": 1 if "vista" in normalizar(forma) else 2},
        "responsavel": RESPONSAVEL,
    }

    ordem = {
        "numero": proximo_numero(url, key, "ordens", f"OS-{MESES[hoje.month - 1]}-"),
        "tipo": args.tipo or "Outro",
        "responsavel": RESPONSAVEL,
        "status": args.status or "Agendada",
        "data": data_iso,
        "orcamento_valor": valor,
        "obs": (campos["obs"][0] if campos["obs"] else None),
        "checklist": [],
        "proc_etapas": [],
    }
    return cliente, orcamento, ordem


def criar_cadeia(url, key, cliente, orcamento, ordem, data_iso, existente=None):
    """Grava cliente → orçamento → OS e devolve a OS criada.

    Com `existente`, o cliente é reaproveitado em vez de criado — caso da OS
    nova para cliente que já está na carteira.
    """
    if existente:
        novo_cliente = existente
        print(f"• Cliente existente reaproveitado: {novo_cliente['nome']}")
    else:
        novo_cliente = inserir(url, key, "clientes", cliente)[0]
        print(f"✓ Cliente criado: {novo_cliente['nome']} ({novo_cliente['tipo']})")

    orcamento = {**orcamento, "cliente_id": novo_cliente["id"]}
    novo_orc = inserir(url, key, "orcamentos", orcamento)[0]
    print(f"✓ Orçamento {novo_orc['numero']} — {brl(float(novo_orc['valor_total']))} (Aprovado)")

    agora = datetime.now()
    abertura = {
        "txt": f"OS criada a partir do orçamento {novo_orc['numero']}",
        "data": agora.strftime("%d/%m/%Y"), "hora": agora.strftime("%H:%M"),
        "user": "diário de bordo",
    }
    ordem = {**ordem, "cliente_id": novo_cliente["id"],
             "orcamento_id": novo_orc["id"], "orcamento_numero": novo_orc["numero"],
             "andamento": [abertura]}
    nova_os = inserir(url, key, "ordens", ordem)[0]
    print(f"✓ OS {nova_os['numero']} criada — {nova_os['tipo']} · {nova_os['status']}")

    atualizar(url, key, "orcamentos", {"os_gerada": nova_os["numero"]},
              id=f"eq.{novo_orc['id']}")
    return nova_os


def diario_ja_tem_os(url, key, cliente_id, data_iso):
    """OS do mesmo cliente que já registrou este diário.

    Sem isto, rodar --criar-os duas vezes abre duas OS com o mesmo dia de
    campo — e a segunda leva o custo junto, dobrando a despesa numa obra que
    nem deveria existir.
    """
    if not cliente_id:
        return []
    marca = marca_diario(data_iso)
    repetidas = []
    for o in buscar(url, key, "ordens", "numero,andamento",
                    cliente_id=f"eq.{cliente_id}"):
        for item in (o.get("andamento") or []):
            txt = item.get("txt") if isinstance(item, dict) else str(item)
            if txt and marca in txt:
                repetidas.append(o.get("numero"))
                break
    return repetidas


def imprimir_cadeia(cliente, orcamento, ordem, parecidos, existente=None):
    print("## Cadeia a criar (cliente → orçamento → OS)\n")
    if existente:
        print(f"- **Cliente:** {existente['nome']} — *já cadastrado, será "
              f"reaproveitado* (tel {existente.get('telefone') or '—'})")
    if parecidos:
        print("> ⛔ **Já existe cliente com nome parecido:** "
              + "; ".join(f"{c['nome']}" + (f" ({c['cidade']})" if c.get("cidade") else "")
                          for c in parecidos)
              + ". Cadastrar de novo divide as OS do mesmo dono em dois cadastros. "
                "Use --os com a OS existente, ou confirme que é outra pessoa.\n")
    if not existente:
        print(f"- **Cliente:** {cliente['nome']} · {cliente['tipo']}"
              f" · tel {cliente['telefone'] or '— não informado —'}"
              f" · {cliente['cidade'] or '—'}/{cliente['estado']}")
    print(f"- **Orçamento {orcamento['numero']}:** "
          f"{brl(float(orcamento['valor_total']))} · {orcamento['status']} · "
          f"{orcamento['pagamento']['forma']}")
    for it in orcamento["itens"]:
        sub = float(it["quantidade"]) * float(it["valor_unitario"])
        print(f"    - {it['nome']} — {it['quantidade']:g} {it['unidade']} × "
              f"{brl(float(it['valor_unitario']))} = **{brl(sub)}**")
    print(f"- **OS {ordem['numero']}:** {ordem['tipo']} · status {ordem['status']} · "
          f"data {datetime.fromisoformat(ordem['data']).strftime('%d/%m/%Y')}")
    if not existente:
        if not cliente["cpfcnpj"]:
            print("\n> ⚠ Sem CPF/CNPJ. Cadastro serve para tocar a OS, mas NF e "
                  "contrato vão exigir o documento depois.")
        if not cliente["telefone"]:
            print("\n> ⚠ Sem telefone. A OS entra na /cobranca-os sem contato.")
    print()


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


def marca_diario(data_iso, hora=None):
    """Assinatura que identifica o andamento deste diário — trava a duplicata.

    Leva a hora de chegada quando o diário traz: a mesma OS pode receber dois
    diários no mesmo dia (equipe de manhã e de tarde, serviços diferentes), e
    marca só de data confundiria o segundo diário com o relançamento do
    primeiro. Sem hora, cai no formato antigo, só data.
    """
    dia = datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
    return f"[diário {dia} {hora}]" if hora else f"[diário {dia}]"


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

    linhas = [" · ".join([marca_diario(data_iso, chegada)] + partes)]
    linhas += bloco("Serviços realizados", campos["servicos"])
    linhas += bloco("Pendências", campos["pendencias"])
    if gastos:
        detalhe = "; ".join(f"{g['descricao']} {brl(g['valor'])}" for g in gastos)
        linhas.append(f"Gastos do dia: {brl(total)} — {detalhe}")
    linhas += bloco("Observações", campos["obs"])
    return "\n".join(linhas)


def montar_lancamentos(os_reg, data_iso, gastos, args):
    # Reprocessar dia antigo: o financeiro daquele dia já foi lançado à mão e
    # relançar dobraria o custo. Só o andamento é reescrito.
    if args.so_andamento:
        return [], []

    # O oposto: o dia já tem andamento e quase todo o financeiro, e falta um
    # item solto. Filtra os gastos pelo texto e não mexe no andamento.
    if args.so_gasto:
        alvos = [normalizar(t) for t in args.so_gasto]
        selecionados = [g for g in gastos
                        if any(a in normalizar(g["descricao"]) for a in alvos)]
        if not selecionados:
            sys.exit(f"Nenhum gasto do diário casa com {args.so_gasto}. "
                     f"Itens do dia: "
                     + ", ".join(repr(g["descricao"]) for g in gastos))
        gastos = selecionados

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
        # O reembolso pode já ter sido devolvido antes de o diário ser lançado.
        # Vencimento fica no dia do campo, que é quando a dívida nasceu; a data
        # do acerto vai em data_pagamento, senão o caixa mostra saída no dia
        # errado.
        pago_em = None
        if args.reembolso_pago:
            pago_em = achar_data([args.reembolso_pago])
            if not pago_em:
                sys.exit(f"Não entendi a data do reembolso: {args.reembolso_pago!r} "
                         f"— use dd/mm/aaaa.")
        pagamentos.append({
            "descricao": f"Reembolso — {desc} — {ref}",
            "categoria": "Pessoal", "valor": valor,
            "vencimento": data_iso, "data_pagamento": pago_em,
            "status": "Pago" if pago_em else "Pendente", "tipo_custo": "OS",
            "os_id": os_reg["id"], "os_manual": numero,
            "obs": f"Reembolso ao sócio — diário de bordo {ref}"
                   + (f", devolvido em "
                      f"{datetime.fromisoformat(pago_em).strftime('%d/%m/%Y')}"
                      if pago_em else "")
                   + ". Não é custo novo da OS: o gasto já está lançado à parte.",
            "_reembolso": True,
        })

    return custos, pagamentos


def checar_gasto_solto(url, key, os_reg, data_iso, pagamentos):
    """Em --so-gasto, avisa se o item já está lançado naquela data.

    Confere por valor: a descrição varia (o Gestor tem 'Pedagio' e o diário
    'Pedágios'), mas o valor de um gasto avulso repetido no mesmo dia e na
    mesma OS é quase sempre relançamento.
    """
    existentes = buscar(url, key, "pagamentos", "descricao,valor",
                        os_id=f"eq.{os_reg['id']}", vencimento=f"eq.{data_iso}")
    achados = []
    for p in pagamentos:
        for e in existentes:
            if abs(float(e.get("valor") or 0) - float(p["valor"])) < 0.009:
                achados.append(
                    f"{brl(p['valor'])} já lançado nesta data como "
                    f"{e.get('descricao') or '—'!r}")
                break
    return achados


def checar_duplicata(url, key, os_reg, data_iso, so_andamento=False, hora=None,
                     so_gasto=False):
    """Avisa o que já existe nesta OS nesta data. Relançar dobra o custo."""
    achados = []
    marca = marca_diario(data_iso, hora)
    generica = marca_diario(data_iso)
    for item in (os_reg.get("andamento") or []):
        txt = item.get("txt") if isinstance(item, dict) else str(item)
        if not txt:
            continue
        if marca in txt:
            achados.append(f"este mesmo diário já está registrado — marca {marca}")
            break
        if generica in txt:
            # Outro diário do mesmo dia nesta OS: as duas equipes acontecem, e
            # o segundo diário é legítimo. Mas dobrar o dia por engano também
            # acontece — quem decide é quem viu o campo.
            achados.append(
                f"já há OUTRO diário desta data nesta OS ({generica}). Se for o "
                f"segundo turno/equipe, é legítimo e vai com --forcar; se for o "
                f"mesmo dia lançado de novo, não aplique")
            break

    # Em --so-andamento o financeiro daquele dia existir é o esperado, não o
    # sintoma: é justamente por ele já estar lançado que nada é relançado.
    if so_andamento:
        return achados
    # Em --so-gasto vale o inverso: o andamento já existir é o normal, e o que
    # importa é se o item específico já está lá. Quem confere isso é
    # checar_gasto_solto, com o valor na mão.
    if so_gasto:
        return []



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

def conferir_lancado(url, key, os_reg, data_iso, total):
    """Compara o total do diário com o que já está lançado naquela data.

    Só faz sentido em --so-andamento, onde nada é gravado no financeiro: é a
    chance de descobrir gasto do diário que nunca entrou no Gestor, ou entrou
    com data trocada. Devolve (lancado, diferenca).
    """
    pags = buscar(url, key, "pagamentos", "valor",
                  os_id=f"eq.{os_reg['id']}", vencimento=f"eq.{data_iso}")
    custos = buscar(url, key, "custos_os", "valor_total",
                    os_id=f"eq.{os_reg['id']}", data=f"eq.{data_iso}")
    lancado = (sum(float(x.get("valor") or 0) for x in pags)
               + sum(float(x.get("valor_total") or 0) for x in custos))
    return round(lancado, 2), round(total - lancado, 2)


def imprimir_previa(os_reg, campos, data_iso, gastos, total, declarado,
                    custos, pagamentos, texto_andamento, duplicatas, motivo, args,
                    conferencia=None):
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
    if args.criar_os:
        print(f"- Status com que a OS nasce: **{os_reg.get('status') or '—'}**")
    else:
        print(f"- Status atual da OS: **{os_reg.get('status') or '—'}**")
        if args.status:
            print(f"- Status será alterado para: **{args.status}**")
    print(f"- Total de gastos do diário: **{brl(total)}**")

    if declarado is not None and abs(declarado - total) > 0.009:
        print(f"\n> ⚠ O diário declara total de {brl(declarado)}, mas os itens somam "
              f"{brl(total)}. Diferença de {brl(abs(declarado - total))} — confira "
              f"antes de aplicar; pode faltar item ou ter valor trocado.")

    if getattr(args, "caixa", None):
        print(f"\n> ℹ Fora do custo da obra, por serem movimento de caixa: "
              + "; ".join(f"*{c}*" for c in args.caixa)
              + ". O adiantamento não é custo — os itens que ele pagou já "
                "estão lançados acima. Se sobrou saldo com quem foi a campo, "
                "isso se acerta no caixa, não na OS.")

    incertos = [g for g in gastos if not g["categoria_certa"]]
    if incertos:
        print(f"\n> ⚠ Sem categoria reconhecida (foram para *Outros*): "
              f"{', '.join(g['descricao'] for g in incertos)}. Confirme a "
              f"categoria antes de aplicar.")

    if duplicatas:
        print("\n> ⛔ **Já existe lançamento nesta OS nesta data:** "
              + "; ".join(duplicatas)
              + ". Aplicar de novo duplica o custo. Use --forcar se for intencional.")

    if args.so_gasto:
        print("\n## Andamento — **não será tocado**\n")
    else:
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

    if args.so_andamento:
        print("\n> Modo `--so-andamento`: nenhum custo ou despesa será lançado. "
              "O financeiro deste dia já está no Gestor e relançar dobraria.")
        if conferencia:
            lancado, diferenca = conferencia
            print(f"\n- Diário: **{brl(total)}** · já lançado na OS nesta data: "
                  f"**{brl(lancado)}**")
            if abs(diferenca) > 0.009:
                print(f"\n> ⚠ **Faltam {brl(diferenca)} lançados nesta data.** O "
                      f"diário registra gasto que não está no Gestor, ou o "
                      f"lançamento entrou com outra data. Confira antes de "
                      f"completar — pode ser o mesmo gasto em dia trocado, e aí "
                      f"lançar de novo duplica."
                      if diferenca > 0 else
                      f"\n> ⚠ **Há {brl(abs(diferenca))} a mais lançados nesta "
                      f"data do que o diário registra.** Pode ser gasto de outro "
                      f"dia com data trocada, ou lançamento em duplicidade.")

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


def aplicar_diario(url, key, os_reg, texto_andamento, custos, pagamentos, total, args):
    """Grava o andamento e os lançamentos numa OS que já existe."""
    agora = datetime.now()
    if args.so_gasto:
        # O andamento do dia já está lá — é só o item que faltou.
        print(f"• Andamento preservado; lançando só o gasto que faltava.")
    else:
        item = {"txt": texto_andamento,
                "data": agora.strftime("%d/%m/%Y"),
                "hora": agora.strftime("%H:%M"),
                "user": "diário de bordo"}
        # A OS recém-criada já vem com o andamento de abertura; preservar.
        novo = [*(os_reg.get("andamento") or []), item]
        patch = {"andamento": novo, "atualizado_em": agora.astimezone().isoformat()}
        if args.status:
            patch["status"] = args.status
        atualizar(url, key, "ordens", patch, id=f"eq.{os_reg['id']}")
        print(f"✓ Andamento registrado em {os_reg.get('numero')}.")

    os_id, numero = os_reg["id"], os_reg.get("numero")
    for c in custos:
        inserir(url, key, "custos_os", {**c, "os_id": os_id})
        print(f"✓ Custo de equipe: {brl(c['valor_total'])}")

    for p in pagamentos:
        p = {k: v for k, v in p.items() if not k.startswith("_")}
        inserir(url, key, "pagamentos", {**p, "os_id": os_id, "os_manual": numero})
        print(f"✓ Despesa: {p['descricao']} — {brl(p['valor'])} ({p['status']})")

    # `total` é o total do diário, não o que esta rodada gravou. Nos modos
    # parciais os dois números divergem, e anunciar o do diário faz parecer
    # que entrou dinheiro que não entrou.
    if args.so_andamento:
        print(f"\nSó o andamento foi gravado. O financeiro de {brl(total)} "
              f"deste dia continua como já estava na OS {numero}.")
    elif args.so_gasto:
        lancado = sum(p["valor"] for p in pagamentos) + sum(c["valor_total"] for c in custos)
        print(f"\nLançado agora: {brl(lancado)} — de {brl(total)} que o diário "
              f"registra no dia. O resto já estava na OS {numero}.")
    else:
        print(f"\nTotal lançado na OS: {brl(total)}. "
              f"Confira em Financeiro → OS {numero}.")


# ─────────────────────────── main ───────────────────────────

# ─────────────────────── dia operacional (várias OS) ───────────────────────

def ratear_valor(total, pesos):
    """Divide `total` (reais) entre len(pesos) fatias, na proporção de `pesos`.

    Conta em centavos inteiros e joga a sobra na última fatia, para a soma
    fechar exatamente com o total. Rateio que não fecha é o que faz o custo do
    dia não bater com a nota depois.
    """
    soma_peso = sum(pesos) or len(pesos)
    total_cent = round(total * 100)
    fatias = [int(total_cent * p / soma_peso) for p in pesos]
    fatias[-1] += total_cent - sum(fatias)
    return [c / 100 for c in fatias]


def carregar_plano(caminho):
    """Lê o plano do dia operacional: quais OS receberam o dia e o que anotar.

    O plano é o que o operador confirmou com o usuário — qual atividade é de
    qual OS. O script nunca deduz isso: custo na obra errada só aparece meses
    depois, quando o resultado da obra não fecha com o que foi cobrado.
    """
    try:
        plano = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"Não consegui ler o plano {caminho!r}: {e}")
    oss = plano.get("os") or []
    if not oss:
        sys.exit('O plano precisa de pelo menos uma OS em "os": [ ... ].')
    for o in oss:
        if not o.get("numero"):
            sys.exit('Cada item de "os" precisa de "numero".')
        if not o.get("atividade"):
            sys.exit(f'OS {o["numero"]}: falta "atividade" (o texto do andamento).')
    return plano


def dia_operacional(url, key, args, data_iso, gastos):
    """Dia que passou por várias OS: rateia os gastos e anota cada OS.

    Diferente do diário normal, aqui não existe uma OS dona do dia — o gasto
    (deslocamento, alimentação) é de um dia inteiro de tarefas espalhadas por
    vários clientes. Jogá-lo numa OS só distorce o custo daquela obra; deixá-lo
    de fora some com a despesa. A saída é ratear entre as OS efetivamente
    tocadas, que vêm no plano confirmado pelo operador — não do palpite do
    script. Atividade sem OS (prospecção, OS não identificada) fica de fora: o
    texto do diário continua no scratchpad da sessão.
    """
    plano = carregar_plano(args.dia_operacional)
    numeros = [o["numero"] for o in plano["os"]]
    pesos = [float(o.get("peso", 1) or 1) for o in plano["os"]]
    conta_pessoal = normalizar(plano.get("conta", "empresa")) == "pessoal"

    # Toda OS do plano tem que existir. Número errado = custo perdido numa OS
    # fantasma; melhor parar aqui do que gravar em lugar nenhum.
    achadas = {o["numero"]: o for o in
               buscar(url, key, "ordens", "id,numero,andamento",
                      numero=f"in.({','.join(numeros)})")}
    faltam = [n for n in numeros if n not in achadas]
    if faltam:
        sys.exit(f"OS do plano que não existem no Gestor: {', '.join(faltam)}. "
                 f"Confira os números e rode de novo.")

    # Rateia por categoria, não pelo total: assim combustível continua
    # combustível e alimentação continua alimentação no Financeiro de cada OS.
    por_categoria = {}
    for g in gastos:
        por_categoria[g["categoria"]] = por_categoria.get(g["categoria"], 0.0) + g["valor"]
    total = round(sum(por_categoria.values()), 2)
    if total <= 0:
        sys.exit("O diário não tem gastos para ratear.")

    rateio = {cat: ratear_valor(val, pesos) for cat, val in por_categoria.items()}
    total_os = [round(sum(rateio[c][i] for c in rateio), 2) for i in range(len(numeros))]

    dia_br = datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
    marca = marca_diario(data_iso)
    origem = "conta pessoal do sócio" if conta_pessoal else "conta da empresa"

    print(f"# Dia operacional {dia_br} — rateio de {brl(total)} entre "
          f"{len(numeros)} OS\n")
    print(f"- Origem do dinheiro: **{origem}**")
    print("- Gastos: " + "; ".join(f"{c} {brl(v)}" for c, v in por_categoria.items()) + "\n")
    print("| OS | Atividade (vai no andamento) | "
          + " | ".join(rateio.keys()) + " | Total |")
    print("|---|---|" + "|".join(["---"] * len(rateio)) + "|---|")
    for i, o in enumerate(plano["os"]):
        cats = " | ".join(brl(rateio[c][i]) for c in rateio)
        print(f"| {o['numero']} | {o['atividade'][:58]} | {cats} | **{brl(total_os[i])}** |")
    print(f"\nSoma do rateio: **{brl(round(sum(total_os), 2))}** (diário: {brl(total)})")
    if conta_pessoal:
        print(f"\n> 💰 Conta pessoal: além dos gastos, entra **1 reembolso pendente "
              f"de {brl(total)}** ao sócio (categoria Pessoal, sem OS).")

    if not args.aplicar:
        print("\n**Prévia — nada gravado.** Rode com `--aplicar` para gravar.")
        return

    agora = datetime.now()
    for i, o in enumerate(plano["os"]):
        reg = achadas[o["numero"]]
        andamento = reg.get("andamento") or []
        ja = any(marca in (a.get("txt", "") if isinstance(a, dict) else str(a))
                 for a in andamento)
        if ja:
            print(f"• {o['numero']}: andamento de {dia_br} já existe, mantido.")
        else:
            entrada = {
                "txt": (f"{marca} {o['atividade']} · rateio operacional do dia "
                        f"(deslocamento+alimentação): {brl(total_os[i])}."),
                "data": agora.strftime("%d/%m/%Y"), "hora": agora.strftime("%H:%M"),
                "user": "diário de bordo",
            }
            atualizar(url, key, "ordens",
                      {"andamento": [*andamento, entrada],
                       "atualizado_em": agora.astimezone().isoformat()},
                      id=f"eq.{reg['id']}")
            print(f"✓ {o['numero']}: andamento registrado.")

        # Guarda contra rodar duas vezes: rateio já lançado nesta OS nesta data.
        existentes = buscar(url, key, "pagamentos", "descricao",
                            os_id=f"eq.{reg['id']}", data_pagamento=f"eq.{data_iso}")
        if any("Rateio dia operacional" in (p.get("descricao") or "") for p in existentes):
            print(f"  {o['numero']}: rateio já lançado nesta data, pulado.")
            continue
        for cat in rateio:
            val = rateio[cat][i]
            if val <= 0:
                continue
            inserir(url, key, "pagamentos", {
                "descricao": f"Rateio dia operacional {dia_br} — {cat} — {o['numero']}",
                "categoria": cat, "valor": val,
                "vencimento": data_iso, "data_pagamento": data_iso,
                "status": "Pago", "tipo_custo": "OS",
                "os_id": reg["id"], "os_manual": o["numero"],
                "obs": (f"Rateio do dia operacional de {dia_br} (total {brl(total)} "
                        f"dividido entre {len(numeros)} OS). Pago via {origem}."),
            })
        print(f"  ✓ {o['numero']}: {brl(total_os[i])} lançado ({', '.join(rateio.keys())}).")

    if conta_pessoal:
        # Dívida única da empresa com o sócio pelo dia inteiro — não é de uma OS.
        # O gasto já entrou rateado como Pago; isto é só a devolução do que saiu
        # do bolso, e some no caixa como conta a pagar até o acerto.
        inserir(url, key, "pagamentos", {
            "descricao": f"Reembolso — dia operacional {dia_br} pago pela conta pessoal",
            "categoria": "Pessoal", "valor": total,
            "vencimento": data_iso, "data_pagamento": None,
            "status": "Pendente", "tipo_custo": "Operacional",
            "obs": (f"Reembolso ao sócio pelo dia operacional de {dia_br}. O gasto "
                    f"já está rateado nas OS à parte; isto é só a devolução do que "
                    f"saiu da conta pessoal."),
        })
        print(f"\n✓ Reembolso pendente de {brl(total)} criado (Pessoal, sem OS).")

    print(f"\nRateio concluído: {brl(round(sum(total_os), 2))} entre {len(numeros)} OS. "
          f"Confira no Financeiro de cada OS.")


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
    ap.add_argument("--reembolso-pago", metavar="DATA",
                    help="data em que o reembolso já foi devolvido (dd/mm/aaaa); "
                         "sem isto ele entra como Pendente")
    ap.add_argument("--so-gasto", metavar="TEXTO", action="append",
                    help="lança só os gastos cuja descrição casa com TEXTO, sem "
                         "tocar no andamento (item que faltou num dia já lançado). "
                         "Pode repetir")
    ap.add_argument("--so-andamento", action="store_true",
                    help="grava só o andamento; não lança custo nem despesa "
                         "(dia antigo, com o financeiro já lançado à mão)")
    ap.add_argument("--criar-os", action="store_true",
                    help="serviço sem OS: cria cliente, orçamento e OS antes de lançar")
    ap.add_argument("--cliente", metavar="NOME", help="nome do cliente a cadastrar")
    ap.add_argument("--telefone", metavar="FONE", help="telefone do cliente")
    ap.add_argument("--cpfcnpj", metavar="DOC", help="CPF ou CNPJ do cliente")
    ap.add_argument("--cidade", metavar="CIDADE", help="cidade do cliente (padrão: local do diário)")
    ap.add_argument("--valor", metavar="VALOR", help="valor combinado do serviço")
    ap.add_argument("--tipo", metavar="TIPO", help="tipo da OS (ex: Locação de Obras)")
    ap.add_argument("--pagamento", metavar="FORMA", help="forma de pagamento do orçamento")
    ap.add_argument("--km", metavar="KM", type=float,
                    help=f"km de deslocamento — vira item '{ITEM_KM}' a "
                         f"R$ {VALOR_KM:.2f}/km no orçamento")
    ap.add_argument("--cliente-existente", action="store_true",
                    help="reaproveita o cliente já cadastrado em vez de criar outro")
    ap.add_argument("--dia-operacional", metavar="PLANO",
                    help="dia que passou por várias OS: rateia os gastos e anota "
                         "cada OS conforme o plano JSON (ver SKILL.md)")
    ap.add_argument("--json", action="store_true", help="imprime o que seria gravado, em JSON")
    args = ap.parse_args()

    texto = (sys.stdin.read() if args.arquivo == "-"
             else Path(args.arquivo).read_text(encoding="utf-8"))
    campos = ler_diario(texto)

    data_iso = achar_data(campos["data"]) or achar_data([texto.splitlines()[0]])
    if not data_iso:
        sys.exit("Não achei a data do diário. Ela precisa estar como dd/mm/aaaa.")

    gastos, declarado, caixa = ler_gastos(campos["gastos"])
    total = round(sum(g["valor"] for g in gastos), 2)
    args.caixa = caixa

    url, key = carregar_env()

    if args.criar_os:
        cliente, orcamento, ordem = montar_cadeia(url, key, args, data_iso, campos)
        parecidos = achar_cliente(url, key, cliente["nome"])

        existente = None
        if args.cliente_existente:
            if len(parecidos) != 1:
                sys.exit(
                    f"--cliente-existente precisa de exatamente um cadastro que "
                    f"case com {cliente['nome']!r}; achei {len(parecidos)}."
                    + ("\nCandidatos: " + "; ".join(c["nome"] for c in parecidos)
                       if parecidos else "")
                )
            existente = parecidos[0]
            parecidos = []  # reaproveitar é a intenção, não o acidente

        imprimir_cadeia(cliente, orcamento, ordem, parecidos, existente)

        ja_lancado = diario_ja_tem_os(url, key, (existente or {}).get("id"), data_iso)
        if ja_lancado:
            print(f"> ⛔ **Este diário já está lançado em {', '.join(ja_lancado)}** "
                  f"(mesmo cliente, mesma data). Criar outra OS duplicaria a obra "
                  f"e o custo. Use `--os` para complementar a existente.\n")

        os_reg = {"id": None, "numero": ordem["numero"], "status": ordem["status"],
                  "clientes": {"nome": cliente["nome"]}, "andamento": []}
        texto_andamento = montar_andamento(campos, data_iso, gastos, total)
        custos, pagamentos = montar_lancamentos(os_reg, data_iso, gastos, args)
        imprimir_previa(os_reg, campos, data_iso, gastos, total, declarado,
                        custos, pagamentos, texto_andamento, [], "número exato", args)

        if not args.aplicar:
            return
        if parecidos and not args.forcar:
            sys.exit("\nAbortado: já existe cliente com nome parecido (ver acima). "
                     "Confirme se é a mesma pessoa antes de criar um cadastro novo.")
        if ja_lancado and not args.forcar:
            sys.exit(f"\nAbortado: este diário já está em {', '.join(ja_lancado)}. "
                     f"Criar outra OS duplicaria a obra e o custo.")

        nova = criar_cadeia(url, key, cliente, orcamento, ordem, data_iso, existente)
        aplicar_diario(url, key, nova, texto_andamento, custos, pagamentos, total, args)
        return

    if args.dia_operacional:
        dia_operacional(url, key, args, data_iso, gastos)
        return

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
    duplicatas = checar_duplicata(url, key, os_reg, data_iso, args.so_andamento,
                                  achar_hora(campos["chegada"]), args.so_gasto)
    if args.so_gasto:
        duplicatas = checar_gasto_solto(url, key, os_reg, data_iso, pagamentos)

    if args.json:
        print(json.dumps({"os": os_reg.get("numero"), "data": data_iso,
                          "andamento": texto_andamento, "custos_os": custos,
                          "pagamentos": pagamentos, "duplicatas": duplicatas},
                         ensure_ascii=False, indent=2))
        return

    conferencia = (conferir_lancado(url, key, os_reg, data_iso, total)
                   if args.so_andamento else None)
    imprimir_previa(os_reg, campos, data_iso, gastos, total, declarado,
                    custos, pagamentos, texto_andamento, duplicatas, motivo, args,
                    conferencia)

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

    aplicar_diario(url, key, os_reg, texto_andamento, custos, pagamentos, total, args)


if __name__ == "__main__":
    main()
