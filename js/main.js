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
      pagina: location.pathname
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
