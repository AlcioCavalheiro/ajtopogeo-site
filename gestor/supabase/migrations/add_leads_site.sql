-- ═══════════════════════════════════════════════════════════════════════
-- LEADS DO SITE — captura o formulário de contato do site público (index)
-- no momento do envio, ANTES de abrir o WhatsApp. Isso garante que, se o
-- visitante preencher nome/telefone mas fechar o WhatsApp sem apertar
-- enviar, a AJ TopoGeo ainda tem o contato salvo para retornar.
--
-- Alimenta o módulo "Leads do Site" do Gestor (Comercial). O site público
-- grava direto nesta tabela usando a chave anon (só INSERT, sem leitura).
--
-- Execute no Supabase (SQL Editor) antes de usar a aba "Leads do Site".
-- Seguro rodar mais de uma vez. Não altera nenhuma tabela existente.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists leads_site (
  id uuid primary key default gen_random_uuid(),
  nome text,
  telefone text,
  email text,
  servico text,
  mensagem text,
  pagina text,            -- ex: /  (de onde veio o formulário)
  contatado boolean not null default false,
  criado_em timestamptz not null default now()
);

create index if not exists leads_site_contatado_idx on leads_site(contatado);

alter table leads_site enable row level security;

-- Site público (chave anon): só pode INSERIR, nunca ler/editar/apagar.
drop policy if exists leads_site_insert_publico on leads_site;
create policy leads_site_insert_publico on leads_site
  for insert to anon
  with check (true);

-- Equipe logada no Gestor: acesso completo (ver, marcar como contatado).
drop policy if exists leads_site_equipe on leads_site;
create policy leads_site_equipe on leads_site
  for all to authenticated
  using (true)
  with check (true);
