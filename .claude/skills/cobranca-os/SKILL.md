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

Separe a entrega em dois blocos: cobranças a enviar e pendências internas.

## Passo 4 — Montar o dossiê e gerar o PDF

**A entrega principal desta rotina é o PDF.** É nele que o usuário decide.

Escreva os textos num dossiê JSON e renderize:

```bash
py rotinas/relatorio_pdf.py <dossie.json> "G:\Meu Drive\EMPRESA\AJ TopoGeo\_ROTINAS\COBRANCA\AAAA-MM-DD-cobranca.pdf"
```

Guarde o JSON no scratchpad da sessão, não no Drive — ele é intermediário.
O modelo da rodada anterior está em `rotinas/exemplo-dossie.json`.

Estrutura do dossiê:

| Campo | Conteúdo |
|---|---|
| `resumo` | `os_abertas`, `total_travado`, `valor_cobrancas`, `valor_internas` |
| `nota_topo` | uma frase situando a rodada e o delta da semana anterior |
| `cobrancas[]` | `titulo`, `valor`, `contato`, `os[]`, `contexto`, `mensagem`, `alerta`, `dica` |
| `internas[]` | `titulo`, `valor`, `os[]`, `texto`, `acao` |
| `observacoes[]` | `titulo`, `texto` — padrões da carteira, não casos isolados |
| `proxima_semana[]` | perguntas objetivas para a rodada seguinte |

Cada `os[]` leva `numero`, `desc`, `valor`, `dias`, `status`.

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
