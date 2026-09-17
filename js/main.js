// Nav scroll effect
const nav = document.getElementById('main-nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 60);
});

// Mobile menu
const toggle = document.getElementById('nav-toggle');
const navLinks = document.getElementById('nav-links');
toggle.addEventListener('click', () => {
  navLinks.classList.toggle('open');
});
navLinks.querySelectorAll('a').forEach(a => {
  a.addEventListener('click', () => navLinks.classList.remove('open'));
});

// Animate on scroll (Intersection Observer)
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      observer.unobserve(e.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

// Rastreamento de cliques em WhatsApp / e-mail (menu, CTAs, rodapé, botão flutuante)
document.addEventListener('click', function(e) {
  const a = e.target.closest('a[href^="https://wa.me/"], a[href^="https://api.whatsapp.com/"], a[href^="mailto:"]');
  if (!a || typeof gtag !== 'function') return;
  const tipo = a.href.indexOf('mailto:') === 0 ? 'email' : 'whatsapp';
  let local = 'cta';
  if (a.closest('#main-nav') || a.closest('nav')) local = 'menu';
  else if (a.classList.contains('whatsapp-float')) local = 'flutuante';
  else if (a.classList.contains('social-link')) local = 'rodape';
  else if (a.closest('#contato')) local = 'secao_contato';
  gtag('event', 'cta_click_' + tipo, { local: local, pagina: location.pathname });
});

// Supabase (leitura pública / inserção de leads — chave anon)
const SUPABASE_URL = 'https://wwmlrifoxnekhgppikxa.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind3bWxyaWZveG5la2hncHBpa3hhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NTE3OTQsImV4cCI6MjA5NTIyNzc5NH0.6VIS72AJC8VOArvXh-4sXDuyrYRkj3zP5cUhuEaYPHo';
const sbSite = (typeof supabase !== 'undefined') ? supabase.createClient(SUPABASE_URL, SUPABASE_KEY) : null;

// Formulário: salva o lead (mesmo que o visitante não envie a mensagem no WhatsApp) e abre o WhatsApp
document.getElementById('form-contato').addEventListener('submit', function(e) {
  e.preventDefault();
  const nome     = document.getElementById('nome').value.trim();
  const telefone = document.getElementById('telefone').value.trim();
  const servico  = document.getElementById('servico').value;
  const mensagem = document.getElementById('mensagem').value.trim();

  if (sbSite) {
    sbSite.from('leads_site').insert({
      nome: nome, telefone: telefone, servico: servico, mensagem: mensagem,
      pagina: location.pathname, origem: 'formulario'
    }).then(function(r) {
      if (r.error) console.warn('Lead não salvo:', r.error.message);
    });
  }
  if (typeof gtag === 'function') {
    gtag('event', 'lead_formulario', { servico: servico, pagina: location.pathname });
  }

  const texto = `Olá! Vim pelo site da AJ TopoGeo.\n\n*Nome:* ${nome}\n*Telefone:* ${telefone}\n*Serviço:* ${servico}\n*Mensagem:* ${mensagem}`;
  const url = `https://wa.me/5567991379210?text=${encodeURIComponent(texto)}`;
  window.open(url, '_blank');
});

// Rascunho: quem preenche nome/telefone mas nunca chega a clicar em "Enviar
// via WhatsApp" também fica salvo, pra equipe poder retornar o contato.
// Dispara uma única vez (no primeiro "sair do campo telefone" com dados
// mínimos), fica em origem='rascunho' — separado do envio real no Gestor.
let _leadRascunhoEnviado = false;
function _tentarSalvarRascunho() {
  if (_leadRascunhoEnviado || !sbSite) return;
  const telefone = document.getElementById('telefone').value.trim();
  if (telefone.replace(/\D/g, '').length < 8) return;
  _leadRascunhoEnviado = true;
  sbSite.from('leads_site').insert({
    nome: document.getElementById('nome').value.trim(),
    telefone: telefone,
    servico: document.getElementById('servico').value,
    mensagem: document.getElementById('mensagem').value.trim(),
    pagina: location.pathname,
    origem: 'rascunho'
  }).then(function(r) {
    if (r.error) console.warn('Rascunho não salvo:', r.error.message);
  });
}
document.getElementById('telefone').addEventListener('blur', _tentarSalvarRascunho);

// Contador animado nas estatísticas
function animarContador(el) {
  const alvo = parseFloat(el.dataset.alvo);
  const sufixo = el.dataset.sufixo || '';
  const duracao = 1800;
  const inicio = performance.now();
  const frame = (agora) => {
    const prog = Math.min((agora - inicio) / duracao, 1);
    const ease = 1 - Math.pow(1 - prog, 3);
    const val = alvo * ease;
    el.textContent = (Number.isInteger(alvo) ? Math.round(val) : val.toFixed(0)) + sufixo;
    if (prog < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

const contadorObs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      animarContador(e.target);
      contadorObs.unobserve(e.target);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('[data-alvo]').forEach(el => contadorObs.observe(el));
