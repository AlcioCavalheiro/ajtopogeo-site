# Como configurar o envio automático de lembretes via WhatsApp

## Pré-requisitos
- Conta no Supabase (já tem)
- Evolution API instalada (cloud ou self-hosted)
- Supabase CLI instalado: https://supabase.com/docs/guides/cli

---

## 1. Instalar e configurar a Evolution API

### Opção A — Cloud (mais fácil)
1. Acesse https://evolution-api.com e crie uma conta
2. Crie uma instância e conecte seu WhatsApp pelo QR Code
3. Anote: URL da API, API Key e nome da instância

### Opção B — Self-hosted (VPS, grátis)
```bash
git clone https://github.com/EvolutionAPI/evolution-api
cd evolution-api
cp .env.example .env
# edite o .env conforme necessário
docker-compose up -d
```
Depois acesse o painel, crie uma instância e conecte pelo QR Code.

---

## 2. Fazer deploy da Edge Function no Supabase

```bash
# Na pasta raiz do projeto (GESTOR/)
supabase login
supabase link --project-ref SEU_PROJECT_REF

# Deploy da função
supabase functions deploy notify-os-daily --no-verify-jwt
```

---

## 3. Configurar as variáveis de ambiente no Supabase

No painel do Supabase → Settings → Edge Functions → Environment Variables, adicione:

| Variável                  | Valor                                    |
|---------------------------|------------------------------------------|
| EVOLUTION_API_URL         | https://sua-evolution.com.br             |
| EVOLUTION_API_KEY         | sua_api_key_aqui                         |
| EVOLUTION_INSTANCE        | nome_da_instancia                        |

As variáveis SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY já são injetadas automaticamente.

---

## 4. Criar o cron job no Supabase (pg_cron)

No painel do Supabase → SQL Editor, execute:

```sql
-- Habilitar pg_cron (se ainda não estiver ativo)
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Agendar para rodar todo dia às 07:00 (horário UTC = 04:00 no Brasil GMT-3)
select cron.schedule(
  'notify-os-daily',
  '0 10 * * *',  -- 10:00 UTC = 07:00 Brasília (GMT-3)
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'supabase_functions_url') || '/notify-os-daily',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'supabase_anon_key')
    ),
    body := '{}'::jsonb
  );
  $$
);
```

### Alternativa mais simples (sem vault):
```sql
select cron.schedule(
  'notify-os-daily',
  '0 10 * * *',
  $$
  select net.http_post(
    url := 'https://SEU_PROJECT_REF.supabase.co/functions/v1/notify-os-daily',
    headers := '{"Content-Type":"application/json","Authorization":"Bearer SUA_ANON_KEY"}'::jsonb,
    body := '{}'::jsonb
  );
  $$
);
```
Substitua SEU_PROJECT_REF e SUA_ANON_KEY pelos valores do seu projeto
(Supabase → Settings → API).

---

## 5. Testar manualmente

Você pode chamar a função diretamente para testar:
```bash
supabase functions invoke notify-os-daily
```
Ou via HTTP:
```
POST https://SEU_PROJECT_REF.supabase.co/functions/v1/notify-os-daily
Authorization: Bearer SUA_ANON_KEY
```

---

## Como funciona

Todos os dias às 07h00 (Brasília), a função:
1. Busca todas as OS com data = hoje (exceto Concluída/Cancelada/Recebida)
2. Busca eventos de agenda com data = hoje que tenham OS vinculada
3. Para cada OS/evento, encontra o funcionário responsável pelo nome e pega o telefone cadastrado
4. Envia uma mensagem de lembrete pelo WhatsApp

## Observações
- O telefone do funcionário deve estar cadastrado com DDD (ex: 67999990000)
- O campo "Responsável" na OS deve conter exatamente o mesmo nome do funcionário cadastrado
- Funcionários sem telefone cadastrado não recebem o lembrete
