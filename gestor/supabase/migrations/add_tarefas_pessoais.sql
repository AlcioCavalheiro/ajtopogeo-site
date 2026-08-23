-- ═══════════════════════════════════════════════════════════════════════
-- TAREFAS PESSOAIS — checklist individual de afazeres, um por usuário
-- logado (ex: "ligar para fulano"), marca como concluída ao terminar.
--
-- Diferente das outras tabelas do Gestor: aqui cada usuário só pode ver e
-- mexer nas próprias tarefas (RLS por usuario_id = auth.uid()), não é
-- "authenticated = tudo liberado".
--
-- Execute no Supabase (SQL Editor) antes de usar a aba "Minhas Tarefas".
-- Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists tarefas_pessoais (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  usuario_nome text,
  texto text not null,
  concluida boolean default false,
  criado_em timestamptz default now(),
  concluido_em timestamptz
);
create index if not exists idx_tarefas_usuario on tarefas_pessoais (usuario_id, concluida);

alter table tarefas_pessoais enable row level security;
drop policy if exists tarefas_pessoais_rw_own on tarefas_pessoais;
create policy tarefas_pessoais_rw_own on tarefas_pessoais
  for all to authenticated
  using (usuario_id = auth.uid())
  with check (usuario_id = auth.uid());
