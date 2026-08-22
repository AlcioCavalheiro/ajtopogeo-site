---
name: radar-noticias
description: Rotina semanal de radar de notícias do setor — busca matérias novas sobre georreferenciamento, INCRA/SIGEF, CAR, ITR, topografia, agrimensura, drones e regularização fundiária, e transforma a mais relevante em um post de blog no site + carrossel + Reel narrado para o Instagram. Use quando o usuário pedir "radar de notícias", "notícia do setor", "novidade sobre georreferenciamento/INCRA", mandar um link de matéria para virar post, ou rodar a rotina semanal de notícias.
---

# Rotina 6 — Radar de Notícias (blog + Instagram)

Cadência: semanal. Objetivo: manter o site e o Instagram com conteúdo de
atualidade, aproveitando notícia do setor para ranquear no Google e dar assunto
para o feed — sem tirar tempo da execução técnica.

**Esta rotina roda quase inteira sem perguntar nada.** Você busca, escolhe a
notícia, escreve e monta tudo. Não pergunte qual notícia usar, qual imagem
escolher, quantos cards fazer ou se pode prosseguir — decida e execute. A única
coisa que você **não faz** é publicar: não commita, não dá push, não posta.

Se o usuário já mandar um link de notícia, pule a busca e trabalhe aquele link.

## Modo retomável — rodar sob `/loop` sem perder o trabalho no meio

Esta rotina é longa e pode bater no limite de uso no meio do caminho. Para que
ela **pause sozinha e retome de onde parou** (sem refazer nem pular etapa), ela
trabalha a partir de um arquivo de estado (checkpoint) e é chamada em ciclo pelo
`/loop`. Quando o limite estoura, a chamada em curso simplesmente não avança; a
próxima chamada do `/loop` retoma pelo estado quando o limite resetar.

**Arquivo de estado:** `C:\Users\ALCIO\.ajtopogeo\estado\radar-noticias.json`
(fora do repo; sobrevive a reinício do app e a nova sessão).

**No começo de TODA execução, carregue o estado e decida:**

- **Não existe** → rodada nova. Crie-o com todos os passos em `pendente`,
  `concluido: false`, e grave o caminho do scratchpad desta sessão.
- **Existe com `concluido: true`** → a rodada anterior já terminou. Trate como
  rodada **nova** (semana nova): sobrescreva com um estado zerado. (Só retome
  aquela se o usuário disser explicitamente que quer continuá-la.)
- **Existe com `concluido: false`** → **retome**: pule os passos marcados `feito`
  e continue do primeiro `pendente`, reusando o que já foi gravado (notícia
  escolhida, slug, pasta das peças).

**Regra de ouro:** faça os passos pendentes **em ordem** e **grave o estado logo
após concluir cada um**, antes de começar o próximo. É essa gravação que torna a
retomada segura. Faça quantos passos couberem nesta execução — não precisa parar
após um só; se o limite cortar no meio, o estado guarda até o último passo
concluído e a próxima chamada do `/loop` continua dali.

Mapa passo → campo do estado (`feito` só quando a condição estiver cumprida):

| passo (seções abaixo) | campo | `feito` quando |
| --- | --- | --- |
| 1–3 Buscar, deduplicar, escolher | `buscar_escolher` | a notícia está escolhida e gravada no estado (slug, título, tema, fonte, url) |
| 4 Post de blog | `post_blog` | `blog-<slug>.html` existe **e** o card está em `blog.html` **e** a URL está no `sitemap.xml` |
| 5 Carrossel + Reel + guia | `pecas_instagram` | os arquivos existem na pasta de saída (cards do carrossel, `_REEL.mp4`, guia PDF) |
| 6 Registrar no histórico | `registrar` | a entrada está em `rotinas/radar-noticias-historico.json` |
| 7 Entregar ao usuário | `entregar` | o resumo em prosa foi apresentado |

**Por que refazer um passo é seguro (idempotência):** `gerar_post_blog.py` recusa
slug repetido e não duplica card nem sitemap; `render.py`, `reel_noticia.py` e
`guia_pdf.py` sobrescrevem as saídas. Então reexecutar um passo que rodou pela
metade não gera lixo. **Única exceção:** se `blog-<slug>.html` já existe mas o
card ainda não está em `blog.html`, o script aborta com "já existe" — nesse caso
não o rode de novo; insira à mão o card em `blog.html` e a URL no `sitemap.xml`
(o formato está nos outros posts) e marque o passo `feito`.

