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

O diário é colado do WhatsApp e vem com sujeira junto: caractere invisível
antes do item de gasto e menção de quem foi marcado na mensagem
(`@Fulano`). O script descarta a menção — ela não pode entrar no andamento,
que é documento de obra e sai no relatório da OS.

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
| Combustível, diesel, posto | `pagamentos` | Combustível |
| Alimentação, almoço, lanche | `pagamentos` | Alimentação |
| Pedágio | `pagamentos` | Pedágio |
| Frete, balsa, estacionamento | `pagamentos` | Transporte / Frete |
| Borracharia, pneu, conserto | `pagamentos` | Manutenção de Equipamento |
| Estacas, marcos, tinta | `pagamentos` | Material de Campo |
| Bateria, GPS, drone, trena | `pagamentos` | Equipamentos |
| Cartório, taxa, certidão | `pagamentos` | Taxas e Emolumentos |

Todas entram como **Pago**, com vencimento e pagamento na data do campo.

**Adiantamento não é gasto.** A equipe anota junto dos gastos o dinheiro que
saiu para a viagem e o que sobrou dele — "Pix viagem: R$400", "SALDO: +108,40".
Isso é movimento de caixa: o custo da obra são os itens que o adiantamento
pagou, e somar os dois conta o mesmo dinheiro duas vezes. O script separa
essas linhas e as reporta à parte. Saldo que ficou com quem foi a campo se
acerta no caixa, não na OS.

Essas categorias são as que o banco **já usa**, não as do `<select>` do
formulário — o Gestor tem "Pedágio", "Material de Campo" e "Manutenção de
Equipamento" gravadas, e nenhuma aparece no dropdown. Não se guie pelo
formulário: gasto de campo em "Outros" vai parar junto de contabilidade e
seguro, que é o que mora nessa categoria.

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

### Data não é chave

Duas equipes saem a campo no mesmo dia, em OS diferentes, às vezes do mesmo
cliente. Um diário de 11/07 em Maracaju não invalida outro de 11/07 em São
Gabriel, e despesa lançada numa data **não** prova que o dia pertence àquela
OS.

Nunca conclua que um lançamento está com data errada porque "não combina"
com o diário que você tem na mão — pode ser da outra equipe. Foi exatamente
o erro que a rotina quase cometeu: um pedágio de 11/07 pareceu ser de 07/07
com data trocada, e era da segunda equipe. Pergunte antes de mover qualquer
lançamento de data.

A mesma OS também recebe **dois diários no mesmo dia** — manhã e tarde,
serviços diferentes. Por isso a marca leva a hora de chegada:
`[diário 14/07/2026 08:20]`. Diário repetido colide na marca cheia e é
bloqueado; diário novo do mesmo dia só avisa que já existe outro, e vai com
`--forcar` depois que o usuário confirmar que foi outro turno.

### Gasto rateado entre OS

Uma despesa única pode ter sido dividida entre duas OS — uma refeição de
R$ 54,00 lançada como R$ 27,00 em cada. Quando o mesmo valor aparecer em
dois diários do mesmo dia, **não presuma duplicidade**: procure o valor em
`pagamentos` na data, em todas as OS. Se só existir uma metade, lançar a
outra completa o gasto em vez de duplicá-lo. A soma final tem que bater com
a nota real — foi assim que a alimentação de 14/07 fechou em R$ 54,00.

## Quando o serviço não tem OS

Acontece de o campo sair antes do sistema: cliente novo, combinado no
telefone, nenhum orçamento lançado. O diário chega sem número de OS e o
cliente não existe no cadastro.

Nesse caso **pergunte os dados ao usuário** e crie a cadeia inteira —
cliente → orçamento → OS — antes de lançar o diário. Nunca invente valor,
nunca cadastre cliente com nome parcial "para resolver depois".

O que perguntar, e o que não perguntar:

| Dado | Como obter |
|---|---|
| Valor combinado | **Só o usuário sabe.** Sem ele não há orçamento nem OS. Ofereça como referência os valores que ele já pratica naquele tipo de serviço — a mediana e o mais frequente, consultados no banco |
| Nome completo | Pergunte. O diário traz o nome curto de campo, e é o nome cheio que vai em contrato, NF e ART |
| Telefone | Pergunte. Sem ele a OS entra na `/cobranca-os` sem contato |
| CPF/CNPJ | Pergunte, mas não trave por isso — o cadastro funciona sem, e a falta só pesa na NF e no contrato |
| Tipo da OS | Ofereça a lista real de `OS_TIPOS` do Gestor, com a sua recomendação |
| Status inicial | O serviço já foi executado, então "Agendada" quase nunca é a resposta certa. Diga o que cada opção implica: "Concluída" tira a OS do radar de faturamento, "Gerar NF" a mantém na fila |
| Cidade, local, serviço, data | **Não pergunte** — já estão no diário |

