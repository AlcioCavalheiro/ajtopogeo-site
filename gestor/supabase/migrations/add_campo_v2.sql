-- ═══════════════════════════════════════════════════════════════════════
-- APP DE CAMPO v2 — Ponto com veículo, diaristas, estabelecimentos e
-- checklist diário de veículo.
--
-- Execute no Supabase (SQL Editor). Seguro rodar mais de uma vez.
-- Depende de: add_frotas.sql (tabela veiculos) e add_atendimentos_campo.sql.
--
-- O que esta migration adiciona:
--   • atendimentos_campo.veiculo_id / veiculo_nome  — qual carro o operador usou
--   • funcionarios.tipo                              — 'Funcionário' ou 'Diarista'
--   • estabelecimentos (tabela)                      — postos/restaurantes/materiais
--   • pagamentos.fornecedor                          — onde a despesa foi feita
--   • checklists_veiculo (tabela)                    — inspeção diária do veículo
-- ═══════════════════════════════════════════════════════════════════════

-- ─── 1. Veículo usado no ponto ─────────────────────────────────
alter table atendimentos_campo add column if not exists veiculo_id uuid references veiculos(id);
alter table atendimentos_campo add column if not exists veiculo_nome text;

-- ─── 2. Tipo de vínculo do trabalhador ─────────────────────────
-- Diaristas ficam na mesma tabela funcionarios (reaproveitam valor_diaria),
-- só marcados por este campo. O app de campo mostra os dois na lista de custo.
alter table funcionarios add column if not exists tipo text default 'Funcionário';

-- ─── 3. Estabelecimentos (onde o operador compra) ──────────────
create table if not exists estabelecimentos (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  tipo text default 'Outro',   -- Posto / Restaurante / Material de Construção / Outro
  cidade text,
  telefone text,
  obs text,
  ativo boolean default true,
  created_at timestamptz default now()
);
create index if not exists idx_estab_tipo on estabelecimentos (tipo, nome);

-- Onde a despesa foi feita (nome do estabelecimento), na tabela de despesa.
alter table pagamentos add column if not exists fornecedor text;

-- ─── 4. Checklist diário do veículo ────────────────────────────
create table if not exists checklists_veiculo (
  id uuid primary key default gen_random_uuid(),
  veiculo_id uuid references veiculos(id) on delete cascade,
  veiculo_nome text,               -- redundância barata p/ exibir sem join
  data date default current_date,
  operador text,
  operador_uid uuid,
  km numeric,
  itens jsonb,                     -- [{item:'Pneus', ok:true}, ...]
  ok boolean,                      -- true = nenhum item reprovado
  obs text,
  foto_url text,
  created_at timestamptz default now()
);
create index if not exists idx_checklist_veic on checklists_veiculo (veiculo_id, data);

-- ═══════════════════════════════════════════════════════════════════════
-- RLS — nascem fechadas: só usuário logado (authenticated), igual ao resto.
-- ═══════════════════════════════════════════════════════════════════════
do $$
declare t text;
begin
  foreach t in array array['estabelecimentos','checklists_veiculo'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists %I on %I', t||'_rw_auth', t);
    execute format('create policy %I on %I for all to authenticated using (true) with check (true)', t||'_rw_auth', t);
  end loop;
end $$;
