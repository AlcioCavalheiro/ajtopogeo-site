-- OS ganha um campo para indicar se é executada em campo ou no escritório.
-- Sem valor definido (NULL) = comportamento atual, sem nenhuma trava nova.
-- Só quando for explicitamente 'Campo' o app de Campo passa a exigir veículo
-- selecionado no turno antes de assumir a OS.
ALTER TABLE ordens ADD COLUMN IF NOT EXISTS local_execucao text;
