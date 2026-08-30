-- ═══════════════════════════════════════════════════════════════════════
-- ADMINISTRATIVO — anexo de arquivo em documentos_empresa.
--
-- A aba "Administrativo" já tem botão de enviar/baixar arquivo, mas a
-- coluna arquivo_url nunca foi criada nesta tabela (notas_fiscais e
-- impostos têm; documentos_empresa não). Sem ela todo upload falha com
-- "column documentos_empresa.arquivo_url does not exist".
--
-- Mesmo padrão das outras tabelas: o arquivo é gravado como data URL
-- (base64) na própria coluna, sem Supabase Storage.
--
-- tem_arquivo é gerada: permite listar os documentos sem trazer o base64
-- inteiro de cada linha na consulta da tela.
--
-- Execute no Supabase (SQL Editor). Seguro rodar mais de uma vez.
-- ═══════════════════════════════════════════════════════════════════════

alter table documentos_empresa
  add column if not exists arquivo_url  text,
  add column if not exists arquivo_nome text;

alter table documentos_empresa
  add column if not exists tem_arquivo boolean
  generated always as (arquivo_url is not null) stored;

comment on column documentos_empresa.arquivo_url  is 'Arquivo em data URL base64 (mesmo padrão de notas_fiscais.arquivo_url).';
comment on column documentos_empresa.arquivo_nome is 'Nome original do arquivo enviado, usado no download.';
comment on column documentos_empresa.tem_arquivo  is 'Gerada: indica anexo sem precisar trazer o base64 na listagem.';
