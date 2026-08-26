// api/agenda-convite.js — Envia por e-mail o convite de uma tarefa agendada no
// Gestor (OS > Agendar Tarefa), com um link "Adicionar ao Google Calendar" e um
// arquivo .ics anexado (funciona em qualquer app de calendário).
//
// Requer a variável de ambiente RESEND_API_KEY (conta em resend.com).
// RESEND_FROM é opcional — sem domínio verificado no Resend, o remetente padrão
// (onboarding@resend.dev) só entrega para o e-mail dono da conta Resend.
//
// Uso: POST /api/agenda-convite  { to, nome, titulo, descricao, data, osNumero, frequencia }
// frequencia (opcional, usado pelas Rotinas Recorrentes): Diária | Semanal | Quinzenal | Mensal | Trimestral | Anual

const RRULE_POR_FREQUENCIA = {
  'Diária': 'FREQ=DAILY',
  'Semanal': 'FREQ=WEEKLY',
  'Quinzenal': 'FREQ=WEEKLY;INTERVAL=2',
  'Mensal': 'FREQ=MONTHLY',
  'Trimestral': 'FREQ=MONTHLY;INTERVAL=3',
  'Anual': 'FREQ=YEARLY',
};

function escapeICS(str) {
  return String(str || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
}

function ymd(dateStr) {
  return String(dateStr || '').replace(/-/g, '');
}

function proximoDia(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  d.setDate(d.getDate() + 1);
  return d.toISOString().split('T')[0];
}

function buildICS({ titulo, descricao, data, uid, frequencia }) {
  const dtStart = ymd(data);
  const dtEnd = ymd(proximoDia(data));
  const dtStamp = new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const rrule = RRULE_POR_FREQUENCIA[frequencia];
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//AJ TopoGeo//Gestor//PT-BR',
    'CALSCALE:GREGORIAN',
    'BEGIN:VEVENT',
    'UID:' + uid,
    'DTSTAMP:' + dtStamp,
    'DTSTART;VALUE=DATE:' + dtStart,
    'DTEND;VALUE=DATE:' + dtEnd,
  ];
  if (rrule) lines.push('RRULE:' + rrule);
  lines.push(
    'SUMMARY:' + escapeICS(titulo),
    'DESCRIPTION:' + escapeICS(descricao),
    'END:VEVENT',
    'END:VCALENDAR',
  );
  return lines.join('\r\n');
}

function googleCalendarLink({ titulo, descricao, data, frequencia }) {
  const dtStart = ymd(data);
  const dtEnd = ymd(proximoDia(data));
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: titulo || '',
    dates: dtStart + '/' + dtEnd,
    details: descricao || '',
  });
  const rrule = RRULE_POR_FREQUENCIA[frequencia];
  if (rrule) params.set('recur', 'RRULE:' + rrule);
  return 'https://calendar.google.com/calendar/render?' + params.toString();
}

function fdBR(dateStr) {
  if (!dateStr) return '';
  const [y, m, d] = String(dateStr).split('-');
  return d + '/' + m + '/' + y;
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }
  if (req.method !== 'POST') { res.statusCode = 405; return res.json({ error: 'Método não permitido' }); }

  try {
    const apiKey = process.env.RESEND_API_KEY;
    if (!apiKey) { res.statusCode = 500; return res.json({ error: 'RESEND_API_KEY não configurada' }); }

    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const { to, nome, titulo, descricao, data, osNumero, frequencia } = body;
    if (!to || !titulo || !data) { res.statusCode = 400; return res.json({ error: 'Parâmetros obrigatórios: to, titulo, data' }); }

    const detalhes = (descricao || '') + (osNumero ? '\n\nOS: ' + osNumero : '');
    const uid = 'tarefa-' + (osNumero || 'geral') + '-' + Date.now() + '@ajtopogeo.com.br';
    const ics = buildICS({ titulo, descricao: detalhes, data, uid, frequencia });
    const gcalLink = googleCalendarLink({ titulo, descricao: detalhes, data, frequencia });
    const from = process.env.RESEND_FROM || 'AJ TopoGeo <onboarding@resend.dev>';
    const assunto = frequencia ? 'Rotina agendada: ' + titulo : 'Tarefa agendada: ' + titulo;

    const html = `
      <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto">
        <h2 style="color:#1a1a1a;margin-bottom:4px">${frequencia ? 'Nova rotina agendada' : 'Nova tarefa agendada'}</h2>
        <p style="color:#555">Olá${nome ? ', ' + nome : ''}! ${frequencia ? 'Uma rotina recorrente foi agendada para você' : 'Uma tarefa foi agendada para você'}${osNumero ? ' na OS <strong>' + osNumero + '</strong>' : ''}:</p>
        <div style="background:#f7f7f5;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0 0 8px;font-weight:600">${titulo}</p>
          ${descricao ? '<p style="margin:0 0 8px;color:#555">' + descricao + '</p>' : ''}
          <p style="margin:0;color:#854F0B"><strong>${frequencia ? 'Próxima execução' : 'Prazo'}:</strong> ${fdBR(data)}</p>
          ${frequencia ? '<p style="margin:4px 0 0;color:#854F0B"><strong>Repete:</strong> ' + frequencia + '</p>' : ''}
        </div>
        <p><a href="${gcalLink}" style="background:#4285F4;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600">Adicionar ao Google Calendar</a></p>
        <p style="color:#999;font-size:12px">Também anexamos um arquivo .ics — abra-o para adicionar em qualquer app de calendário${frequencia ? ' (já com a recorrência configurada)' : ''}.</p>
      </div>`;

    const emailResp = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from,
        to: [to],
        subject: assunto,
        html,
        attachments: [{ filename: 'tarefa.ics', content: Buffer.from(ics).toString('base64') }],
      }),
    });

    const result = await emailResp.json();
    if (!emailResp.ok) { res.statusCode = emailResp.status; return res.json({ error: result.message || 'Falha ao enviar e-mail', detail: result }); }

    res.statusCode = 200;
    return res.json({ ok: true, id: result.id });
  } catch (err) {
    res.statusCode = 500;
    return res.json({ error: err.message || 'Erro interno' });
  }
};
