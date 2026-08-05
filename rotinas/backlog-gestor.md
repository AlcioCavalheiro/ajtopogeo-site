# Backlog — Gestor AJ TopoGeo

Alimentado pela rotina `/checkpoint-gestor` toda sexta.
Sem dado de cliente neste arquivo — ele é versionado no Git.

**Último checkpoint:** 2026-08-05
**Escopo da semana atual (05 a 12/08):** fechado — P0 do "Aguardando" e reativação do Pipeline de
Projetos, ambos resolvidos no mesmo dia do checkpoint.

---

## P0 — Quebra fluxo

_vazio — o único item (status "Aguardando" órfão) foi resolvido em 2026-08-05, ver Histórico._

## P1 — Atrito

- **Conciliar os recebimentos antigos sem OS.** A trava nova impede novos, mas
  os que já existem seguem soltos e inflam o saldo em aberto no relatório de
  cobrança. É tarefa de dados, não de código: abrir cada um no Gestor e
  vincular à OS certa. Cuidado com clientes que têm várias OS de valor
  idêntico — conferir pela NF ou pela data, nunca pelo valor.
- **Recebimento em lote / parcial.** Hoje um recebimento aponta para uma única
  OS. Quando o cliente paga várias de uma vez (um PIX cobrindo três OS), não há
  como registrar sem escolher uma e deixar as outras abertas. Foi o que gerou
  boa parte dos lançamentos soltos.

## P2 — Incremental

_vazio — Pipeline de Projetos reativado em 2026-08-05, ver Histórico._

## P3 — Ideias / dívida técnica

- **Padrão de telas duplicadas (`rX` / `rXFixed`).** Várias páginas têm duas
  implementações no arquivo (`rConfig`/`rConfigFixed`, `rPendencias`/
  `rPendenciasFixed`, `rMedicao`/`rMedicaoFixed`, `rPipeline`/
  `rPipelineFixed`, `rOS`/`rOSFixed`), e qual está ativa depende de uma linha
  `pageMap.x = yFixed` estar comentada mais adiante no arquivo (ex.:
  `gestor/index.html:13580,13606,13616,14177`). Já confundiu na hora de
  escrever o manual — a tela de Configuração real (`rConfigFixed`, ativa) tem
  mais campos que a `rConfig` "morta". Risco real: mexer na cópia errada não
  tem efeito nenhum no sistema. Não é tarefa de uma sexta — é candidata a uma
  semana dedicada só a limpar código morto, sem misturar com feature nova.

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
