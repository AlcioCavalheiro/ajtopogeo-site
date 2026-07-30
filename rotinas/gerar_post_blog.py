# -*- coding: utf-8 -*-
"""Gera um post de blog da AJ TopoGeo a partir de um JSON e cuida do resto.

    py rotinas/gerar_post_blog.py caminho/do/post.json

A partir de UM json descrevendo a notícia, o script:
  1. escreve  blog-<slug>.html  na raiz do repositório, com o mesmo template
     dos posts existentes (head de SEO completo, nav, hero, artigo, sidebar,
     faixa de CTA, footer, botão de WhatsApp, js/paginas.js);
  2. insere o card do post no TOPO do grid em  blog.html;
  3. acrescenta a entrada de URL em  sitemap.xml.

Nada de conteúdo é decidido aqui: título, texto, imagem e links vêm todos do
JSON. A ideia é a mesma da rotina de Instagram — refazer um post vira editar
JSON, e o boilerplate de SEO (canonical de URL limpa, og, JSON-LD) nunca sai
errado por descuido de digitação.

Esquema do JSON em  rotinas/exemplo-post-blog.json .

O script NÃO publica: ele só edita arquivos no repositório. Quem revisa,
commita e dá push é o usuário.
"""

import sys as _s
_s.stdout.reconfigure(encoding="utf-8", errors="replace")
import html
import json
import os
import re
import sys

# raiz do repositório: este arquivo fica em <repo>/rotinas/gerar_post_blog.py
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://ajtopogeo.com.br"

# categorias do filtro em blog.html (data-cat / botões .filtro-btn)
CATS = {"geo", "topo", "reg", "amb", "drone", "doc"}


def esc(s):
    """Escapa para uso em atributo HTML (aspas duplas)."""
    return html.escape(str(s), quote=True)


def _parag(texto):
    """Um parágrafo. Aceita HTML inline (o autor do JSON controla o conteúdo)."""
    return f"      <p>{texto}</p>"


def _secao(sec):
    partes = []
    if sec.get("h2"):
        partes.append(f"      <h2>{sec['h2']}</h2>")
    for p in sec.get("paragrafos", []):
        partes.append(_parag(p))
    lista = sec.get("lista")
    if lista:
        partes.append("      <ul>")
        for item in lista:
            partes.append(f"        <li>{item}</li>")
        partes.append("      </ul>")
    return "\n".join(partes)


def montar_html(d):
    slug = d["slug"]
    url = f"{SITE}/blog-{slug}"
    img_url = f"{SITE}/img/{d['imagem']}"
    accent = "var(--verde)"

    # corpo do artigo
    corpo = [_parag(d["intro"])]
    for sec in d.get("secoes", []):
        corpo.append(_secao(sec))

    # bloco de fonte (atribuição da notícia)
    fonte = d.get("fonte")
    if fonte:
        corpo.append(
            f'      <p class="fonte-nota" style="font-size:.9rem;color:var(--cinza);'
            f'margin-top:32px;">Fonte: {fonte["nome"]}'
            + (f' · <a href="{esc(fonte["url"])}" target="_blank" rel="noopener nofollow" '
               f'style="color:{accent};">matéria original</a>' if fonte.get("url") else "")
            + ".</p>"
        )
    corpo_html = "\n\n".join(corpo)

    # "Leia também" na sidebar
    leia = "\n".join(
        f'          <a href="{esc(l["href"])}">{l["label"]}</a>'
        for l in d.get("leia_tambem", [])
    )

    cta_s = d.get("cta_sidebar", {})
    cta_f = d.get("cta_faixa", {})
    wa_s = esc_wa(cta_s.get("wa_text", "Olá! Vim pelo blog da AJ TopoGeo."))
    wa_f = esc_wa(cta_f.get("wa_text", "Olá! Vim pelo blog e quero um orçamento."))

    jsonld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": d.get("og_title", d["title"]),
        "image": img_url,
        "author": {"@type": "Organization", "name": "AJ TopoGeo"},
        "publisher": {"@type": "Organization", "name": "AJ TopoGeo"},
        "datePublished": d["data_publicacao"],
        "description": d.get("og_description", d["meta_description"]),
    }

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(d['title'])}</title>
  <meta name="description" content="{esc(d['meta_description'])}" />
  <meta name="keywords" content="{esc(d['meta_keywords'])}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{esc(d.get('og_title', d['title']))}" />
  <meta property="og:description" content="{esc(d.get('og_description', d['meta_description']))}" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:url" content="{url}" />
  <script type="application/ld+json">
  {json.dumps(jsonld, ensure_ascii=False, separators=(',', ':'))}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/style.css" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%233E8FC4'/><text x='16' y='22' font-size='16' text-anchor='middle' fill='%230d1b2a' font-family='Arial' font-weight='900'>AJ</text></svg>" />
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-0ZY8XR9WYR"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-0ZY8XR9WYR');
  </script></head>
