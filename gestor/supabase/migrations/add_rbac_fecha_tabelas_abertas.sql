-- ============================================================
-- RBAC — Fase 2: fecha as tabelas que a auditoria encontrou sem
-- proteção real. Todas viram módulo "financeiro".
--
-- Estado encontrado na auditoria ao vivo (2026-08-17):
--   contas_bancarias      rowsecurity=true,  ZERO políticas
--                          -> hoje bloqueada até pra você (bug
--                             pré-existente); esta migration
--                             corrige isso de brinde.
--   socios                rowsecurity=false (RLS desligado -> aberta)
--   parametros_tributarios rowsecurity=false (aberta)
--   parametros_gerais     rowsecurity=false (aberta)
--   das_mensal             rowsecurity=false (aberta)
--   retencoes              rowsecurity=false (aberta)
--
-- Pré-requisito: add_rbac_perfis.sql já rodado (precisa de
-- modulo_permitido() e de você já estar como admin).
-- ============================================================

do $$
declare
  t text;
begin
  foreach t in array array[
    'contas_bancarias','socios','parametros_tributarios',
    'parametros_gerais','das_mensal','retencoes'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I_financeiro on %I', t, t);
    execute format(
      'create policy %I_financeiro on %I for all to authenticated using (public.modulo_permitido(''financeiro'')) with check (public.modulo_permitido(''financeiro''))',
      t, t
    );
  end loop;
end $$;
