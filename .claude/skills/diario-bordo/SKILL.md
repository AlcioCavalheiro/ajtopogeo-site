---
name: diario-bordo
description: Lança o diário de bordo de um dia de campo na OS correspondente do Gestor — registra o andamento, o custo de equipe e as despesas do dia. Use quando o usuário mandar um "Diário de Bordo" (data, local, cliente, OS, horários, serviços, gastos) ou pedir para lançar o dia de campo na OS.
---

# Rotina 3 — Diário de bordo → OS

Cadência: sob demanda, no fim de cada dia de campo. Objetivo: o custo real da
obra entrar no Gestor no dia em que aconteceu, não na hora de fechar a medição.

## Entrada

O usuário cola o diário no chat, no formato que a equipe manda do campo:

```
📋 Diário de Bordo – Data - 16/07/2026
📍Local: ...      👤Cliente: ...    📄OS: ...
🕒Hora chegada / 🕤Hora saida
✅ Serviços realizados / ⏳ Pendências
💰 Gastos do dia (com Total)
📝 Observações
```

Salve o texto **como veio** num arquivo no scratchpad da sessão. Ele tem nome de
cliente, local e valor: nunca no repositório, que é público.

Campo faltando não trava a rotina — só a data é obrigatória. O que faltar sai
sinalizado na prévia.

## Passo 1 — Prévia

```bash
py rotinas/diario_bordo.py <scratchpad>/diario.txt
```

Nada é gravado sem `--aplicar`. A prévia mostra a OS identificada, o texto do
andamento e cada lançamento que entraria em `custos_os` e em `pagamentos`.

Para onde vai cada gasto, seguindo a divisão que o próprio Gestor faz na tela
Financeiro da OS:

| Gasto | Destino | Como entra |
|---|---|---|
| Ajudante, diarista, auxiliar | `custos_os` | tipo **Diária**, sem funcionário vinculado, nome na observação |
| Combustível, diesel, posto | `pagamentos` | categoria Combustível, status Pago |
| Alimentação, almoço, lanche | `pagamentos` | categoria Alimentação, status Pago |
| Pedágio, manutenção, borracharia | `pagamentos` | categoria Outros |
| Estacas, marcos, bateria, tinta | `pagamentos` | categoria Equipamentos |
| Hospedagem | `pagamentos` | categoria Infraestrutura |

O ajudante entra em `custos_os` de propósito: é mão de obra da OS e precisa
somar no custo de pessoal da obra junto com a equipe fixa. Os diaristas não são
cadastrados em Funcionários, então `func_id` fica vazio e o nome vai na
observação — não cadastre ninguém para "resolver" isso sem o usuário pedir.

## O que fica registrado no andamento da OS

O andamento é o registro do dia — é o que se lê meses depois para justificar
prazo com o cliente e para fechar medição. Ele reproduz o diário na mesma ordem,
uma linha por bloco:

```
[diário 03/07/2026] · Campo em Sidrolândia · 06:15 às 17:00
Serviços realizados:
• Amarração dos vértices
• Conferência de cerca
Pendências: Falta o vértice P7, área alagada
Gastos do dia: R$ 1.630,00 — Diesel R$ 1.250,00; Guincho da caminhonete R$ 380,00
```

Serviço único sai na mesma linha do rótulo; vários saem em lista, um por linha.
Nunca junte os serviços do dia num parágrafo só — perde qual foi feito em qual
dia, que é justamente o que a medição precisa.

A marca `[diário dd/mm/aaaa]` na primeira linha é o que identifica o registro e
trava o relançamento do mesmo dia. Não a remova nem a edite.

Isso vale tanto na tela da OS quanto no PDF do relatório: `renderAndamentoList`
converte a quebra de linha em `<br>` e escapa HTML, e o `splitTextToSize` do
jsPDF já quebra em `\n`. Se um dia o andamento voltar a aparecer como parágrafo
corrido na tela, o que quebrou foi `andamentoHtml` em `gestor/index.html`.

## Passo 2 — Ler os avisos antes de aplicar

A prévia só é confiável depois que você tratou o que ela sinalizou:

