-- ═══════════════════════════════════════════════════════════════════════
-- APP DE CAMPO v4 — Km por OS (não mais por expediente)
--
-- Execute no Supabase (SQL Editor). Seguro rodar mais de uma vez.
-- Depende de: add_campo_v3_turno.sql (tabela atendimentos_campo_os).
--
-- Antes (v3): km inicial/final eram digitados ao bater/encerrar o ponto —
-- um único km para o expediente inteiro, mesmo que o operador passasse por
-- várias OS no mesmo dia.
--
-- Agora: bater/encerrar o ponto não pede mais km (só foto/GPS/veículo). O
-- km passa a ser digitado por OS — no momento de "Assumir" (km inicial,
-- indo pra obra) e "Concluir" (km final) — dando o km rodado de cada
-- atendimento em vez de só o total do dia.
-- ═══════════════════════════════════════════════════════════════════════

alter table atendimentos_campo_os add column if not exists km_inicial numeric;
alter table atendimentos_campo_os add column if not exists km_final numeric;

do $$
begin
  if not exists (
    select 1 from information_schema.columns
     where table_name='atendimentos_campo_os' and column_name='km_rodado'
  ) then
    alter table atendimentos_campo_os add column km_rodado numeric
      generated always as (
        case when km_final is not null and km_inicial is not null
             then km_final - km_inicial end
      ) stored;
  end if;
end $$;