**Encerramento:** ao terminar o passo 7, grave `concluido: true`. Se estiver sob
`/loop`, avise que a rotina terminou e **encerre o loop** (pare os disparos
agendados); não reexecute.

Esquema do estado:

```json
{
  "rotina": "radar-noticias",
  "atualizado_em": "2026-07-30T14:00:00-04:00",
  "scratchpad": "C:\\...\\scratchpad",
  "noticia": { "titulo": "", "tema": "", "fonte": "", "fonte_url": "", "slug": "", "resumo": "" },
  "pasta_pecas": "",
  "passos": {
    "buscar_escolher": "pendente",
    "post_blog": "pendente",
    "pecas_instagram": "pendente",
    "registrar": "pendente",
    "entregar": "pendente"
  },
  "concluido": false
}
```

## Ambiente

Todos os scripts rodam no venv da empresa (o mesmo das outras rotinas de
conteúdo):

```
C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe
```

Leia `scripts/README.md` antes de montar as peças — ele tem o esquema dos JSON
e as armadilhas já pagas.

## Passo 1 — Buscar a notícia

Use `WebSearch` para achar matérias das **últimas ~2 semanas** nos temas do
portfólio. Faça algumas buscas, cobrindo frentes diferentes:

- **Federal / cadastro rural:** INCRA, SIGEF, SNCR, certificação de imóvel rural,
  Governança Fundiária, decreto/lei de georreferenciamento, prazo 2029.
- **Ambiental:** CAR / SICAR, regularização ambiental, PRA, área de reserva legal,
  Código Florestal, supressão vegetal / DOF.
- **Documentação / tributo:** ITR, CCIR, retificação de registro, usucapião,
  regularização fundiária (Lei 13.465).
- **Topografia / obras / drones:** normas de agrimensura (CFT/CREA), NBR 13133,
  aerofotogrametria, agricultura de precisão.
- **Mato Grosso do Sul:** IMASUL, governo de MS, prazos e programas estaduais de
  regularização — o público é o produtor rural de MS, então notícia com recorte
  de MS vale mais.

Prefira **fontes confiáveis**: gov.br (INCRA, MDA, Receita Federal, Serpro),
Agência Brasil, Poder360, Canal Rural, Globo Rural / g1, Notícias Agrícolas,
sites de legislação. Descarte blog de opinião e portal sem autoria.

Prefira notícia com **gancho concreto** que faça o dono de imóvel em MS agir:
prazo, decreto, lei nova, sistema novo, mudança de regra, multa. Novidade de
processo (um sistema que unifica cadastros, um prazo que muda) rende post melhor
que matéria genérica.

Leia os 2–3 melhores candidatos com `WebFetch` para **confirmar os fatos e a
data** antes de escolher. Notícia velha ou boato não vira post.

## Passo 2 — Deduplicar e escolher uma

Antes de decidir, cheque o que já foi coberto:

- `rotinas/radar-noticias-historico.json` — o histórico da rotina (data, título,
  fonte, slug de cada post já feito).
- Os `blog-*.html` na raiz — os artigos que já existem.

Não repita um tema já coberto, **a não ser que haja atualização real** (mudou o
prazo, saiu o decreto que antes era projeto). Se for atualização, deixe isso
claro no texto e referencie o post anterior.

Escolha **uma** notícia — a mais relevante e acionável para o produtor de MS. Uma
notícia forte por rodada vale mais que três fracas.

Se, depois de buscar, nada relevante tiver saído na semana, **diga isso ao
usuário** e sugira ou pular a rodada ou revisitar um tema perene (sem inventar
notícia). Não encha linguiça: post de notícia sem notícia queima a credibilidade
do blog.

## Passo 3 — Direitos autorais (inegociável)

**Nunca copie a matéria original.** Reescreva tudo com palavras próprias, no
ângulo da AJ TopoGeo: o que a notícia significa **na prática para quem tem imóvel
rural em MS** e como a empresa ajuda. A notícia é a matéria-prima, não o produto.

- Nada de blocos de texto copiados. No máximo uma citação curta e entre aspas, se
  for essencial, com atribuição.
- Cite a fonte: preencha o campo `fonte` (nome do veículo + link) no `post.json`.
  O gerador põe a linha "Fonte: …" no rodapé do artigo, com `rel="nofollow"`.
- **Só afirme o que a fonte confirma.** Não invente número, prazo, artigo de lei
  ou estatística. Se um dado não estiver claro na matéria, não o afirme — escreva
  em torno do que está confirmado. Errar um fato de lei no site da empresa é pior
  que não ter o post.

## Passo 4 — Gerar o post de blog

