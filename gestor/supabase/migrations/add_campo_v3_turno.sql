-- ═══════════════════════════════════════════════════════════════════════
-- APP DE CAMPO v3 — Ponto (turno) independente da OS
--
-- Execute no Supabase (SQL Editor). Seguro rodar mais de uma vez.
-- Depende de: add_atendimentos_campo.sql.
--
-- Antes (v1/v2): o operador só batia o ponto DENTRO de uma OS — cada
-- atendimento pertencia a uma única OS (os_id obrigatório na prática).
--
-- Agora: o operador bate o ponto para iniciar o EXPEDIENTE (km, foto, GPS —
-- sem escolher OS nenhuma). Com o expediente aberto, ele "assume" qualquer
-- OS disponível, trabalha nela, "conclui", pode assumir outra em seguida, e
-- só encerra o ponto no fim — não pode fechar o expediente com uma OS ainda
-- assumida.
--
-- atendimentos_campo continua sendo o turno (entrada/saída, km, foto, GPS),
-- agora sem exigir os_id. O vínculo com cada OS trabalhada durante o turno
-- fica nesta tabela nova.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists atendimentos_campo_os (
  id uuid primary key default gen_random_uuid(),
  atendimento_id uuid references atendimentos_campo(id) on delete cascade not null,
  os_id uuid references ordens(id) not null,
  os_numero text,
  operador text,
  operador_uid uuid,
  ts_assumida timestamptz default now(),
  ts_concluida timestamptz,
  status text not null default 'assumida' check (status in ('assumida','concluida')),
  obs text,
  criado_em timestamptz default now()
);

create index if not exists idx_atend_os_turno on atendimentos_campo_os (atendimento_id);
create index if not exists idx_atend_os_os    on atendimentos_campo_os (os_id);

-- Trava de negócio: um operador não pode assumir uma 2ª OS sem concluir a
-- atual (mesma lógica do ponto — 1 turno aberto por vez, agora 1 OS assumida
-- por vez), garantida no banco além da validação no app.
create unique index if not exists uq_atend_os_assumida_por_operador
  on atendimentos_campo_os (operador_uid)
  where status = 'assumida';

alter table atendimentos_campo_os enable row level security;
drop policy if exists atend_campo_os_rw_auth on atendimentos_campo_os;
create policy atend_campo_os_rw_auth
  on atendimentos_campo_os for all to authenticated
  using (true) with check (true);