- **⛔ OS identificada por nome de cliente, não pelo número.** O diário é escrito
  à mão em campo e traz "OS01" enquanto o Gestor usa "OS-JUL-009". O script
  **não grava** nesse caso. Mostre ao usuário qual OS ele encontrou e peça
  confirmação; só então rode com `--os <NÚMERO>`. Nunca confirme você mesmo por
  semelhança de nome: a carteira tem clientes com várias OS e nomes parecidos, e
  custo lançado na obra errada estraga o resultado das duas.
- **⛔ Já existe lançamento nesta OS nesta data.** Diário reenviado é comum.
  Confira no Gestor se é o mesmo dia antes de qualquer coisa; `--forcar` só
  quando o usuário disser que houve mesmo dois lançamentos.
- **⚠ Total declarado diferente da soma dos itens.** O total do diário é o
  fechamento de caixa da equipe. Divergência quase sempre é item esquecido ou
  valor digitado errado — pergunte, não escolha um dos dois números.
- **⚠ Categoria não reconhecida.** Caiu em Outros. Se for gasto recorrente, vale
  acrescentar a palavra em `DESTINO_GASTO` no script em vez de corrigir à mão
  toda vez.

Se a OS não for encontrada, o script lista candidatas e sai. Leve a lista ao
usuário; não escolha por proximidade de número.

## Passo 3 — Observações: o que é dinheiro de fora

O bloco 📝 Observações é texto livre e o script não o interpreta — **você** lê e
decide. O caso que aparece toda semana é gasto de campo pago pela conta pessoal
do sócio.

Quando isso acontecer, o gasto continua sendo custo da OS (entra normal), e a
parte que saiu do bolso vira um reembolso pendente da empresa:

```bash
py rotinas/diario_bordo.py <scratchpad>/diario.txt --os OS-JUL-009 \
   --reembolso 110,00 --reembolso-desc "Ajudante pago pela conta pessoal"
```

Isso cria um lançamento em `pagamentos`, categoria Pessoal, **status Pendente** —
some no fluxo de caixa como dívida da empresa com o sócio e some no Recebimentos
como conta a pagar. Não é custo novo da OS; o custo já está lançado à parte.

Duas conferências antes de passar o `--reembolso`:

- O valor é só a parte da conta pessoal, não o gasto inteiro. No exemplo, o
  ajudante custou R$ 120,00, dos quais R$ 110,00 saíram do pessoal — o reembolso
  é 110, o custo da OS é 120.
- Se a observação não separar quanto foi de cada conta, pergunte. Chutar a
  divisão coloca dívida errada no caixa.

Observação que não for sobre dinheiro (acesso à área, cerca, chuva, cliente
ausente) não vira lançamento — ela já entra no texto do andamento, e é ali que
tem valor na hora de justificar prazo com o cliente.

## Passo 4 — Aplicar

```bash
py rotinas/diario_bordo.py <scratchpad>/diario.txt --os OS-JUL-009 --aplicar
```

Grava o andamento na OS (marcado com `[diário dd/mm/aaaa]`, que é o que trava a
duplicata depois), os custos e as despesas. Confirme ao usuário o que entrou,
com os valores.

## Passo 5 — Status e pendências

O status da OS **não muda sozinho**. Depois de aplicar, olhe o campo Pendências
e proponha:

- Pendências "Nenhuma" e serviço concluído → sugira avançar (`--status` na mesma
  rodada, ou pelo Gestor). Quem decide é o usuário.
- Pendência que depende do cliente (documento, acesso, anuência) → isso é
  cobrança, não diário. Anote para a `/cobranca-os` de segunda.
- Pendência técnica de campo (vértice faltando, área alagada, retorno à área) →
  a OS continua em campo e o retorno precisa de agenda. Diga isso explicitamente
  em vez de deixar a pendência só dentro do andamento.

## Regra de ouro

Este é o único ponto onde dinheiro entra no Gestor sem passar pela tela do
sistema. Duas coisas nunca se resolvem por dedução: **qual OS** e **de qual
conta saiu o dinheiro**. Nas duas, pergunte. Um gasto no lugar errado só é
descoberto meses depois, quando o custo da obra não fecha com o que foi cobrado.