Escreva um `post.json` (esquema em `rotinas/exemplo-post-blog.json`) e rode:

```bash
py rotinas/gerar_post_blog.py <scratchpad>/post.json
```

O script escreve `blog-<slug>.html`, insere o card no topo de `blog.html` e
adiciona a URL ao `sitemap.xml`. Ao preencher o JSON:

- **slug:** curto, com a palavra-chave (ex.: `incra-unifica-sistemas-cadastro`).
- **categoria / tag:** categoria é uma de `geo/topo/reg/amb/drone/doc`; a tag do
  card começa com `Notícia · ` (ex.: `Notícia · Georreferenciamento`), como nos
  posts de notícia que já existem.
- **imagem:** um arquivo real de `img/` que combine com o tema (marco-geodesico,
  campo-gnss, aereo-1, etc.). Confira a lista com `ls img/`.
- **SEO:** `title` até ~60 caracteres terminando em `| AJ TopoGeo`;
  `meta_description` de 140–160 caracteres; `meta_keywords` com os termos que o
  produtor buscaria.
- **corpo:** `intro` + 3 a 5 seções (`h2` + parágrafos, lista quando couber).
  Uma seção sempre é "Como a AJ TopoGeo ajuda", amarrando o serviço com link para
  a página de serviço ou um post relacionado.
- **leia_tambem / CTAs:** aponte para posts e serviços que já existem no site.

Guarde o `post.json` no scratchpad da sessão. Ele não tem dado sigiloso (notícia
é pública), mas também não precisa ir para o repo.

## Passo 5 — Gerar carrossel + Reel narrado + guia

Escreva um `pauta.json` com **duas peças** (esquema em `scripts/README.md`):

1. **Carrossel** (`formato: "carrossel"`): capa + 3 a 4 cards de corpo + um card
   de CTA. Cada card com uma foto **diferente** de `img/` (o `render.py` aborta
   se repetir imagem). Legenda com o gancho na primeira linha; hashtags.
2. **Reel narrado** (`formato: "reel"` com `narracao`): capa + 3 a 4 slides + CTA.
   `narracao` é o texto falado (para o ouvido); `texto` é o que aparece na tela
   (para o olho) — escreva os dois separados. Sem música: a trilha é a locução.

Rode, na ordem (o `pauta.json` é o mesmo arquivo, com caminho absoluto):

```bash
py .claude/skills/conteudo-instagram/scripts/render.py <scratchpad>/pauta.json
py .claude/skills/radar-noticias/scripts/reel_noticia.py <scratchpad>/pauta.json
py .claude/skills/conteudo-instagram/scripts/guia_pdf.py <scratchpad>/pauta.json
```

**Confira olhando**, não presumindo: extraia um frame do Reel e abra um card do
carrossel para ver se o texto não estourou a margem, não sumiu no céu claro nem
caiu atrás do rodapé. Se quebrou, ajuste o JSON e rode de novo.

Saída das peças em `C:\Users\ALCIO\Pictures\POST_NOTICIA_<slug>_<AAAA-MM-DD>\`,
o guia PDF junto.

## Passo 6 — Registrar

Acrescente a entrada ao histórico (versionado, sem dado sigiloso):

```
rotinas/radar-noticias-historico.json
```

Campos: `data`, `titulo`, `tema`, `fonte`, `fonte_url`, `slug`. É esse arquivo
que impede repetir notícia na semana seguinte.

## Passo 7 — Entregar ao usuário

Um resumo em prosa com:

- **Qual notícia** você escolheu e por quê (e o que descartou, se relevante).
- **O post de blog:** título, a URL final (`/blog-<slug>`, ativa só após o
  deploy), e que `blog.html` + `sitemap.xml` foram atualizados.
- **As peças de Instagram:** o gancho de cada uma e onde ficaram salvas.
- **Próximas ações do usuário** (a rotina não faz nenhuma): revisar o post,
  fazer `commit` + `push` para publicar no site, e postar o carrossel e o Reel.
- Aponte o **guia PDF** como o documento que ele lê antes de postar.

## Limite

Você escreve, desenha e monta. **Quem publica é o usuário.** Criar o arquivo
`blog-<slug>.html` **não** é publicar — o post só vai ao ar quando o usuário der
`commit` + `push` (o site é estático, deploy automático na Vercel a partir do
GitHub). Não commite, não dê push, não faça deploy, não poste nada no Instagram
e não suba nada para lugar nenhum, mesmo que o usuário diga "pode publicar" — não
há canal de publicação conectado aqui, e a decisão de ir ao ar é dele.