<body>

<nav id="main-nav" class="scrolled">
  <div class="container nav-inner">
    <a href="/" class="logo"><div class="logo-icon">AJ</div><span class="logo-text">AJ <span>TopoGeo</span></span></a>
    <ul class="nav-links" id="nav-links">
      <li><a href="sobre">Sobre</a></li>
      <li class="has-dropdown">
        <a href="/#servicos" class="dropdown-toggle">Serviços</a>
        <div class="dropdown-menu">
          <a href="georreferenciamento-incra">Georreferenciamento INCRA</a>
          <a href="topografia-levantamento-planialtimetrico">Topografia e Levantamento</a>
          <a href="agrimensura">Agrimensura e Regularização</a>
          <a href="car-cadastro-ambiental-rural">CAR – Cadastro Ambiental Rural</a>
          <a href="mapeamento-com-drones">Mapeamento com Drones</a>
          <a href="itr-regularizacao-rural">ITR e Documentação Rural</a>
        </div>
      </li>
      <li><a href="blog">Blog</a></li>
      <li><a href="/#galeria">Galeria</a></li>
      <li><a href="/#contato" class="nav-cta">Solicitar Orçamento</a></li>
    </ul>
    <button class="nav-toggle" id="nav-toggle" aria-label="Menu"><span></span><span></span><span></span></button>
  </div>
</nav>

<header class="page-hero">
  <div class="container">
    <div class="breadcrumb"><a href="/">Início</a> › <a href="blog">Blog</a> › {esc(d['breadcrumb'])}</div>
    <h1>{d['hero_h1']}</h1>
    <p class="lead">{d['hero_lead']}</p>
  </div>
</header>

<section class="artigo">
  <div class="container artigo-grid">
    <article class="artigo-conteudo">
      <img src="img/{esc(d['imagem'])}" alt="{esc(d['imagem_alt'])}" class="artigo-img" />

{corpo_html}
    </article>

    <aside>
      <div class="sidebar-card">
        <h3>{cta_s.get('titulo', 'Fale com a AJ TopoGeo')}</h3>
        <p>{cta_s.get('texto', 'Atendemos todo o Mato Grosso do Sul com responsabilidade técnica.')}</p>
        <a href="https://wa.me/5567991379210?text={wa_s}" target="_blank" rel="noopener" class="btn-primary">📲 Falar no WhatsApp</a>
        <div class="sidebar-links">
          <h4>Leia também</h4>
{leia}
        </div>
      </div>
    </aside>
  </div>
</section>

<section class="cta-faixa">
  <div class="container">
    <h2>{cta_f.get('titulo', 'Precisa regularizar seu imóvel?')}</h2>
    <p>{cta_f.get('texto', 'Georreferenciamento, topografia e regularização com precisão e responsabilidade técnica em MS.')}</p>
    <a href="https://wa.me/5567991379210?text={wa_f}" target="_blank" rel="noopener" class="btn-branco">📲 Solicitar Orçamento</a>
  </div>
</section>

<footer>
  <div class="container">
    <div class="footer-inner">
      <a href="/" class="logo"><div class="logo-icon">AJ</div><span class="logo-text">AJ <span>TopoGeo</span></span></a>
      <div class="social-links">
        <a href="https://instagram.com/aj_topogeo" target="_blank" rel="noopener" class="social-link">📸</a>
        <a href="https://wa.me/5567991379210" target="_blank" rel="noopener" class="social-link">💬</a>
        <a href="mailto:alcio@ajtopogeo.com.br" class="social-link">✉️</a>
      </div>
    </div>
    <div style="border-top:1px solid rgba(255,255,255,0.06);padding-top:20px;">
      <p class="footer-copy">© 2026 AJ TopoGeo · CNPJ 46.639.961/0001-41 · Sidrolândia–MS</p>
    </div>
  </div>
</footer>

