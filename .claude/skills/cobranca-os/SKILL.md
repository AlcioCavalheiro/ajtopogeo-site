---
name: cobranca-os
description: Rotina semanal de cobrança das OS paradas — puxa as ordens em aberto do Gestor, prioriza por valor/tempo/proximidade de conclusão e escreve os rascunhos de cobrança. Use quando o usuário pedir "cobrança das OS", "OS paradas", "o que está travado", ou rodar a rotina de segunda-feira.
---

# Rotina 1 — Cobrança das OS paradas

Cadência: toda segunda-feira, 20–30 min. Objetivo: destravar receita.

## Passo 1 — Puxar e priorizar

```bash
py rotinas/os_paradas.py --top 10
```

O script lê `.env.local`, consulta a tabela `ordens` do Supabase e ordena por score
(valor 40% + dias parada 35% + proximidade de conclusão 25%).

Variações úteis:
- `--min-dias 15` — ignora o que mexeu na última quinzena
- `--top 20` — semana de faxina
- `--json` — para cruzar com outra base

Se der erro de `.env.local`, pare e avise o usuário. Não tente contornar
consultando com a chave anônima: o RLS devolve lista vazia e você vai
concluir, erradamente, que não há OS parada.

## Passo 2 — Conferir antes de escrever

O campo `motivo_provavel` do relatório é **inferido do status**, não é fato.
Antes de redigir, confira o `ultimo_andamento` e as `obs` de cada OS. Se o
motivo real não estiver claro no dado, escreva o rascunho pedindo a informação
em vez de afirmar uma causa errada — cobrar alegando motivo errado queima
credibilidade com o cliente.

Cruze também com a semana anterior (ver Passo 4): se uma OS já foi cobrada e
não andou, o tom muda — é segunda cobrança, não primeira.

## Passo 3 — Redigir os rascunhos

Para cada uma das 5–10 primeiras, escreva uma mensagem curta de WhatsApp
(o canal real de contato do cliente), seguindo:

- Abertura direta, sem "espero que esteja bem".
- Uma frase situando: qual serviço, qual imóvel.
- O que está travando, em português de cliente — não em jargão de status
  do sistema. "Falta a matrícula atualizada" e não "OS em Análise Jurídica".
- **Uma** ação clara e específica pedida a ele, com prazo.
- Se o travamento for interno (Revisão Técnica, Desenho, Processamento),
  **não** é mensagem de cobrança: vira tarefa sua. Marque como `[INTERNO]`
  e liste como pendência de execução, não de cobrança.

Separe a entrega em dois blocos: `## Cobranças a enviar` e `## Pendências internas`.

## Passo 4 — Registrar

Salve o resultado em:

```
G:\Meu Drive\EMPRESA\AJ TOPOGEO\_ROTINAS\COBRANCA\AAAA-MM-DD-cobranca.md
```

Inclua no topo o comparativo com a semana anterior (arquivo mais recente na
mesma pasta): quais avançaram, quais seguem paradas, quanto entrou. Esse
delta é o que dá sentido à rotina ser semanal.

## Limite

Você redige e salva. **Você não envia.** O envio é sempre do usuário, mesmo
que ele diga "pode mandar" — não há canal de WhatsApp conectado aqui.
