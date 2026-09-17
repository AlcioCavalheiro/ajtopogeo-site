// Nav scroll
const nav = document.getElementById('main-nav');
if (nav) {
  window.addEventListener('scroll', () => nav.classList.toggle('scrolled', window.scrollY > 60));
}
// Menu mobile
const toggle = document.getElementById('nav-toggle');
const navLinks = document.getElementById('nav-links');
if (toggle && navLinks) {
  toggle.addEventListener('click', () => navLinks.classList.toggle('open'));
  navLinks.querySelectorAll('a').forEach(a => a.addEventListener('click', () => navLinks.classList.remove('open')));
}
// FAQ accordion
document.querySelectorAll('.faq-pergunta').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.closest('.faq-item').classList.toggle('aberto');
  });
});

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

// Filtro de categorias do blog
const filtroBtns = document.querySelectorAll('.filtro-btn');
if (filtroBtns.length) {
  const cards = document.querySelectorAll('.blog-card');
  filtroBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filtroBtns.forEach(b => b.classList.remove('ativo'));
      btn.classList.add('ativo');
      const f = btn.dataset.f;
      cards.forEach(c => {
        const mostra = (f === 'todos' || c.dataset.cat === f);
        c.classList.toggle('oculto', !mostra);
      });
    });
  });
}
