/* AJ TopoGeo — rastreamento de conversões GA4 + Meta Pixel
   Delegação de eventos: cobre qualquer link/formulário da página,
   inclusive os inseridos dinamicamente. Não requer alterar o HTML dos botões. */
(function () {
  'use strict';

  function ga(nome, params) {
    if (typeof window.gtag === 'function') window.gtag('event', nome, params || {});
  }
  function fb(nome, params) {
    if (typeof window.fbq === 'function') window.fbq('track', nome, params || {});
  }

  // Trava anti-duplicidade: ignora o mesmo evento repetido em menos de 1s
  var ultimo = { chave: '', ts: 0 };
  function dispara(chave, fn) {
    var agora = Date.now();
    if (ultimo.chave === chave && (agora - ultimo.ts) < 1000) return;
    ultimo = { chave: chave, ts: agora };
    try { fn(); } catch (e) { /* nunca quebrar a navegação do usuário */ }
  }

  function contexto(el) {
    return {
      link_url: el && el.href ? el.href : '',
      link_text: el ? (el.innerText || el.textContent || '').trim().slice(0, 100) : '',
      page_location: location.href,
      page_title: document.title
    };
  }

  function merge(a, b) {
    var r = {}, k;
    for (k in a) if (Object.prototype.hasOwnProperty.call(a, k)) r[k] = a[k];
    for (k in b) if (Object.prototype.hasOwnProperty.call(b, k)) r[k] = b[k];
    return r;
  }

  // ---- Cliques em links de contato ----
  document.addEventListener('click', function (ev) {
    var alvo = ev.target;
    if (!alvo || !alvo.closest) return;
    var a = alvo.closest('a[href]');
    if (!a) return;

    var href = (a.getAttribute('href') || '').toLowerCase();
    var ctx = contexto(a);

    if (href.indexOf('wa.me') !== -1 ||
        href.indexOf('api.whatsapp.com') !== -1 ||
        href.indexOf('whatsapp://') === 0) {
      dispara('whatsapp', function () {
        ga('cta_click_whatsapp', merge({ button_type: 'whatsapp' }, ctx));
        fb('Contact', { content_name: 'whatsapp', content_category: 'contato' });
      });
    } else if (href.indexOf('tel:') === 0) {
      dispara('phone', function () {
        ga('cta_click_phone', merge({ button_type: 'telefone' }, ctx));
        fb('Contact', { content_name: 'telefone', content_category: 'contato' });
      });
    } else if (href.indexOf('mailto:') === 0) {
      dispara('email', function () {
        ga('cta_click_email', merge({ button_type: 'email' }, ctx));
        fb('Contact', { content_name: 'email', content_category: 'contato' });
      });
    }
  }, true); // capture: dispara antes de a navegação sair da página

  // ---- Envio do formulário de contato ----
  document.addEventListener('submit', function (ev) {
    var f = ev.target;
    if (!f || f.tagName !== 'FORM') return;

    var servico = f.querySelector('[name*="servic" i], [name*="assunto" i], #servico, #tipo-servico');

    dispara('form', function () {
      ga('form_submit_contato', {
        form_id: f.id || 'formulario-contato',
        service_type: servico && servico.value ? servico.value : '(nao informado)',
        page_location: location.href,
        page_title: document.title
      });
      fb('Lead', {
        content_name: f.id || 'formulario-contato',
        content_category: servico && servico.value ? servico.value : 'geral'
      });
    });
  }, true);
})();
