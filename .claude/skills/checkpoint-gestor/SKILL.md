---
name: checkpoint-gestor
description: Checkpoint semanal de desenvolvimento do Gestor AJ TopoGeo — recolhe bugs e faltas da semana, prioriza crítico vs. incremental e fecha o escopo da próxima semana. Use nas sextas, ou quando o usuário listar bugs/melhorias do Gestor.
---

# Rotina 7 — Checkpoint semanal do Gestor

Cadência: toda sexta, 20–30 min. Objetivo: tirar o desenvolvimento do modo
reativo (só mexe quando quebra) e dar previsibilidade.

## Backlog

Arquivo único, versionado no repo: `rotinas/backlog-gestor.md`.
Ele não contém dado de cliente — pode ficar no Git. Leia antes de tudo.

## Passo 1 — Recolher

O usuário lista o que encontrou na semana. Para cada item, antes de classificar,
**localize no código** (`gestor/index.html`, ~13k linhas, mais `gestor/gestor-assets.js`).
Um relato de usuário raramente aponta a causa certa; confirmar no código evita
priorizar o sintoma errado.

Some ao que ele trouxe o que fechou na semana: rode
`git log --oneline --since="7 days ago" -- gestor/` para saber o que já entrou.

## Passo 2 — Classificar

| Nível | Critério | Prazo |
|---|---|---|
| **P0 — quebra fluxo** | Impede concluir uma tarefa, corrompe ou perde dado, erro em documento que vai para órgão/cliente | Mesma semana |
| **P1 — atrito** | Dá para contornar, mas custa tempo toda vez que aparece | Próxima semana |
| **P2 — incremental** | Melhoria de conforto, ganho pontual | Fila |
| **P3 — ideia** | Vale registrar, não vale planejar ainda | Sem prazo |

Peso extra para P0 se o defeito atinge saída oficial — memorial, planilha ODS
do SIGEF, ART, NF. Erro que chega no INCRA ou no cartório custa muito mais que
erro de tela.

## Passo 3 — Fechar o escopo

Escolha o que entra na próxima semana com honestidade de capacidade: o usuário
executa topografia em campo durante a semana, o tempo de desenvolvimento é
resto de dia. **Um P0 mais dois P1 é uma semana cheia.** Escopo inflado
transforma o checkpoint em lista de culpa e a rotina morre.

Para cada item aceito, esboce a implementação: onde mexe, o que muda, qual o
risco de regressão. Se dois itens tocam a mesma função, agrupe.

## Passo 4 — Atualizar o backlog

Reescreva `rotinas/backlog-gestor.md`: mova o que fechou para o histórico no
rodapé (com a data e o commit), reordene o resto, registre a data do checkpoint.

## Cuidados deste projeto

- `gestor/index.html` é um arquivo único enorme. Edições cirúrgicas, sem
  reformatar bloco vizinho — o diff fica ilegível e o merge, arriscado.
- O Gestor é servido em produção pelo mesmo deploy do site. Bug empurrado é
  bug no ar: teste antes de commitar.
- Alterou schema? A migration correspondente entra em `gestor/supabase/migrations/`
  e precisa ser rodada no SQL Editor do Supabase — o deploy não roda sozinho.
- A chave no `gestor/index.html` é a anônima e é pública por natureza. A proteção
  real é RLS. Nunca troque por service_role para "resolver" um bug de permissão.