<a href="https://wa.me/5567991379210?text=Ol%C3%A1!%20Vim%20pelo%20site%20da%20AJ%20TopoGeo." target="_blank" rel="noopener" class="whatsapp-float" aria-label="WhatsApp">
  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="currentColor" viewBox="0 0 16 16"><path d="M13.601 2.326A7.854 7.854 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.204-1.102a7.933 7.933 0 0 0 3.79.965h.004c4.368 0 7.926-3.558 7.93-7.93A7.898 7.898 0 0 0 13.6 2.326zM7.994 14.521a6.573 6.573 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c0-3.626 2.957-6.584 6.591-6.584a6.56 6.56 0 0 1 4.66 1.931 6.557 6.557 0 0 1 1.928 4.66c-.004 3.639-2.961 6.592-6.592 6.592zm3.615-4.934c-.197-.099-1.17-.578-1.353-.646-.182-.065-.315-.099-.445.099-.133.197-.513.646-.627.775-.114.133-.232.148-.43.05-.197-.1-.836-.308-1.592-.985-.59-.525-.985-1.175-1.103-1.372-.114-.198-.011-.304.088-.403.087-.088.197-.232.296-.346.1-.114.133-.198.198-.33.065-.134.034-.248-.015-.347-.05-.099-.445-1.076-.612-1.47-.16-.389-.323-.335-.445-.34-.114-.007-.247-.007-.38-.007a.729.729 0 0 0-.529.247c-.182.198-.691.677-.691 1.654 0 .977.71 1.916.81 2.049.098.133 1.394 2.132 3.383 2.992.47.205.84.326 1.129.418.475.152.904.129 1.246.08.38-.058 1.171-.48 1.338-.943.164-.464.164-.86.114-.943-.049-.084-.182-.133-.38-.232z"/></svg>
</a>

<script src="js/paginas.js"></script>
</body>
</html>
"""


def esc_wa(texto):
    """Codifica texto para o parâmetro ?text= do wa.me (%20 etc.)."""
    from urllib.parse import quote
    return quote(texto)


def inserir_card_blog(d):
    """Insere o card do post no topo de .blog-grid em blog.html."""
    caminho = os.path.join(REPO, "blog.html")
    with open(caminho, encoding="utf-8") as fh:
        conteudo = fh.read()

    if f'href="blog-{d["slug"]}"' in conteudo:
        print(f"  card já existe em blog.html para blog-{d['slug']} — pulei")
        return

    cat = d.get("categoria", "geo")
    if cat not in CATS:
        raise SystemExit(f"categoria inválida: {cat} (use {sorted(CATS)})")

    card = f"""
      <article class="blog-card" data-cat="{cat}">
        <img src="img/{esc(d['imagem'])}" alt="{esc(d['imagem_alt'])}" class="blog-card-img" />
        <div class="blog-card-body">
          <span class="blog-tag">{esc(d['tag'])}</span>
          <h3>{esc(d['titulo_card'])}</h3>
          <p>{esc(d['resumo_card'])}</p>
          <a href="blog-{d['slug']}" class="servico-link">Ler artigo →</a>
        </div>
      </article>
"""
    marcador = '<div class="blog-grid">'
    idx = conteudo.find(marcador)
    if idx == -1:
        raise SystemExit("não achei <div class=\"blog-grid\"> em blog.html")
    pos = idx + len(marcador)
    novo = conteudo[:pos] + "\n" + card + conteudo[pos:]
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(novo)
    print("  card inserido no topo de blog.html")


def inserir_sitemap(d):
    caminho = os.path.join(REPO, "sitemap.xml")
    with open(caminho, encoding="utf-8") as fh:
        conteudo = fh.read()
    loc = f"{SITE}/blog-{d['slug']}"
    if loc in conteudo:
        print("  sitemap já tem a URL — pulei")
        return
    entrada = (
        f"  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>0.8</priority>\n"
        f"  </url>\n"
    )
    conteudo = conteudo.replace("</urlset>", entrada + "</urlset>")
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(conteudo)
    print("  entrada adicionada ao sitemap.xml")


def validar(d):
    obrig = ["slug", "categoria", "tag", "titulo_card", "resumo_card", "imagem",
             "imagem_alt", "title", "meta_description", "meta_keywords",
             "breadcrumb", "hero_h1", "hero_lead", "data_publicacao", "intro"]
    faltando = [k for k in obrig if not d.get(k)]
    if faltando:
        raise SystemExit("faltam campos no JSON: " + ", ".join(faltando))
    if not re.fullmatch(r"[a-z0-9-]+", d["slug"]):
        raise SystemExit("slug deve ser minúsculo, com hífens: " + d["slug"])
    img = os.path.join(REPO, "img", d["imagem"])
    if not os.path.exists(img):
        raise SystemExit(f"imagem não existe em img/: {d['imagem']}")


def main(caminho_json):
    with open(caminho_json, encoding="utf-8") as fh:
        d = json.load(fh)
    validar(d)

    destino = os.path.join(REPO, f"blog-{d['slug']}.html")
    if os.path.exists(destino):
        raise SystemExit(f"já existe: {destino} (apague se quer regerar)")

    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(montar_html(d))
    print(f"gerado: blog-{d['slug']}.html")

    inserir_card_blog(d)
    inserir_sitemap(d)
    print(f"\nURL final (após deploy): {SITE}/blog-{d['slug']}")
    print("Revise e, quando aprovar, faça commit + push você mesmo.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: py rotinas/gerar_post_blog.py caminho/do/post.json")
    main(sys.argv[1])
