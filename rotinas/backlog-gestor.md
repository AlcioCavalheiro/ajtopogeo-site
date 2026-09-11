# Backlog — Gestor AJ TopoGeo

Alimentado pela rotina `/checkpoint-gestor` toda sexta.
Sem dado de cliente neste arquivo — ele é versionado no Git.

**Último checkpoint:** 2026-09-10
**Escopo da semana atual (10 a 17/09):** 4 P1 fechados no mesmo dia do checkpoint — espólio,
campo/escritório + veículo obrigatório, confrontantes por trecho no CAD e conciliação de
recebimentos (parcial). Ver Histórico.

---

## P0 — Quebra fluxo

_vazio._

## P1 — Atrito

- **Recebimento em lote / parcial.** Hoje um recebimento aponta para uma única
  OS. Quando o cliente paga várias de uma vez (um PIX cobrindo três OS), não há
  como registrar sem escolher uma e deixar as outras abertas. Foi o que gerou
  boa parte dos lançamentos soltos que motivaram a conciliação de 2026-09-10.
- **12 recebimentos soltos sem identificador seguro (revisão manual).** Do
  levantamento de 2026-09-10: 7 são recebimentos antigos "Recebido" com
  descrição genérica (ex: "Efort", "Negrimaq", "Conceito") e várias OS
  candidatas do mesmo cliente — só dá para casar pela NF ou pela data, olhando
  um por um. 5 nem têm cliente vinculado no cadastro (ex: "Leonardo Campina",
  "TRANSFERÊNCIA — recebido da Sicredi") — parecem lançamento de importação
  bancária nunca completado. Lista completa dos IDs ficou fora deste arquivo
  (tem dado de cliente); pedir para o assistente refazer o levantamento
  (`recebimentos` com `os_id is null`) se for retomar.
- **F&B Participações — parcela prevista órfã.** 2 parcelas de R$ 3.250
  (venc. 08 e 09/2026) apontam para o orçamento ORC-2026-099, cuja única OS
  gerada (OS-JUL-019) está Cancelada. Provavelmente a cobrança não deveria
  mais existir — confirmar com o cliente/orçamento antes de excluir ou marcar
  como avulsa.

## P2 — Incremental

_vazio._

## P3 — Ideias / dívida técnica

- **Padrão de telas duplicadas (`rX` / `rXFixed`).** Várias páginas têm duas
  implementações no arquivo (`rConfig`/`rConfigFixed`, `rPendencias`/
  `rPendenciasFixed`, `rMedicao`/`rMedicaoFixed`, `rOS`/`rOSFixed`), e qual
  está ativa depende de uma linha `pageMap.x = yFixed` estar comentada mais
  adiante no arquivo. Já confundiu na hora de escrever o manual — a tela de
  Configuração real (`rConfigFixed`, ativa) tem mais campos que a `rConfig`
  "morta". Risco real: mexer na cópia errada não tem efeito nenhum no
  sistema. Não é tarefa de uma sexta — é candidata a uma semana dedicada só a
  limpar código morto, sem misturar com feature nova. (O par `rPipeline`/
  `rPipelineFixed` foi removido inteiro em 2026-08-16 junto com a Pipeline de
  Projetos — um a menos.)

---

## Histórico

| Data | Item | Commit |
|---|---|---|
| 2026-07-19 | Backlog criado junto com a estruturação das rotinas | — |
| 2026-07-19 | Recebimento passa a exigir OS vinculada, ou marcação explícita de receita avulsa | a seguir |
| 2026-08-05 | Primeiro checkpoint rodado: 4 itens levantados e confirmados no código (status Aguardando, Pipeline inacessível, função órfã, padrão Fixed) | — |
| 2026-08-05 | Status "Aguardando" trocado por "Processamento" em `campo/index.html` (linhas 1046 e 1068); as 6 OS que já estavam presas em "Aguardando" no banco (OS-JUL-020, OS-JUL-021, OS-AGO-001, OS-AGO-002, OS-AGO-004, OS-AGO-005) foram corrigidas via API do Supabase | a seguir |
| 2026-08-05 | Pipeline de Projetos reativado: `pageMap.pipeline` nunca tinha sido atribuído (achado só ao implementar — não era só falta de menu) foi adicionado ao `Object.assign(pageMap,...)`, e o item de menu voltou pro grupo "Produção" em `gestor/index.html` | a seguir |
| 2026-08-05 | Função órfã `preencherContratoPorOrca` removida de `gestor/index.html` (nunca era chamada; substituída por `preencherContratoDoOrca`) | a seguir |
| 2026-08-16 | Pipeline de Projetos removida de `gestor/index.html`: item de menu, `pageMap.pipeline`, `rPipeline`/`kbCard` (kanban), `salvarProjeto`/`openNovoProjeto`/`criarNovoProjeto` (órfãs, nunca chamadas por botão nenhum) e o trio morto `rPipelineFixed`/`kbCardReadonly`/`verOSdoCard`. A sincronização automática pra tabela `projetos` (`sincPipelineOrçamento`, `sincPipelineOS` no Gestor e `movSincPipeline` no App de Campo) foi mantida de propósito, porque alimenta o contador/PDF de Pendências e a lista de Tarefas vencidas, que não são a Pipeline e continuam ativos | a seguir |
| 2026-09-10 | Checkpoint rodado após ~5 semanas parado: 4 P1 levantados a partir de uma lista de melhorias do usuário, confirmados no código antes de priorizar | — |
| 2026-09-10 | Espólio + representante do espólio: novo tipo "Espólio" na pessoa do CAD de proprietários (`vizPessoaFormHtml`/`vizSalvarPessoa`/`anuenciaPessoaFrase` em `gestor/index.html`), reaproveitando a estrutura de representante já usada para PJ. Alimenta automaticamente Anuência, Requerimento ao Cartório, Comprobatória, Zoneamento, Declarações e o auto-preenchimento do Memorial — sem migration, `obras.proprietarios` já é JSONB | a seguir |
| 2026-09-10 | OS ganha campo "Local de execução" (Campo/Escritório) em `gestor/index.html` (criação via orçamento, criação manual e edição) + migration `add_os_local_execucao.sql`. No app de Campo, assumir uma OS marcada "Campo" sem veículo no turno agora exige selecionar o veículo na hora (`assumirOS`/`confirmarAssumirOS` em `campo/index.html`) — sem quebrar OS sem esse campo definido (comportamento antigo preservado) | a seguir |
| 2026-09-10 | Confrontante por trecho cadastrado direto no CAD (`cadAtualizarPainel`/`cadAplicarEdicaoPonto`, novo campo `confrontante` no ponto, sem migration — já é JSONB), puxado automaticamente pro Memorial (`memorialImportarCad`) e pro Gerador de Mapa de Perímetro (`cadAbrirModalMapa`) em vez de digitar de novo em cada ferramenta | a seguir |
| 2026-09-10 | Conciliação de 18 recebimentos soltos vinculados à OS certa via número de orçamento (identificador explícito no lançamento, nunca por valor) — script rodado direto no Supabase via service_role, fora do Git. 12 seguem soltos para revisão manual (ver P1) e 1 caso (F&B/OS-JUL-019 cancelada) ficou de fora por parecer cobrança órfã | a seguir |
