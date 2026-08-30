# Manual de Uso — Gestor (AJ TopoGeo)

> Sistema web de gestão da AJ TopoGeo: cadastros, orçamentos, contratos, ordens de serviço, financeiro, medições e um conjunto de ferramentas de topografia/georreferenciamento. Todo o sistema roda em uma única página (`gestor/index.html`), com Supabase como banco de dados, e é acessado pelo navegador (computador ou celular).
>
> Este manual segue a ordem do menu lateral. Onde não foi possível capturar uma tela real do sistema (login com usuário/senha do banco de dados não disponível no momento da escrita), há uma indicação **📸 [Print sugerido: ...]** descrevendo exatamente o que a captura deveria mostrar — pode ser inserida depois.

---

## Sumário

1. [Login e visão geral](#1-login-e-visão-geral)
2. [Dashboard](#2-dashboard)
3. [Agenda](#3-agenda)
4. [Pendências](#4-pendências)
5. [Ordens de Serviço](#5-ordens-de-serviço)
6. [Clientes](#6-clientes)
7. [Obras](#7-obras)
8. [Serviços](#8-serviços)
9. [Orçamentos](#9-orçamentos)
10. [Contratos](#10-contratos)
11. [Medições](#11-medições)
12. [Financeiro (Contas, Recebimentos, Pagamentos, Impostos, Folha, Notas Fiscais)](#12-financeiro)
13. [DRE / Resultado](#13-dre--resultado)
14. [Acompanhamento por Obra](#14-acompanhamento-por-obra)
15. [Controle Tributário](#15-controle-tributário)
16. [Ferramentas Geo](#16-ferramentas-geo)
17. [Rotinas Recorrentes](#17-rotinas-recorrentes)
18. [Documentos](#18-documentos)
19. [Funcionários](#19-funcionários)
20. [Frotas](#20-frotas)
21. [Ponto de Campo](#21-ponto-de-campo)
22. [Estabelecimentos](#22-estabelecimentos)
23. [Relatórios / PDF](#23-relatórios--pdf)
24. [Configuração](#24-configuração)

---

## 1. Login e visão geral

📸 *[Print sugerido: tela de login — campos "E-mail" e "Senha", botão "Entrar", logo AJ TopoGeo]*

O acesso é feito por e-mail e senha cadastrados no Supabase (mesmo login usado no app de Campo). Depois de entrar, o menu lateral esquerdo dá acesso a todos os módulos; o topo da tela tem uma barra de busca (que filtra a lista da página atual) e o botão de ação principal da página (ex.: "Novo Cliente", "Nova Obra").

📸 *[Print sugerido: tela inteira do sistema logado, mostrando o menu lateral completo e o Dashboard aberto]*

---

## 2. Dashboard

Tela inicial — visão geral do negócio: indicadores de OS por status, valores a receber (com destaque para os vencidos), atalho para o DRE, próximos agendamentos, alertas de pendências e rotinas recorrentes atrasadas. Cada indicador é clicável e leva direto para a tela correspondente (ex.: clicar em "A Receber" abre Recebimentos).

📸 *[Print sugerido: Dashboard completo, com os cartões de indicadores e a seção de próximos agendamentos]*

---

## 3. Agenda

Cadastro de compromissos (reuniões, prazos, entregas, tarefas de OS).

**Para criar um compromisso:**
1. Menu → **Agenda** → botão **Novo Compromisso**.
2. Preencha: **Título*** (obrigatório), **Tipo** (Geral/OS/Prazo/Reunião/Entrega), **Data*** (obrigatória), **Hora**, **OS Vinculada** (número, texto livre), **Responsável**, **Descrição**.
3. Salvar.

Itens de agenda vinculados a uma OS aparecem também na tela daquela OS e no app de Campo (aba Agenda), e alimentam a lista de **Pendências** quando vencem sem serem concluídos.

📸 *[Print sugerido: lista da Agenda com alguns compromissos, e o formulário "Novo Compromisso" aberto]*

---

## 4. Pendências

Painel somente leitura que reúne tudo que está **atrasado** no sistema: rotinas recorrentes vencidas, compromissos de agenda atrasados, pagamentos em atraso e projetos com documentos pendentes. Cada bloco tem atalhos diretos para resolver (Concluir, Editar, Pagar) sem precisar navegar até o módulo original. Quando não há nada pendente, mostra uma mensagem de "Nenhuma pendência!".

📸 *[Print sugerido: tela de Pendências com os blocos "Rotinas atrasadas", "Compromissos atrasados" e "Pagamentos em atraso" preenchidos]*

---

## 5. Ordens de Serviço

As OS **não são criadas diretamente** neste módulo — elas nascem automaticamente quando um **Orçamento é aprovado** (veja [seção 9](#9-orçamentos)). O botão "Novo" desta tela mostra esse aviso e não abre formulário.

### 5.1 Lista e filtros
A lista mostra **abas por status** (uma aba para cada etapa do fluxo: Agendada, Logística/Preparação, Em campo, Em andamento, Processamento, Desenho, Revisão Técnica, Análise Jurídica, Pendência Documental, Pronto para Protocolo, Protocolada, Encaminhada para Medição, Medição Realizada, NF Gerada, Recebido, Pronto para Enviar ao Cliente, Documentos Enviados ao Cliente, Concluída, Cancelada) — clique na aba para ver só as OS daquele status; a contagem de cada aba aparece no próprio rótulo. Ao mudar o status de uma OS, ela migra automaticamente para a aba correspondente. Há também filtro por Cliente, ordenação e busca por texto.

📸 *[Print sugerido: lista de Ordens de Serviço com as abas de status visíveis no topo e a tabela de OS abaixo]*

### 5.2 Abrir e editar uma OS
Clique em **Abrir** na linha da OS. A janela tem 4 abas:

- **Geral** — dados só-leitura (cliente, obra, responsável, orçamento de origem) + campos editáveis: **Data de Execução**, **Status da OS** (select com todo o fluxo), **Responsável(is)** (marcar funcionários), **Observações**.
- **Andamento** — histórico de anotações (texto + data/hora + autor); permite registrar nova anotação e agendar uma tarefa vinculada à OS. As tarefas agendadas ligadas à OS também aparecem aqui.
- **Checklist docs** — lista de documentos necessários, marcáveis como concluídos, com botão para adicionar itens extras.
- **Financeiro** — resumo de custos de equipe, despesas, recebimentos e saldo daquela OS especificamente.

Botões no rodapé: **Salvar alterações**, **Ordem de Serviço** (PDF resumido para levar a campo) e **Impressão Completa** (PDF com o financeiro incluso).

📸 *[Print sugerido: modal de uma OS aberta na aba "Geral", mostrando o select de Status e o campo Observações]*

---

## 6. Clientes

**Para cadastrar:** Menu → **Clientes** → **Novo Cliente**.

Campos: **Nome / Razão Social*** · **CPF/CNPJ** · **RG** · **Tipo** (PF/PJ) · **Profissão** · **Estado civil** (solteiro(a)/casado(a)/divorciado(a)/viúvo(a)/separado(a) judicialmente) · **Telefone** · **E-mail** · **Endereço** · Estado/Cidade (com busca automática de municípios) · **CEP** (busca automática de endereço ao digitar) · **Status** (Ativo/Inativo).

> RG, Profissão e Estado civil existem para alimentar automaticamente a qualificação do cliente pessoa física nos **Contratos** gerados (cláusula "Das Partes"). Ficam em branco = o contrato usa o texto padrão sem citar esses dados.

📸 *[Print sugerido: formulário "Novo Cliente" preenchido, destacando os campos RG, Profissão e Estado civil]*

---

## 7. Obras

Representa o imóvel/empreendimento onde o serviço será executado — vinculado a um cliente.

**Campos principais:** Nome da obra*, Tipo de obra (Georreferenciamento, Loteamento, Construção, Levantamento Planialtimétrico, Demarcação, Locação de Obras, Regularização Fundiária, Desmembramento, Incorporação Imobiliária, Infraestrutura Urbana, Outro), Cliente, Estado/Município, Endereço, **Área (ha)**, **Matrícula (CRI)**, **Tipo de cadastro do imóvel** (INCRA/SNCR para imóvel rural ou Prefeitura para imóvel urbano — muda os campos seguintes), **Código INCRA/SNCR** ou inscrição municipal, **CCIR**, **Comarca**, **Cartório de Registro de Imóveis**, **RT** (registro/ART do responsável técnico), Observações.

> Os dados da obra alimentam automaticamente várias Ferramentas Geo (Requerimentos, Memorial, Planilha SIGEF, Anuência de Limites, Mapa PDF) — vale a pena preencher com cuidado.

### 7.1 Vizinhos / Proprietários da obra
Na lista de Obras, botão **Vizinhos** abre um cadastro à parte com duas abas:
- **Proprietário(s)** do imóvel principal.
- **Vizinhos** (confrontantes) — cada um com pessoa(s) física(s)/jurídica(s), documento, estado civil, cônjuge (se casado), percentual de participação.

Esse cadastro alimenta a geração da **Anuência de Limites** e dos **Requerimentos**.

📸 *[Print sugerido: formulário de cadastro de Obra completo, e a tela de "Vizinhos" com um vizinho cadastrado]*

---

## 8. Serviços

Catálogo de serviços que podem ser adicionados como itens de um Orçamento.

**Campos:** Nome*, Categoria (Georreferenciamento, Levantamento, Locação, Nivelamento, Regularização Fundiária, Diárias, Deslocamento, Materiais, Outro), Unidade (ex.: serviço, ha, km), Valor unitário (R$), Descrição, Documentos gerados (lista separada por vírgula).

📸 *[Print sugerido: lista de Serviços cadastrados com valores]*

---

## 9. Orçamentos

### 9.1 Criar um orçamento
Menu → **Orçamentos** → **Novo Orçamento**.

1. **Cliente*** e **Obra/Imóvel** (a lista de obras é filtrada pelo cliente escolhido).
2. **Validade** da proposta.
3. **Responsável(is) pela execução** — marque um ou mais funcionários.
4. **Local/Endereço** e coordenadas (Latitude/Longitude), se souber.
5. **Status**: Rascunho, Enviado, Aprovado ou Recusado.
6. **Descrição/Objeto** — texto livre explicando o serviço (é isso que aparece no contrato depois, se o orçamento for vinculado a um).
7. **Itens do orçamento** — escolha um serviço no seletor "Adicionar serviço" (os campos de nome/unidade/valor vêm pré-preenchidos do cadastro de Serviços, mas são editáveis linha a linha); ajuste **quantidade** e **valor unitário**; o subtotal e o **total do orçamento** são calculados automaticamente. Pode remover itens com o ícone de lixeira.
8. **Forma de pagamento** — Modalidade (À vista, Parcelado, PIX, Boleto, Transferência, Cheque, Outro), Nº de parcelas, Observações de pagamento.
9. **Checklist de documentos necessários** — adicione itens que o cliente precisa entregar.
10. Salvar. O **número** (ORC-ano-NNN) é gerado automaticamente.

📸 *[Print sugerido: formulário de Novo Orçamento com pelo menos 2 itens adicionados na tabela e o total calculado]*

### 9.2 Aprovar e gerar a Ordem de Serviço
Ao abrir um orçamento com status **Aprovado**, aparece o botão **Criar OS** — ele gera a Ordem de Serviço automaticamente a partir dos dados do orçamento (cliente, itens, valor, responsáveis). É esse o único caminho para criar uma OS no sistema.

### 9.3 Gerar o PDF da proposta
Botão **Gerar PDF** (na lista ou dentro do orçamento) monta um PDF profissional: capa com número/validade, dados do cliente e da obra, tabela de itens com quantidade/valor unitário/subtotal, total, forma de pagamento, observações e página de assinatura.

📸 *[Print sugerido: primeira página do PDF de orçamento gerado, mostrando a capa e a tabela de itens]*

---

## 10. Contratos

### 10.1 Criar um contrato
Menu → **Contratos** → **Novo Contrato**.

1. **Orçamento de origem** — selecione um orçamento **Aprovado** na lista; ao escolher, o sistema preenche automaticamente **Cliente**, **Descrição/Objeto** (com o texto do próprio orçamento) e **Valor**.
2. Ajuste **Status** (Em andamento/Concluído/Cancelado) e **Observações** se necessário.
3. Salvar. O **número** (CTR-ano-NNN) é gerado automaticamente.

> O contrato guarda o **vínculo vivo** com o orçamento de origem — isso significa que, se depois você alterar os itens, valores ou a forma de pagamento no orçamento, o contrato reflete a mudança automaticamente na próxima vez que for visualizado ou que o PDF for gerado (não precisa recriar o contrato).

📸 *[Print sugerido: formulário de Novo Contrato logo após selecionar um orçamento de origem, mostrando os campos preenchidos automaticamente]*

### 10.2 Visualizar e gerar o PDF
Na lista de Contratos, botão **olho** abre um resumo (cliente, status, valor, recebido, saldo, e — se houver orçamento vinculado — o objeto e a tabela de itens/valores dele). Botão **Gerar Contrato** monta o PDF completo:

- Capa com número e nome do cliente.
- Cláusulas 1ª a 10ª (objeto, obrigações das partes, prazo de execução, preço e condições de pagamento — puxando a forma de pagamento do orçamento quando disponível —, descumprimento/rescisão, prazo e validade, LGPD, disposições gerais, foro).
- **Tabela de valores** do orçamento vinculado (serviço, quantidade, unidade, valor unitário, subtotal e total), logo após a cláusula do preço.
- Página de assinaturas (contratada e contratante) e testemunhas.

Se o cliente for pessoa física com **RG**, **Estado civil** e/ou **Profissão** cadastrados, esses dados entram automaticamente na qualificação do contratante.

📸 *[Print sugerido: PDF do contrato aberto na página da Cláusula Quinta, mostrando a tabela de valores do orçamento]*

---

## 11. Medições

Usadas para faturamento parcial/por etapas de uma obra (medições de andamento físico-financeiro).

### 11.1 Lista por status
A lista tem **abas por status**: Fechar Medição, Gerar NF, Falta Pagamento, Recebido — cada aba mostra só as medições daquele status, com a contagem no rótulo. Ao mudar o status de uma medição, ela migra de aba automaticamente.

📸 *[Print sugerido: lista de Medições com as 4 abas de status visíveis]*

### 11.2 Criar uma medição
Botão **Nova Medição**: Descrição*, Cliente, OS Vinculada, Valor*, % Executado, Status, Observações.

### 11.3 Gerar a planilha de medição (PDF)
Botão **Gerar PDF** monta a planilha no padrão da empresa, com os dados da OS vinculada, período e valores.

---

## 12. Financeiro

### 12.1 Contas Bancárias
Cadastro das contas/carteiras usadas para saber o saldo real. Campos: Banco/Nome*, Tipo (Conta Corrente, Poupança, Conta Digital, Investimento, Caixa), Saldo inicial, Agência, Conta, Cor (usada nos gráficos), Observação. **O saldo não é digitado depois** — ele é calculado automaticamente a partir dos Recebimentos e Pagamentos vinculados à conta.

### 12.2 Recebimentos
Contas a receber de clientes. Campos: Descrição*, Cliente, Valor*, Forma de pagamento, Vencimento, Data de recebimento, **OS Vinculada*** (obrigatória, a menos que marque "Receita avulsa — não pertence a nenhuma OS"), Conta movimentada, Status (Pendente/Recebido). A tela tem abas **A Receber** / **Recebidos**, com os vencidos destacados em vermelho.

> Sem vínculo com OS (e sem marcar avulsa), o valor não abate o saldo de nenhuma ordem e ela continua aparecendo como não paga na cobrança — o sistema bloqueia salvar nesse caso.

### 12.3 Pagamentos
Contas a pagar da empresa — reúne o que antes eram telas separadas (Contas Fixas, Saídas Variáveis, Passivo) em uma só, com sub-abas. Campos: Descrição*, Categoria (Combustível, Alimentação, Pessoal, Pró-labore, Salário, INSS/FGTS/IRRF Folha, Infraestrutura, Equipamentos, Software, Financiamento, Parcelamento Tributário, Impostos, Outros), Valor*, Vencimento, Data de pagamento, Juros/Multa (com cálculo automático do total efetivo), OS Vinculada, Conta movimentada, **Natureza** (Fixo = repete todo mês / Variável), Tipo de custo (OS/Operacional/Administrativo), Status, Competência, anexo de boleto/comprovante (PDF/imagem). Pode marcar **pagamento recorrente** para gerar vários meses de uma vez (número definido ou contínuo, 24 meses).

### 12.4 Impostos
Registro de tributos pagos: Tipo (Simples Nacional/DAS, INSS, IRPJ/CSLL, FGTS, ISS, IRRF, Outro), Valor*, Descrição, OS Vinculada (se não vincular, o valor pode ser distribuído entre as OS do mês), Data, Período de referência, comprovante em PDF.

### 12.5 Folha / Pró-labore
Visão filtrada dos Pagamentos nas categorias de folha (Pró-labore, Salário, INSS/FGTS/IRRF Folha), com indicadores de total pago no período. Lançar usa o mesmo formulário de Pagamentos.

### 12.6 Notas Fiscais
Campos: Número da NF*, Cliente, Valor*, Alíquota ISS % (calcula o valor do ISS automaticamente), OS Vinculada, Data de emissão, Status (Pendente/Emitida/Cancelada), anexo do PDF da NF.

📸 *[Print sugerido: tela de Pagamentos com as sub-abas "Contas Fixas / Saídas Variáveis / Por Mês" visíveis]*

---

## 13. DRE / Resultado

Demonstrativo de Resultado do Exercício — relatório (só leitura) do mês selecionado, cruzando Recebimentos, Pagamentos, Impostos e Custos de equipe para mostrar receita, despesas categorizadas e resultado do período. Selecione o mês no topo da tela.

📸 *[Print sugerido: DRE de um mês com receitas e despesas]*

---

## 14. Acompanhamento por Obra

Relatório (só leitura) por Ordem de Serviço: valor contratado × recebido × custos (pagamentos + equipe + impostos) = resultado, percentual já recebido e situação do próximo vencimento (em dia, vencendo, atrasado). Ajuda a enxergar rapidamente quais OS estão dando lucro e quais têm saldo em aberto.

---

## 15. Controle Tributário

Painel do Simples Nacional: calcula a **RBT12** (receita bruta dos últimos 12 meses), a **alíquota efetiva do DAS** conforme a faixa vigente, compara Anexo III × Anexo V, projeta os próximos 3 meses e gera alertas (ex.: proximidade de mudar de faixa). Alimentado pelos sub-cadastros:

- **Sócios** — nome, % de participação, status.
- **Registrar DAS** — competência, anexo aplicado, RBT12, Fator R, alíquota efetiva, valor estimado.
- **Registrar Retenção** — tipo (INSS/ISS/IRRF), valor retido, tomador do serviço, OS vinculada, se já foi compensada, se o tomador é órgão público.
- **Editar Faixa do Simples** — tabela de alíquotas por anexo/faixa de receita (parâmetros oficiais, normalmente não precisa mexer).

📸 *[Print sugerido: painel de Controle Tributário com o gráfico de alíquota histórica]*

---

## 16. Ferramentas Geo

Conjunto de 12 ferramentas técnicas de topografia, acessadas em abas dentro de **Ferramentas Geo**.

### 16.1 Conversor de Arquivos
Converte entre **KML**, **Shapefile (.zip)** e **DXF**. Para DXF é preciso informar o Datum e a Zona UTM do arquivo (coordenada projetada, não graus). DWG não é suportado — só DXF.

### 16.2 Conversor de Coordenadas
Converte coordenadas entre formatos (Decimal, GMS, UTM) e datums, por **entrada manual** (linha a linha) ou **arquivo TXT**. A cota Z, se informada, é só repassada (sem conversão de datum altimétrico).

### 16.3 Extrair Pontos DXF
Lê um arquivo DXF e exporta os pontos encontrados para TXT, com prefixo/numeração e código configuráveis, na ordem de colunas escolhida.

### 16.4 Pontos → Arquivo
Caminho inverso: lê um TXT de pontos (nome, E, N, Z), opcionalmente liga como perímetro fechado, e gera KML, Shapefile ou DXF.

### 16.5 Memorial Descritivo
Monta o texto do memorial descritivo a partir do cliente/obra selecionados (imóvel, proprietário, comarca, local, confrontantes e vértices).

### 16.6 Shape para CAR
Gera o shapefile no padrão exigido para o CAR (Resolução SEMAC nº 12/2014) a partir de um DXF de perímetro — contém só a geometria e o atributo CLASSE, sem elementos gráficos extras, conforme a norma.

### 16.7 Importar Memorial INCRA
Importa o **PDF do memorial descritivo** gerado pelo SIGEF/INCRA (precisa ser PDF com texto real, não escaneado) — extrai automaticamente o cabeçalho e a tabela de vértices, que alimentam as demais ferramentas (Anuência, DXF, Requerimentos).

> Na tabela de vértices importada há uma caixa de seleção por linha — **desmarque os pontos que não quer usar** antes de clicar em "Usar na Anuência de Limites" ou gerar o DXF: só os marcados são levados adiante.

### 16.8 Anuência de Limites
Gera o documento de anuência (.docx) entre o proprietário e um vizinho confrontante:
1. Selecione a **Obra** e o **Vizinho** (imóvel 2) — ambos vêm do cadastro de Vizinhos da Obra.
2. Marque quais **proprietários** assinam.
3. Confira/ajuste os **marcos** trazidos da aba "Importar Memorial INCRA" (pode marcar/desmarcar, o botão "Usar na Anuência de Limites" daquela aba já traz só os que estavam marcados lá).
4. Preencha ART/RT, credenciamento, responsável técnico, local/UF.
5. **Gerar Anuência (.docx)**.

### 16.9 Requerimentos
Gera 9 modelos de documento diferentes (Solicitação de Anuência, Requerimento ao Cartório, Cancelamento de Georreferenciamento no INCRA, Certidão Comprobatória, Certidão de Zoneamento, Procuração Particular, Declaração de Responsabilidade do Profissional, Declaração dos Proprietários, Declaração do art. 213 §14 II) a partir dos dados da Obra e dos Vizinhos/Proprietários cadastrados. Selecione o **Tipo de requerimento** e a **Obra**; os campos mudam conforme o tipo escolhido.

### 16.10 CAD
Editor de desenho: importa DXF/KML/Shapefile, permite criar/editar pontos por coordenada ou clicando no desenho, organizar em camadas, medir distâncias, desenhar polilinhas, ativar um fundo de satélite (Esri/Google/Sentinel-2), consultar parcelas do **INCRA** e do **CAR/SICAR** na área visível na tela, gerar o **Mapa de Perímetro em PDF A3**, e gerar **curvas de nível**.

**Curvas de nível:** no painel "Curvas de Nível", escolha a camada de pontos com cota (Z) real — normalmente pontos importados via TXT ou Reporte HTML de levantamento RTK/GNSS, não pontos criados manualmente — defina a equidistância (metros entre curvas) e clique em **Gerar curvas de nível**. O sistema avisa se houver poucos pontos ou se os pontos não tiverem variação de cota suficiente.

📸 *[Print sugerido: tela do CAD com um perímetro importado, camadas listadas à direita, e curvas de nível geradas sobre os pontos]*

### 16.11 Planilha SIGEF (.ods)
Preenche a planilha oficial do INCRA (.ods) com os dados do cliente/obra e a lista de vértices do perímetro (pode reaproveitar pontos já lançados na CAD), mantendo a formatação e as demais abas do modelo intactas.

### 16.12 Ponto do Maps
Cole um link do Google Maps ou coordenadas decimais para extrair a posição, opcionalmente com nome e cota Z, e exportar como TXT/arquivo topográfico.

### 16.13 Pastas para Monitor
Envia o desenho (linhas de plantio/pulverização ou limite de área) e escolhe a marca/modelo do monitor agrícola de bordo — o sistema gera um .zip já com a pasta e os nomes de arquivo certos para copiar direto no pendrive do monitor.

---

## 17. Rotinas Recorrentes

Checklist de tarefas que se repetem (ex.: conferir protocolos no INCRA todo mês). Campos: Nome*, Descrição, Frequência (Diária/Semanal/Quinzenal/Mensal/Trimestral/Anual), Responsável, Próxima execução. Rotinas vencidas aparecem em **Pendências** e no Dashboard; o botão **Concluir** já agenda a próxima ocorrência.

---

## 18. Documentos

Arquivo de documentos separado por dono e com cobrança automática dos que vencem todo mês.

**Abas:** *Pendências* (o que falta enviar), *Empresa*, *Funcionários* e *Sócios*. Nas duas últimas cada pessoa tem seu próprio cartão, com o botão **+ Documento** já vinculado a ela.

**Cadastro:** Nome*, **De quem é** (Empresa/Funcionário/Sócio) + a pessoa, Categoria, Número/Código, **Periodicidade**, Responsável, Observações.

- **Única** — documento com data de emissão, validade e um arquivo anexo (PDF, imagem, Word ou Excel). Entra em Pendências quando está vencido ou vence nos próximos 30 dias.
- **Mensal / Trimestral / Anual** — não tem arquivo único: tem **um arquivo por competência** (ASO, holerite, folha de ponto, guia do INSS, certidão negativa...). Informe *Cobrar a partir de* e o *Dia limite do envio* (padrão 10). Toda competência sem arquivo aparece como pendência — na aba **Pendências** desta tela e também na tela geral de **Pendências** — até alguém enviar o documento daquele mês. O botão de histórico (⟳) na linha mostra as últimas 24 competências, quais já foram enviadas e permite baixar ou enviar cada uma.

> Requer a migração `gestor/supabase/migrations/add_documentos_organizados.sql` no Supabase.

---

## 19. Funcionários

Cadastro da equipe: Nome*, Tipo (Funcionário/Diarista), CPF, Cargo, Telefone, E-mail, **Valor hora**, **Valor diária**, Data de admissão, Status (Ativo/Inativo). Esses valores são usados no lançamento de **Custo de Equipe** por OS (Financeiro da OS → funcionário, tipo de custo Hora/Diária/Empreitada, quantidade → total calculado automaticamente).

---

## 20. Frotas

Cadastro dos veículos usados em campo: Apelido/Nome*, Placa, Marca, Modelo, Ano, Tipo (Caminhonete/Carro/Moto/Caminhão/Máquina/Outro), Combustível, Cor, **Hodômetro atual**, Responsável, Status (Ativo/Em manutenção/Inativo/Vendido), RENAVAM, Observações. É esse cadastro que aparece nos seletores de veículo do app de Campo (Ponto, Abastecimento, Checklist).

---

## 21. Ponto de Campo

Painel **só leitura** que mostra os expedientes registrados pelo app de Campo: operador, veículo, quantas OS foram trabalhadas em cada turno, horário de entrada/saída, km rodado e status (em andamento/encerrado). Também mostra totais do mês (expedientes, km rodado, quantos estão em campo agora). Não tem cadastro manual — os dados vêm do app de Campo.

> Se aparecer o aviso "Ponto de Campo indisponível", é preciso rodar as migrations `add_atendimentos_campo.sql` e `add_campo_v3_turno.sql` no Supabase.

---

## 22. Estabelecimentos

Cadastro de postos, restaurantes e outros locais parceiros usados em campo: Nome*, Tipo (Posto/Restaurante/Material de Construção/Outro), Cidade, Telefone, Status (Ativo/Inativo), Observações.

---

## 23. Relatórios / PDF

Central para gerar (ou regerar) qualquer PDF do sistema sem precisar abrir o registro original: selecione o Orçamento, a OS (com opção "Ordem de Serviço" resumida ou "Impressão Completa"), o Contrato, ou vá direto para o DRE. Também é aqui que se carrega a **imagem da assinatura do técnico**, usada em todos os PDFs de orçamento.

---

## 24. Configuração

Tem dois cartões de dados da empresa:

- **Dados da empresa**: Nome, CNPJ, CFT, Responsável técnico, Cidade, Site, E-mail, Telefone.
- **Dados para Contratos** — usados especificamente na geração do PDF de Contratos (qualificação da CONTRATADA, assinatura e foro): **Razão social**, **Endereço/Sede completa**, **Nome do responsável (assinante)**, **Cargo**, **CPF do responsável**, **RG do responsável**, **Foro (comarca)**.

Cada cartão tem seu próprio botão **Salvar**. Também é aqui que fica o botão de **Sair** da conta.

> Essas configurações ficam salvas no navegador (localStorage), não no banco de dados — se acessar de outro computador/navegador, é preciso preencher de novo.

---

## Observações gerais

- **Colunas novas do banco de dados:** alguns campos adicionados recentemente (`clientes.rg`, `clientes.profissao`, `clientes.estado_civil`, `contratos.orcamento_id`) exigem rodar um comando `ALTER TABLE` uma única vez no SQL Editor do Supabase antes de usar — os comandos exatos estão comentados no próprio código-fonte (`gestor/index.html`, procure por `ALTER TABLE`). Se ao salvar aparecer o aviso "Salvo, mas sem o campo ... — essa coluna ainda não existe no banco", é esse o caso.
- **Vínculo com Orçamento:** vários módulos (Contratos, Ordens de Serviço) buscam os dados do orçamento de origem **ao vivo** a cada vez que são abertos — ou seja, alterar o orçamento depois reflete automaticamente nos documentos gerados a partir dele, sem precisar recriar nada.
