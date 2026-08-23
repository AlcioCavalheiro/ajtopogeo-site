-- ═══════════════════════════════════════════════════════════════════════
-- SEGURANÇA E TRABALHO (SST) — catálogo de EPIs, entregas de EPI (Ficha de
-- Controle de EPI), Ordens de Serviço NR-1 e Treinamentos (Lista de
-- Presença). Base para a aba "Segurança e Trabalho" do Gestor.
--
-- Execute no Supabase (SQL Editor) antes de usar a aba. Seguro rodar mais
-- de uma vez. Não altera nenhuma tabela existente.
-- ═══════════════════════════════════════════════════════════════════════

-- ─── CATÁLOGO DE EPIs ──────────────────────────────────────────
create table if not exists epis (
  id uuid primary key default gen_random_uuid(),
  nome text,                       -- "Capacete de Proteção"
  categoria text,                  -- Cabeça/Auditivo/Visão/Mãos/Pés/Corpo/Outro
  ca_padrao text,                  -- nº do Certificado de Aprovação padrão deste item
  obs text,
  ativo boolean default true,
  created_at timestamptz default now()
);

-- ─── ENTREGAS DE EPI (Ficha de Controle de EPI) ────────────────
-- Dados da pessoa ficam desnormalizados aqui (nome/cargo/registro/admissão
-- no momento da entrega): a ficha impressa não pode mudar retroativamente
-- se o cadastro for editado depois, e isso cobre tanto funcionários quanto
-- sócios (que não têm cargo/admissão na tabela socios).
create table if not exists epi_entregas (
  id uuid primary key default gen_random_uuid(),
  pessoa_tipo text not null default 'funcionario', -- 'funcionario' | 'socio'
  pessoa_id uuid,
  pessoa_nome text,
  pessoa_cargo text,
  pessoa_registro text,
  pessoa_admissao date,
  epi_id uuid references epis(id),
  descricao text,                  -- nome do EPI no momento da entrega
  ca text,
  quantidade numeric default 1,
  data_entrega date default current_date,
  data_devolucao date,
  obs text,
  created_at timestamptz default now()
);
create index if not exists idx_epi_entregas_pessoa on epi_entregas (pessoa_tipo, pessoa_id);

-- ─── ORDENS DE SERVIÇO (NR-1) ───────────────────────────────────
create table if not exists sst_ordens_servico (
  id uuid primary key default gen_random_uuid(),
  numero int,                      -- sequencial (Nº da Ordem)
  pessoa_tipo text not null default 'funcionario',
  pessoa_id uuid,
  pessoa_nome text,
  pessoa_cargo text,
  pessoa_cbo text,
  pessoa_admissao date,
  atividades text,
  riscos_fisicos text,
  riscos_quimicos text,
  riscos_biologicos text,
  riscos_ergonomicos text,
  riscos_acidentes text,
  epis_necessarios text,
  medidas_preventivas text,
  orientacoes text,
  data_emissao date default current_date,
  created_at timestamptz default now()
);
create index if not exists idx_sst_os_pessoa on sst_ordens_servico (pessoa_tipo, pessoa_id);

-- ─── TREINAMENTOS (Lista de Presença) ───────────────────────────
create table if not exists sst_treinamentos (
  id uuid primary key default gen_random_uuid(),
  titulo text,                     -- "Treinamento no uso de EPI's e Ordem de Serviço"
  instituicao text,
  data date default current_date,
  turno text,                      -- Diurno - Manhã / Diurno - Tarde / Noturno
  participantes jsonb default '[]'::jsonb, -- [{nome,cpf}]
  created_at timestamptz default now()
);

-- ═══════════════════════════════════════════════════════════════════════
-- RLS — nascem fechadas: só usuário logado (authenticated) acessa, igual ao
-- resto do módulo Empresa. Repetível: dropa e recria a policy.
-- ═══════════════════════════════════════════════════════════════════════
do $$
declare t text;
begin
  foreach t in array array['epis','epi_entregas','sst_ordens_servico','sst_treinamentos'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I on %I', t||'_rw_auth', t);
    execute format('create policy %I on %I for all to authenticated using (true) with check (true)', t||'_rw_auth', t);
  end loop;
end $$;
