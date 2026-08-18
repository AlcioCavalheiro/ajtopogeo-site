-- ============================================================
-- RBAC — Fase 3: substitui as políticas antigas ("qualquer
-- logado, acesso total") pelas políticas por módulo.
--
-- Pré-requisito: add_rbac_perfis.sql e
-- add_rbac_fecha_tabelas_abertas.sql já rodados.
--
-- Não mexe em: agenda (fica aberta pra todo mundo, é o
-- workspace comum, junto com o dashboard).
-- ============================================================

-- ---- 1) Derruba as políticas antigas, pelos nomes exatos
--         encontrados na auditoria ao vivo (pg_policies) ----
drop policy if exists acesso_auth on custos_os;
drop policy if exists acesso_auth on servicos;
drop policy if exists acesso_auth on recebimentos;
drop policy if exists acesso_auth on contratos;
drop policy if exists acesso_auth on rotinas;
drop policy if exists acesso_auth on clientes;
drop policy if exists acesso_auth on orcamentos;
drop policy if exists acesso_auth on funcionarios;
drop policy if exists acesso_auth on medicoes;
drop policy if exists acesso_auth on documentos_empresa;
drop policy if exists acesso_auth on impostos;
drop policy if exists acesso_auth on pagamentos;
drop policy if exists acesso_auth on historico_recebimentos;
drop policy if exists acesso_auth on notas_fiscais;
drop policy if exists acesso_auth on projetos;
drop policy if exists acesso_auth on ordens;

drop policy if exists checklists_veiculo_rw_auth on checklists_veiculo;
drop policy if exists abastecimentos_rw_auth on abastecimentos;
drop policy if exists manutencoes_rw_auth on manutencoes;
drop policy if exists documentos_veiculo_rw_auth on documentos_veiculo;
drop policy if exists estabelecimentos_rw_auth on estabelecimentos;
drop policy if exists atend_campo_rw_autenticado on atendimentos_campo;
drop policy if exists atend_campo_os_rw_auth on atendimentos_campo_os;
drop policy if exists veiculos_rw_auth on veiculos;
drop policy if exists "Acesso livre" on parcelas_geo;

drop policy if exists allow_select_obras on obras;
drop policy if exists allow_insert_obras on obras;
drop policy if exists allow_update_obras on obras;
drop policy if exists allow_delete_obras on obras;

-- ---- 2) Dados de referência: leitura aberta pra qualquer
--         logado (evita quebrar dropdown de cliente/OS/obra/
--         funcionário nos formulários de outros módulos),
--         escrita (criar/editar/excluir) travada por módulo ----
do $$
declare
  rec record;
begin
  for rec in select * from (values
    ('clientes',     'comercial'),
    ('obras',        'comercial'),
    ('servicos',     'comercial'),
    ('orcamentos',   'comercial'),
    ('ordens',       'producao'),
    ('funcionarios', 'empresa')
  ) as t(tabela, modulo)
  loop
    execute format('create policy %I_select_aberta on %I for select to authenticated using (true)', rec.tabela, rec.tabela);
    execute format('create policy %I_insert_modulo on %I for insert to authenticated with check (public.modulo_permitido(%L))', rec.tabela, rec.tabela, rec.modulo);
    execute format('create policy %I_update_modulo on %I for update to authenticated using (public.modulo_permitido(%L)) with check (public.modulo_permitido(%L))', rec.tabela, rec.tabela, rec.modulo, rec.modulo);
    execute format('create policy %I_delete_modulo on %I for delete to authenticated using (public.modulo_permitido(%L))', rec.tabela, rec.tabela, rec.modulo);
  end loop;
end $$;

-- ---- 3) Tabelas travadas de verdade: leitura E escrita só
--         pro módulo dono ----
do $$
declare
  rec record;
begin
  for rec in select * from (values
    ('contratos',              'comercial'),
    ('projetos',                'comercial'),
    ('custos_os',                'producao'),
    ('recebimentos',            'financeiro'),
    ('pagamentos',               'financeiro'),
    ('impostos',                 'financeiro'),
    ('medicoes',                 'financeiro'),
    ('notas_fiscais',            'financeiro'),
    ('historico_recebimentos',   'financeiro'),
    ('rotinas',                  'empresa'),
    ('documentos_empresa',       'empresa'),
    ('veiculos',                 'empresa'),
    ('abastecimentos',           'empresa'),
    ('manutencoes',              'empresa'),
    ('documentos_veiculo',       'empresa'),
    ('checklists_veiculo',       'empresa'),
    ('atendimentos_campo',       'empresa'),
    ('atendimentos_campo_os',    'empresa'),
    ('estabelecimentos',         'empresa'),
    ('parcelas_geo',             'ferramentas')
  ) as t(tabela, modulo)
  loop
    execute format(
      'create policy %I_modulo on %I for all to authenticated using (public.modulo_permitido(%L)) with check (public.modulo_permitido(%L))',
      rec.tabela, rec.tabela, rec.modulo, rec.modulo
    );
  end loop;
end $$;

-- ---- 4) Exceção pagamentos: Produção/Campo enxerga só o total
--         gasto por OS (linhas com os_id preenchido) — não
--         enxerga folha, pró-labore nem contas administrativas,
--         que não têm os_id ----
create policy pagamentos_select_os on pagamentos
  for select to authenticated
  using (public.modulo_permitido('producao') and os_id is not null);

-- ---- 5) Exceção obras.cad_dados: a Ferramentas Geo salva o
--         desenho técnico de volta em obras.cad_dados. Em vez
--         de liberar UPDATE na linha inteira da obra pro perfil
--         Ferramentas (o que deixaria nome/cliente/endereço
--         editável por quem só devia mexer no CAD), esta função
--         só grava essa coluna, chamada via RPC pelo front-end
--         no lugar do update direto ----
-- Garante a coluna antes de criar a função (a função falha ao
-- ser criada se a coluna ainda não existir neste banco).
alter table obras add column if not exists cad_dados jsonb;

create or replace function public.salvar_cad_dados(p_obra_id uuid, p_dados jsonb)
returns void
language sql
security definer
set search_path = public, pg_temp
as $$
  update obras
  set cad_dados = p_dados
  where id = p_obra_id
    and (public.modulo_permitido('comercial') or public.modulo_permitido('ferramentas'));
$$;

revoke execute on function public.salvar_cad_dados(uuid, jsonb) from public;
grant execute on function public.salvar_cad_dados(uuid, jsonb) to authenticated;

-- ---- 6) Perfis iniciais ----
insert into perfil_modulos (perfil, modulo) values
  ('comercial',  'producao'),
  ('comercial',  'comercial'),
  ('financeiro', 'financeiro'),
  ('ferramentas','ferramentas'),
  ('empresa',    'empresa'),
  ('campo',      'producao'),
  ('campo',      'empresa')
on conflict do nothing;
-- 'admin' não precisa de linha: modulo_permitido() já dá bypass total.
