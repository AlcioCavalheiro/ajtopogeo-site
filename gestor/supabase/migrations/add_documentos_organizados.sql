-- ═══════════════════════════════════════════════════════════════════════
-- DOCUMENTOS — organização por escopo (empresa / funcionário / sócio) e
-- controle de documentos periódicos (mensais, trimestrais, anuais).
--
-- Antes tudo caía numa lista única em documentos_empresa, sem dizer de
-- quem era o papel e sem jeito de cobrar a versão nova todo mês (ASO,
-- folha de ponto, guia do INSS, holerite, certidões negativas...).
--
-- 1) documentos_empresa ganha o vínculo e a periodicidade;
-- 2) documentos_competencia guarda UM arquivo por mês/período exigido —
--    é a ausência da linha da competência que vira pendência na tela.
--
-- Mesmo padrão de anexo do resto do sistema: data URL base64 na coluna,
-- sem Supabase Storage.
--
-- Execute no Supabase (SQL Editor). Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

-- ─── 1. Vínculo e periodicidade em documentos_empresa ──────────────────
alter table documentos_empresa
  add column if not exists escopo          text    not null default 'Empresa',
  add column if not exists funcionario_id  uuid    references funcionarios(id) on delete cascade,
  add column if not exists socio_id        uuid    references socios(id)       on delete cascade,
  add column if not exists periodicidade   text    not null default 'Única',
  add column if not exists inicio_exigencia date,
  add column if not exists dia_limite      integer,
  add column if not exists ativo           boolean not null default true;

comment on column documentos_empresa.escopo          is 'Empresa | Funcionário | Sócio — de quem é o documento.';
comment on column documentos_empresa.funcionario_id  is 'Preenchido quando escopo = Funcionário.';
comment on column documentos_empresa.socio_id        is 'Preenchido quando escopo = Sócio.';
comment on column documentos_empresa.periodicidade   is 'Única | Mensal | Trimestral | Anual — Única é o documento com validade; os demais exigem um arquivo por competência.';
comment on column documentos_empresa.inicio_exigencia is 'Primeira competência cobrada. Vazio = começa no mês do cadastro.';
comment on column documentos_empresa.dia_limite      is 'Dia do mês até o qual a competência corrente deve ser enviada (default 10 na tela).';
comment on column documentos_empresa.ativo           is 'Documento periódico desativado para de gerar pendência.';

alter table documentos_empresa drop constraint if exists documentos_empresa_escopo_chk;
alter table documentos_empresa add constraint documentos_empresa_escopo_chk
  check (escopo in ('Empresa','Funcionário','Sócio'));

alter table documentos_empresa drop constraint if exists documentos_empresa_periodicidade_chk;
alter table documentos_empresa add constraint documentos_empresa_periodicidade_chk
  check (periodicidade in ('Única','Mensal','Trimestral','Anual'));

create index if not exists documentos_empresa_escopo_idx      on documentos_empresa(escopo);
create index if not exists documentos_empresa_funcionario_idx on documentos_empresa(funcionario_id);
create index if not exists documentos_empresa_socio_idx       on documentos_empresa(socio_id);

-- ─── 2. Um arquivo por competência ─────────────────────────────────────
-- competencia é sempre o dia 1 do mês de referência (2026-08-01 = agosto/26).
create table if not exists documentos_competencia (
  id            uuid primary key default gen_random_uuid(),
  documento_id  uuid not null references documentos_empresa(id) on delete cascade,
  competencia   date not null,
  arquivo_url   text,
  arquivo_nome  text,
  observacoes   text,
  enviado_em    timestamptz not null default now(),
  tem_arquivo   boolean generated always as (arquivo_url is not null) stored
);

comment on table  documentos_competencia            is 'Entrega mensal/periódica de um documento de documentos_empresa. Linha ausente = pendência.';
comment on column documentos_competencia.competencia is 'Sempre o dia 1 do mês de referência.';

create unique index if not exists documentos_competencia_uidx
  on documentos_competencia(documento_id, competencia);
create index if not exists documentos_competencia_comp_idx
  on documentos_competencia(competencia desc);

alter table documentos_competencia enable row level security;
drop policy if exists documentos_competencia_rw_auth on documentos_competencia;
create policy documentos_competencia_rw_auth on documentos_competencia
  for all to authenticated
  using (true)
  with check (true);
