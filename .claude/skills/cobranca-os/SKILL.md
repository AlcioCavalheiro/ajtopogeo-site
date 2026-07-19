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

O script lê `.env.local`, consulta `ordens` e `recebimentos` no Supabase e
ordena por score (valor **em aberto** 40% + dias parada 35% + proximidade de
conclusão 25%).

Variações úteis:
- `--min-dias 15` — ignora o que mexeu na última quinzena
- `--dossie <arquivo>` — grava a base factual do PDF (ver Passo 4)
- `--json` — dados crus

Se der erro de `.env.local`, pare e avise o usuário. Não tente contornar
consultando com a chave anônima: o RLS devolve lista vazia e você vai
concluir, erradamente, que não há OS parada.

### Valor em aberto, nunca valor da OS

O que importa é **contratado menos já recebido**. A maioria das OS é paga em
duas partes (50% na assinatura), então o valor cheio superestima a dívida em
quase o dobro. Toda cifra que você citar — no PDF, no texto da mensagem ou na
conversa — é o saldo em aberto.

OS com saldo zero continuam na lista quando ainda estão abertas, marcadas como
quitadas. Elas **não são cobrança**: a pendência é de entrega. Tratar como
cobrança é constrangedor com quem já pagou.

### Recebimentos sem vínculo

Só são abatidos os recebimentos com `os_id`. Os que estão soltos (ligados por
texto livre em `descricao`) voltam numa lista separada e **nunca devem ser
atribuídos por semelhança de nome ou valor**. Um cliente pode ter várias OS do
mesmo valor — casar por coincidência leva a cobrar quem já pagou, que é o pior
erro possível desta rotina.

Quando um recebimento solto puder corresponder a uma OS da lista, diga isso no
alerta do card e mande conferir o extrato antes de qualquer contato.

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

Separe a entrega em dois blocos: cobranças a enviar e pendências internas.

## Passo 4 — Montar o dossiê e gerar o PDF

**A entrega principal desta rotina é o PDF.** É nele que o usuário decide.

Primeiro gere a base factual, depois escreva a narrativa por cima dela:

```bash
py rotinas/os_paradas.py --dossie <scratchpad>/base.json
# preencha cobrancas / internas / observacoes / proxima_semana / nota_topo
py rotinas/relatorio_pdf.py <scratchpad>/dossie.json "G:\Meu Drive\EMPRESA\AJ TopoGeo\_ROTINAS\COBRANCA\AAAA-MM-DD-cobranca.pdf"
```

Guarde os JSON no scratchpad da sessão, **nunca no repo**: eles têm nome,
telefone e valor de cliente, e o repositório é público. O modelo de estrutura
(fictício) está em `rotinas/exemplo-dossie.json`.

O `--dossie` já preenche sozinho:

| Campo | Conteúdo |
|---|---|
| `resumo` | `os_abertas`, `contratado`, `recebido`, `em_aberto` |
| `todas_os[]` | **todas** as OS em aberto, ordenadas por prioridade |
| `recebimentos_sem_os[]` | os lançamentos não conciliados |

Você escreve:

| Campo | Conteúdo |
|---|---|
| `nota_topo` | uma frase situando a rodada e o delta da semana anterior |
| `cobrancas[]` | `titulo`, `valor`, `contato`, `os[]`, `contexto`, `mensagem`, `alerta`, `dica` |
| `internas[]` | `titulo`, `valor`, `os[]`, `texto`, `acao` |
| `observacoes[]` | `titulo`, `texto` — padrões da carteira, não casos isolados |
| `proxima_semana[]` | perguntas objetivas para a rodada seguinte |

Cada `os[]` leva `numero`, `desc`, `valor` (em aberto), `dias`, `status`.

O PDF sai com a lista completa das OS e os recebimentos não conciliados
automaticamente — você não precisa repetir isso na narrativa. Use os cards
para o que exige decisão.

Regras de preenchimento:

- `mensagem` é o texto literal que vai para o WhatsApp. Sem markdown, sem
  HTML — ela é renderizada como está e o usuário copia daí.
- `alerta` (vermelho) é para quando o motivo da parada **não está confirmado**
  no dado. Todo caso em que você inferiu algo precisa de alerta.
- `dica` (âmbar) é para oportunidade: agrupar cobranças, emitir NF antes, etc.
- Nos campos de narrativa (`nota_topo`, `contexto`, `texto`, `acao`, `alerta`,
  `dica`, `observacoes.texto`) pode usar `<b>` e `<i>`. Nos demais, não — eles
  são escapados porque vêm do banco.

Cada card sai no PDF com uma linha de decisão para marcar: enviar como está,
ajustar, não enviar, já resolvido.

## Passo 5 — Registrar

Salve também a versão markdown ao lado do PDF, mesma pasta e mesmo nome:

```
G:\Meu Drive\EMPRESA\AJ TOPOGEO\_ROTINAS\COBRANCA\AAAA-MM-DD-cobranca.md
```

O PDF é para decidir; o markdown é para eu reler na semana seguinte e
montar o comparativo. Inclua nele o delta em relação ao arquivo mais recente
da pasta: quais avançaram, quais seguem paradas, quanto entrou. Esse delta é
o que dá sentido à rotina ser semanal.

## Limite

Você redige e salva. **Você não envia.** O envio é sempre do usuário, mesmo
que ele diga "pode mandar" — não há canal de WhatsApp conectado aqui.
