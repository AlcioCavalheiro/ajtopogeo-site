---
name: relatorio-os-orcamentos
description: Relatório geral de acompanhamento — uma ficha completa por OS aberta (andamento, cliente, valores) e a lista de orçamentos Enviados aguardando resposta do cliente. Use quando o usuário pedir "relatório de OS", "relatório de orçamentos", "status de tudo que está aberto", ou quiser um PDF único com o retrato completo da carteira.
---

# Rotina 8 — Relatório geral de OS e orçamentos

Sem cadência fixa: rode quando o usuário pedir um retrato completo da
carteira (reunião, fechamento de mês, ou só para conferir tudo de uma vez).
Diferente da [[cobranca-os]] (que prioriza e cura uma narrativa semanal),
aqui não há curadoria — é o dado completo, direto do Gestor.

## Passo 1 — Gerar o dossiê

```bash
py rotinas/relatorio_geral.py --dossie <scratchpad>/dossie.json
```

O script lê `.env.local`, consulta `ordens` e `orcamentos` no Supabase e monta
sozinho:

- `os_por_status` — **todas** as OS em aberto, agrupadas por status na ordem
  do fluxo técnico (Agendada → ... → Documentos Enviados ao Cliente; status
  fora desse mapa vão para o fim). Cada ficha já vem com cliente, contato,
  obra, tipo, contratado/recebido/em aberto, dias parada, responsável,
  origem (número do orçamento que a gerou) e o histórico de andamento
  (últimas 5 entradas, mais recente primeiro).
- `orcamentos_enviados` — só os orçamentos com status **Enviado**, aguardando
  resposta do cliente: número, cliente, valor, obra/local, data de emissão,
  dias desde o envio e se já passou da validade (`vencido`). Orçamentos
  Aprovados/Recusados/Rascunho/Finalizados não entram no relatório — só são
  usados internamente para achar a origem de cada OS.

Guarde o JSON no scratchpad da sessão, **nunca no repo** — tem nome, telefone
e valor de cliente, e o repositório é público.

Se der erro de `.env.local`, pare e avise o usuário — não contorne com a
chave anônima (o RLS devolve lista vazia e o relatório sairia vazio, não por
não haver dado, mas por falta de permissão).

## Passo 2 — Conferir antes de gerar o PDF

Dê uma olhada rápida no `--json` (ou no dossiê) antes de renderizar:

- Confira o total de `os_abertas` e `orcamentos_enviados` contra o que o
  usuário espera — um número muito fora do esperado costuma ser sinal de
  dado sem `cliente_id`/`obra_id` vinculado, não de erro do script.
- O texto de `historico` vem direto do campo `andamento` da OS, digitado no
  Gestor — reproduza como está, não reescreva nem resuma. Se estiver em
  CAIXA ALTA ou com erro de digitação, mantenha: é o registro original.
- Orçamentos com `vencido: true` só significa que passou a data de
  `validade` sem resposta — não é o mesmo que "recusado". Reporte como
  "validade vencida, sem retorno do cliente", não como recusa.

## Passo 3 — Renderizar o PDF

```bash
py rotinas/relatorio_geral_pdf.py <scratchpad>/dossie.json "G:\Meu Drive\EMPRESA\AJ TopoGeo\_ROTINAS\RELATORIO\AAAA-MM-DD-relatorio-geral.pdf"
```

O PDF sai em duas partes:

1. **OS em aberto** — separadas em seções por status (Agendada, Em campo,
   Processamento, Pendência Documental...), cada seção com o total em aberto
   do grupo. Dentro da seção, uma ficha por OS (não é tabela): cliente,
   contato, obra, contratado/recebido/em aberto e o andamento recente. É o
   "todas as informações importantes" pedido — não precisa complementar na
   narrativa.
2. **Orçamentos enviados** — tabela dos que aguardam resposta do cliente,
   com os dias desde o envio e o aviso de vencido em vermelho.

Não peça para escrever `cobrancas[]`/`internas[]` como na rotina de cobrança:
este relatório não tem cards de destaque nem narrativa manual — é o dado
completo, o usuário decide o que fazer a partir dele.

## Limite

Este relatório só reporta estado — não redige mensagem para cliente e não
marca nenhum orçamento como aprovado/recusado. Se o usuário quiser agir sobre
algo do relatório (cobrar, reenviar orçamento vencido), isso é um pedido à
parte, feito depois de ler o PDF.
