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

// Formulário: envio via WhatsApp
document.getElementById('form-contato').addEventListener('submit', function(e) {
  e.preventDefault();
  const nome     = document.getElementById('nome').value.trim();
  const telefone = document.getElementById('telefone').value.trim();
  const servico  = document.getElementById('servico').value;
  const mensagem = document.getElementById('mensagem').value.trim();
  const texto = `Olá! Vim pelo site da AJ TopoGeo.\n\n*Nome:* ${nome}\n*Telefone:* ${telefone}\n*Serviço:* ${servico}\n*Mensagem:* ${mensagem}`;
  const url = `https://wa.me/5567993480660?text=${encodeURIComponent(texto)}`;
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
