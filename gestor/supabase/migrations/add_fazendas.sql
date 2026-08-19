-- ═══════════════════════════════════════════════════════════════════════
-- FAZENDAS À VENDA — cadastro de imóveis rurais para venda (corretagem
-- CRECI). Alimenta o módulo "Fazendas" do Gestor (Comercial) e a página
-- pública /fazendas-a-venda do site, que lê esta tabela direto do
-- Supabase (chave anon, só leitura, só linhas com status público).
--
-- Execute no Supabase (SQL Editor) antes de usar a aba "Fazendas". Seguro
-- rodar mais de uma vez. Não altera nenhuma tabela existente.
--
-- Depois de rodar este SQL, crie manualmente o bucket de Storage
-- "fazendas-fotos" (Supabase → Storage → New bucket → marcar "Public
-- bucket"). Não é possível criar bucket via SQL/migration.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists fazendas (
  id uuid primary key default gen_random_uuid(),
  titulo text not null,             -- Ex: "Fazenda Santa Rita — 240 ha"
  descricao text,
  area_ha numeric,
  municipio text,
  uf text,
  preco numeric,
  matricula text,
  status text not null default 'Rascunho', -- Rascunho/Disponível/Reservada/Vendida
  destaque boolean not null default false,
  fotos jsonb not null default '[]'::jsonb, -- array de URLs públicas do Storage
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists fazendas_status_idx on fazendas(status);

alter table fazendas enable row level security;

-- Equipe (perfil "comercial" ou admin) tem CRUD completo.
drop policy if exists fazendas_modulo on fazendas;
create policy fazendas_modulo on fazendas
  for all to authenticated
  using (public.modulo_permitido('comercial'))
  with check (public.modulo_permitido('comercial'));

-- ─── Dados do proprietário e da autorização de venda ────────────
-- Necessários para gerar a Autorização de Venda (documento assinado com
-- o proprietário, conforme normas do CRECI). São dados sensíveis (CPF/RG)
-- — por isso NÃO ficam na política pública abaixo, só na view restrita.
alter table fazendas add column if not exists proprietario_nome text;
alter table fazendas add column if not exists proprietario_cpf_cnpj text;
alter table fazendas add column if not exists proprietario_rg text;
alter table fazendas add column if not exists proprietario_estado_civil text;
alter table fazendas add column if not exists proprietario_endereco text;
alter table fazendas add column if not exists comissao_percentual numeric;
alter table fazendas add column if not exists condicoes_pagamento text;
alter table fazendas add column if not exists validade_autorizacao date;
alter table fazendas add column if not exists exclusividade boolean not null default true;
alter table fazendas add column if not exists autorizacao_assinada boolean not null default false;

-- Site público (chave anon) NÃO tem nenhum acesso direto à tabela —
-- só à view "fazendas_publicas" abaixo, que nunca inclui os dados do
-- proprietário (CPF, RG, endereço) nem condições de comissão/pagamento.
drop policy if exists fazendas_publico_select on fazendas;

create or replace view fazendas_publicas as
select id, titulo, descricao, area_ha, municipio, uf, preco, status,
       destaque, fotos, created_at
from fazendas
where status in ('Disponível', 'Reservada');

grant select on fazendas_publicas to anon;

-- ─── Storage: bucket das fotos das fazendas ─────────────────────
-- Se você já criou o bucket "fazendas-fotos" manualmente pelo painel
-- (Storage → New bucket → Public bucket), a linha abaixo não faz nada
-- (idempotente). Se ainda não criou, ela cria.
insert into storage.buckets (id, name, public)
select 'fazendas-fotos', 'fazendas-fotos', true
where not exists (select 1 from storage.buckets where id = 'fazendas-fotos');

-- Leitura pública das fotos (necessária mesmo com "Public bucket" ligado,
-- pois cobre também listagem/metadata, não só a URL /object/public/).
drop policy if exists "fazendas-fotos leitura publica" on storage.objects;
create policy "fazendas-fotos leitura publica"
  on storage.objects for select
  using (bucket_id = 'fazendas-fotos');

-- Upload só para quem está logado no Gestor (o bucket público, sozinho,
-- NÃO libera upload — só libera leitura. Sem esta política, o upload de
-- foto falha mesmo autenticado, com "row-level security policy").
drop policy if exists "fazendas-fotos upload autenticado" on storage.objects;
create policy "fazendas-fotos upload autenticado"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'fazendas-fotos');

-- Permite também apagar foto (ex: substituir/remover) por quem está logado.
drop policy if exists "fazendas-fotos delete autenticado" on storage.objects;
create policy "fazendas-fotos delete autenticado"
  on storage.objects for delete to authenticated
  using (bucket_id = 'fazendas-fotos');
