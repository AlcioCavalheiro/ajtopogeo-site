# Backlog — Gestor AJ TopoGeo

Alimentado pela rotina `/checkpoint-gestor` toda sexta.
Sem dado de cliente neste arquivo — ele é versionado no Git.

**Último checkpoint:** — (ainda não realizado)
**Escopo da semana atual:** — (definir no primeiro checkpoint)

---

## P0 — Quebra fluxo

_vazio_

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

_vazio_

## P3 — Ideias

_vazio_

---

## Histórico

| Data | Item | Commit |
|---|---|---|
| 2026-07-19 | Backlog criado junto com a estruturação das rotinas | — |
| 2026-07-19 | Recebimento passa a exigir OS vinculada, ou marcação explícita de receita avulsa | a seguir |
