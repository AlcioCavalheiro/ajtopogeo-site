-- Execute este SQL no Supabase (SQL Editor) antes de usar a nova ordenação de OS.
-- Adiciona a coluna atualizado_em e um trigger que a atualiza sozinha
-- em qualquer UPDATE na tabela ordens (cobre edições feitas fora do app também).

alter table ordens add column if not exists atualizado_em timestamptz;

create or replace function set_atualizado_em()
returns trigger as $$
begin
  new.atualizado_em = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_ordens_atualizado_em on ordens;
create trigger trg_ordens_atualizado_em
before update on ordens
for each row
execute function set_atualizado_em();
