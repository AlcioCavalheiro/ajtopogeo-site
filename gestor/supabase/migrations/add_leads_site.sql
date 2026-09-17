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
--
-- Coluna "origem": 'formulario' = clicou em Enviar via WhatsApp (pode não
-- ter chegado a mandar a mensagem lá dentro). 'rascunho' = só preencheu
-- nome e telefone e saiu do campo, sem nunca clicar em enviar — sinal mais
-- fraco, fica separado na aba "Rascunhos" do Gestor.
-- ═══════════════════════════════════════════════════════════════════════

create table if not exists leads_site (
  id uuid primary key default gen_random_uuid(),
  nome text,
  telefone text,
  email text,
  servico text,
  mensagem text,
  pagina text,            -- ex: /  (de onde veio o formulário)
  origem text not null default 'formulario', -- 'formulario' | 'rascunho'
  contatado boolean not null default false,
  criado_em timestamptz not null default now()
);

-- Rodando a migration de novo em banco já criado antes da coluna existir:
alter table leads_site add column if not exists origem text not null default 'formulario';

create index if not exists leads_site_contatado_idx on leads_site(contatado);
create index if not exists leads_site_origem_idx on leads_site(origem);

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