Peça em pergunta estruturada, com opções, sempre que a resposta for
enumerável. Valor, telefone, CPF e nome são texto livre: peça em texto, e
confira se a resposta veio mesmo com o dado — escolher a opção "vou informar
agora" não traz o número junto.

```bash
py rotinas/diario_bordo.py <scratchpad>/diario.txt --criar-os \
   --cliente "Nome Completo" --telefone "67 99999-8888" \
   --valor 400,00 --tipo "Locação de Obras" --status "Concluída" \
   --pagamento "À vista" --aplicar
```

O script numera igual ao Gestor (`ORC-<ano>-<seq>`, `OS-<MES>-<seq>`, sempre
do mês corrente), cria o orçamento já **Aprovado** — é registro retroativo de
combinação que nunca passou pelo sistema — preenche `os_gerada` e só então
lança o diário na OS nova.

**Cliente que já está na carteira** — caso de OS nova para cliente antigo —
usa `--cliente-existente`, que reaproveita o cadastro em vez de criar outro.
Exige que exatamente um cadastro case com o nome; com dois ou nenhum, para.

**Deslocamento é item próprio**, não embutido no valor do serviço:
`--km 375` acrescenta "Mobilização e Desmobilização de Equipe" a **R$ 1,50/km**
— a taxa é a mesma em todos os orçamentos da carteira que cobram km. Quando o
usuário disser "1500 + 375 km", são R$ 1.500,00 de serviço mais R$ 562,50 de
deslocamento, total R$ 2.062,50. Confirme a leitura antes de gravar: "375"
também pode ser reais, e a diferença é de quase R$ 200.

**Cliente parecido bloqueia.** Se já existir cadastro com nome que encaixe no
informado, o script para. Cadastro duplicado divide as OS do mesmo dono em
dois donos e quebra o histórico. Confirme com o usuário se é a mesma pessoa;
se for, use `--os` com a OS existente em vez de criar outra.

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

O diário costuma chegar dias depois, e o acerto pode já ter acontecido.
Nesse caso acrescente `--reembolso-pago 18/07/2026`: entra como **Pago**, com
o vencimento no dia do campo — quando a dívida nasceu — e a data do acerto em
`data_pagamento`. Sem essa separação o caixa mostra a saída no dia errado.

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

## Reprocessar dia antigo — `--so-andamento`

Dia em que o financeiro já foi lançado à mão, e só o andamento está pobre
("11/07 — Levantamento Planialtimétrico", sem horário nem pendência):

```bash
py rotinas/diario_bordo.py <scratchpad>/diario.txt --os OS-JUN-025 \
   --so-andamento --aplicar
```

Grava só o andamento. Não toca em `custos_os` nem em `pagamentos`, e a
checagem de duplicata passa a olhar apenas a marca `[diário dd/mm/aaaa]` —
o financeiro daquele dia existir é o esperado, não o sintoma.

**Isso exige o diário original.** Horário, pendência e observação não estão
em lugar nenhum do sistema: reconstruir a partir da OS só recupera data,
serviço e gastos. Peça o texto do WhatsApp ao usuário. Se ele não tiver
mais, diga o que dá para recuperar e o que vai faltar, e deixe **ele**
decidir se vale — não preencha horário por estimativa. Um andamento com
hora inventada é pior que um andamento curto: ele parece registro de campo.

## Lançar o item que faltou — `--so-gasto`

O complemento do anterior: o dia já tem andamento e quase todo o financeiro,
e falta um item. `--forcar` relançaria o dia inteiro e dobraria o resto.

```bash
py rotinas/diario_bordo.py <scratchpad>/diario.txt --os OS-JUN-025 \
   --so-gasto pedagio --aplicar
```

Lança só os gastos cuja descrição casa com o texto (pode repetir a opção) e
**não toca no andamento**. A checagem de duplicata muda de critério: em vez
de olhar a data, compara o **valor** com o que já está lançado ali — a
descrição varia entre o Gestor ("Pedagio") e o diário ("Pedágios"), o valor
não.

Depois de completar, rode `--so-andamento` só para ler a conferência: ela
tem que fechar diário = lançado. Foi assim que 07/07 da OS-JUN-025 saiu de
R$ 189,54 para os R$ 220,14 do diário.

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
