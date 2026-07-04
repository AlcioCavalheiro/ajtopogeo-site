-- Execute este SQL no Supabase (SQL Editor) antes de usar o módulo "Controle Tributário".
-- Cria as tabelas de apoio ao cálculo de Fator R / alíquota efetiva do Simples Nacional
-- (Anexo III e V) e ao registro de DAS e retenções. Não mexe em nenhuma tabela/dado
-- já existente — RBT12 e folha de 12 meses continuam calculados em tempo real a partir
-- de "notas_fiscais" (emitidas) e "pagamentos" (categoria Pró-labore/Salário/INSS Folha/
-- FGTS Folha), não são duplicados aqui.

-- ─── SÓCIOS ───────────────────────────────────────────────────
create table if not exists socios (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  percentual_participacao numeric,
  ativo boolean default true,
  created_at timestamptz default now()
);

insert into socios (nome, percentual_participacao)
select v.nome, v.pct
from (values
  ('Álcio', 33.34),
  ('Josiani', 33.33),
  ('Talmom', 33.33)
) as v(nome, pct)
where not exists (select 1 from socios);

-- Vincula lançamentos de pró-labore (tabela "pagamentos" já existente) a um sócio,
-- para permitir simular por sócio individualmente. Lançamentos antigos ficam com
-- socio_id nulo e continuam entrando no total de folha (só não entram na quebra por sócio).
alter table pagamentos add column if not exists socio_id uuid references socios(id);


-- ─── PARÂMETROS DO SIMPLES NACIONAL (Anexo III / V) ───────────
-- IMPORTANTE: valores abaixo são a tabela vigente desde jan/2018 (LC 123/2006, alterada
-- pela LC 155/2016). A Reforma Tributária (EC 132/2023) está em transição a partir de
-- 2026 — confirme com o contador se essas faixas continuam válidas antes de usar os
-- números para decisão real. A faixa 6 de cada anexo tem repartição especial (parte do
-- ISS/ICMS é calculada por fora do DAS) — não é só "alíquota nominal menos dedução".
create table if not exists parametros_tributarios (
  id uuid primary key default gen_random_uuid(),
  anexo text not null check (anexo in ('III','V')),
  faixa int not null,
  receita_de numeric not null,
  receita_ate numeric not null,
  aliquota numeric not null,       -- percentual, ex. 6.00 = 6%
  valor_deduzir numeric not null default 0,
  vigencia_inicio date not null default '2018-01-01',
  vigencia_fim date,               -- null = vigente
  observacao text
);

insert into parametros_tributarios (anexo, faixa, receita_de, receita_ate, aliquota, valor_deduzir, observacao)
select v.anexo, v.faixa, v.de, v.ate, v.aliq, v.deduzir, v.obs
from (values
  ('III',1,     0.00,    180000.00,  6.00,      0.00,  null),
  ('III',2,180000.01,    360000.00, 11.20,   9360.00,  null),
  ('III',3,360000.01,    720000.00, 13.50,  17640.00,  null),
  ('III',4,720000.01,   1800000.00, 16.00,  35640.00,  null),
  ('III',5,1800000.01,  3600000.00, 21.00, 125640.00,  null),
  ('III',6,3600000.01,  4800000.00, 33.00, 648000.00, 'Alíquota nominal — parte do ISS/ICMS recolhida por fora do DAS. Confirmar apuração com contador.'),
  ('V',  1,     0.00,    180000.00, 15.50,      0.00,  null),
  ('V',  2,180000.01,    360000.00, 18.00,   4500.00,  null),
  ('V',  3,360000.01,    720000.00, 19.50,   9900.00,  null),
  ('V',  4,720000.01,   1800000.00, 20.50,  17100.00,  null),
  ('V',  5,1800000.01,  3600000.00, 23.00,  62100.00,  null),
  ('V',  6,3600000.01,  4800000.00, 30.50, 540000.00, 'Alíquota nominal — parte do ISS/ICMS recolhida por fora do DAS. Confirmar apuração com contador.')
) as v(anexo, faixa, de, ate, aliq, deduzir, obs)
where not exists (select 1 from parametros_tributarios);


-- ─── PARÂMETROS GERAIS (chave/valor) ───────────────────────────
-- Constantes usadas no simulador (ex. INSS sobre pró-labore adicional). Atualizar
-- anualmente com o contador — valor de teto do INSS muda todo ano.
create table if not exists parametros_gerais (
  chave text primary key,
  valor numeric not null,
  descricao text,
  atualizado_em timestamptz default now()
);

insert into parametros_gerais (chave, valor, descricao)
select v.chave, v.valor, v.descricao
from (values
  ('aliquota_inss_prolabore', 11.00, 'Alíquota de INSS do contribuinte individual/sócio sobre pró-labore (%)'),
  ('teto_inss_mensal', 908.85, 'Valor de referência do teto de contribuição mensal do INSS — CONFIRMAR valor atualizado com o contador todo ano')
) as v(chave, valor, descricao)
where not exists (select 1 from parametros_gerais);


-- ─── DAS MENSAL (memória de cálculo) ───────────────────────────
-- Não substitui a tabela "impostos" (onde o DAS pago já é lançado hoje) — guarda o
-- snapshot do cálculo (RBT12/Fator R/alíquota usados) daquela competência, para
-- auditoria e para os gráficos comparativos, mesmo que os parâmetros mudem depois.
create table if not exists das_mensal (
  id uuid primary key default gen_random_uuid(),
  competencia text not null unique,  -- 'YYYY-MM'
  anexo_aplicado text,
  rbt12 numeric,
  fator_r numeric,
  aliquota_efetiva numeric,
  valor_das_estimado numeric,
  imposto_id uuid references impostos(id),
  observacao text,
  created_at timestamptz default now()
);


-- ─── RETENÇÕES (INSS/ISS/IRRF retidos por PJ/órgão público) ───
create table if not exists retencoes (
  id uuid primary key default gen_random_uuid(),
  os_id uuid references ordens(id),
  nota_fiscal_id uuid references notas_fiscais(id),
  tipo text not null check (tipo in ('INSS','ISS','IRRF')),
  tomador text,
  orgao_publico boolean default false,
  valor_retido numeric not null,
  competencia text,  -- 'YYYY-MM'
  data date,
  compensado boolean default false,
  data_compensacao date,
  observacao text,
  created_at timestamptz default now()
);


-- ─── Como atualizar as faixas do Simples quando o governo mudar ─
-- Não apague a linha antiga: feche a vigência e insira uma nova linha. Exemplo:
--
--   update parametros_tributarios set vigencia_fim = '2026-12-31'
--     where anexo = 'III' and faixa = 1 and vigencia_fim is null;
--
--   insert into parametros_tributarios (anexo, faixa, receita_de, receita_ate, aliquota, valor_deduzir, vigencia_inicio)
--     values ('III', 1, 0.00, 180000.00, 6.50, 0.00, '2027-01-01');
--
-- Isso preserva o histórico para recalcular corretamente competências passadas.
