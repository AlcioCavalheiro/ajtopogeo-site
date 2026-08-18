-- ============================================================
-- RBAC — Fase 1: base (usuarios_gestor, perfil_modulos, funções)
-- Não toca em nenhuma tabela de negócio. Só depois de confirmar
-- que este bloco funcionou (você aparece como admin) seguimos
-- para a Fase 2.
-- ============================================================

-- Tabela de usuários do Gestor: liga o auth.users a um perfil.
create table if not exists usuarios_gestor (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  nome text,
  perfil text not null default 'comercial',
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

alter table usuarios_gestor enable row level security;

drop policy if exists usuarios_gestor_self_read on usuarios_gestor;
create policy usuarios_gestor_self_read on usuarios_gestor
  for select to authenticated
  using (id = auth.uid());
-- De propósito: ainda não existe política de escrita aqui.
-- Ninguém consegue se promover a admin editando a própria linha
-- via API. A tela de administração (Fase 4) usa uma política de
-- admin dedicada, criada só depois que o admin bootstrap existir.

-- Tabela de mapeamento perfil -> módulos liberados.
-- 'admin' é especial: não precisa de linha aqui (bypass total em
-- modulo_permitido()).
create table if not exists perfil_modulos (
  perfil text not null,
  modulo text not null,
  primary key (perfil, modulo)
);

alter table perfil_modulos enable row level security;

drop policy if exists perfil_modulos_read_all on perfil_modulos;
create policy perfil_modulos_read_all on perfil_modulos
  for select to authenticated
  using (true);
-- Tabela de configuração, não de dados sensíveis — leitura aberta
-- pra qualquer logado é intencional (é só "nome do papel -> nome
-- do módulo", sem informação de negócio).

-- Função central: true se o usuário autenticado tem acesso ao
-- módulo informado (ou é admin, que sempre tem).
-- security definer + search_path fixo (recomendação padrão do
-- Supabase pra função security definer, evita sequestro de
-- schema); exists() em vez de join propositalmente — um join
-- direto com perfil_modulos quebraria o bypass do admin sempre
-- que 'admin' não tiver nenhuma linha lá (que é o estado normal).
create or replace function public.modulo_permitido(p_modulo text)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from usuarios_gestor u
    where u.id = auth.uid()
      and u.ativo
      and (
        u.perfil = 'admin'
        or exists (
          select 1 from perfil_modulos pm
          where pm.perfil = u.perfil and pm.modulo = p_modulo
        )
      )
  );
$$;

revoke execute on function public.modulo_permitido(text) from public;
grant execute on function public.modulo_permitido(text) to authenticated;

-- Helper de admin, usado só na política de escrita de
-- usuarios_gestor (Fase 4) — mesma lógica isolada, sem repetir a
-- subquery em todo lugar.
create or replace function public.eh_admin()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from usuarios_gestor u
    where u.id = auth.uid() and u.ativo and u.perfil = 'admin'
  );
$$;

revoke execute on function public.eh_admin() from public;
grant execute on function public.eh_admin() to authenticated;

-- Bootstrap: as contas que já existem hoje (você + as outras duas
-- já em uso) precisam existir em usuarios_gestor como admin ANTES
-- de qualquer política restritiva ir pro ar, senão ficam trancadas
-- pra fora do próprio sistema. Perfis segmentados (comercial,
-- financeiro, ferramentas, empresa, campo) são só pra quem for
-- contratado daqui pra frente — essas 3 contas atuais mantêm
-- acesso total.
insert into usuarios_gestor (id, email, nome, perfil, ativo)
select id, email,
       coalesce(raw_user_meta_data->>'name', split_part(email, '@', 1)),
       'admin', true
from auth.users
where lower(email) = any(array[
  lower('alciocavalheiro@gmail.com'),
  lower('jcabreira23@gmail.com'),
  lower('talmom.regularize@gmail.com')
])
on conflict (id) do update set perfil = 'admin', ativo = true;

-- Trava de segurança: se algum dos e-mails não bateu com nenhum
-- auth.users (erro de digitação, conta diferente etc.), a
-- migration inteira falha e diz exatamente qual faltou, em vez de
-- seguir em frente com admin faltando.
do $$
declare
  v_esperados text[] := array['alciocavalheiro@gmail.com','jcabreira23@gmail.com','talmom.regularize@gmail.com'];
  v_faltando text[];
begin
  select array_agg(e) into v_faltando
  from unnest(v_esperados) e
  where not exists (
    select 1 from usuarios_gestor u where lower(u.email) = lower(e) and u.perfil = 'admin'
  );
  if v_faltando is not null then
    raise exception 'Bootstrap do admin incompleto — nenhuma conta auth.users encontrada para: %', array_to_string(v_faltando, ', ');
  end if;
end $$;

-- Só agora, com o admin garantidamente já semeado, liberamos a
-- política de escrita: admin pode ler/criar/editar qualquer
-- linha de usuarios_gestor (é como a tela "Usuários" atribui
-- perfil pra gente nova). Continua não existindo política de
-- self-write, então ninguém não-admin se promove sozinho.
drop policy if exists usuarios_gestor_admin_write on usuarios_gestor;
create policy usuarios_gestor_admin_write on usuarios_gestor
  for all to authenticated
  using (public.eh_admin())
  with check (public.eh_admin());

-- Vincula um login já criado no painel do Supabase (Authentication
-- > Add User) a um perfil. O front-end nunca tem acesso direto a
-- auth.users (a chave anon não permite) — esta função, rodando
-- como security definer, é a única ponte, e só funciona pra quem
-- já é admin.
create or replace function public.vincular_usuario(p_email text, p_perfil text)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_id uuid;
begin
  if not public.eh_admin() then
    raise exception 'Só o admin pode vincular usuários';
  end if;
  select id into v_id from auth.users where lower(email) = lower(p_email);
  if v_id is null then
    raise exception 'Nenhuma conta de login encontrada com este e-mail. Crie a conta primeiro no painel do Supabase (Authentication > Add User).';
  end if;
  insert into usuarios_gestor (id, email, nome, perfil, ativo)
  values (v_id, p_email, split_part(p_email, '@', 1), p_perfil, true)
  on conflict (id) do update set perfil = excluded.perfil, ativo = true;
end;
$$;

revoke execute on function public.vincular_usuario(text, text) from public;
grant execute on function public.vincular_usuario(text, text) to authenticated;
