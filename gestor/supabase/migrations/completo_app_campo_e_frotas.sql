-- ═══════════════════════════════════════════════════════════════════════════
-- AJ TopoGeo — SQL ÚNICO: App de Campo + Frotas
--
-- Rode TUDO de uma vez no Supabase → SQL Editor → New query → colar → Run.
-- Seguro rodar mais de uma vez (idempotente). Não altera dados existentes.
--
-- Ativa:
--   1) App de campo (/campo): ponto com km/foto/GPS + foto de comprovante de despesa
--   2) Frotas no Gestor: veículos, abastecimentos, manutenções, documentos
--      (com "lançar também no financeiro")
-- ═══════════════════════════════════════════════════════════════════════════


-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ PARTE 1 — APP DE CAMPO (ponto do operador)                            ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

-- ─── Atendimentos de campo (o "abrir/fechar dia na obra") ──────
create table if not exists atendimentos_campo (
  id uuid primary key default gen_random_uuid(),
  os_id uuid references ordens(id),
  os_numero text,
  operador text,                  -- nome/e-mail do operador logado
  operador_uid uuid,              -- auth.uid() de quem bateu o ponto

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

create index if not exists idx_atend_campo_os      on atendimentos_campo (os_id);
create index if not exists idx_atend_campo_operador on atendimentos_campo (operador_uid, status);

-- Um atendimento em andamento por operador (impede dois pontos abertos ao mesmo tempo)
create unique index if not exists uq_atend_campo_aberto_por_operador
  on atendimentos_campo (operador_uid)
  where status = 'em_andamento';

-- Foto do comprovante na despesa de campo (a despesa em si vai em "pagamentos")
alter table pagamentos add column if not exists comprovante_url text;

-- RLS: só usuário logado (authenticated) acessa
alter table atendimentos_campo enable row level security;
drop policy if exists atend_campo_rw_autenticado on atendimentos_campo;
create policy atend_campo_rw_autenticado
  on atendimentos_campo for all to authenticated
  using (true) with check (true);

-- ─── Storage: bucket das fotos de campo (ponto + comprovantes) ──
insert into storage.buckets (id, name, public)
select 'campo-fotos', 'campo-fotos', true
where not exists (select 1 from storage.buckets where id = 'campo-fotos');

drop policy if exists "campo-fotos leitura publica" on storage.objects;
create policy "campo-fotos leitura publica"
  on storage.objects for select
  using (bucket_id = 'campo-fotos');

drop policy if exists "campo-fotos upload autenticado" on storage.objects;
create policy "campo-fotos upload autenticado"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'campo-fotos');


-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ PARTE 2 — FROTAS                                                       ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

-- ─── Veículos ──────────────────────────────────────────────────
create table if not exists veiculos (
  id uuid primary key default gen_random_uuid(),
  nome text,                       -- apelido: "Hilux branca"
  placa text,
  marca text,
  modelo text,
  ano int,
  cor text,
  tipo text default 'Caminhonete', -- Carro/Caminhonete/Moto/Caminhão/Máquina/Outro
  combustivel text default 'Flex', -- Gasolina/Etanol/Diesel/Flex/GNV
  renavam text,
  chassi text,
  hodometro_tipo text default 'km',
  km_atual numeric default 0,
  responsavel text,
  status text default 'Ativo',     -- Ativo/Em manutenção/Inativo/Vendido
  obs text,
  ativo boolean default true,
  created_at timestamptz default now()
);

-- ─── Abastecimentos ────────────────────────────────────────────
create table if not exists abastecimentos (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade not null,
  data date default current_date,
  km numeric,
  litros numeric,
  valor_litro numeric,
  valor_total numeric,
  combustivel text,
  posto text,
  tanque_cheio boolean default true,
  motorista text,
  os_id uuid references ordens(id),
  pagamento_id uuid references pagamentos(id), -- "lançar também no financeiro"
  obs text,
  created_at timestamptz default now()
);
alter table abastecimentos add column if not exists pagamento_id uuid references pagamentos(id);
create index if not exists idx_abast_veic on abastecimentos (veiculo_id, km);

