-- Execute este SQL no Supabase (SQL Editor) antes de usar a nova versão do PDF de Medição.
-- Guarda na própria medição os dados que antes eram digitados toda vez que se gerava o PDF
-- (obra, contrato, município/UF, período e datas). Assim o PDF só pega esses dados prontos;
-- para corrigir algo, edita-se a medição em vez de preencher tudo de novo na hora de gerar o PDF.

alter table medicoes add column if not exists obra text;
alter table medicoes add column if not exists contrato text;
alter table medicoes add column if not exists municipio text;
alter table medicoes add column if not exists data_ini date;
alter table medicoes add column if not exists data_fim date;
alter table medicoes add column if not exists data_documento date;
