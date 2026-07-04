// Supabase Edge Function — notify-os-daily
// Roda diariamente via cron e envia lembretes de OS/agenda pelo WhatsApp (Evolution API)

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SUPABASE_SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const EVO_URL = Deno.env.get('EVOLUTION_API_URL')!;       // ex: https://api.suaevo.com.br
const EVO_KEY = Deno.env.get('EVOLUTION_API_KEY')!;       // apikey da Evolution
const EVO_INSTANCE = Deno.env.get('EVOLUTION_INSTANCE')!; // nome da instância conectada

const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

// Normaliza telefone para formato internacional sem +  ex: 5567999990000
function normFone(tel: string): string {
  const digits = tel.replace(/\D/g, '');
  if (digits.startsWith('55') && digits.length >= 12) return digits;
  if (digits.length === 11) return '55' + digits; // celular com DDD
  if (digits.length === 10) return '55' + digits; // fixo com DDD
  return '55' + digits;
}

async function enviarWhatsApp(telefone: string, mensagem: string) {
  const numero = normFone(telefone);
  const url = `${EVO_URL}/message/sendText/${EVO_INSTANCE}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': EVO_KEY,
    },
    body: JSON.stringify({
      number: numero,
      textMessage: { text: mensagem },
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error(`Erro ao enviar para ${numero}:`, err);
  } else {
    console.log(`Enviado para ${numero}`);
  }
}

Deno.serve(async (_req) => {
  try {
    const hoje = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

    // Buscar funcionários indexados por nome (lowercase) → telefone
    const { data: funcs } = await sb
      .from('funcionarios')
      .select('nome, telefone')
      .eq('ativo', true)
      .not('telefone', 'is', null);

    const funcMap: Record<string, string> = {};
    for (const f of funcs ?? []) {
      if (f.telefone) funcMap[f.nome.trim().toLowerCase()] = f.telefone;
    }

    // ── 1. OS com data de hoje ─────────────────────────────────
    const { data: ordens } = await sb
      .from('ordens')
      .select('numero, tipo, responsavel, clientes(nome)')
      .eq('data', hoje)
      .not('status', 'in', '("Concluída","Cancelada","Recebido")');

    let enviados = 0;

    for (const os of ordens ?? []) {
      if (!os.responsavel) continue;
      // responsavel pode ser string simples ou "Nome1, Nome2"
      const responsaveis = String(os.responsavel).split(',').map((r: string) => r.trim());
      const clienteNome = (os.clientes as any)?.nome ?? '—';

      for (const nome of responsaveis) {
        const tel = funcMap[nome.toLowerCase()];
        if (!tel) {
          console.warn(`Telefone não encontrado para: ${nome}`);
          continue;
        }
        const msg =
          `🔧 *Lembrete de OS — ${hoje}*\n\n` +
          `Olá, *${nome}*! Você tem uma OS agendada para hoje:\n\n` +
          `📋 *OS:* ${os.numero}\n` +
          `🏗️ *Tipo:* ${os.tipo ?? '—'}\n` +
          `👤 *Cliente:* ${clienteNome}\n\n` +
          `Acesse o sistema para mais detalhes. Bom trabalho! 💪`;
        await enviarWhatsApp(tel, msg);
        enviados++;
      }
    }

    // ── 2. Tarefas de agenda com data de hoje ─────────────────
    const { data: agenda } = await sb
      .from('agenda')
      .select('titulo, tipo, descricao, hora, os_numero')
      .eq('data', hoje);

    // agenda não tem responsável direto — envia para todos os funcionários
    // que têm OS vinculada; se não tiver, envia para quem tiver a OS no campo os_numero
    for (const ev of agenda ?? []) {
      if (!ev.os_numero) continue;
      // Buscar OS para pegar o responsável
      const { data: osRef } = await sb
        .from('ordens')
        .select('responsavel')
        .eq('numero', ev.os_numero)
        .single();

      if (!osRef?.responsavel) continue;
      const responsaveis = String(osRef.responsavel).split(',').map((r: string) => r.trim());

      for (const nome of responsaveis) {
        const tel = funcMap[nome.toLowerCase()];
        if (!tel) continue;
        const hora = ev.hora ? ` às ${ev.hora}` : '';
        const msg =
          `📅 *Lembrete de Agenda — ${hoje}*\n\n` +
          `Olá, *${nome}*! Você tem um compromisso hoje${hora}:\n\n` +
          `📌 *${ev.titulo}*\n` +
          `🏷️ *Tipo:* ${ev.tipo ?? '—'}\n` +
          (ev.os_numero ? `🔗 *OS vinculada:* ${ev.os_numero}\n` : '') +
          (ev.descricao ? `📝 ${ev.descricao}\n` : '') +
          `\nFique atento ao horário! ✅`;
        await enviarWhatsApp(tel, msg);
        enviados++;
      }
    }

    return new Response(
      JSON.stringify({ ok: true, hoje, enviados }),
      { headers: { 'Content-Type': 'application/json' } },
    );
  } catch (err) {
    console.error(err);
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    );
  }
});
