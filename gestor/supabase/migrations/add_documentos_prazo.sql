-- ═══════════════════════════════════════════════════════════════════════
-- DOCUMENTOS — prazo de entrega da competência.
--
-- Guia fiscal não vence dentro do próprio mês de referência: o DAS, o
-- INSS e o FGTS da competência de agosto vencem no dia 20 de SETEMBRO, e
-- o holerite de agosto sai até o 5º dia de setembro. Sem isso o Gestor
-- marcava a competência como atrasada assim que o mês virava.
--
-- prazo_meses = quantos meses depois da competência cai o vencimento
-- (0 = dentro do próprio mês, 1 = mês seguinte). Junto com dia_limite
-- forma a data de vencimento da competência.
--
-- Execute no Supabase (SQL Editor). Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

alter table documentos_empresa
  add column if not exists prazo_meses integer not null default 0;

comment on column documentos_empresa.prazo_meses is 'Meses entre a competência e o vencimento do envio (0 = mesmo mês, 1 = mês seguinte).';
