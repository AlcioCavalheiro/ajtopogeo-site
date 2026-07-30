-- ═══════════════════════════════════════════════════════════════════════
-- FROTAS — controle de veículos: cadastro, abastecimentos, manutenções,
-- documentos. Base para alertas (manutenção prevista, documento vencendo) e
-- indicadores (consumo km/l, custo por km, gasto por veículo).
--
-- Execute no Supabase (SQL Editor) antes de usar a aba "Frotas". Seguro rodar
-- mais de uma vez. Não altera nenhuma tabela existente.
-- ═══════════════════════════════════════════════════════════════════════

-- ─── VEÍCULOS ──────────────────────────────────────────────────
create table if not exists veiculos (
  id uuid primary key default gen_random_uuid(),
  nome text,                       -- apelido: "Hilux branca", "Strada"
  placa text,
  marca text,
  modelo text,
  ano int,
  cor text,
  tipo text default 'Caminhonete', -- Carro/Caminhonete/Moto/Caminhão/Máquina/Outro
  combustivel text default 'Flex', -- Gasolina/Etanol/Diesel/Flex/GNV
  renavam text,
  chassi text,
  hodometro_tipo text default 'km',-- 'km' (veículo) ou 'h' (máquina/horímetro)
  km_atual numeric default 0,      -- último hodômetro conhecido
  responsavel text,
  status text default 'Ativo',     -- Ativo/Em manutenção/Inativo/Vendido
  obs text,
  ativo boolean default true,
  created_at timestamptz default now()
);

-- ─── ABASTECIMENTOS ────────────────────────────────────────────
create table if not exists abastecimentos (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade not null,
  data date default current_date,
  km numeric,                      -- hodômetro no momento do abastecimento
  litros numeric,
  valor_litro numeric,
  valor_total numeric,
  combustivel text,
  posto text,
  tanque_cheio boolean default true, -- necessário p/ calcular consumo entre cheios
  motorista text,
  os_id uuid references ordens(id),      -- opcional: abastecimento de uma OS
  pagamento_id uuid references pagamentos(id), -- se "lançar também no financeiro" gerou um pagamento
  obs text,
  created_at timestamptz default now()
);
-- garante a coluna mesmo se a tabela já existia de uma execução anterior
alter table abastecimentos add column if not exists pagamento_id uuid references pagamentos(id);
create index if not exists idx_abast_veic on abastecimentos (veiculo_id, km);

-- ─── MANUTENÇÕES ───────────────────────────────────────────────
create table if not exists manutencoes (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade not null,
  data date default current_date,
  km numeric,
  tipo text default 'Preventiva', -- Preventiva/Corretiva
  categoria text,                 -- Troca de óleo/Pneus/Freios/Suspensão/Motor/Revisão/Elétrica/Outro
  descricao text,
  oficina text,
  valor numeric,
  proxima_data date,              -- lembrete: próxima revisão por data
  proxima_km numeric,             -- lembrete: próxima revisão por km
  status text default 'Realizada',-- Realizada/Agendada
  os_id uuid references ordens(id),
  pagamento_id uuid references pagamentos(id), -- se "lançar também no financeiro" gerou um pagamento
  obs text,
  created_at timestamptz default now()
);
alter table manutencoes add column if not exists pagamento_id uuid references pagamentos(id);
create index if not exists idx_manut_veic on manutencoes (veiculo_id, data);

-- ─── DOCUMENTOS DO VEÍCULO ─────────────────────────────────────
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

-- ═══════════════════════════════════════════════════════════════════════
-- RLS — nascem fechadas: só usuário logado (authenticated) acessa, igual ao
-- resto do Gestor. Repetível: dropa e recria a policy.
-- ═══════════════════════════════════════════════════════════════════════
do $$
declare t text;
begin
  foreach t in array array['veiculos','abastecimentos','manutencoes','documentos_veiculo'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I on %I', t||'_rw_auth', t);
    execute format('create policy %I on %I for all to authenticated using (true) with check (true)', t||'_rw_auth', t);
  end loop;
end $$;
