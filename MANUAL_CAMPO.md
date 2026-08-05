# Manual de Uso — App de Campo (AJ TopoGeo)

> Aplicativo web (PWA — Progressive Web App) usado pelos operadores em campo para bater ponto, assumir e movimentar Ordens de Serviço, lançar gastos e abastecimentos, e fazer o checklist diário do veículo. Roda no navegador do celular, funciona **offline** (guarda tudo localmente e sincroniza quando volta o sinal) e usa o mesmo login e o mesmo banco de dados (Supabase) do Gestor.
>
> Arquivo-fonte: `campo/index.html`.

📸 *[Print sugerido: tela de login do app de Campo — campos "E-mail" e "Senha", botão "Entrar"]*

---

## 1. Como acessar

1. Abra o endereço do app de Campo no navegador do celular (o mesmo domínio do site, na pasta `/campo/`).
2. Informe o **e-mail** e a **senha** cadastrados (é o mesmo login usado no Gestor — não existe cadastro de usuário dentro do app de Campo).
3. Se aparecer uma barra oferecendo **instalar o app** (ícone na tela inicial), você pode aceitar — funciona como um aplicativo normal, sem precisar abrir o navegador toda vez.
4. Para sair, toque no ícone de logout (seta saindo de uma porta) no canto superior do app.

O app tem 4 abas fixas na parte de baixo da tela:

| Aba | Ícone | Para que serve |
|---|---|---|
| **Agenda** | calendário | Compromissos futuros (a tela que abre por padrão) |
| **Executar** | prancheta | Lista de Ordens de Serviço para abrir, assumir e movimentar |
| **Ponto** | localização | Bater ponto (abrir/fechar o expediente do dia) |
| **Veículo** | carro | Abastecimento e checklist diário do veículo |

---

## 2. Aba Agenda

Mostra os **compromissos futuros ainda não concluídos**, agrupados por data (hoje aparece destacado como "Hoje"). Cada cartão mostra título, tipo de compromisso e, se houver, o número da OS vinculada.

- Toque em um compromisso vinculado a uma OS para abrir direto a tela daquela OS.
- Essa lista vem do mesmo cadastro de **Agenda** do Gestor — o app de Campo não tem um formulário próprio para criar compromissos novos, é só leitura.

---

## 3. Aba Ponto (bater ponto / expediente)

O "ponto" é o **expediente do dia**, independente de qual OS você vai trabalhar. Você precisa ter o ponto batido para poder assumir qualquer OS.

### 3.1 Iniciar o expediente ("Bater ponto")

1. Na aba **Ponto**, toque em **"Bater ponto (iniciar expediente)"**.
2. Selecione o **veículo** que vai usar (opcional, lista vem do cadastro de Frotas do Gestor).
3. Tire a **foto de entrada** (obrigatória — botão "Tirar foto").
4. A localização (GPS) é capturada automaticamente.
5. Escreva uma observação se quiser (opcional).
6. Toque em **"Iniciar expediente"**. A data/hora são registradas automaticamente pelo sistema, não dá pra digitar.

Enquanto o expediente estiver aberto, a tela de Ponto mostra: horário de entrada, veículo selecionado, e qual OS está assumida no momento (se houver).

### 3.2 Encerrar o expediente

1. Toque em **"Encerrar expediente"**.
2. **Regra importante:** só é possível encerrar se **nenhuma OS estiver assumida no momento** — se você estiver com uma OS assumida, o sistema avisa "Conclua a OS ... antes de encerrar o expediente" e bloqueia o botão.
3. Tire a **foto de saída** (obrigatória), confira a localização e escreva uma observação se quiser.
4. Toque em **"Encerrar"**.

---

## 4. Aba Executar (Ordens de Serviço)

Lista as Ordens de Serviço disponíveis para abrir/movimentar. Por padrão mostra **todas** as OS em aberto; toque no botão **"Todas / Minhas"** no topo para filtrar só as OS onde você aparece como responsável.

> A OS que você está executando agora aparece destacada com a etiqueta **"Você está aqui"**.

### 4.1 Abrir uma OS

Toque no cartão da OS na lista para ver os detalhes: tipo de serviço, valor orçado, responsável, dados do cliente (com botões de **Ligar** e **WhatsApp** direto), localização (com botão para abrir no mapa), observações, totais de equipe/despesas gastos naquela OS, e o histórico de andamento (últimos registros).

Na parte de baixo da tela da OS ficam os botões de ação:

- **Movimentar** — muda o status da OS e/ou registra uma anotação (disponível sempre, independente de a OS estar assumida ou não).
- **Gasto** — lança uma despesa vinculada a essa OS (disponível sempre).
- **Assumir OS** *(se ninguém a assumiu ainda)* **ou** **Concluir OS** *(se for você quem está com ela assumida agora)*.

### 4.2 Movimentar (mudar status / registrar anotação)