-- ─── Manutenções ───────────────────────────────────────────────
create table if not exists manutencoes (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade not null,
  data date default current_date,
  km numeric,
  tipo text default 'Preventiva', -- Preventiva/Corretiva
  categoria text,                 -- Troca de óleo/Pneus/Freios/Suspensão/Motor/Elétrica/Revisão/Outro
  descricao text,
  oficina text,
  valor numeric,
  proxima_data date,              -- lembrete por data
  proxima_km numeric,             -- lembrete por km
  status text default 'Realizada',
  os_id uuid references ordens(id),
  pagamento_id uuid references pagamentos(id), -- "lançar também no financeiro"
  obs text,
  created_at timestamptz default now()
);
alter table manutencoes add column if not exists pagamento_id uuid references pagamentos(id);
create index if not exists idx_manut_veic on manutencoes (veiculo_id, data);

-- ─── Documentos do veículo ─────────────────────────────────────
create table if not exists documentos_veiculo (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade not null,
  tipo text,                      -- CRLV/IPVA/Seguro/Licenciamento/Multa/Outro
  numero text,
  emissao date,
  validade date,                  -- base do alerta de vencimento
  valor numeric,
  arquivo_url text,
  obs text,
  created_at timestamptz default now()
);
create index if not exists idx_docveic_veic on documentos_veiculo (veiculo_id, validade);

-- ─── RLS das tabelas de frotas (só usuário logado) ─────────────
do $$
declare t text;
begin
  foreach t in array array['veiculos','abastecimentos','manutencoes','documentos_veiculo'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I on %I', t||'_rw_auth', t);
    execute format('create policy %I on %I for all to authenticated using (true) with check (true)', t||'_rw_auth', t);
  end loop;
end $$;

-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ PARTE 3 — APP DE CAMPO v2 (veículo no ponto, diaristas,               ║
-- ║ estabelecimentos e checklist diário do veículo)                       ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

-- Veículo usado no ponto
alter table atendimentos_campo add column if not exists veiculo_id uuid references veiculos(id);
alter table atendimentos_campo add column if not exists veiculo_nome text;

-- Tipo de vínculo do trabalhador (Funcionário / Diarista)
alter table funcionarios add column if not exists tipo text default 'Funcionário';

-- Estabelecimentos (postos, restaurantes, materiais de construção...)
create table if not exists estabelecimentos (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  tipo text default 'Outro',
  cidade text,
  telefone text,
  obs text,
  ativo boolean default true,
  created_at timestamptz default now()
);
create index if not exists idx_estab_tipo on estabelecimentos (tipo, nome);

-- Onde a despesa foi feita
alter table pagamentos add column if not exists fornecedor text;

-- Checklist diário do veículo
create table if not exists checklists_veiculo (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade,
  veiculo_nome text,
  data date default current_date,
  operador text,
  operador_uid uuid,
  km numeric,
  itens jsonb,
  ok boolean,
  obs text,
  foto_url text,
  created_at timestamptz default now()
);
create index if not exists idx_checklist_veic on checklists_veiculo (veiculo_id, data);

do $$
declare t text;
begin
  foreach t in array array['estabelecimentos','checklists_veiculo'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I on %I', t||'_rw_auth', t);
    execute format('create policy %I on %I for all to authenticated using (true) with check (true)', t||'_rw_auth', t);
  end loop;
end $$;


-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ PARTE 4 — TURNO INDEPENDENTE DA OS (v3)                                ║
-- ║ Ponto vira "expediente": bate uma vez, depois assume/conclui OS's à    ║
-- ║ vontade, encerra o ponto no fim. Ver add_campo_v3_turno.sql.           ║
-- ╚═══════════════════════════════════════════════════════════════════════╝

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

create unique index if not exists uq_atend_os_assumida_por_operador
  on atendimentos_campo_os (operador_uid)
  where status = 'assumida';

alter table atendimentos_campo_os enable row level security;
drop policy if exists atend_campo_os_rw_auth on atendimentos_campo_os;
create policy atend_campo_os_rw_auth
  on atendimentos_campo_os for all to authenticated
  using (true) with check (true);

-- ═══════════════════════════════════════════════════════════════════════════
-- FIM. Depois de rodar: recarregue o Gestor e o app /campo.
-- ═══════════════════════════════════════════════════════════════════════════
