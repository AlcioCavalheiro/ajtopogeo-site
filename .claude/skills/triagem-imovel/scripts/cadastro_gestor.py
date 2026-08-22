# -*- coding: utf-8 -*-
"""Cria/atualiza cliente e obra no Gestor (Supabase) a partir da triagem.

Uso:
    python cadastro_gestor.py <spec.json>

O spec.json tem dois blocos, "cliente" e "obra" (obra.cliente_id e
preenchido automaticamente com o id do cliente criado/encontrado):

{
  "cliente": {
    "nome": "PAULO ROBERTO BOTTON",
    "tipo": "PF",
    "cpfcnpj": "992.684.001-97",
    "endereco": "Rua Minas Gerais, n 991, Centro",
    "cidade": "Sidrolandia",
    "estado": "MS",
    "profissao": "Produtor rural",
    "estado_civil": "Divorciado"
  },
  "obra": {
    "nome": "ESTANCIA TALISMA - Desmembramento",
    "municipio": "Sidrolandia - MS",
    "endereco": "Rod. Dalton Derzi Wasilewski (BR-060)",
    "area_ha": 58.1040,
    "ccir": "950.173.668.036-1",
    "matricula": "26.938",
    "tipo_obra": "Desmembramento",
    "comarca": "Sidrolandia/MS",
    "cartorio": "1 Servico de Registro Publico - RI da Comarca de Sidrolandia/MS",
    "codigo_incra_tipo": "SIGEF",
    "codigo_incra": "27b8504e-...",
    "obs": "...",
    "proprietarios": [ {..qualificacao completa, mesmo formato do app..} ]
  }
}

Credenciais: le SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY de
C:\\Users\\ALCIO\\.ajtopogeo\\supabase_service_role.env (fora do repo -
nunca comitar essa chave). Se o arquivo nao existir, para com instrucao
de como cria-lo.

Dedup: por CPF/CNPJ (cliente) e por nome da obra (obra). Se ja existir,
ATUALIZA em vez de duplicar.

A chave usada e service_role - acesso total, sem RLS. Rode so a partir
desta skill, com o spec revisado por voce antes.
"""
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG = Path.home() / ".ajtopogeo" / "supabase_service_role.env"


def ler_credenciais():
    if not CONFIG.exists():
        sys.exit(
            "Faltam as credenciais do Supabase.\n"
            f"Crie {CONFIG} com duas linhas:\n"
            "SUPABASE_URL=https://xxxx.supabase.co\n"
            "SUPABASE_SERVICE_ROLE_KEY=eyJ...\n"
            "(pegue a service_role key em Supabase > Project Settings > API)"
        )
    env = {}
    for linha in CONFIG.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        env[k.strip()] = v.strip()
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        sys.exit(f"{CONFIG} incompleto — falta SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY.")
    return url, key


def req(url, key, path, method="GET", body=None):
    full = url.rstrip("/") + "/rest/v1/" + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(full, data=data, method=method)
    r.add_header("apikey", key)
    r.add_header("Authorization", "Bearer " + key)
    r.add_header("Content-Type", "application/json")
    if method in ("POST", "PATCH"):
        r.add_header("Prefer", "return=representation")
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        sys.exit(f"Erro {e.code} em {method} {path}:\n{msg}")


def upsert_cliente(url, key, c):
    existente = []
    if c.get("cpfcnpj"):
        cpf = urllib.parse.quote(c["cpfcnpj"].strip(), safe="")
        existente = req(url, key, f"clientes?select=id,nome&cpfcnpj=eq.{cpf}")
    if not existente and c.get("nome"):
        nome_q = urllib.parse.quote(c["nome"].strip(), safe="")
        existente = req(url, key, f"clientes?select=id,nome&nome=ilike.{nome_q}")
    if existente:
        cid = existente[0]["id"]
        print(f"Cliente ja existe ({existente[0]['nome']}) — atualizando id {cid}")
        req(url, key, f"clientes?id=eq.{cid}", method="PATCH", body=c)
        return cid
    novo = req(url, key, "clientes", method="POST", body=c)
    cid = novo[0]["id"]
    print(f"Cliente criado: {c.get('nome')} — id {cid}")
    return cid


def upsert_obra(url, key, o, cliente_id):
    o = dict(o)
    o["cliente_id"] = cliente_id
    existente = []
    if o.get("nome"):
        nome_q = urllib.parse.quote(o["nome"].strip(), safe="")
        existente = req(url, key, f"obras?select=id,nome&nome=ilike.{nome_q}")
    if existente:
        oid = existente[0]["id"]
        print(f"Obra ja existe ({existente[0]['nome']}) — atualizando id {oid}")
        req(url, key, f"obras?id=eq.{oid}", method="PATCH", body=o)
        return oid
    nova = req(url, key, "obras", method="POST", body=o)
    oid = nova[0]["id"]
    print(f"Obra criada: {o.get('nome')} — id {oid}")
    return oid


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python cadastro_gestor.py <spec.json>")
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    url, key = ler_credenciais()
    cliente = spec.get("cliente")
    obra = spec.get("obra")
    if not cliente:
        sys.exit("spec.json precisa do bloco 'cliente'.")
    cid = upsert_cliente(url, key, cliente)
    if obra:
        oid = upsert_obra(url, key, obra, cid)
        print(f"\nPronto: cliente {cid} / obra {oid}")
    else:
        print(f"\nPronto: cliente {cid} (spec nao trouxe bloco 'obra')")


if __name__ == "__main__":
    main()
