-- ═══════════════════════════════════════════════════════════════════════
-- SST — ROSTER (quem entra no controle de EPI/Ordens de Serviço)
--
-- Antes, a aba "EPIs & Ordens de Serviço" listava automaticamente todo
-- funcionário/sócio ativo. Esta tabela deixa isso explícito: só quem for
-- adicionado aqui (a partir do cadastro de Funcionários/Sócios) aparece no
-- painel — e dá pra remover sem apagar o funcionário/sócio nem o
-- histórico de entregas/Ordens de Serviço já lançado.
--
-- Execute no Supabase (SQL Editor) antes de usar o botão "Adicionar
-- pessoa" em Segurança e Trabalho. Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists sst_pessoas (
  id uuid primary key default gen_random_uuid(),
  pessoa_tipo text not null default 'funcionario', -- 'funcionario' | 'socio'
  pessoa_id uuid not null,
  pessoa_nome text,
  pessoa_cargo text,
  created_at timestamptz default now(),
  unique (pessoa_tipo, pessoa_id)
);

alter table sst_pessoas enable row level security;
drop policy if exists sst_pessoas_rw_auth on sst_pessoas;
create policy sst_pessoas_rw_auth on sst_pessoas for all to authenticated using (true) with check (true);
