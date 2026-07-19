-- ═══════════════════════════════════════════════════════════════════════
-- Separa gasto FIXO da empresa de saída VARIÁVEL na tabela pagamentos.
--
-- Fixo    = conta que se repete todo mês, tenha ou não obra rodando
--           (folha, pró-labore, infraestrutura, software, financiamento).
-- Variável = gasto que só existe porque teve serviço
--           (combustível, alimentação, equipamento avulso, material de campo).
--
-- Seguro de rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

alter table pagamentos add column if not exists natureza text;

-- Backfill 1 — categorias que são fixas por definição
update pagamentos
   set natureza = 'Fixo'
 where natureza is null
   and categoria in (
     'Pró-labore','Salário','INSS Folha','FGTS Folha','IRRF',
     'Infraestrutura','Software','Financiamento','Parcelamento Tributário',
     'Custo Fixo'
   );

-- Backfill 2 — tudo que foi gerado por recorrência é fixo
-- (a coluna recorrencia_id pode não existir em bancos antigos)
do $$
begin
  if exists (
    select 1 from information_schema.columns
     where table_name = 'pagamentos' and column_name = 'recorrencia_id'
  ) then
    execute 'update pagamentos set natureza = ''Fixo''
              where natureza is null and recorrencia_id is not null';
  end if;
end $$;

-- Backfill 3 — o resto é variável
update pagamentos set natureza = 'Variável' where natureza is null;

alter table pagamentos alter column natureza set default 'Variável';

create index if not exists idx_pagamentos_natureza on pagamentos (natureza);

-- Conferência: distribuição depois do backfill
-- select natureza, categoria, count(*), sum(valor)
--   from pagamentos group by 1,2 order by 1,3 desc;
