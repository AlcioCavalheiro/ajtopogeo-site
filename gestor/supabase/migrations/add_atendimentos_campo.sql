-- ═══════════════════════════════════════════════════════════════════════
-- APP DE CAMPO — Ciclo de ponto do operador (km, foto, GPS)
--
-- Execute no Supabase (SQL Editor) ANTES de usar o app de campo (/campo).
-- Seguro rodar mais de uma vez.
--
-- O que ESTA migration cria (só o que ainda não existe no sistema):
--   • tabela atendimentos_campo — o "abrir/fechar dia na obra": km inicial/final,
--     foto biométrica + GPS de entrada e de saída, e o status do atendimento.
--   • coluna comprovante_url em pagamentos — foto do comprovante da despesa de campo.
--
-- O que NÃO é duplicado (continua nas tabelas que já existem):
--   • Gasto de equipe (diária/hora)  -> custos_os        (os_id, func_id, ...)
--   • Despesa (combustível, etc.)     -> pagamentos        (os_id, categoria, ...)
--   • Movimentação / andamento da OS   -> ordens.status + ordens.andamento (jsonb)
--   • Agenda de execução               -> agenda            (tipo 'OS'/'Tarefa OS')
-- ═══════════════════════════════════════════════════════════════════════

-- ─── ATENDIMENTOS DE CAMPO (ponto) ─────────────────────────────
create table if not exists atendimentos_campo (
  id uuid primary key default gen_random_uuid(),
  os_id uuid references ordens(id),
  os_numero text,                 -- redundância barata p/ exibir sem join
  operador text,                  -- nome/e-mail do operador logado
  operador_uid uuid,              -- auth.uid() do operador (quem bateu o ponto)

  -- Entrada
  km_inicial numeric,
  foto_entrada_url text,
  geo_entrada_lat numeric,
  geo_entrada_lng numeric,
  ts_entrada timestamptz,

  -- Saída
  km_final numeric,
  foto_saida_url text,
  geo_saida_lat numeric,
  geo_saida_lng numeric,
  ts_saida timestamptz,

  km_rodado numeric generated always as (
    case when km_final is not null and km_inicial is not null
         then km_final - km_inicial end
  ) stored,

  status text not null default 'em_andamento'
    check (status in ('em_andamento','concluido')),
  obs text,
  criado_em timestamptz default now()
);

create index if not exists idx_atend_campo_os       on atendimentos_campo (os_id);
create index if not exists idx_atend_campo_operador  on atendimentos_campo (operador_uid, status);

-- Regra de negócio "um atendimento em andamento por operador": garantida por
-- índice único parcial (o operador não consegue abrir dois pontos ao mesmo tempo).
create unique index if not exists uq_atend_campo_aberto_por_operador
  on atendimentos_campo (operador_uid)
  where status = 'em_andamento';

-- ─── Foto do comprovante na despesa de campo ───────────────────
-- pagamentos já é a tabela de despesa (o app grava combustível/alimentação/etc.
-- aqui, vinculado por os_id). Só faltava onde guardar a foto do comprovante.
alter table pagamentos add column if not exists comprovante_url text;


-- ═══════════════════════════════════════════════════════════════════════
-- SEGURANÇA (RLS)
-- A tabela nova nasce fechada: só usuário LOGADO (role authenticated) mexe.
-- O app de campo usa a mesma anon key + login do Gestor, então cai em
-- 'authenticated'. Visitante anônimo (sem login) não acessa o ponto.
-- ═══════════════════════════════════════════════════════════════════════
alter table atendimentos_campo enable row level security;

drop policy if exists atend_campo_rw_autenticado on atendimentos_campo;
create policy atend_campo_rw_autenticado
  on atendimentos_campo
  for all
  to authenticated
  using (true)
  with check (true);

-- OBS: para restringir cada operador a ver só o próprio ponto no futuro, troque
-- o USING/CHECK por (operador_uid = auth.uid()) e crie uma policy separada de
-- leitura ampla para o papel gestor. Deixado aberto (true) na v1 para bater com
-- o modelo atual do Gestor, onde qualquer logado enxerga a operação inteira.


-- ═══════════════════════════════════════════════════════════════════════
-- STORAGE — bucket das fotos de campo (ponto + comprovantes)
--
-- O bloco abaixo cria o bucket e as políticas por SQL. Se preferir pela UI:
--   Dashboard -> Storage -> New bucket -> nome: campo-fotos -> Public: ON
--   (público facilita exibir a foto no Gestor; as URLs são longas e não listáveis).
-- ═══════════════════════════════════════════════════════════════════════
insert into storage.buckets (id, name, public)
select 'campo-fotos', 'campo-fotos', true
where not exists (select 1 from storage.buckets where id = 'campo-fotos');

-- Upload/leitura por usuário logado; leitura pública para exibir a imagem.
drop policy if exists "campo-fotos leitura publica" on storage.objects;
create policy "campo-fotos leitura publica"
  on storage.objects for select
  using (bucket_id = 'campo-fotos');

drop policy if exists "campo-fotos upload autenticado" on storage.objects;
create policy "campo-fotos upload autenticado"
  on storage.objects for insert
  to authenticated
  with check (bucket_id = 'campo-fotos');
