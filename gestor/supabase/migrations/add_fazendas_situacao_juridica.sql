-- ═══════════════════════════════════════════════════════════════════════
-- FAZENDAS À VENDA — situação jurídica, uso do solo e documentação.
--
-- Acrescenta à tabela "fazendas" (que já é o imóvel e o anúncio ao mesmo
-- tempo) os campos que faltavam para anunciar imóvel de espólio/usufruto/
-- litígio e detalhar a área:
--   situacao_juridica  livre | espolio | usufruto | litigio
--   condicao_venda     nota livre (ex: "venda condicionada a alvará")
--   area_mata_ha + area_util_ha   precisam fechar com area_ha
--   certificacao_incra, ccir, cib, car, distancia_sede_km
-- Novo status "Pendente de alvará": fica fora do site, como o Rascunho.
--
-- Rode depois de add_fazendas.sql. Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

do $$ begin
  create type situacao_juridica_imovel as enum ('livre', 'espolio', 'usufruto', 'litigio');
exception when duplicate_object then null; end $$;

alter table fazendas add column if not exists situacao_juridica situacao_juridica_imovel not null default 'livre';
alter table fazendas add column if not exists condicao_venda text;
alter table fazendas add column if not exists area_mata_ha numeric;
alter table fazendas add column if not exists area_util_ha numeric;
alter table fazendas add column if not exists certificacao_incra text;
alter table fazendas add column if not exists ccir text;
alter table fazendas add column if not exists cib text;
alter table fazendas add column if not exists car text;
alter table fazendas add column if not exists distancia_sede_km numeric;

-- Mata + útil tem que fechar com a área total (tolerância de 1 m² para
-- arredondamento). Só vale quando os três campos estão preenchidos.
alter table fazendas drop constraint if exists fazendas_areas_fecham;
alter table fazendas add constraint fazendas_areas_fecham check (
  area_mata_ha is null or area_util_ha is null or area_ha is null
  or abs(area_mata_ha + area_util_ha - area_ha) <= 0.0001
);

-- View pública: mesmos campos de antes + uso do solo, distância e a
-- situação jurídica (o site mostra aviso quando não é "livre"). Continua
-- sem CPF/RG/endereço/comissão. Colunas novas vão no fim (exigência do
-- "create or replace view").
create or replace view fazendas_publicas as
select id, titulo, descricao, area_ha, municipio, uf, preco, status,
       destaque, fotos, created_at,
       situacao_juridica, condicao_venda, area_mata_ha, area_util_ha,
       distancia_sede_km
from fazendas
where status in ('Disponível', 'Reservada');

grant select on fazendas_publicas to anon;
