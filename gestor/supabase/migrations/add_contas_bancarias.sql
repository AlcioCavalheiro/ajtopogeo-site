-- ═══════════════════════════════════════════════════════════════════════
-- CONTAS BANCÁRIAS — em qual conta o dinheiro entrou / saiu.
--
-- Execute no Supabase (SQL Editor) antes de usar a tela "Contas Bancárias".
-- Não altera nenhum lançamento existente: pagamentos e recebimentos antigos
-- ficam com conta_id nulo e aparecem como "Sem conta" até serem classificados.
--
-- O saldo NÃO é guardado. Ele é sempre recalculado como
--   saldo_inicial + recebimentos Recebidos da conta − pagamentos Pagos da conta
-- para não existir a possibilidade de o saldo gravado divergir dos lançamentos.
-- "Ajustar saldo" na tela reescreve o saldo_inicial para bater com o extrato.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists contas_bancarias (
  id uuid primary key default gen_random_uuid(),
  nome text not null,                       -- Banco do Brasil, Sicredi, Nubank...
  tipo text default 'Conta Corrente',       -- Corrente / Poupança / Digital / Investimento / Caixa
  agencia text,
  numero text,
  saldo_inicial numeric default 0,          -- saldo de partida; a movimentação vem dos lançamentos
  cor text default '#1a6fc4',
  ativo boolean default true,
  obs text,
  created_at timestamptz default now()
);

-- Em qual conta o valor foi movimentado
alter table pagamentos   add column if not exists conta_id uuid references contas_bancarias(id);
alter table recebimentos add column if not exists conta_id uuid references contas_bancarias(id);

create index if not exists idx_pagamentos_conta   on pagamentos (conta_id);
create index if not exists idx_recebimentos_conta on recebimentos (conta_id);

-- Caixa em espécie: gasto de campo pago em dinheiro tem onde cair.
-- Só é criado uma vez (identificado pelo tipo 'Caixa').
insert into contas_bancarias (nome, tipo, cor, obs)
select 'Dinheiro em espécie', 'Caixa', '#854F0B', 'Carteira / caixa físico da empresa'
where not exists (select 1 from contas_bancarias where tipo = 'Caixa');

-- Conferência: saldo calculado de cada conta
-- select c.nome,
--        c.saldo_inicial
--        + coalesce((select sum(r.valor) from recebimentos r
--                     where r.conta_id = c.id and r.status = 'Recebido'), 0)
--        - coalesce((select sum(p.valor + coalesce(p.juros,0)) from pagamentos p
--                     where p.conta_id = c.id and p.status = 'Pago'), 0) as saldo
--   from contas_bancarias c order by c.nome;