1. Na tela da OS, toque em **Movimentar**.
2. Escolha o **novo status** (a lista tem todas as etapas do fluxo — desde "Agendada" e "Logística / Preparação" até "Protocolada", "Encaminhada para Medição", "Concluída" etc. — a mesma lista usada no Gestor).
3. Escreva uma **anotação** sobre o que aconteceu (obrigatória se você não mudar o status).
4. Toque em **Salvar**.

Isso fica registrado no histórico de "Andamento" da OS e sincroniza com o Pipeline e a Agenda do Gestor automaticamente (quando há sinal).

### 4.3 Assumir uma OS

1. Toque em **Assumir OS**.
2. Informe o **km inicial** (opcional — indo para a obra; se você já selecionou um veículo no Ponto, o km atual dele vem pré-preenchido).
3. Toque em **Assumir**.

**Regras:**
- Só é possível assumir uma OS se o **expediente (Ponto) estiver aberto**.
- Só é possível ter **uma OS assumida por vez** — para assumir outra, primeiro conclua a atual.
- Se outra pessoa já assumiu aquela OS, o sistema avisa quem está com ela e bloqueia.
- Ao assumir, o status da OS muda automaticamente para **"Em campo"** (se estava "Agendada").

### 4.4 Concluir a OS assumida

1. Na OS que você assumiu, toque em **Concluir OS**.
2. Informe o **km final** (opcional — não pode ser menor que o km inicial informado ao assumir).
3. Toque em **Concluir**.

Isso libera você para assumir outra OS ou encerrar o expediente, atualiza o hodômetro do veículo (se km final foi informado) e registra o km rodado no turno.

### 4.5 Lançar um gasto

1. Na tela da OS, toque em **Gasto**.
2. Preencha: **Categoria** (Combustível, Alimentação, Pedágio, Estadia/Hospedagem, Material de Campo, Transporte/Frete, Manutenção de Equipamento, Aluguel de Equipamento, Terceiro/Subcontratado, Taxas e Emolumentos, Outros), **Tipo de custo** (Diária, Hora, Empreitada), **valor**, e demais dados do formulário.
3. Salvar — o gasto entra no financeiro do Gestor (tabela de Pagamentos) já vinculado a essa OS.

---

## 5. Aba Veículo

Tem duas sub-abas: **Abastecimento** e **Checklist do dia**.

### 5.1 Abastecimento

1. Selecione o **veículo** (obrigatório).
2. Informe **km/horímetro** atual, **hora**, **local/posto** (com botão para capturar por GPS).
3. Informe **litros** (opcional, usado pra calcular consumo) e o **valor total** (obrigatório).
4. Marque se o **tanque ficou cheio** (usado no cálculo de consumo) e se deve **lançar também no financeiro** (categoria Combustível) — ambos vêm marcados por padrão.
5. Toque em **"Registrar abastecimento"**.

### 5.2 Checklist do dia

Confira o veículo antes de sair, item por item (óleo, água, combustível, pneus, estepe, freios, luzes, buzina, retrovisores, palhetas, cinto, documento CRLV, kit de segurança, limpeza geral):

1. Selecione o **veículo** — se já existe um checklist feito hoje para ele, o sistema avisa.
2. Informe o **km/horímetro atual**.
3. Para cada item, toque em **✓** (OK) ou **⚠** (problema) — todos começam marcados como OK.
4. Escreva **observações** sobre qualquer problema encontrado.
5. Tire uma **foto** (opcional).
6. Toque em **"Salvar checklist do dia"**.

---

## 6. Como funciona o modo offline

O app foi feito para funcionar em campo, onde nem sempre há sinal:

- As últimas listas (Agenda, OS para Executar) ficam salvas no celular; se você abrir sem sinal, vê um aviso **"Offline — mostrando a última lista baixada"**.
- Qualquer ação (bater ponto, assumir/concluir OS, movimentar, lançar gasto, abastecimento, checklist) pode ser salva **mesmo sem sinal** — o sistema mostra "Salvo offline — sincroniza ao pegar sinal" e guarda a ação numa fila local.
- Assim que o celular pegar sinal de novo, a fila é enviada automaticamente para o banco de dados.
- **Atenção:** para conseguir abrir uma OS específica offline, é preciso ter aberto ela **uma vez com sinal** antes — só assim ela fica salva no cache do celular.

---

## 7. Perguntas frequentes

**Não aparece a OS que eu preciso na aba Executar.**
Confira se o filtro está em "Todas" (não "Minhas") e se a OS não está com status "Concluída", "Cancelada" ou "Recebido" — essas não aparecem na lista de execução por já estarem fechadas.

**Não consigo encerrar o expediente.**
Você precisa concluir a OS que está assumida primeiro (o app mostra o aviso com o número dela).

**Não consigo assumir uma OS.**
Confira se o Ponto está aberto (bata o ponto primeiro) e se você já não está com outra OS assumida.
